#!/bin/bash
# Backend 一键启动脚本

set -euo pipefail

# 脚本目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 默认值
PROFILE="dev"
SKIP_MIGRATE=false
VENV_NAME="venv"
USE_WS=false
USE_VENV=true
NON_INTERACTIVE=false
PORT=8000

# 帮助信息
show_help() {
    echo "用法: ./start.sh [选项]"
    echo ""
    echo "选项:"
    echo "  dev             开发环境 (默认)"
    echo "  prod            生产环境"
    echo "  --skip-migrate  跳过数据库迁移"
    echo "  --ws            启用 WebSocket 支持 (使用 Daphne ASGI 服务器)"
    echo "  --no-venv       不使用虚拟环境 (使用系统 Python)"
    echo "  --non-interactive, -y  非交互模式，跳过所有询问 (适合 CI)"
    echo "  --port PORT     指定端口号 (默认 8000)"
    echo "  -h, --help      显示帮助信息"
    echo ""
    echo "命令示例:"
    echo "  ./start.sh                       # 开发环境完整启动"
    echo "  ./start.sh dev                   # 开发环境"
    echo "  ./start.sh prod                  # 生产环境"
    echo "  ./start.sh --ws                  # 开发环境 + WebSocket"
    echo "  ./start.sh --skip-migrate        # 跳过迁移快速启动"
    echo "  ./start.sh -y                    # 非交互模式 (CI 场景)"
    echo "  ./start.sh --port 8080           # 使用 8080 端口"
    echo ""
    echo "环境配置:"
    echo "  dev:  SQLite本地数据库, DEBUG=True"
    echo "  prod: 使用环境变量或 .env.production"
    echo ""
    echo "注意:"
    echo "  --ws 使用 Daphne ASGI 服务器，支持 WebSocket 通知"
    echo "  不带 --ws 使用 Django runserver，不支持 WebSocket"
}

# 检查 Python 安装
check_python() {
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}错误: Python 3 未安装${NC}"
        exit 1
    fi

    local major minor
    major=$(python3 -c 'import sys; print(sys.version_info.major)')
    minor=$(python3 -c 'import sys; print(sys.version_info.minor)')

    if [ "$major" -lt 3 ] || { [ "$major" -eq 3 ] && [ "$minor" -lt 10 ]; }; then
        echo -e "${RED}错误: Python 3.10+ required, 当前版本: $(python3 --version)${NC}"
        exit 1
    fi

    echo -e "${GREEN}Python 版本: $(python3 --version)${NC}"
}

# 设置虚拟环境
setup_venv() {
    if [ "$USE_VENV" = true ]; then
        if [ ! -d "$VENV_NAME" ]; then
            echo -e "${GREEN}创建虚拟环境...${NC}"
            python3 -m venv "$VENV_NAME"
        fi
        echo -e "${GREEN}激活虚拟环境...${NC}"
        VENV_PYTHON="$VENV_NAME/bin/python"
        VENV_PIP="$VENV_NAME/bin/pip"
    else
        echo -e "${YELLOW}使用系统 Python（不推荐）${NC}"
        VENV_PYTHON="python3"
        VENV_PIP="pip3"
    fi
}

# 安装依赖（仅在需要时）
install_deps() {
    if [ "$USE_VENV" = true ]; then
        local stamp="$VENV_NAME/.installed"
        if [ -f "$stamp" ] && [ "$stamp" -nt "requirements.txt" ]; then
            echo -e "${GREEN}依赖已是最新，跳过安装${NC}"
            return
        fi
    fi

    echo -e "${GREEN}安装依赖...${NC}"
    $VENV_PIP install --upgrade pip -q
    $VENV_PIP install -r requirements.txt

    if [ "$USE_VENV" = true ]; then
        touch "$VENV_NAME/.installed"
    fi
}

# 环境配置
setup_env() {
    case $PROFILE in
        dev)
            if [ ! -f ".env" ]; then
                if [ -f ".env.example" ]; then
                    echo -e "${GREEN}复制 .env.example -> .env${NC}"
                    cp .env.example .env
                fi
            fi
            export DEBUG=True
            ;;
        prod)
            if [ -f ".env.production" ]; then
                echo -e "${GREEN}使用生产环境配置 .env.production${NC}"
                export DEBUG=False
            fi
            ;;
    esac
}

# 数据库迁移
run_migrate() {
    if [ "$SKIP_MIGRATE" = true ]; then
        echo -e "${YELLOW}跳过数据库迁移${NC}"
        return
    fi

    echo -e "${GREEN}检查数据库迁移状态...${NC}"
    $VENV_PYTHON manage.py migrate --skip-checks
}

