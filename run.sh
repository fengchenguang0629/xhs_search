#!/bin/bash
# XHS Spider Web 启动脚本
# 用法: ./run.sh web         - 本地运行
#      ./run.sh docker       - Docker 运行
#      ./run.sh build        - 构建新镜像

set -e

MODE=${1:-web}
IMAGE_NAME="xhs-spider-web"
CONTAINER_NAME="xhs-spider-web"
SERVICE_PORT="5000"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# 检查 .env 文件
check_env() {
    if [ ! -f ".env" ]; then
        echo -e "${RED}错误: .env 文件不存在${NC}"
        echo "请创建 .env 文件并设置 COOKIES"
        exit 1
    fi
}

# 创建数据目录
create_dirs() {
    mkdir -p datas/media_datas datas/excel_datas
}

# 本地 Web 模式
run_web() {
    echo -e "${GREEN}=========================================="
    echo "启动 XHS Spider Web 服务"
    echo "==========================================${NC}\n"
    
    check_env
    
    echo "[1] 安装 Python 依赖..."
    uv pip install -q -r requirements.txt
    
    echo "[2] 安装 NPM 依赖..."
    npm install
    
    echo "[3] 创建数据目录..."
    create_dirs
    
    echo "[4] 启动服务..."
    echo "访问: http://localhost:5000"
    echo "按 Ctrl+C 停止服务"
    echo ""
    
    python -m web.app
}

# Docker 模式
run_docker() {
    echo -e "${GREEN}=========================================="
    echo "XHS Spider Web - Docker 部署"
    echo "==========================================${NC}\n"
    
    check_env
    
    # 检查 Docker
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}错误: Docker 未安装${NC}"
        exit 1
    fi
    
    # 停止旧容器
    if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        echo -e "${YELLOW}[1] 停止旧容器...${NC}"
        docker stop ${CONTAINER_NAME} || true
        docker rm ${CONTAINER_NAME} || true
    fi
    
    # 构建镜像
    echo -e "${YELLOW}[2] 构建镜像...${NC}"
    sudo docker build --network=host -f Dockerfile.web -t ${IMAGE_NAME}:latest .
    
    if [ $? -ne 0 ]; then
        echo -e "${RED}构建失败${NC}"
        exit 1
    fi
    
    # 创建数据目录
    echo -e "${YELLOW}[3] 创建数据目录...${NC}"
    create_dirs
    
    # 启动容器
    echo -e "${YELLOW}[4] 启动容器...${NC}"
    docker run -d \
        -p ${SERVICE_PORT}:5000 \
        -e PYTHONUNBUFFERED=1 \
        -v "$(pwd)/datas:/app/datas" \
        -v "$(pwd)/.env:/app/.env:ro" \
        --name ${CONTAINER_NAME} \
        --restart unless-stopped \
        ${IMAGE_NAME}:latest
    
    if [ $? -ne 0 ]; then
        echo -e "${RED}启动失败${NC}"
        exit 1
    fi
    
    sleep 3
    
    if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        echo -e "${GREEN}✓ 服务已启动${NC}"
    else
        echo -e "${RED}✗ 服务启动失败${NC}"
        docker logs ${CONTAINER_NAME}
        exit 1
    fi
    
    echo ""
    echo -e "${GREEN}=========================================="
    echo "服务信息"
    echo "==========================================${NC}"
    echo -e "容器名: ${YELLOW}${CONTAINER_NAME}${NC}"
    echo -e "端口: ${YELLOW}${SERVICE_PORT}${NC}"
    echo -e "URL: ${YELLOW}http://localhost:${SERVICE_PORT}${NC}"
    echo ""
}

# 构建新镜像
build_image() {
    echo -e "${GREEN}=========================================="
    echo "构建 Docker 镜像"
    echo "==========================================${NC}\n"
    
    # 检查 Docker
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}错误: Docker 未安装${NC}"
        exit 1
    fi
    
    echo -e "${YELLOW}[1] 构建镜像: ${IMAGE_NAME}:latest${NC}"
    sudo docker build --network=host -f Dockerfile.web -t ${IMAGE_NAME}:latest .
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ 镜像构建成功${NC}"
        echo ""
        echo "可以执行以下命令启动容器:"
        echo "  ./run.sh docker"
    else
        echo -e "${RED}✗ 构建失败${NC}"
        exit 1
    fi
}

# 显示帮助
show_help() {
    echo "XHS Spider Web 启动脚本"
    echo ""
    echo "本地模式:"
    echo "  ./run.sh web              - 本地运行 Python 服务"
    echo "  ./run.sh docker           - Docker 本地运行"
    echo "  ./run.sh build            - 构建新镜像"
    echo ""
}

# 主逻辑
case $MODE in
    web)
        run_web
        ;;
    docker)
        run_docker
        ;;
    build)
        build_image
        ;;
    *)
        show_help
        exit 1
        ;;
esac