@echo off
chcp 65001 > nul
echo IMA Copilot MCP 服务器启动脚本 (简化版)
echo =============================================

REM 检查 Python 是否可用
python --version >nul 2>&1
if errorlevel 1 (
    echo 错误: 未找到 Python，请确保 Python 已安装并添加到 PATH
    pause
    exit /b 1
)

REM 检查 fastmcp 是否可用
fastmcp --version >nul 2>&1
if errorlevel 1 (
    echo 警告: 未找到 fastmcp，尝试安装...
    pip install fastmcp
    if errorlevel 1 (
        echo 错误: fastmcp 安装失败，请手动安装: pip install fastmcp
        pause
        exit /b 1
    )
)

REM 检查 .env 文件
if not exist .env (
    echo 错误: 未找到 .env 文件
    echo 请复制 .env.example 为 .env 并配置相应的环境变量
    echo.
    echo 配置步骤:
    echo 1. copy .env.example .env
    echo 2. 编辑 .env 文件，填入 IMA 认证信息
    echo 3. 重新运行此脚本
    pause
    exit /b 1
)

echo.
echo ✅ 环境检查通过，启动 IMA Copilot MCP 服务器...
echo.

REM 启动服务器
python run.py

pause