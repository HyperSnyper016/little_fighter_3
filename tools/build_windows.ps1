$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $repoRoot
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (!(Test-Path $python)) {
    throw "Create the .venv build environment and install requirements-build.txt first."
}

& $python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)"
if ($LASTEXITCODE -ne 0) {
    throw "Python 3.12 or newer is required to build the Windows release."
}

$architecture = (& $python -c "import struct; print(8 * struct.calcsize('P'))").Trim()
if ($architecture -ne "64") {
    throw "Build with 64-bit Python to produce the Windows x64 release."
}

$version = (& $python -c "from game.constants import VERSION; print(VERSION)").Trim()
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($version)) {
    throw "Could not read the game version."
}

$distRoot = Join-Path $repoRoot "dist\$version"
$archivePath = Join-Path $repoRoot "dist\LittleFighter3-$version-windows-x64.zip"
if ((Test-Path $distRoot) -or (Test-Path $archivePath)) {
    throw "Release output already exists. Move or remove only the existing $version output before rebuilding."
}

& $python -m unittest discover -s tests
if ($LASTEXITCODE -ne 0) {
    throw "Unit tests failed; the release was not built."
}

$workPath = Join-Path $repoRoot "build\pyinstaller\$version"
& $python -m PyInstaller `
    --noconfirm `
    --clean `
    --distpath $distRoot `
    --workpath $workPath `
    (Join-Path $repoRoot "little_fighter_3.spec")
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed."
}

$appPath = Join-Path $distRoot "LittleFighter3"
$executablePath = Join-Path $appPath "LittleFighter3.exe"
if (!(Test-Path $executablePath)) {
    throw "The packaged executable was not created."
}

$internalPath = Join-Path $appPath "_internal"
if (!(Test-Path (Join-Path $internalPath "assets")) -or
    !(Test-Path (Join-Path $internalPath "UPDATE_HISTORY.md"))) {
    throw "The packaged assets or update history are missing."
}

Compress-Archive -Path (Join-Path $appPath "*") -DestinationPath $archivePath
Write-Output "Created $archivePath"
