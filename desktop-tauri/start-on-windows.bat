@ECHO OFF
REM Windows desktop: same Tinode web UI as browser (no redesign).
REM Prefer Chrome/Edge app window = Chromium Blink, identical page.
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