# 加载初始数据
load_initial_data() {
    if [ "$NON_INTERACTIVE" = true ]; then
        echo -e "${YELLOW}非交互模式，跳过初始数据加载${NC}"
        return
    fi

    echo ""
    echo -e "${YELLOW}是否加载初始数据?${NC}"
    echo "  1) 是 (加载测试用户和产品数据)"
    echo "  2) 否 (跳过)"
    echo ""
    read -rp "请输入选择 [1-2]: " choice

    case $choice in
        1)
            echo -e "${GREEN}初始化工序...${NC}"
            $VENV_PYTHON manage.py reset_processes --force 2>/dev/null || true
            echo -e "${GREEN}初始化部门和工序关系...${NC}"
            $VENV_PYTHON manage.py init_departments 2>/dev/null || true
            echo -e "${GREEN}初始化用户组...${NC}"
            $VENV_PYTHON manage.py init_groups 2>/dev/null || true
            echo -e "${GREEN}初始化任务分派规则...${NC}"
            $VENV_PYTHON manage.py load_assignment_rules 2>/dev/null || true
            echo -e "${GREEN}加载初始用户...${NC}"
            $VENV_PYTHON manage.py load_initial_users 2>/dev/null || true
            echo -e "${GREEN}加载产品数据...${NC}"
            $VENV_PYTHON manage.py loaddata workorder/fixtures/initial_products.json 2>/dev/null || true
            ;;
        2)
            echo -e "${YELLOW}跳过初始数据加载${NC}"
            ;;
        *)
            echo -e "${YELLOW}无效选择，跳过${NC}"
            ;;
    esac
}

# 创建超级用户
create_superuser() {
    if [ "$NON_INTERACTIVE" = true ]; then
        echo -e "${YELLOW}非交互模式，跳过超级用户创建${NC}"
        return
    fi

    echo ""
    echo -e "${YELLOW}是否创建超级用户?${NC}"
    echo "  1) 是"
    echo "  2) 否 (跳过)"
    echo ""
    read -rp "请输入选择 [1-2]: " choice

    case $choice in
        1)
            echo -e "${GREEN}创建超级用户...${NC}"
            $VENV_PYTHON manage.py createsuperuser
            ;;
        2)
            echo -e "${YELLOW}跳过${NC}"
            ;;
        *)
            echo -e "${YELLOW}无效选择，跳过${NC}"
            ;;
    esac
}

# 检查端口占用
check_port() {
    if command -v ss &> /dev/null; then
        if ss -tlnp 2>/dev/null | grep -q ":${PORT} "; then
            echo -e "${YELLOW}警告: 端口 $PORT 已被占用${NC}"
            ss -tlnp 2>/dev/null | grep ":${PORT} " || true
            echo -e "${YELLOW}可以 --port 指定其他端口${NC}"
        fi
    elif command -v lsof &> /dev/null; then
        if lsof -i ":$PORT" &>/dev/null; then
            echo -e "${YELLOW}警告: 端口 $PORT 已被占用${NC}"
            lsof -i ":$PORT" 2>/dev/null || true
            echo -e "${YELLOW}可以 --port 指定其他端口${NC}"
        fi
    fi
}

# 启动服务器
launch_server() {
    setup_env
    check_port

    echo ""
    echo -e "${GREEN}=======================================${NC}"
    echo -e "${GREEN}  Backend 启动配置${NC}"
    echo -e "${GREEN}=======================================${NC}"
    echo "  环境:   $PROFILE"
    echo "  DEBUG:  $DEBUG"
    echo "  Python: $($VENV_PYTHON --version)"
    echo "  端口:   $PORT"
    echo "  WebSocket: $([ "$USE_WS" = true ] && echo "启用 (Daphne)" || echo "禁用 (runserver)")"
    echo -e "${GREEN}=======================================${NC}"
    echo ""

    if [ "$USE_WS" = true ]; then
        echo -e "${BLUE}启动 Daphne ASGI 服务器 (支持 WebSocket)...${NC}"
        echo -e "${YELLOW}访问 http://127.0.0.1:${PORT}/api/ 查看 API${NC}"
        echo -e "${YELLOW}WebSocket: ws://127.0.0.1:${PORT}/ws/notifications/${NC}"
        echo ""
        $VENV_PYTHON -m daphne -b 0.0.0.0 -p "$PORT" config.asgi:application
    else
        echo -e "${BLUE}启动 Django 开发服务器...${NC}"
        echo -e "${YELLOW}注意: 不支持 WebSocket (如需 WebSocket 请使用 --ws)${NC}"
        echo ""
        $VENV_PYTHON manage.py runserver --skip-checks "0.0.0.0:${PORT}"
    fi
}

# 解析参数
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_help
                exit 0
                ;;
            --skip-migrate)
                SKIP_MIGRATE=true
                ;;
            --ws)
                USE_WS=true
                ;;
            --no-venv)
                USE_VENV=false
                ;;
            --non-interactive|-y)
                NON_INTERACTIVE=true
                ;;
            --port)
                PORT="${2:?--port 需要端口号参数}"
                shift
                ;;
            dev|prod)
                PROFILE="$1"
                ;;
            *)
                echo -e "${RED}未知参数: $1${NC}"
                show_help
                exit 1
                ;;
        esac
        shift
    done
}

# 主流程
main() {
    echo -e "${GREEN}=======================================${NC}"
    echo -e "${GREEN}  印刷施工单 - Backend 启动${NC}"
    echo -e "${GREEN}=======================================${NC}"
    echo ""

    check_python
    parse_args "$@"
    setup_venv
    install_deps
    run_migrate

    # 开发环境询问
    if [ "$PROFILE" = "dev" ]; then
        load_initial_data
        create_superuser
    fi

    launch_server
}

main "$@"
