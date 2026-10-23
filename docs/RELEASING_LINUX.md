# Gerando o pacote Ubuntu

O pacote Linux é construído nativamente no Ubuntu 24.04. O PyInstaller não faz
cross-build do executável Linux no Windows. O `.deb` gerado contém o runtime do
widget, mas não inclui Codex CLI, Claude Code nem Antigravity CLI.

## Pré-requisitos

```bash
sudo apt install python3 python3-venv python3-tk dpkg-dev
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-build.txt
```

## Build local

```bash
AI_LIMITS_BUILD_PYTHON=.venv/bin/python bash scripts/build-linux.sh
```

Os artefatos ficam em:

- `build/linux/ai-limits-widget_<versão>_<arquitetura>.deb`
- `build/linux/ai-limits-widget_<versão>_<arquitetura>.deb.sha256`

Para gerar uma versão de teste sem alterar `pyproject.toml`:

```bash
AI_LIMITS_BUILD_PYTHON=.venv/bin/python bash scripts/build-linux.sh 0.1.0~beta1
```

Valide o conteúdo e instale em uma máquina de teste:

```bash
dpkg-deb --info build/linux/*.deb
dpkg-deb --contents build/linux/*.deb
sudo apt install ./build/linux/*.deb
ai-limits-widget --help
```

O pacote instala o aplicativo em `/usr/lib/ai-limits-widget`, o launcher em
`/usr/bin/ai-limits-widget` e a entrada do menu em
`/usr/share/applications`. Preferências e caches do usuário não são removidos
ao desinstalar o pacote.

## GitHub Actions e publicação

O workflow **Build Ubuntu** roda manualmente e também para tags `v*`. Em tags,
ele exige que `v<versão>` corresponda à versão de `pyproject.toml`. O workflow
publica o `.deb` e o `.sha256` como artefatos; a publicação na GitHub Release
continua manual.

1. Atualize a versão em `pyproject.toml` e `src/ai_limits_widget/__init__.py`.
2. Confirme os checks **Testes (Windows)** e **Testes (Ubuntu)**.
3. Crie e envie a tag `v<versão>`.
4. Baixe os artefatos do workflow **Build Ubuntu**.
5. Anexe `.deb`, `.deb.sha256`, `.exe` e `.exe.sha256` à mesma release.
