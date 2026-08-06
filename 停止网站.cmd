@echo off
chcp 65001 >nul
title 停止金融分析系统
echo 正在停止金融分析系统 (端口 8532)...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8532" ^| findstr "LISTENING"') do (
    taskkill /PID %%a /F >nul 2>nul
)
echo.
echo [完成] 网站已停止, 端口 8532 已释放
echo 下次打开: 双击 启动网站.cmd
pause
