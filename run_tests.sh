#!/bin/bash

# 测试运行脚本
# 用于运行所有测试并生成覆盖率报告

set -e

echo "======================================"
echo "印刷施工单跟踪系统 - 测试运行器"
echo "======================================"
echo

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 切换到后端目录
cd "$(dirname "$0")"

# 激活虚拟环境
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
    echo -e "${GREEN}✓${NC} 虚拟环境已激活"
else
    echo -e "${RED}✗${NC} 未找到虚拟环境"
    exit 1
fi

echo

# 解析命令行参数
TEST_CMD="${1:-all}"
COVERAGE="${2:-false}"

# 运行测试
case $TEST_CMD in
    "all")
        echo -e "${YELLOW}运行所有测试...${NC}"
        python manage.py test workorder.tests --verbosity=2 -v 2
        ;;
    "models")
        echo -e "${YELLOW}运行模型测试...${NC}"
        python manage.py test workorder.tests.test_models --verbosity=2
        ;;
    "api")
        echo -e "${YELLOW}运行 API 测试...${NC}"
        python manage.py test workorder.tests.test_api --verbosity=2
        ;;
    "permissions")
        echo -e "${YELLOW}运行权限测试...${NC}"
        python manage.py test workorder.tests.test_permissions --verbosity=2
        ;;
    "approval")
        echo -e "${YELLOW}运行审核验证测试...${NC}"
        python manage.py test workorder.tests.test_approval_validation --verbosity=2
        ;;
    "coverage")
        echo -e "${YELLOW}运行测试并生成覆盖率报告...${NC}"
        if ! command -v coverage &> /dev/null; then
            echo -e "${RED}✗${NC} 未安装 coverage，正在安装..."
            pip install coverage
        fi
        coverage run --source='.' manage.py test workorder.tests --verbosity=2
        coverage report
        coverage html
        echo -e "${GREEN}✓${NC} 覆盖率报告已生成: htmlcov/index.html"
        ;;
    "lint")
        echo -e "${YELLOW}运行代码检查...${NC}"
        if ! command -v flake8 &> /dev/null; then
            echo -e "${YELLOW}!${NC} 未安装 flake8，跳过代码检查"
        else
            flake8 workorder --exclude=migrations
        fi
        ;;
    *)
        echo -e "${RED}错误: 未知的测试命令 '$TEST_CMD'${NC}"
        echo
        echo "用法: $0 [测试类型] [覆盖率]"
        echo
        echo "测试类型:"
        echo "  all         - 运行所有测试 (默认)"
        echo "  models      - 运行模型测试"
        echo "  api         - 运行 API 测试"
        echo "  permissions - 运行权限测试"
        echo "  approval    - 运行审核验证测试"
        echo "  coverage    - 运行测试并生成覆盖率报告"
        echo "  lint        - 运行代码检查"
        echo
        echo "示例:"
        echo "  $0                # 运行所有测试"
        echo "  $0 models         # 运行模型测试"
        echo "  $0 api            # 运行 API 测试"
        echo "  $0 coverage       # 生成覆盖率报告"
        exit 1
        ;;
esac

# 检查测试结果
if [ $? -eq 0 ]; then
    echo
    echo -e "${GREEN}======================================"
    echo "✓ 所有测试通过！"
    echo "======================================${NC}"
    exit 0
else
    echo
    echo -e "${RED}======================================"
    echo "✗ 测试失败！"
    echo "======================================${NC}"
    exit 1
fi
