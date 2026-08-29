@echo off
REM 매일 정해진 시각에 채용공고를 수집해 슬랙으로 보낸다.
REM 작업 스케줄러가 이 파일을 호출한다. 실패해도 조용히 끝나면 안 되므로
REM 표준출력과 오류를 모두 로그에 남긴다.
setlocal
cd /d "%~dp0.."
if not exist var mkdir var

set "LOG=var\daily.log"
echo.>> "%LOG%"
echo ===== %date% %time% =====>> "%LOG%"
".venv\Scripts\jobwatch.exe" run --buttons >> "%LOG%" 2>&1
set "CODE=%ERRORLEVEL%"
echo [exit %CODE%]>> "%LOG%"

REM 로그가 무한정 커지지 않도록 최근 1000줄만 남긴다
powershell -NoProfile -Command "$p='%LOG%'; if ((Get-Content $p).Count -gt 2000) { Get-Content $p -Tail 1000 | Set-Content $p -Encoding utf8 }"

exit /b %CODE%
