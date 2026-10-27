# AI Limits Widget

[🇺🇸 English](.github/readme/README.en.md) · [🇪🇸 Español](.github/readme/README.es.md) · 🇧🇷 Português

Um widget leve para Windows e Ubuntu que deixa, na área de trabalho, uma visão simples
dos limites de uso restantes do Codex, Claude Code e Gemini pelo AGY.

> Este é um projeto independente. Ele não é afiliado, aprovado nem mantido por
> OpenAI, Anthropic ou Google.

## O que ele faz

- Mostra o percentual restante de cada janela de uso, sem inventar uma
  equivalência para “tokens restantes”.
- Atualiza Codex, Claude Code e o cache do Gemini no intervalo que você escolher
  (cinco minutos por padrão).
- Roda localmente e pode ficar sempre visível, se isso ajudar no seu fluxo.
- Mantém o último dado válido do Claude durante um bloqueio temporário.
- Explica de forma clara quando uma sessão expirou, uma ferramenta está ausente
  ou um serviço não está disponível.

## O que ele não faz

- Não cria, aumenta nem contorna limites de contas.
- Não envia seus dados para servidores deste projeto.
- Não guarda senhas, chaves de API ou tokens de autenticação.
- Não exige nenhuma assinatura além das contas que você já usa.

## Requisitos

- Windows 10 ou 11, ou Ubuntu 24.04 LTS.
- Para executar pelo código-fonte: Python 3.10 ou superior com Tkinter.
- Opcional: Codex CLI autenticado, para exibir Codex.
- Opcional: Claude Code autenticado, para exibir Claude Code.
- Opcional: Antigravity CLI (`agy`) autenticado, para exibir o modelo Gemini ativo.

Instale apenas o que você pretende usar. Se alguma CLI não estiver instalada ou
autenticada, o widget continua abrindo e mostra o motivo na seção correspondente.

## Instalação no Windows

