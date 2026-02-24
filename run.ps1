# XHS Spider Web 启动脚本 (Windows PowerShell)
# 用法: .\run.ps1 web         - 本地运行
#      .\run.ps1 docker       - Docker 运行
#      .\run.ps1 build        - 构建新镜像

param(
    [string]$Mode = "web"
)

$ErrorActionPreference = "Stop"

$IMAGE_NAME = "xhs-spider-web"
$CONTAINER_NAME = "xhs-spider-web"
$SERVICE_PORT = "5000"

# 颜色定义 (Windows Console 支持)
function Get-ColorOutput {
    param([string]$Text, [string]$Color)
    
    $colors = @{
        "RED"     = [ConsoleColor]::Red
        "GREEN"   = [ConsoleColor]::Green
        "YELLOW"  = [ConsoleColor]::Yellow
        "CYAN"    = [ConsoleColor]::Cyan
    }
    
    $originalColor = [ConsoleColor]::White
    if ($colors.ContainsKey($Color)) {
        $originalColor = [ConsoleColor]::White
        Write-Host $Text -ForegroundColor $colors[$Color]
    } else {
        Write-Host $Text
    }
}

# 检查 .env 文件
function Check-Env {
    if (-not (Test-Path ".env")) {
        Write-Host "错误: .env 文件不存在" -ForegroundColor Red
        echo "请创建 .env 文件并设置 COOKIES"
        exit 1
    }
}

# 创建数据目录
function Create-Dirs {
    $dirs = @("datas/media_datas", "datas/excel_datas")
    foreach ($dir in $dirs) {
        if (-not (Test-Path $dir)) {
            New-Item -ItemType Directory -Path $dir -Force | Out-Null
            Write-Host "创建目录: $dir" -ForegroundColor Cyan
        }
    }
}

# 本地 Web 模式
function Run-Web {
    Write-Host "==========================================" -ForegroundColor Green
    Write-Host "启动 XHS Spider Web 服务"
    Write-Host "==========================================" -ForegroundColor Green
    Write-Host ""
    
    Check-Env
    
    Write-Host "[1] 安装 Python 依赖..." -ForegroundColor Yellow
    uv pip install -q -r requirements.txt
    
    Write-Host "[2] 安装 NPM 依赖..." -ForegroundColor Yellow
    npm install
    
    Write-Host "[3] 创建数据目录..." -ForegroundColor Yellow
    Create-Dirs
    
    Write-Host "[4] 启动服务..." -ForegroundColor Yellow
    Write-Host "访问: http://localhost:5000" -ForegroundColor Cyan
    Write-Host "按 Ctrl+C 停止服务"
    Write-Host ""
    
    python -m web.app
}

# Docker 模式
function Run-Docker {
    Write-Host "==========================================" -ForegroundColor Green
    Write-Host "XHS Spider Web - Docker 部署"
    Write-Host "==========================================" -ForegroundColor Green
    Write-Host ""
    
    Check-Env
    
    # 检查 Docker
    $dockerCmd = Get-Command docker -ErrorAction SilentlyContinue
    if (-not $dockerCmd) {
        Write-Host "错误: Docker 未安装" -ForegroundColor Red
        exit 1
    }
    
    # 停止旧容器
    $containers = docker ps -a --format "{{.Names}}"
    if ($containers -contains $CONTAINER_NAME) {
        Write-Host "[1] 停止旧容器..." -ForegroundColor Yellow
        docker stop $CONTAINER_NAME 2>$null
        docker rm $CONTAINER_NAME 2>$null
    }
    
    # 构建镜像
    Write-Host "[2] 构建镜像..." -ForegroundColor Yellow
    docker build --network=host -f Dockerfile.web -t ${IMAGE_NAME}:latest .
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "构建失败" -ForegroundColor Red
        exit 1
    }
    
    # 创建数据目录
    Write-Host "[3] 创建数据目录..." -ForegroundColor Yellow
    Create-Dirs
    
    # 启动容器
    Write-Host "[4] 启动容器..." -ForegroundColor Yellow
    $currentDir = Get-Location
    
    docker run -d `
        -p ${SERVICE_PORT}:5000 `
        -e PYTHONUNBUFFERED=1 `
        -v "$currentDir/datas:/app/datas" `
        -v "$currentDir/.env:/app/.env:ro" `
        --name ${CONTAINER_NAME} `
        --restart unless-stopped `
        ${IMAGE_NAME}:latest
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "启动失败" -ForegroundColor Red
        exit 1
    }
    
    Start-Sleep -Seconds 3
    
    $runningContainers = docker ps --format "{{.Names}}"
    if ($runningContainers -contains $CONTAINER_NAME) {
        Write-Host "服务已启动" -ForegroundColor Green
    } else {
        Write-Host "服务启动失败" -ForegroundColor Red
        docker logs $CONTAINER_NAME
        exit 1
    }
    
    Write-Host ""
    Write-Host "==========================================" -ForegroundColor Green
    Write-Host "服务信息"
    Write-Host "==========================================" -ForegroundColor Green
    Write-Host "容器名: $CONTAINER_NAME" -ForegroundColor Yellow
    Write-Host "端口: $SERVICE_PORT" -ForegroundColor Yellow
    Write-Host "URL: http://localhost:$SERVICE_PORT" -ForegroundColor Yellow
    Write-Host ""
}

# 构建新镜像
function Build-Image {
    Write-Host "==========================================" -ForegroundColor Green
    Write-Host "构建 Docker 镜像"
    Write-Host "==========================================" -ForegroundColor Green
    Write-Host ""
    
    # 检查 Docker
    $dockerCmd = Get-Command docker -ErrorAction SilentlyContinue
    if (-not $dockerCmd) {
        Write-Host "错误: Docker 未安装" -ForegroundColor Red
        exit 1
    }
    
    Write-Host "[1] 构建镜像: ${IMAGE_NAME}:latest" -ForegroundColor Yellow
    docker build --network=host -f Dockerfile.web -t ${IMAGE_NAME}:latest .
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "镜像构建成功" -ForegroundColor Green
        Write-Host ""
        Write-Host "可以执行以下命令启动容器:" -ForegroundColor Cyan
        Write-Host "  .\run.ps1 docker"
    } else {
        Write-Host "构建失败" -ForegroundColor Red
        exit 1
    }
}

# 显示帮助
function Show-Help {
    Write-Host "XHS Spider Web 启动脚本 (Windows)"
    Write-Host ""
    Write-Host "用法:" -ForegroundColor Cyan
    Write-Host "  .\run.ps1 web              - 本地运行 Python 服务"
    Write-Host "  .\run.ps1 docker          - Docker 本地运行"
    Write-Host "  .\run.ps1 build           - 构建新镜像"
    Write-Host ""
    Write-Host "或者直接运行 (默认 web 模式):" -ForegroundColor Cyan
    Write-Host "  .\run.ps1"
    Write-Host ""
}

# 主逻辑
switch ($Mode.ToLower()) {
    "web"    { Run-Web }
    "docker" { Run-Docker }
    "build"  { Build-Image }
    default  { Show-Help }
}
