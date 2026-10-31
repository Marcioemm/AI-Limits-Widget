# Gerando o instalador Windows

Para o pacote Ubuntu, consulte [RELEASING_LINUX.md](RELEASING_LINUX.md).

O instalador é gerado apenas no Windows e não inclui credenciais nem os CLIs do
Codex ou Claude Code. Esses programas continuam sendo detectados no perfil local
da pessoa usuária quando o widget é aberto.

## Pré-requisitos para quem mantém o projeto

- Python 3.10 ou superior;
- [Inno Setup 6](https://jrsoftware.org/isinfo.php);
- PyInstaller, instalado somente no ambiente de build:

  ```powershell
  python -m pip install -r requirements-build.txt
  ```

## Build local

Na raiz do repositório, execute:

```powershell
.\scripts\build-installer.ps1
```

Caso o PyInstaller esteja em um ambiente virtual não ativado, passe o Python
desse ambiente explicitamente:

```powershell
.\scripts\build-installer.ps1 -PythonPath .\.venv\Scripts\python.exe
```

O script cria estes arquivos, que não devem ser versionados:

- `build\installer\AI-Limits-Widget-Setup-<versão>.exe`
- `build\installer\AI-Limits-Widget-Setup-<versão>.exe.sha256`

Para gerar uma versão de teste sem modificar `pyproject.toml`, informe-a
explicitamente:

```powershell
.\scripts\build-installer.ps1 -Version 0.1.0-beta.1
```

O instalador usa instalação por usuário em
`%LOCALAPPDATA%\Programs\AI Limits Widget`; assim, não requer privilégios de
administrador. Ele oferece atalhos no Menu Iniciar e, opcionalmente, na Área de
Trabalho, além de criar um desinstalador.

## Publicação manual

1. Atualize a versão em `pyproject.toml` e em `src\ai_limits_widget\__init__.py`.
2. Mova as alterações de **Não lançado** no [CHANGELOG.md](../CHANGELOG.md) para
   uma seção com a nova versão e a data de publicação; recrie **Não lançado**.
3. Integre essas alterações à `main`, gere o instalador a partir do commit
   correspondente e teste a instalação em uma conta Windows sem Python.
4. Crie e envie uma tag `v<versão>` apontando para esse mesmo commit.
5. Crie uma GitHub Release baseada nessa tag, use o histórico como base para as
   notas e anexe o `.exe` e o `.sha256`.
6. Inclua nas notas de versão que Codex CLI e Claude Code são opcionais e devem
   ser instalados/autenticados separadamente.

O instalador Windows permanece manual. O pacote Ubuntu é automatizado pelo
workflow **Build Ubuntu**, descrito em [RELEASING_LINUX.md](RELEASING_LINUX.md).
