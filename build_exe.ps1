$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$iconFile = Join-Path $PSScriptRoot 'Icon/Ollama.png'
$iconDirectory = Join-Path $PSScriptRoot 'Icon'
$chatFile = Join-Path $PSScriptRoot 'CHAT/ollama-say.html'
python -m PyInstaller --noconfirm --clean --onefile --windowed --name Ollama_Park --icon $iconFile --add-data "$iconDirectory;Icon" --add-data "$chatFile;CHAT" --workpath .data/build --distpath .data/dist --specpath .data app.py
if ($LASTEXITCODE -ne 0) { throw 'EXE build failed.' }
$builtExe = Join-Path $PSScriptRoot '.data/dist/Ollama_Park.exe'
if ((Get-Item -LiteralPath $builtExe).Length -ge 100MB) { throw 'EXE exceeds 100 MB.' }
Copy-Item -LiteralPath $builtExe -Destination (Join-Path $PSScriptRoot 'Ollama_Park.exe') -Force
Write-Output 'Updated Ollama_Park.exe'
