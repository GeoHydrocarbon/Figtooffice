# 在 Figstooffcie 目录生成 dist\Figstooffcie\Figstooffcie.exe（目录分发，Qt 更稳定）
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$py = Join-Path $root "conda_env\python.exe"
if (-not (Test-Path $py)) {
    Write-Error "未找到 conda_env\python.exe。请先创建环境并安装 requirements.txt，或改用本机已安装依赖的 Python 并修改本脚本中的 `$py。"
}

& $py -m PyInstaller --version *> $null
if ($LASTEXITCODE -ne 0) {
    & $py -m pip install -q -r (Join-Path $root "requirements-build.txt")
    if ($LASTEXITCODE -ne 0) {
        throw "安装打包依赖失败。"
    }
}

# 某些环境会装入 pathlib 的旧回移植包，PyInstaller 会直接拒绝启动；打包前定点移除
$sitePackages = Join-Path $root "conda_env\Lib\site-packages"
$pathlibTargets = @(
    (Join-Path $sitePackages "pathlib.py"),
    (Join-Path $sitePackages "pathlib-1.0.1.dist-info"),
    (Join-Path $sitePackages "__pycache__\pathlib.cpython-312.pyc"),
    (Join-Path $sitePackages "__pycache__\pathlib.cpython-313.pyc")
)
foreach ($target in $pathlibTargets) {
    if (Test-Path $target) {
        Remove-Item -LiteralPath $target -Recurse -Force
    }
}

# 避免 PyInstaller 清理 dist 时因 exe 仍占用而 Permission denied
Stop-Process -Name "Figstooffcie" -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 1
& $py -m PyInstaller --noconfirm --clean (Join-Path $root "Figstooffcie.spec")
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller 打包失败。"
}

Write-Host ""
Write-Host "完成。运行: $($root)\dist\Figstooffcie\Figstooffcie.exe"
