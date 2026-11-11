# Build do programa desktop para Windows: interface, lote de exemplo, PyInstaller, teste de
# fumaça e zip com SHA-256. Rode da raiz do repositório:
#   powershell -ExecutionPolicy Bypass -File deploy/windows/build.ps1
# Requisitos: uv, Node 22 e as fontes DejaVu em $env:QA_SYNTH_FONT_DIR (lote de exemplo).
$ErrorActionPreference = "Stop"
$root = (Resolve-Path "$PSScriptRoot\..\..").Path
Set-Location $root

$version = (uv run --project engine python -c "import qa_engine; print(qa_engine.__version__)").Trim()
$name = "QA-SOS-Docs-$version"
$build = Join-Path $root "build"
$dist = Join-Path $build "dist"
$out = Join-Path $dist $name
# build/models fica (cache): fetch.py só baixa o que falta ou não confere.
foreach ($dir in "dist", "work", "samples", "site") {
  Remove-Item -Recurse -Force (Join-Path $build $dir) -ErrorAction SilentlyContinue
}

Write-Host "0. versão no QA.exe"
$parts = ($version.Split(".") + @("0", "0", "0"))[0..3] -join ", "
(Get-Content deploy/windows/version.txt -Raw) `
  -replace "filevers=\([^)]*\)", "filevers=($parts)" `
  -replace "prodvers=\([^)]*\)", "prodvers=($parts)" `
  -replace '"FileVersion", "[^"]*"', ('"FileVersion", "' + $version + '"') `
  -replace '"ProductVersion", "[^"]*"', ('"ProductVersion", "' + $version + '"') |
  Set-Content deploy/windows/version.txt -Encoding utf8

Write-Host "1. interface"
Push-Location ui
npm ci --no-audit --no-fund
$env:VITE_API_URL = ""
npm run build
Pop-Location

Write-Host "2. lote de exemplo do teste de fumaça"
uv run --project engine python tools/synth/synth.py selftest --out "$build/samples/lote-exemplo"

Write-Host "2b. modelos (baixados e conferidos pelo SHA-256 de models.lock.json)"
uv run --project engine python tools/models/fetch.py --out "$build/models"
if ($LASTEXITCODE -ne 0) { throw "modelos não conferem" }

Write-Host "3. documentação offline"
uvx --with mkdocs-material==9.5.44 --with "mkdocstrings[python]==0.27.0" --with pymdown-extensions==10.12 mkdocs==1.6.1 build --strict --site-dir "$build/site"

Write-Host "4. PyInstaller"
uv run --project engine --extra desktop --group build pyinstaller deploy/windows/qa.spec --noconfirm --distpath $dist --workpath "$build/work"
Rename-Item (Join-Path $dist "QA") $name

Write-Host "5. recursos ao lado do QA.exe"
Copy-Item -Recurse ui/dist (Join-Path $out "ui")
Copy-Item -Recurse profiles (Join-Path $out "profiles")
New-Item -ItemType Directory (Join-Path $out "samples") | Out-Null
Copy-Item -Recurse "$build/samples/lote-exemplo" (Join-Path $out "samples/lote-exemplo")
Copy-Item -Recurse "$build/site" (Join-Path $out "docs")
Copy-Item deploy/windows/LEIA-ME.txt $out
Copy-Item models.lock.json $out
Copy-Item -Recurse "$build/models" (Join-Path $out "models")

Write-Host "6. teste de fumaça"
& (Join-Path $out "QA-suporte.exe") --self-test
if ($LASTEXITCODE -ne 0) { throw "teste de fumaça falhou" }

Write-Host "7. zip e SHA-256"
$zip = Join-Path $dist "$name.zip"
Compress-Archive -Path $out -DestinationPath $zip
$hash = (Get-FileHash $zip -Algorithm SHA256).Hash.ToLower()
"$hash  $name.zip" | Out-File -Encoding ascii "$zip.sha256"
Write-Host "pronto: $zip ($hash)"
