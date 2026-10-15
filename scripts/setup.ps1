[CmdletBinding()]
param(
  [ValidateSet('codex', 'claude', 'gemini', 'both', 'all')]
  [string]$Providers,
  [ValidateRange(5, 120)]
  [int]$RefreshMinutes = 5,
  [string]$CodexPath,
  [string]$ClaudePath,
  [string]$AgyPath,
  [switch]$CreateDesktopShortcut,
  [switch]$Start
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$interactive = -not $PSBoundParameters.ContainsKey('Providers')

function Find-Executable {
  param([string[]]$Names)
  foreach ($name in $Names) {
    $command = Get-Command $name -ErrorAction SilentlyContinue
    if ($command -and (Test-Path -LiteralPath $command.Source -PathType Leaf)) {
      return $command.Source
    }
  }
  return $null
}

function Resolve-Executable {
  param(
    [string]$Provider,
    [string]$ProvidedPath,
    [string]$DetectedPath
  )

  if ($ProvidedPath) {
    if (-not (Test-Path -LiteralPath $ProvidedPath -PathType Leaf)) {
      throw "O caminho informado para $Provider não é um arquivo: $ProvidedPath"
    }
    return (Resolve-Path -LiteralPath $ProvidedPath).Path
  }

  if ($DetectedPath) {
    Write-Host "$Provider encontrado: $DetectedPath" -ForegroundColor Green
    $answer = Read-Host 'Usar este executável? [S/n]'
    if ($answer -notmatch '^(n|nao|não)$') {
      return $DetectedPath
    }
  }

  $path = Read-Host "Informe o caminho completo do executável do $Provider (ou deixe vazio para procurar pelo PATH)"
  if ($path) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
      throw "O caminho informado para $Provider não é um arquivo: $path"
    }
    return (Resolve-Path -LiteralPath $path).Path
  }

  Write-Warning "$Provider não foi encontrado. Você poderá executar este instalador novamente depois de instalá-lo."
  return $null
}

if (-not $Providers) {
  Write-Host ''
  Write-Host 'AI Limits Widget - configuração' -ForegroundColor Cyan
  Write-Host 'O instalador não solicita nem salva senhas, tokens ou chaves de API.'
  do {
    $answer = (Read-Host 'Quais provedores deseja monitorar? [C]odex, [A]nthropic/Claude, [G]emini/AGY, [B]oth (Codex+Claude), [T]odos').Trim().ToLowerInvariant()
    $Providers = switch ($answer) {
      'c' { 'codex' }
      'a' { 'claude' }
      'g' { 'gemini' }
      'b' { 'both' }
      't' { 'all' }
      default { $null }
    }
  } until ($Providers)

  $minutes = Read-Host "Atualizar a cada quantos minutos? [padrão: $RefreshMinutes; mínimo: 5]"
  if ($minutes) {
    if ($minutes -notmatch '^\\d+$' -or [int]$minutes -lt 5 -or [int]$minutes -gt 120) {
      throw 'Informe um número entre 5 e 120 minutos.'
    }
    $RefreshMinutes = [int]$minutes
  }
}

$selected = switch ($Providers) {
  'both' { @('codex', 'claude') }
  'all' { @('codex', 'claude', 'gemini') }
  default { @($Providers) }
}

$executables = [ordered]@{ codex = $null; claude = $null; gemini = $null }
if ('codex' -in $selected) {
  $executables.codex = Resolve-Executable -Provider 'Codex CLI' -ProvidedPath $CodexPath -DetectedPath (Find-Executable @('codex.exe', 'codex.cmd', 'codex'))
}
if ('claude' -in $selected) {
  $claudeDetected = Find-Executable @('claude.exe', 'claude.cmd', 'claude')
  if (-not $claudeDetected) {
    $npmCandidate = Join-Path $env:APPDATA 'npm\\claude.cmd'
    if (Test-Path -LiteralPath $npmCandidate -PathType Leaf) {
      $claudeDetected = $npmCandidate
    }
  }
  $executables.claude = Resolve-Executable -Provider 'Claude Code' -ProvidedPath $ClaudePath -DetectedPath $claudeDetected
}
if ('gemini' -in $selected) {
  $executables.gemini = Resolve-Executable -Provider 'Antigravity CLI (AGY)' -ProvidedPath $AgyPath -DetectedPath (Find-Executable @('agy.exe', 'agy.cmd', 'agy'))
  $python = Get-Command python.exe -ErrorAction SilentlyContinue
  if ($executables.gemini -and $python) {
    & $python.Source (Join-Path $projectRoot 'src\ai_limits_widget\app.py') --install-agy-integration
    if ($LASTEXITCODE -ne 0) {
      throw 'Não foi possível ativar a integração segura com a statusline do AGY.'
    }
  }
}

