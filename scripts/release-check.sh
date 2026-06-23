#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

OVERALL_STATUS=0

echo -e "${BLUE}[backend/release-check] Django 系统检查...${NC}"
if [ ! -f "venv/bin/activate" ]; then
    echo -e "${RED}✗ Python 虚拟环境不存在，请先运行: bash scripts/setup.sh${NC}"
    exit 1
fi
source venv/bin/activate

if python manage.py check; then
    echo -e "${GREEN}✓ Django check 通过${NC}"
else
    echo -e "${RED}✗ Django check 失败${NC}"
    OVERALL_STATUS=1
fi

echo ""
echo -e "${BLUE}[backend/release-check] 检查 migration 是否完整...${NC}"
if python manage.py makemigrations --check --dry-run; then
    echo -e "${GREEN}✓ migration 完整${NC}"
else
    echo -e "${RED}✗ migration 不完整，请运行 makemigrations${NC}"
    OVERALL_STATUS=1
fi

echo ""
echo -e "${BLUE}[backend/release-check] 运行核心流程测试...${NC}"
if pytest workorder/tests/test_api.py workorder/tests/test_work_order_flow_service.py workorder/tests/smoke -q --tb=short; then
    echo -e "${GREEN}✓ 核心流程测试通过${NC}"
else
    echo -e "${RED}✗ 核心流程测试失败${NC}"
    OVERALL_STATUS=1
fi

exit $OVERALL_STATUS
