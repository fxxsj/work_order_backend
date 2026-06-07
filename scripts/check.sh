#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

OVERALL_STATUS=0

echo -e "${BLUE}[backend] Django 系统检查...${NC}"
if [ ! -f "venv/bin/activate" ]; then
    echo -e "${RED}✗ Python 虚拟环境不存在，请先运行: bash scripts/setup.sh${NC}"
    exit 1
fi
source venv/bin/activate
python manage.py check
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Django check 通过${NC}"
else
    echo -e "${RED}✗ Django check 失败${NC}"
    OVERALL_STATUS=1
fi

echo ""
echo -e "${BLUE}[backend] 代码风格检查 (flake8)...${NC}"
if command -v flake8 &> /dev/null; then
    flake8 workorder --exclude=migrations
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ flake8 通过${NC}"
    else
        echo -e "${RED}✗ flake8 发现问题${NC}"
        OVERALL_STATUS=1
    fi
else
    echo -e "${YELLOW}! flake8 未安装，跳过 (pip install flake8)${NC}"
fi

exit $OVERALL_STATUS
