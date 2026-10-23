[CmdletBinding()]
param(
  [string]$Version,
  [string]$PythonPath
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$python = if ($PythonPath) {
  Get-Item -LiteralPath $PythonPath -ErrorAction SilentlyContinue
} else {
  Get-Command python.exe -ErrorAction SilentlyContinue
}

if (-not $python) {
  throw 'Python não foi encontrado. Instale Python 3.10 ou superior ou informe -PythonPath.'
}
$pythonExe = $python.Source
if (-not $pythonExe) { $pythonExe = $python.FullName }

if (-not $Version) {
  $Version = & $pythonExe -c "import tomllib, pathlib; print(tomllib.loads(pathlib.Path('pyproject.toml').read_text(encoding='utf-8'))['project']['version'])"
}

if ($Version -notmatch '^\d+(\.\d+){1,3}([-.][0-9A-Za-z.-]+)?$') {
  throw "A versão '$Version' não é compatível com o instalador."
}

$isccCandidates = @(
  (Get-Command ISCC.exe -ErrorAction SilentlyContinue).Source,
  (Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6\ISCC.exe'),
  (Join-Path $env:ProgramFiles 'Inno Setup 6\ISCC.exe'),
  (Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 6\ISCC.exe')
) | Where-Object { $_ -and (Test-Path -LiteralPath $_ -PathType Leaf) }
$iscc = $isccCandidates | Select-Object -First 1
if (-not $iscc) {
  throw 'Inno Setup 6 não foi encontrado. Instale-o antes de gerar o instalador.'
}

Push-Location $projectRoot
try {
  & $pythonExe -m PyInstaller --version *> $null
  if ($LASTEXITCODE -ne 0) {
    throw 'PyInstaller não foi encontrado. Execute: python -m pip install -r requirements-build.txt'
  }

  $buildRoot = Join-Path $projectRoot 'build'
  $distPath = Join-Path $buildRoot 'dist'
  $workPath = Join-Path $buildRoot 'work'
  $specPath = Join-Path $buildRoot 'spec'
  $appName = 'AI Limits Widget'
  $appPath = Join-Path $distPath $appName

  & $pythonExe -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --name $appName `
    --paths (Join-Path $projectRoot 'src') `
    --collect-submodules ai_limits_widget `
    --distpath $distPath `
    --workpath $workPath `
    --specpath $specPath `
    (Join-Path $projectRoot 'packaging\frozen_launcher.py')
  if ($LASTEXITCODE -ne 0) {
    throw 'O empacotamento com PyInstaller falhou.'
  }

  & $pythonExe -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --console `
    --name 'AI Limits AGY Bridge' `
    --paths (Join-Path $projectRoot 'src') `
    --distpath $appPath `
    --workpath (Join-Path $workPath 'agy-bridge') `
    --specpath $specPath `
    (Join-Path $projectRoot 'src\ai_limits_widget\agy_bridge.py')
  if ($LASTEXITCODE -ne 0) {
    throw 'O empacotamento do coletor do AGY falhou.'
  }

  $executable = Join-Path $appPath "$appName.exe"
  if (-not (Test-Path -LiteralPath $executable -PathType Leaf)) {
    throw "Executável esperado não foi gerado: $executable"
  }
  $agyBridge = Join-Path $appPath 'AI Limits AGY Bridge.exe'
  if (-not (Test-Path -LiteralPath $agyBridge -PathType Leaf)) {
    throw "Coletor do AGY esperado não foi gerado: $agyBridge"
  }

  & $iscc "/DMyAppVersion=$Version" "/DSourceDir=$appPath" (Join-Path $projectRoot 'installer\AI Limits Widget.iss')
  if ($LASTEXITCODE -ne 0) {
    throw 'A compilação do instalador com Inno Setup falhou.'
  }

  $installer = Join-Path $buildRoot "installer\AI-Limits-Widget-Setup-$Version.exe"
  if (-not (Test-Path -LiteralPath $installer -PathType Leaf)) {
    throw "Instalador esperado não foi gerado: $installer"
  }

  $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $installer).Hash.ToLowerInvariant()
  $hashFile = "$installer.sha256"
  [System.IO.File]::WriteAllText($hashFile, "$hash  $([System.IO.Path]::GetFileName($installer))`n", [System.Text.UTF8Encoding]::new($false))

  Write-Host 'Instalador gerado com sucesso.' -ForegroundColor Green
  Write-Host "Arquivo: $installer"
  Write-Host "Checksum: $hashFile"
} finally {
  Pop-Location
}
