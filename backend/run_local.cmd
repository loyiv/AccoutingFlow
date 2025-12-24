@echo off
setlocal

cd /d %~dp0

REM 如果没设置 DATABASE_URL，使用默认本机 MySQL（可自行改密码/库名）
if "%DATABASE_URL%"=="" set DATABASE_URL=mysql+pymysql://accountingflow:accountingflow@127.0.0.1:3306/accountingflow?charset=utf8mb4
if "%CORS_ORIGINS%"=="" set CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173

REM PowerShell 可能禁止运行 ps1；这里强制 Bypass
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_local.ps1"

endlocal




