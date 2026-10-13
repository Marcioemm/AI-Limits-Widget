$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
$app = Join-Path $projectRoot 'src\ai_limits_widget\app.py'

$processes = Get-CimInstance Win32_Process -Filter "Name = 'pythonw.exe'" -ErrorAction SilentlyContinue |
  Where-Object { $_.CommandLine -and $_.CommandLine.Contains($app) }

if (-not $processes) {
  Write-Output 'O widget não está em execução.'
  exit 0
}

foreach ($process in $processes) {
  Stop-Process -Id $process.ProcessId
}

Write-Output 'Widget encerrado.'