$profiles = @()
foreach ($provider in $selected) {
  $profiles += [ordered]@{
    id = "$provider-default"
    provider = $provider
    label = 'Padrão'
    executable = $executables[$provider]
    configDir = $null
  }
}

if ($interactive) {
  while ((Read-Host 'Adicionar outro perfil/conta local? [s/N]') -match '^(s|sim)$') {
    do {
      $kind = (Read-Host 'Provedor do novo perfil: [C]odex ou [A]nthropic/Claude').Trim().ToLowerInvariant()
      $provider = switch ($kind) {
        'c' { 'codex' }
        'a' { 'claude' }
        default { $null }
      }
    } until ($provider)
    $label = (Read-Host 'Nome para exibir (ex.: Trabalho)').Trim()
    if (-not $label) { $label = "Perfil $($profiles.Count + 1)" }
    $configDir = (Read-Host $(if ($provider -eq 'codex') {
      'Diretório CODEX_HOME deste perfil (vazio = perfil padrão)'
    } else {
      'Diretório CLAUDE_CONFIG_DIR deste perfil (vazio = perfil padrão)'
    })).Trim()
    if ($configDir -and -not (Test-Path -LiteralPath $configDir -PathType Container)) {
      Write-Warning 'Diretório não encontrado; o perfil será salvo mesmo assim e ficará oculto até ser válido.'
    }
    $path = Resolve-Executable -Provider $provider -ProvidedPath '' -DetectedPath $executables[$provider]
    $safeId = ($label.ToLowerInvariant() -replace '[^a-z0-9]+', '-').Trim('-')
    $profiles += [ordered]@{
      id = "$provider-$safeId-$($profiles.Count + 1)"
      provider = $provider
      label = $label
      executable = $path
      configDir = if ($configDir) { (Resolve-Path -LiteralPath $configDir -ErrorAction SilentlyContinue).Path } else { $null }
    }
  }
}

$localData = [Environment]::GetFolderPath('LocalApplicationData')
$configDirectory = Join-Path $localData 'LimitesIA'
New-Item -ItemType Directory -Force -Path $configDirectory | Out-Null
$configPath = Join-Path $configDirectory 'config.json'
$config = [ordered]@{
  providers = @($selected)
  refreshMinutes = $RefreshMinutes
  executables = $executables
  profiles = @($profiles)
}
[System.IO.File]::WriteAllText(
  $configPath,
  ($config | ConvertTo-Json -Depth 3),
  [System.Text.UTF8Encoding]::new($false)
)

if (-not $PSBoundParameters.ContainsKey('CreateDesktopShortcut')) {
  $shortcutAnswer = Read-Host 'Criar atalho na Área de Trabalho? [s/N]'
  $CreateDesktopShortcut = $shortcutAnswer -match '^(s|sim)$'
}
if ($CreateDesktopShortcut) {
  $desktop = [Environment]::GetFolderPath('Desktop')
  $shortcutPath = Join-Path $desktop 'AI Limits Widget.lnk'
  $shell = New-Object -ComObject WScript.Shell
  $shortcut = $shell.CreateShortcut($shortcutPath)
  $shortcut.TargetPath = (Get-Command powershell.exe).Source
  $shortcut.Arguments = '-NoProfile -ExecutionPolicy Bypass -File "' + (Join-Path $PSScriptRoot 'start.ps1') + '"'
  $shortcut.WorkingDirectory = $projectRoot
  $pythonw = Get-Command pythonw.exe -ErrorAction SilentlyContinue
  if ($pythonw) {
    $shortcut.IconLocation = $pythonw.Source
  }
  $shortcut.Save()
}

Write-Host ''
Write-Host 'Configuração salva.' -ForegroundColor Green
Write-Host "Arquivo: $configPath"
Write-Host "Provedores: $($selected -join ', ')"
Write-Host "Atualização: a cada $RefreshMinutes minuto(s)"
foreach ($profile in $profiles) {
  $profileDirectory = if ($profile.configDir) { $profile.configDir } else { 'perfil padrão' }
  Write-Host "$($profile.provider) / $($profile.label): $profileDirectory"
}

if (-not $PSBoundParameters.ContainsKey('Start')) {
  $startAnswer = Read-Host 'Abrir o widget agora? [S/n]'
  $Start = $startAnswer -notmatch '^(n|nao|não)$'
}
if ($Start) {
  & (Join-Path $PSScriptRoot 'start.ps1')
}

