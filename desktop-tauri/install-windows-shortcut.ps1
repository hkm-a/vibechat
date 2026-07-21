# Install Windows desktop shortcut -> Chrome/Edge app window for localhost:6060
# Same web UI as browser. Does NOT launch WSL/Linux Tauri or Qt.
# Run from WSL:
#   powershell.exe -ExecutionPolicy Bypass -File desktop-tauri/install-windows-shortcut.ps1

$ErrorActionPreference = "Stop"
$installDir = Join-Path $env:LOCALAPPDATA "VibeChat-Desktop-Web"
New-Item -ItemType Directory -Force -Path $installDir | Out-Null

$winBat = Join-Path $installDir "start-web.bat"
@'
@ECHO OFF
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
'@ | Set-Content -Path $winBat -Encoding ASCII

$candidates = @(
  "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
  "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
  "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe",
  "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe",
  "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe",
  "$env:LOCALAPPDATA\Microsoft\Edge\Application\msedge.exe"
)
$browser = $candidates | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1

$desktop = [Environment]::GetFolderPath("Desktop")
$lnkPath = Join-Path $desktop "VibeChat.lnk"
$w = New-Object -ComObject WScript.Shell
$sc = $w.CreateShortcut($lnkPath)
if ($browser) {
  $sc.TargetPath = $browser
  $sc.Arguments = "--app=http://localhost:6060/ --new-window"
  $sc.WorkingDirectory = Split-Path $browser
  Write-Host "Browser: $browser"
} else {
  $sc.TargetPath = $winBat
  $sc.Arguments = ""
  $sc.WorkingDirectory = $installDir
  Write-Host "Browser not found; using bat fallback"
}
$sc.Description = "VibeChat = same web UI as http://localhost:6060/"
$sc.Save()

# also keep bat copy
Copy-Item $winBat (Join-Path $env:LOCALAPPDATA "VibeChat-Tauri\start-on-windows.bat") -Force -ErrorAction SilentlyContinue

Write-Host "Desktop shortcut: $lnkPath"
Write-Host "Args: $($sc.Arguments)"
Write-Host "UI is Tinode web; packaging does not redesign the page."