Baixe `AI-Limits-Widget-Setup-<versão>.exe` na página de
[Releases](https://github.com/Marcioemm/AI-Limits-Widget/releases) e execute-o.
Você pode criar um atalho na Área de Trabalho durante a instalação. O instalador
já inclui o necessário para rodar o widget — não é preciso instalar Python.

Codex CLI, Claude Code e Antigravity CLI (`agy`) continuam opcionais. Para que
os limites apareçam, instale e autentique cada um na mesma conta do Windows.
O instalador não copia nem pede suas credenciais.

O aplicativo desktop do Codex sozinho não oferece a integração local usada pelo
widget. Instale também o [Codex CLI](https://learn.chatgpt.com/docs/codex/cli)
para acompanhar seus limites. Para Claude, siga a instalação oficial do
[Claude Code](https://docs.anthropic.com/en/docs/claude-code/getting-started).
Para Gemini, instale o [Antigravity CLI](https://antigravity.google/docs/cli/)
e marque **Gemini (AGY)** nas configurações. O widget ativa uma statusline local
para ler a cota oficial do modelo Gemini ativo. Se nenhuma CLI estiver
disponível, ele mostra os links de instalação e o botão **Verificar novamente**;
não é necessário reiniciar o aplicativo.

## Instalação no Ubuntu

Baixe `ai-limits-widget_<versão>_amd64.deb` e o respectivo `.sha256` na página
de [Releases](https://github.com/Marcioemm/AI-Limits-Widget/releases). Depois:

```bash
sha256sum --check ai-limits-widget_<versão>_amd64.deb.sha256
sudo apt install ./ai-limits-widget_<versão>_amd64.deb
```

Abra **AI Limits Widget** pelo menu ou execute `ai-limits-widget`. O pacote já
inclui o runtime do widget; as CLIs dos provedores continuam opcionais e são
detectadas no `PATH` da mesma conta Linux.

## Instalação pelo código-fonte

1. Clone o repositório no Windows ou Ubuntu:

   ```powershell
   git clone https://github.com/Marcioemm/AI-Limits-Widget.git
   cd ai-limits-widget
   ```

2. No Windows, inicie o widget:

   ```powershell
   .\scripts\start.ps1
   ```

3. No Ubuntu, instale as dependências e configure a entrada do menu:

   ```bash
   sudo apt install python3 python3-venv python3-tk
   bash scripts/setup.sh
   ```

4. Abra **⚙ Configurações** para escolher os provedores, ajustar o intervalo,
   indicar um executável fora do `PATH`, cadastrar perfis extras e decidir se o
   widget deve abrir junto com o sistema. Nenhuma credencial é pedida ou salva.

5. No Windows, para encerrar apenas este widget:

   ```powershell
   .\scripts\stop.ps1
   ```

Arraste o widget pela barra superior. Nela você também encontra botões para
atualizar ou verificar novamente, abrir as configurações, copiar um diagnóstico
seguro, fixar, recolher e encerrar. Passe o cursor sobre qualquer ícone para ver
o que ele faz.

Use o botão de layout (`⊟`/`⊞`) ao lado do título **LIMITES DE IA** para
alternar entre **Cartões** e **Compacto**. A escolha é salva somente neste
computador. No modo compacto, o widget vira uma pequena pílula e mostra somente
uma bateria horizontal com o indicador principal escolhido em **Configurações**.
Ela possui cinco segmentos e representa a janela
de 5 horas e, quando essa janela não é fornecida pela CLI, representa a janela
semanal.
Também é possível escolher entre uma e três baterias visíveis na pílula
reduzida. A principal aparece primeiro e as demais são posicionadas ao lado.
Mantenha o cursor sobre a pílula para revelar as outras baterias. Ao passar
sobre a pílula, ela abre colunas suficientes para os perfis disponíveis e cada
bateria mostra logo abaixo dela o perfil, a janela
acompanhada e a renovação, em linhas alinhadas, sem fazer uma nova consulta.
A ilha expande e recolhe suavemente, mantendo o tamanho das baterias durante
toda a transição. Perto do rodapé do monitor, ela detecta a
área útil disponível, mantém as baterias no lugar e revela os detalhes acima
delas para evitar cortes.
Arraste pela própria
pílula e use o botão direito para mostrar os cartões, atualizar, configurar,
fixar ou fechar o widget.

O widget sempre inicia no monitor principal. Ele pode ser movido livremente
durante o uso, mas volta ao monitor principal na próxima abertura.

### Configuração por script (opcional)

Para automatizar a instalação, passe as opções diretamente:

```powershell
.\scripts\setup.ps1 -Providers both -RefreshMinutes 5 -CreateDesktopShortcut -Start
```

Os valores aceitos em `-Providers` são `codex`, `claude`, `gemini`, `both` e
`all`. Se a
CLI não estiver no PATH, informe seu arquivo executável — por exemplo,
`-ClaudePath 'D:\ferramentas\claude.cmd'` ou `-AgyPath 'D:\ferramentas\agy.exe'`.
Os caminhos são opcionais: o
widget tenta encontrar as ferramentas novamente a cada abertura.

No Ubuntu, `bash scripts/setup.sh` cria o ambiente virtual e registra o widget
no menu de aplicativos.

### Várias contas

O widget mostra um cartão para cada perfil local que consegue identificar. O
Claude Code é descoberto automaticamente nas pastas `.claude`, `.claude-*` e
no diretório indicado por `CLAUDE_CONFIG_DIR`. Essa busca roda na primeira
abertura e sempre que **Verificar novamente** é acionado, inclusive quando já
existem perfis salvos. Perfis manuais são preservados e a mesma pasta nunca é
adicionada duas vezes. Para contas guardadas em outros locais, informe um nome
de exibição e o diretório de configuração usado por ela:

- Codex: o diretório definido como `CODEX_HOME` para aquele perfil;
- Claude Code: o diretório definido como `CLAUDE_CONFIG_DIR` para aquele
  perfil, contendo o arquivo de credencial local.

Se a CLI ou a configuração de um perfil não existir, ele fica oculto — não há
uma barra vazia para provedores indisponíveis. O aplicativo nunca procura
credenciais em pastas arbitrárias: ele usa os locais padrão descritos acima ou
os diretórios que a própria pessoa indicou.

## Configuração dos provedores

### Codex

Instale e autentique o Codex CLI na mesma conta do sistema. O widget inicia o
processo local do Codex apenas durante a consulta e o encerra em seguida, para
reduzir o consumo de memória em repouso.

### Claude Code

Instale e autentique o Claude Code na mesma conta do sistema. Caso a sessão
expire, o widget pede ao próprio CLI para renová-la localmente. Em respostas
temporárias de limite de requisições, o último saldo válido é mantido e uma nova
tentativa é agendada automaticamente.

### Gemini pelo Antigravity CLI

O widget usa a integração oficial de statusline do AGY. O JSON recebido contém
vários dados de sessão, mas o coletor descarta tudo, exceto o nome do modelo
Gemini ativo, o percentual semanal, a renovação e o horário da coleta. Se o
modelo ativo no AGY for Claude ou GPT, ele é ignorado e não substitui o último
Gemini conhecido. Uma statusline personalizada já existente nunca é
sobrescrita automaticamente. Depois da ativação, abra o AGY ao menos uma vez;
enquanto ele estiver em uso, o cache é atualizado sem consumir uma solicitação
de modelo adicional.

As integrações dependem das interfaces oferecidas pelas CLIs e podem exigir
ajustes quando elas mudarem.

## Privacidade e segurança

O aplicativo consulta apenas os processos e serviços necessários para os
provedores que você ativou. Não há analytics, banco de dados remoto nem envio de
credenciais para este repositório. Os dados ficam no seu computador, em
`%LOCALAPPDATA%\LimitesIA` no Windows. No Linux, configurações ficam em
`~/.config/ai-limits-widget` e caches em `~/.cache/ai-limits-widget`. Esses
arquivos contêm somente preferências, percentuais e horários de atualização.
No caso do AGY, o cache sanitizado não inclui e-mail, conversa, diretório de
trabalho ou token.

Antes de abrir uma issue, leia [SECURITY.md](SECURITY.md). Não envie arquivos de
autenticação, tokens, logs completos ou capturas com informações privadas. O
botão `?` copia um diagnóstico seguro: versões das CLIs, configuração de
atualização e janelas disponíveis. Ele não inclui tokens, IDs de conta ou
caminhos locais.

## Diagnóstico

Para consultar sem abrir a janela:

```text
python src/ai_limits_widget/app.py --once
```

Se o Claude Code disser que a sessão expirou, execute:

```powershell
claude login
```

Se o Codex não for encontrado, confirme que o comando `codex` funciona no
PowerShell e reinicie o widget.

## Desenvolvimento

O projeto não usa dependências de terceiros. Para uma validação básica:

```powershell
python -m pip install --editable .
python -m compileall .\src
python -m unittest discover -s .\tests -v
python .\src\ai_limits_widget\app.py --once
```

Contribuições são bem-vindas. Veja [CONTRIBUTING.md](CONTRIBUTING.md) para o
fluxo por fork e pull request e use `git commit -s` para assinar os commits
conforme o [DCO](DCO.md).

## Licença

Copyright © 2026 Marcio Emmanuel. Distribuído sob a [licença MIT](LICENSE).
Consulte também os [avisos de componentes de terceiros](THIRD_PARTY_NOTICES.md).

