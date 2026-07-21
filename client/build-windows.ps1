# 在 Windows 上打包 VibeChat 桌面客户端
# 用法（PowerShell）:
#   cd C:\Users\hkm\projects\vibechat-desktop-src
#   powershell -ExecutionPolicy Bypass -File .\build-windows.ps1
#
# 产出:
#   dist\VibeChat\VibeChat.exe
#   桌面快捷方式: Desktop\VibeChat.lnk
#   安装目录: %LOCALAPPDATA%\VibeChat-Desktop\

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

function Resolve-Python {
  # 优先 3.11/3.12（PySide6 轮子成熟）；避开 3.14 若无 wheel
  $candidates = @(
    "$env:APPDATA\uv\python\cpython-3.11.15-windows-x86_64-none\python.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe"
  )
  foreach ($c in $candidates) {
    if (Test-Path $c) { return $c }
  }
  # py launcher tags
  foreach ($tag in @("-3.11", "-3.12", "-3.13", "-3")) {
    try {
      $out = & py $tag -c "import sys; print(sys.executable)" 2>$null
      if ($LASTEXITCODE -eq 0 -and $out) { return $out.Trim() }
    } catch {}
  }
  throw "未找到可用的 Windows Python（建议安装 3.11/3.12）"
}

Write-Host "==> 1/4 解析 Python"
$py = Resolve-Python
Write-Host "    $py"
& $py -c "import sys; print(sys.version)"

$venv = Join-Path $Root ".venv-win"
if (-not (Test-Path (Join-Path $venv "Scripts\python.exe"))) {
  & $py -m venv $venv
}

$python = Join-Path $venv "Scripts\python.exe"
$pip = Join-Path $venv "Scripts\pip.exe"
$pyi = Join-Path $venv "Scripts\pyinstaller.exe"

Write-Host "==> 2/4 安装依赖 (仅 Essentials，包体更小)"
& $python -m pip install -U pip wheel
# Essentials = Widgets/Core/Gui/Network；不要 Addons（WebEngine/3D 等）
& $pip install "PySide6_Essentials>=6.6" "websockets>=12" "pyinstaller>=6.0"

Write-Host "==> 3/4 PyInstaller 打包"
if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
if (Test-Path "dist\VibeChat") { Remove-Item -Recurse -Force "dist\VibeChat" }
& $pyi --noconfirm VibeChat.spec

$distExe = Join-Path $Root "dist\VibeChat\VibeChat.exe"
if (-not (Test-Path $distExe)) {
  throw "打包失败: 找不到 $distExe"
}

Write-Host "==> 4/4 安装到本机并创建桌面快捷方式"
# 避免覆盖用户已有的其它 VibeChat 安装
$installDir = Join-Path $env:LOCALAPPDATA "VibeChat-Desktop"
if (Test-Path $installDir) { Remove-Item -Recurse -Force $installDir }
New-Item -ItemType Directory -Path $installDir | Out-Null
Copy-Item -Recurse -Force (Join-Path $Root "dist\VibeChat\*") $installDir

$target = Join-Path $installDir "VibeChat.exe"
$desktop = [Environment]::GetFolderPath("Desktop")
$lnkPath = Join-Path $desktop "VibeChat.lnk"

$w = New-Object -ComObject WScript.Shell
$sc = $w.CreateShortcut($lnkPath)
$sc.TargetPath = $target
$sc.WorkingDirectory = $installDir
$sc.Description = "VibeChat Desktop - Tinode 客户端（连本机 6060）"
$sc.Save()

Write-Host ""
Write-Host "完成。"
Write-Host "  程序: $target"
Write-Host "  快捷方式: $lnkPath"
Write-Host "  登录服务器填: localhost:6060"
Write-Host "  需 WSL 里 Docker Tinode 已启动 (docker compose up -d)"