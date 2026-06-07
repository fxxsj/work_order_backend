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

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Backend 初始化安装${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# 创建虚拟环境
if [ ! -d "venv" ]; then
    echo -e "${BLUE}创建虚拟环境...${NC}"
    python -m venv venv
    echo -e "${GREEN}✓ 虚拟环境已创建${NC}"
else
    echo -e "${GREEN}✓ 虚拟环境已存在${NC}"
fi

# 激活虚拟环境
echo -e "${BLUE}激活虚拟环境...${NC}"
source venv/bin/activate

# 安装依赖
echo -e "${BLUE}安装依赖...${NC}"
pip install -r requirements.txt
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ 依赖安装完成${NC}"
else
    echo -e "${RED}✗ 依赖安装失败${NC}"
    exit 1
fi

# 数据库迁移
echo -e "${BLUE}运行数据库迁移...${NC}"
python manage.py migrate --skip-checks
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ 数据库迁移完成${NC}"
else
    echo -e "${YELLOW}! 数据库迁移可能失败（数据库未启动？）${NC}"
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Backend 安装完成${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "开发: bash scripts/dev-up.sh"
echo "测试: bash scripts/test.sh"
