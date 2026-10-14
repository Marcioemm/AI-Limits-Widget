#ifndef MyAppVersion
  #define MyAppVersion "0.1.0"
#endif

#ifndef SourceDir
  #define SourceDir "..\build\dist\AI Limits Widget"
#endif

#define MyAppName "AI Limits Widget"
#define MyAppPublisher "AI Limits Widget contributors"
#define MyAppURL "https://github.com/Marcioemm/AI-Limits-Widget"
#define MyAppExeName "AI Limits Widget.exe"

[Setup]
AppId={{F074A8B7-4D2E-42D9-B728-9F1279DB2199}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/issues
AppUpdatesURL={#MyAppURL}/releases
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
LicenseFile=..\LICENSE
OutputDir=..\build\installer
OutputBaseFilename=AI-Limits-Widget-Setup-{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na Área de Trabalho"; GroupDescription: "Atalhos adicionais:"; Flags: unchecked

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Abrir {#MyAppName}"; Flags: nowait postinstall skipifsilent

[Code]
var
  CodexCliPage: TOutputMsgWizardPage;
  CodexCliLink: TNewStaticText;

procedure OpenCodexCliDocs(Sender: TObject);
var
  ErrorCode: Integer;
begin
  ShellExec('open', 'https://learn.chatgpt.com/docs/codex/cli', '', '', SW_SHOWNORMAL, ewNoWait, ErrorCode);
end;

procedure InitializeWizard;
begin
  CodexCliPage := CreateOutputMsgPage(
    wpSelectTasks,
    'Codex CLI (opcional)',
    'Instale o Codex CLI para monitorar limites do Codex',
    'O widget consulta o Codex CLI localmente. Se ele ainda não estiver instalado, abra a documentação oficial para instalá-lo e entrar com a sua conta ChatGPT.'
  );

  CodexCliLink := TNewStaticText.Create(CodexCliPage);
  CodexCliLink.Parent := CodexCliPage.Surface;
  CodexCliLink.Caption := 'Abrir documentação de instalação do Codex CLI';
  CodexCliLink.Font.Color := clBlue;
  CodexCliLink.Font.Style := [fsUnderline];
  CodexCliLink.Cursor := crHand;
  CodexCliLink.Top := ScaleY(100);
  CodexCliLink.OnClick := @OpenCodexCliDocs;
end;
