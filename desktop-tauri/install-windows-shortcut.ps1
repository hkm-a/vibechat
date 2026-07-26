# 安装 Windows 桌面快捷方式，使用 Chrome 或 Edge 应用窗口打开 localhost:6060。
# 界面与浏览器一致，不会启动 WSL/Linux Tauri 或 Qt 客户端。
# 从 WSL 运行：
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
  Write-Host "浏览器：$browser"
} else {
  $sc.TargetPath = $winBat
  $sc.Arguments = ""
  $sc.WorkingDirectory = $installDir
  Write-Host "未找到受支持的浏览器，改用批处理回退入口"
}
$sc.Description = "VibeChat：打开 http://localhost:6060/ 的桌面入口"
$sc.Save()

# 同时保留批处理副本，便于修复已有快捷方式。
Copy-Item $winBat (Join-Path $env:LOCALAPPDATA "VibeChat-Tauri\start-on-windows.bat") -Force -ErrorAction SilentlyContinue

Write-Host "桌面快捷方式：$lnkPath"
Write-Host "启动参数：$($sc.Arguments)"
Write-Host "界面直接使用 Tinode Web，打包过程不会重绘页面。"
