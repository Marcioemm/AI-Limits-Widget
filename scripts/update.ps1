[CmdletBinding()]
param(
  [switch]$Restart
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
  throw 'Git não foi encontrado. Baixe a versão mais recente pela página Releases do projeto.'
}

if (-not (Test-Path '.git' -PathType Container)) {
  throw 'Esta cópia não foi instalada pelo Git. Baixe a versão mais recente pela página Releases do projeto.'
}

$changes = git status --porcelain
if ($changes) {
  Write-Error @'
Atualização cancelada: há alterações locais neste diretório.
Faça commit, descarte ou mova essas alterações antes de atualizar. A configuração
pessoal em %LOCALAPPDATA%\LimitesIA não é alterada por este script.
'@
}

$branch = git branch --show-current
if ($branch -ne 'main') {
  Write-Warning "Você está na branch '$branch', não na main. O script atualizará a branch atual."
}

$before = git rev-parse HEAD
git fetch --prune origin
git pull --ff-only
$after = git rev-parse HEAD

if ($before -eq $after) {
  Write-Host 'Você já está na versão mais recente.' -ForegroundColor Green
  exit 0
}

Write-Host 'Atualização concluída.' -ForegroundColor Green
Write-Host 'Suas preferências e perfis locais foram preservados.'
Write-Host 'Se esta versão trouxer novas opções, execute scripts\setup.ps1 para configurá-las.'

if ($Restart) {
  & (Join-Path $PSScriptRoot 'stop.ps1')
  & (Join-Path $PSScriptRoot 'start.ps1')
}

