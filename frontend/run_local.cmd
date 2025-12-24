@echo off
setlocal

cd /d %~dp0

REM PowerShell 可能禁止运行 npm.ps1；使用 npm.cmd 可绕过
call npm.cmd i
if errorlevel 1 exit /b 1

call npm.cmd run dev
endlocal


