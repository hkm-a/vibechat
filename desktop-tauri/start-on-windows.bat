@ECHO OFF
REM Windows 桌面端直接复用浏览器中的 Tinode Web 界面。
REM 优先使用 Chrome 或 Edge 应用窗口，以保持相同的 Blink 渲染效果。
setlocal EnableExtensions
set "URL=http://localhost:6060/"
set "BIN="

if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" set "BIN=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
if not defined BIN if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" set "BIN=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
if not defined BIN if exist "%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe" set "BIN=%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"
if not defined BIN if exist "%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe" set "BIN=%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"
if not defined BIN if exist "%ProgramFiles%\Microsoft\Edge\Application\msedge.exe" set "BIN=%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"
if not defined BIN if exist "%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe" set "BIN=%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe"

if defined BIN (
  start "" "%BIN%" --app=%URL% --new-window
  exit /b 0
)

start "" %URL%
exit /b 0
