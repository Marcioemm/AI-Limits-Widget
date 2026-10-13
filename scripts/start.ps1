$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
$app = Join-Path $projectRoot 'src\ai_limits_widget\app.py'
$pythonw = Get-Command pythonw.exe -ErrorAction SilentlyContinue

if (-not $pythonw) {
  Write-Error 'Python com Tkinter não foi encontrado. Instale Python 3.10 ou superior e marque a opção para adicioná-lo ao PATH.'
}

$existing = Get-CimInstance Win32_Process -Filter "Name = 'pythonw.exe'" -ErrorAction SilentlyContinue |
  Where-Object { $_.CommandLine -and $_.CommandLine.Contains($app) }

if (-not $existing) {
  Start-Process -WindowStyle Hidden -FilePath $pythonw.Source -ArgumentList @($app)
}

