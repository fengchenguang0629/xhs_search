#!/bin/bash
# XHS Spider Web 启动脚本
# 用法: ./run.sh web         - 本地运行
#      ./run.sh docker       - Docker 运行
#      ./run.sh push <addr>  - 推送镜像到 Registry（如: ./run.sh push 192.168.1.100:5000）
#      ./run.sh pull <addr>  - 从 Registry 拉取镜像并运行
#      ./run.sh registry     - 启动本地 Registry 服务

set -e

MODE=${1:-web}
IMAGE_NAME="xhs-spider-web"
CONTAINER_NAME="xhs-spider-web"
REGISTRY_PORT="5000"
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
    pip install -q -r requirements.txt
    
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
    docker build -f Dockerfile.web -t ${IMAGE_NAME}:latest .
    
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

# 启动本地 Registry
start_registry() {
    echo -e "${GREEN}=========================================="
    echo "启动本地 Docker Registry"
    echo "==========================================${NC}\n"
    
    # 检查 Docker
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}错误: Docker 未安装${NC}"
        exit 1
    fi
    
    # 停止旧 Registry
    if docker ps -a --format '{{.Names}}' | grep -q "^registry$"; then
        echo "停止旧 Registry..."
        docker stop registry || true
        docker rm registry || true
    fi
    
    # 启动 Registry
    echo "启动 Registry 服务..."
    docker run -d \
        -p ${REGISTRY_PORT}:5000 \
        --name registry \
        --restart unless-stopped \
        registry:2
    
    sleep 2
    
    if docker ps --format '{{.Names}}' | grep -q "^registry$"; then
        echo -e "${GREEN}✓ Registry 已启动${NC}"
        echo ""
        echo "获取本机 IP 地址:"
        echo "  Linux/Mac: ifconfig 或 hostname -I"
        echo "  Windows: ipconfig"
        echo ""
        echo "其他电脑使用 Registry:"
        echo "  ./run.sh push <本机IP>:5000"
    else
        echo -e "${RED}✗ Registry 启动失败${NC}"
        exit 1
    fi
}

# 推送镜像到 Registry
push_to_registry() {
    local registry_addr=$2
    
    if [ -z "$registry_addr" ]; then
        echo -e "${RED}错误: 需要指定 Registry 地址${NC}"
        echo "用法: ./run.sh push <registry_addr>"
        echo "示例: ./run.sh push 192.168.1.100:5000"
        exit 1
    fi
    
    echo -e "${GREEN}=========================================="
    echo "推送镜像到 Registry"
    echo "==========================================${NC}\n"
    
    # 检查 Docker
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}错误: Docker 未安装${NC}"
        exit 1
    fi
    
    # 构建镜像（如果不存在）
    if ! docker images | grep -q "^${IMAGE_NAME}"; then
        echo "构建镜像..."
        docker build -f Dockerfile.web -t ${IMAGE_NAME}:latest .
    fi
    
    # 标记镜像
    echo "标记镜像: ${registry_addr}/${IMAGE_NAME}:latest"
    docker tag ${IMAGE_NAME}:latest ${registry_addr}/${IMAGE_NAME}:latest
    
    # 推送镜像
    echo "推送镜像到 ${registry_addr}..."
    docker push ${registry_addr}/${IMAGE_NAME}:latest
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ 镜像推送成功${NC}"
        echo ""
        echo "在另外一台电脑上执行:"
        echo "  ./run.sh pull ${registry_addr}"
    else
        echo -e "${RED}✗ 推送失败${NC}"
        exit 1
    fi
}

# 从 Registry 拉取镜像并运行
pull_from_registry() {
    local registry_addr=$2
    
    if [ -z "$registry_addr" ]; then
        echo -e "${RED}错误: 需要指定 Registry 地址${NC}"
        echo "用法: ./run.sh pull <registry_addr>"
        echo "示例: ./run.sh pull 192.168.1.100:5000"
        exit 1
    fi
    
    echo -e "${GREEN}=========================================="
    echo "从 Registry 拉取镜像"
    echo "==========================================${NC}\n"
    
    check_env
    
    # 检查 Docker
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}错误: Docker 未安装${NC}"
        exit 1
    fi
    
    # 停止旧容器
    if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        echo "停止旧容器..."
        docker stop ${CONTAINER_NAME} || true
        docker rm ${CONTAINER_NAME} || true
    fi
    
    # 拉取镜像
    echo "从 ${registry_addr} 拉取镜像..."
    docker pull ${registry_addr}/${IMAGE_NAME}:latest
    
    if [ $? -ne 0 ]; then
        echo -e "${RED}拉取失败${NC}"
        exit 1
    fi
    
    # 标记镜像
    docker tag ${registry_addr}/${IMAGE_NAME}:latest ${IMAGE_NAME}:latest
    
    # 创建数据目录
    echo "创建数据目录..."
    create_dirs
    
    # 启动容器
    echo "启动容器..."
    docker run -d \
        -p ${SERVICE_PORT}:5000 \
        -e PYTHONUNBUFFERED=1 \
        -v "$(pwd)/datas:/app/datas" \
        -v "$(pwd)/.env:/app/.env:ro" \
        --name ${CONTAINER_NAME} \
        --restart unless-stopped \
        ${IMAGE_NAME}:latest
    
    sleep 3
    
    if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        echo -e "${GREEN}✓ 服务已启动${NC}"
        echo ""
        echo "访问地址: http://localhost:${SERVICE_PORT}"
    else
        echo -e "${RED}✗ 启动失败${NC}"
        docker logs ${CONTAINER_NAME}
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
    echo ""
    echo "Registry 模式（局域网共享）:"
    echo "  ./run.sh registry         - 在一台电脑启动 Registry 服务"
    echo "  ./run.sh push <addr>      - 构建并推送镜像到 Registry"
    echo "  ./run.sh pull <addr>      - 从 Registry 拉取镜像并运行"
    echo ""
    echo "示例:"
    echo "  电脑 A（Registry 服务器）:"
    echo "    ./run.sh registry"
    echo ""
    echo "  电脑 A（构建并推送）:"
    echo "    ./run.sh push 192.168.1.100:5000"
    echo ""
    echo "  电脑 B（拉取并运行）:"
    echo "    ./run.sh pull 192.168.1.100:5000"
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
    registry)
        start_registry
        ;;
    push)
        push_to_registry "$@"
        ;;
    pull)
        pull_from_registry "$@"
        ;;
    *)
        show_help
        exit 1
        ;;
esac
