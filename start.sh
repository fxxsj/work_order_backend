#!/bin/bash
# Backend 一键启动脚本

set -e

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

# 帮助信息
show_help() {
    echo "用法: ./start.sh [选项]"
    echo ""
    echo "选项:"
    echo "  dev          开发环境 (默认)"
    echo "  prod         生产环境"
    echo "  --skip-migrate  跳过数据库迁移"
    echo "  --no-venv    不使用虚拟环境 (使用系统 Python)"
    echo "  -h, --help   显示帮助信息"
    echo ""
    echo "命令示例:"
    echo "  ./start.sh              # 开发环境完整启动"
    echo "  ./start.sh dev          # 开发环境"
    echo "  ./start.sh prod         # 生产环境"
    echo "  ./start.sh --skip-migrate  # 跳过迁移快速启动"
    echo ""
    echo "环境配置:"
    echo "  dev:  SQLite本地数据库, DEBUG=True"
    echo "  prod: 使用环境变量或 .env.production"
}

# 检查 Python 安装
check_python() {
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}错误: Python 3 未安装${NC}"
        exit 1
    fi

    PYTHON_VERSION=$(python3 --version 2>&1 | grep -oP '\d+\.\d+' | head -1)
    if [ "$(echo "$PYTHON_VERSION < 3.10" | bc)" = "1" ]; then
        echo -e "${RED}错误: Python 3.10+ required, 当前版本: $PYTHON_VERSION${NC}"
        exit 1
    fi

    echo -e "${GREEN}Python 版本: $(python3 --version)${NC}"
}

# 设置虚拟环境
setup_venv() {
    USE_VENV=true

    for arg in "$@"; do
        if [ "$arg" = "--no-venv" ]; then
            USE_VENV=false
        fi
    done

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

# 安装依赖
install_deps() {
    echo -e "${GREEN}安装依赖...${NC}"
    $VENV_PIP install --upgrade pip
    $VENV_PIP install -r requirements.txt
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
    echo ""
    echo -e "${YELLOW}是否加载初始数据?${NC}"
    echo "  1) 是 (加载测试用户和产品数据)"
    echo "  2) 否 (跳过)"
    echo ""
    read -p "请输入选择 [1-2]: " choice

    case $choice in
        1)
            echo -e "${GREEN}加载初始用户...${NC}"
            $VENV_PYTHON manage.py load_initial_users 2>/dev/null || true
            echo -e "${GREEN}加载产品数据...${NC}"
            $VENV_PYTHON manage.py loaddata workorder/fixtures/initial_products.json 2>/dev/null || true
            echo -e "${GREEN}初始化用户组...${NC}"
            $VENV_PYTHON manage.py init_groups 2>/dev/null || true
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
    echo ""
    echo -e "${YELLOW}是否创建超级用户?${NC}"
    echo "  1) 是"
    echo "  2) 否 (跳过)"
    echo ""
    read -p "请输入选择 [1-2]: " choice

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

# 启动服务器
launch_server() {
    setup_env

    echo ""
    echo -e "${GREEN}=======================================${NC}"
    echo -e "${GREEN}  Backend 启动配置${NC}"
    echo -e "${GREEN}=======================================${NC}"
    echo "  环境:   $PROFILE"
    echo "  DEBUG:  $DEBUG"
    echo "  Python: $($VENV_PYTHON --version)"
    echo -e "${GREEN}=======================================${NC}"
    echo ""
    echo -e "${BLUE}启动 Django 开发服务器...${NC}"
    echo -e "${YELLOW}访问 http://127.0.0.1:8000/api/ 查看 API${NC}"
    echo ""

    $VENV_PYTHON manage.py runserver --skip-checks 0.0.0.0:8000
}

# 解析参数
parse_args() {
    for arg in "$@"; do
        case $arg in
            -h|--help)
                show_help
                exit 0
                ;;
            --skip-migrate)
                SKIP_MIGRATE=true
                ;;
            --no-venv)
                # handled in setup_venv
                ;;
            dev|prod)
                PROFILE="$arg"
                ;;
        esac
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
    setup_venv "$@"
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
