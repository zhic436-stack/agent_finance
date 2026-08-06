@echo off
chcp 65001 >nul
title 金融分析系统 - 启动器
cd /d "%~dp0"

echo ============================================
echo   金融分析系统 (多视角金融研究 Agent)
echo ============================================
echo.

REM ========== 1. 检查 Python ==========
where python >nul 2>nul
if errorlevel 1 (
    echo [错误] 未检测到 Python，请先安装 Python 3.9 及以上版本
    echo 下载地址: https://www.python.org/downloads/
    echo 安装时务必勾选 "Add Python to PATH"
    pause
    exit /b 1
)

REM ========== 2. 检查端口 8532 是否已被占用 ==========
netstat -ano | findstr ":8532" | findstr "LISTENING" >nul 2>nul
if not errorlevel 1 (
    echo [警告] 端口 8532 已有服务在运行!
    echo.
    echo   原因: 上一次启动的黑色窗口还没关闭, 或已有实例在运行
    echo   解决: 1. 直接访问 http://localhost:8532 试试能否打开
    echo         2. 若打不开, 请关闭旧的黑色窗口后重新双击本脚本
    echo.
    pause
    exit /b 1
)

REM ========== 3. 依赖完整性检查 (缺任一则自动安装) ==========
python -c "import streamlit, curl_cffi, st_aggrid, akshare, pandas, numpy, plotly, schedule" >nul 2>nul
if errorlevel 1 (
    echo [提示] 检测到依赖缺失，正在安装依赖 (约几分钟，请耐心等待)...
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo [错误] 依赖安装失败，请检查网络后重试
        echo 可尝试国内镜像: python -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt
        pause
        exit /b 1
    )
    echo [完成] 依赖安装完成
)

REM ========== 4. .env 模板 ==========
if not exist .env (
    echo [提示] 未检测到 .env，已从 .env.example 生成模板
    echo 如需 LLM 润色报告，请编辑 .env 填入 API Key
    copy /y .env.example .env >nul
)

REM ========== 5. 启动 ==========
echo.
echo ============================================
echo   [重要] 本窗口就是网站服务本体, 请勿关闭!
echo   关闭本窗口 = 停止网站 (刷新就再也打不开)
echo ============================================
echo.
echo 正在启动服务...
echo 就绪后请用浏览器访问: http://localhost:8532
echo (浏览器一般会自动弹出)
echo.
python -m streamlit run ui/app.py --server.port 8532
pause
