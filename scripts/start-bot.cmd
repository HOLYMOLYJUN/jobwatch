@echo off
REM Socket Mode 봇. 이게 떠 있어야 알림의 [관심]/[패스] 버튼이 동작한다.
REM 로그인 시 자동 실행되도록 작업 스케줄러에 등록해 두면 신경 쓸 일이 없다.
setlocal
cd /d "%~dp0.."
if not exist var mkdir var
".venv\Scripts\jobwatch.exe" bot >> "var\bot.log" 2>&1
