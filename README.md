# AI Limits Widget

Widget leve para Windows que exibe, na área de trabalho, os limites de uso
restantes do Codex e do Claude Code.

> O projeto é independente e não é afiliado, aprovado ou mantido pela OpenAI
> ou Anthropic.

## O que ele faz

- Mostra percentuais restantes de janelas de uso, em vez de inventar uma
  conversão para “tokens restantes”.
- Atualiza Codex e Claude Code em intervalos configurados (o padrão é 5 minutos).
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

Instale apenas as integrações que você pretende usar. Se uma CLI não estiver
instalada ou autenticada, o widget continuará funcionando e mostrará o motivo
na respectiva seção.

## Instalação pelo código-fonte

1. Clone o repositório:

   ```powershell
   git clone https://github.com/Marcioemm/AI-Limits-Widget.git
   cd ai-limits-widget
   ```

2. Execute a configuração guiada:

   ```powershell
   .\scripts\setup.ps1
   ```

   Ela pergunta quais provedores serão usados, detecta os CLIs instalados,
   permite informar um caminho alternativo, configura o intervalo de atualização
   e pode criar um atalho na Área de Trabalho. Ao final, também permite cadastrar
   perfis extras, como uma conta pessoal e outra de trabalho. Nenhuma credencial
   é pedida ou salva.

3. Inicie o widget:

   ```powershell
   .\scripts\start.ps1
   ```

4. Para encerrar apenas este widget:

   ```powershell
   .\scripts\stop.ps1
   ```

O widget pode ser arrastado pela barra superior, lembra sua posição e possui
botões para atualizar, fixar, recolher e encerrar.

## Atualização

Quem instalou pelo Git atualiza sem perder posição, perfis ou preferências:

```powershell
.\scripts\update.ps1
```

O atualizador interrompe se houver mudanças locais, usa apenas atualização
rápida (`git pull --ff-only`) e nunca altera
`%LOCALAPPDATA%\LimitesIA`. Para atualizar e reabrir o widget:

```powershell
.\scripts\update.ps1 -Restart
```

Quem usar uma futura versão `.exe` deverá atualizar pela página **Releases**;
esse script é destinado a instalações feitas com `git clone`.

### Configuração sem perguntas

Para automatizar a instalação, passe as opções diretamente:

```powershell
.\scripts\setup.ps1 -Providers both -RefreshMinutes 5 -CreateDesktopShortcut -Start
```

Os valores aceitos em `-Providers` são `codex`, `claude` e `both`. Se a
CLI não estiver no PATH, informe seu arquivo executável — por exemplo,
`-ClaudePath 'D:\ferramentas\claude.cmd'`. Os caminhos são opcionais: o
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

As integrações dependem das interfaces oferecidas pelas CLIs e podem exigir
ajustes quando elas mudarem.

## Privacidade e segurança

O aplicativo consulta somente processos e serviços necessários aos provedores
ativados. Não há analytics, banco de dados remoto nem envio de credenciais para
este repositório. Os dados locais ficam em
`%LOCALAPPDATA%\LimitesIA` e contêm apenas preferências, percentuais e
horários de atualização.

Antes de abrir uma issue, leia [SECURITY.md](SECURITY.md). Nunca envie arquivos
de autenticação, tokens, logs completos ou capturas com informações privadas.

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
python .\src\ai_limits_widget\app.py --once
```

Contribuições são bem-vindas; veja [CONTRIBUTING.md](CONTRIBUTING.md).

## Licença

Distribuído sob a [licença MIT](LICENSE).

