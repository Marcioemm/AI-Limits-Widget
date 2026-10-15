# AI Limits Widget

[🇺🇸 English](.github/readme/README.en.md) · [🇪🇸 Español](.github/readme/README.es.md) · 🇧🇷 Português

Widget leve para Windows que exibe, na área de trabalho, os limites de uso
restantes do Codex, Claude Code e Gemini pelo AGY.

> O projeto é independente e não é afiliado, aprovado ou mantido pela OpenAI
> OpenAI, Anthropic ou Google.

## O que ele faz

- Mostra percentuais restantes de janelas de uso, em vez de inventar uma
  conversão para “tokens restantes”.
- Atualiza Codex, Claude Code e o cache do Gemini em intervalos configurados (o padrão é 5 minutos).
- Funciona localmente e mantém o widget sempre visível, se desejado.
- Preserva o último dado válido do Claude durante um bloqueio temporário.
- Indica sessão expirada, ferramenta ausente e indisponibilidade de forma clara.

## O que ele não faz

- Não cria, aumenta ou contorna limites de contas.
- Não envia dados a um servidor deste projeto.
- Não armazena senhas, chaves de API ou tokens de autenticação.
- Não exige uma assinatura além das contas que cada pessoa já usa.

## Requisitos

- Windows 10 ou 11.
- Python 3.10 ou superior, com Tkinter (incluído no instalador oficial do Python).
- Opcional: Codex CLI autenticado, para exibir Codex.
- Opcional: Claude Code autenticado, para exibir Claude Code.
- Opcional: Antigravity CLI (`agy`) autenticado, para exibir o modelo Gemini ativo.

Instale apenas as integrações que você pretende usar. Se uma CLI não estiver
instalada ou autenticada, o widget continuará funcionando e mostrará o motivo
na respectiva seção.

## Instalação pelo instalador

Baixe `AI-Limits-Widget-Setup-<versão>.exe` na página de
[Releases](https://github.com/Marcioemm/AI-Limits-Widget/releases), execute-o e
opte pelo atalho na Área de Trabalho se desejar. O instalador inclui o runtime
necessário para o widget; Python não é necessário para usá-lo.

O Codex CLI, o Claude Code e o Antigravity CLI (`agy`) continuam opcionais e precisam estar instalados e
autenticados na mesma conta do Windows para que seus limites apareçam. O
instalador não copia nem solicita credenciais.

O aplicativo desktop do Codex, por si só, não fornece a integração local usada
pelo widget: instale também o [Codex CLI](https://learn.chatgpt.com/docs/codex/cli)
para monitorar seus limites. Para Claude, siga a instalação oficial do
[Claude Code](https://docs.anthropic.com/en/docs/claude-code/getting-started).
Para Gemini, instale o [Antigravity CLI](https://antigravity.google/docs/cli/)
e marque **Gemini (AGY)** nas configurações. O widget ativa uma statusline local
que recebe a cota oficial do modelo Gemini ativo.
Se nenhuma CLI estiver disponível, o widget mostra os links de instalação e o
botão **Verificar novamente**; não é necessário reiniciar o aplicativo.

## Instalação pelo código-fonte

1. Clone o repositório:

   ```powershell
   git clone https://github.com/Marcioemm/AI-Limits-Widget.git
   cd ai-limits-widget
   ```

2. Inicie o widget:

   ```powershell
   .\scripts\start.ps1
   ```

   Abra **⚙ Configurações** no widget para escolher os provedores, alterar o
   intervalo, indicar um executável fora do `PATH` e cadastrar perfis extras.
   Nenhuma credencial é pedida ou salva.

3. Para encerrar apenas este widget:

   ```powershell
   .\scripts\stop.ps1
   ```

O widget pode ser arrastado pela barra superior e possui
botões para atualizar/verificar novamente, abrir configurações, copiar um
diagnóstico seguro, fixar, recolher e encerrar. Deixe o cursor sobre qualquer
ícone da barra para ver uma descrição rápida da ação.

Use o botão de layout (`▤`/`▥`) ao lado do título **LIMITES DE IA** para
alternar entre **Cartões** e **Compacto**. A escolha é salva somente neste
computador. No modo compacto, cada perfil aparece como uma bateria segmentada,
com células de carga e o percentual dentro; são exibidas até duas baterias por
linha. Ela representa a janela de 5 horas e, quando essa janela não é fornecida
pela CLI, representa a janela semanal. O modo compacto não mostra rodapé ou
horário de atualização.
Deixe o cursor por um segundo sobre uma bateria para expandir o widget e ver
rapidamente o perfil, a janela acompanhada, a renovação e a última atualização,
sem fazer uma nova consulta.

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

### Várias contas

O widget mostra um cartão para cada perfil local que consegue identificar. O
instalador cria os perfis padrão e, no modo guiado, permite adicionar outros.
Para uma segunda conta, informe um nome de exibição e o diretório de
configuração usado por ela:

- Codex: o diretório definido como `CODEX_HOME` para aquele perfil;
- Claude Code: o diretório definido como `CLAUDE_CONFIG_DIR` para aquele
  perfil, contendo o arquivo de credencial local.

Se a CLI ou a configuração de um perfil não existir, ele fica oculto — não há
uma barra vazia para provedores indisponíveis. O aplicativo nunca procura
credenciais em pastas arbitrárias: ele usa apenas o perfil padrão ou os
diretórios que a própria pessoa indicou no instalador.

## Configuração dos provedores

### Codex

Instale e autentique o Codex CLI na mesma conta do Windows. O widget inicia o
processo local do Codex apenas durante a consulta e o encerra em seguida, para
reduzir o consumo de memória em repouso.

### Claude Code

Instale e autentique o Claude Code na mesma conta do Windows. Caso a sessão
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

O aplicativo consulta somente processos e serviços necessários aos provedores
ativados. Não há analytics, banco de dados remoto nem envio de credenciais para
este repositório. Os dados locais ficam em
`%LOCALAPPDATA%\LimitesIA` e contêm apenas preferências, percentuais e
horários de atualização. No caso do AGY, o cache sanitizado não contém e-mail,
conversa, diretório de trabalho ou token.

Antes de abrir uma issue, leia [SECURITY.md](SECURITY.md). Nunca envie arquivos
de autenticação, tokens, logs completos ou capturas com informações privadas.
O botão `?` do widget copia um diagnóstico que contém somente versões das CLIs,
configuração de atualização e quais janelas foram disponibilizadas; não inclui
tokens, IDs de conta ou caminhos locais.

## Diagnóstico

Para consultar sem abrir a janela:

```powershell
python .\src\ai_limits_widget\app.py --once
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

