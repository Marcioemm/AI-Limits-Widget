# Integração local v1 — AI Limits Widget 1.1.16

O AI Limits coleta os limites das contas locais e publica um snapshot público
somente de leitura. Vários aplicativos podem ler o mesmo arquivo sem novas
consultas. Os valores são globais por conta, sem associação a repositório ou à
sessão de outro aplicativo. O Compasso é um consumidor possível; esta entrega
implementa somente o produtor (etapa A).

## Ativar e executar

No widget, marque **Disponibilizar limites para outros aplicativos** nas
configurações. A coleta que atualiza os cartões publica também o snapshot.
A preferência é inicialmente desativada.

No Windows, marque também **Funcionar em segundo plano** e salve. O widget
fecha e o mesmo aplicativo passa a executar o modo `--integration`, mantendo
o JSON atualizado. A publicação é ativada automaticamente. O ícone **AI Limits**
aparece na bandeja do sistema (pode ficar entre os ícones ocultos do Windows).
Clique com o botão direito para **Abrir widget** ou **Sair**; um duplo clique
também abre o widget. Abrir o widget desativa a preferência de segundo plano;
sair preserva o modo escolhido para a próxima abertura. A opção de iniciar com
o Windows é independente e respeita o modo salvo.

Para usar sem janela pela linha de comando:

```powershell
ai-limits-widget --integration
# Distribuição Windows (não exige Python instalado):
& 'C:\caminho\AI Limits Widget.exe' --integration
# Encerramento limpo, após a consulta em andamento:
& 'C:\caminho\AI Limits Widget.exe' --stop-integration
# Retornar ao widget, depois de encerrar o produtor anterior:
& 'C:\caminho\AI Limits Widget.exe' --widget
```

No checkout: `python -m ai_limits_widget --integration`, após instalar com
`python -m pip install -e .`. O executável vem do mesmo launcher e build do
instalador: `scripts/build-installer.ps1`. O diretório gerado é
`build/dist/AI Limits Widget/`; mantenha `_internal` junto ao `.exe`.

`--integration` salva `integrationMode: true` e `integrationEnabled: true`;
`--widget` salva `integrationMode: false`. A entrada já existente de login inicia
o mesmo programa, que lê o modo salvo. O comando não habilita login automático
por conta própria. No Windows, o modo sem janela também mostra o ícone na
bandeja. Para alterar perfis/intervalo, abra o widget pelo ícone e salve as
configurações. No Linux, o modo sem janela continua sem bandeja.

Há um lock do sistema por diretório de dados, inclusive no widget sem exportação.
O segundo produtor informa que há uma instância ativa e termina com código 2;
não modifica preferências nem inicia consultas. O arquivo `producer.lock` pode
permanecer no disco: o kernel libera o lock ao encerrar ou matar o processo.
O modo headless aceita SIGINT/SIGTERM; no Windows use `--stop-integration` para
encerrar sem forçar. O pedido usa um arquivo privado `integration.stop`, fora do
contrato público. O consumidor não deve criar nem alterar esse arquivo.

## Localização

- Windows: `%LOCALAPPDATA%\LimitesIA\integration\v1\snapshot.json`.
- Linux: `${XDG_CONFIG_HOME:-~/.config}/ai-limits-widget/integration/v1/snapshot.json`.

O widget remove o snapshot quando a exportação é desabilitada. Ao parar o
produtor, o último arquivo permanece para diagnóstico e expira pelo heartbeat.
Fechar um consumidor não encerra o produtor. Nenhum consumidor é instalado ou
iniciado automaticamente.

## Contrato

Veja o exemplo completo em [normal.json](../tests/fixtures/integration/normal.json).
Os fixtures são artificiais e não contêm consumo ou identidade reais.

| Campo | Semântica |
| --- | --- |
| `schemaVersion` | Inteiro 1. Versão maior incompatível exige atualização do consumidor. |
| `producer` | Nome `ai-limits-widget` e versão do pacote. |
| `instanceId` | UUID aleatório por execução do coletor. |
| `revision` | Inteiro crescente por tentativa de publicação na instância; pode haver saltos por falha de escrita. |
| `publishedAt`, `heartbeatAt` | UTC/RFC 3339, atualizados por publicação. |
| `heartbeatIntervalSeconds` | 15 segundos; não dispara consulta. |
| `profiles` | Todos os perfis habilitados, inclusive indisponíveis; `[]` significa nenhum. |

Cada perfil contém `id`, `provider`, `label`, `status`, `lastAttemptAt`,
`lastSuccessAt`, `nextAttemptAt`, `error` e `windows`. IDs são UUIDs estáveis
persistidos no mapa privado `integration-profile-ids.json`; renomear um rótulo
preserva o ID. Não copie um snapshot para reconstruir configuração ou contas.
Excluir o mapa privado recria IDs. Só rótulos de perfis salvos são exportados;
perfis descobertos automaticamente usam o nome do provedor para evitar exportar
identidade inferida de e-mail ou diretório.

Estados: `loading` antes da primeira tentativa, `ok` com observação válida,
`stale` com observação anterior/expirada, `unavailable` sem CLI ou sem janelas,
`auth_required` quando é necessário login e `error` para falha sem dado anterior.
Falha posterior com histórico preserva janelas e usa `stale`; `error.code`
identifica a causa. `lastAttemptAt` inclui verificação local de disponibilidade.

Erros têm somente `{ "code": "...", "message": "mensagem fixa" }`:

| Código | Mensagem |
| --- | --- |
| `unavailable` | CLI ou sessão local indisponível |
| `auth_required` | Autentique novamente o provedor |
| `rate_limited` | Nova tentativa agendada |
| `collection_failed` | Não foi possível atualizar os limites |
| `stale_data` | Observação desatualizada |

Janelas conhecidas usam IDs `five_hour` e `weekly`. `windows` contém apenas
janelas fornecidas. `label` é descritivo; use `durationMinutes` para apresentar
`2h`, `5h`, `7d` etc. Duração desconhecida é `null`, nunca inferida pelo ID.
`remainingPercent` é número de 0 a 100, sem arredondamento, ou `null`.
`0` é cota esgotada e não ausência. `usedPercent` é convertido uma única vez.
Números não finitos, booleanos e valores fora do intervalo tornam-se `null`.

`observedAt` preserva `fetchedAt` da janela/provedor. Somente o Codex, que
retorna uma leitura ao vivo sem timestamp, recebe o horário da consulta.
`validUntil` é no máximo a observação mais dois intervalos normais de coleta,
limitada também por `resetsAt`. Heartbeat não estende essa validade.
`lastSuccessAt` só avança com observação válida mais recente. Cache de fallback
do Gemini e cache stale do Claude permanecem antigos, inclusive ao iniciar.
Ao vencer a renovação, o percentual vira `null`: não se assume 100%.
Todas as datas desconhecidas são `null`; datas conhecidas incluem timezone UTC.

## Coleta, leitura e privacidade

O coletor é compartilhado por widget e headless, reutiliza clientes e fecha seus
recursos ao encerrar. O intervalo normal vem de `refreshMinutes` (5 a 120),
respeita o mínimo do provedor e `nextRetryAt`. Falhas sem backoff próprio usam
esperas de 1, 2, 4 e 8 intervalos, limitadas nesse último fator; recuperação
reinicia a contagem. Atualização manual também respeita esse agendamento.
Uma falha não cancela os demais perfis. O heartbeat tem thread própria e segue
publicando durante uma consulta lenta, sem consultar os provedores.

A integração não executa prompts e não instala statusline nem modifica
autenticação. No coletor compartilhado, o Claude usa a API de limites sem o
fallback de CLI `/usage` para renovar token; sessão expirada pede login manual.
O comando legado `--once` conserva seu formato e comportamento anteriores e
não é o contrato de integração.

O produtor grava UTF-8 em temporário no mesmo diretório, faz flush/fsync e
substituição atômica. Em erro de escrita/compartilhamento, tenta novamente após
50, 150 e 300 ms; mantém o arquivo anterior se falhar. O consumidor pode ler a
cada 5 segundos, limitar o arquivo a 1 MiB, validar tipos, schema e limites
numéricos, tolerar novos campos/IDs/provedores e considerar offline após 60
segundos sem heartbeat. Em leitura inválida ou bloqueio transitório, deve manter
o último dado em memória com aviso de desatualização. Nunca deve executar
conteúdo do JSON. Também precisa verificar `validUntil`/`resetsAt` mesmo com
heartbeat atual. Percentuais antigos exigem indicação visual de dado antigo.

O snapshot exclui credenciais, e-mail inferido, caminhos, argumentos, prompts e
payloads brutos. Erros públicos são mensagens fixas. Rótulos salvos são dados
locais escolhidos pelo usuário e ficam visíveis aos consumidores locais.

## Validação

`tests/test_integration.py` cobre conversão, timestamps, IDs, cache, recuperação,
falha parcial, backoff, heartbeat sem consultas, leituras concorrentes, retentativa
de escrita, liberação de lock após morte e headless sem importar Tk/UI.
Fixtures: `normal`, `multiple_profiles`, `auth_required`, `stale_cache`,
`partial_error`, `no_profiles` e `missing_window` em `tests/fixtures/integration`.
Os testes gráficos existentes validam cartões, ilha e configurações. O script
`scripts/test-integration-package.py` testa o executável gerado, com dados
isolados e sem autenticação ou consultas reais.

### Evidência local em 02/11/2026

- Base: `main` em `d07ee81`, worktree separado, versão implementada `0.1.16`.
- 80 testes aprovados, incluindo os gráficos Windows; cobertura total 68%.
- Ruff, formatação, mypy (incluindo coletor/publicador) e compilação aprovados.
- Executável PyInstaller Windows validado: snapshot v1, heartbeat real de 15 s
  e encerramento pelo comando `--stop-integration`.
- Consulta real em diretório isolado: Codex `ok`, com duas janelas; Claude
  `unavailable`, sem impedir a publicação. Nenhum prompt foi executado.
- Snapshot real de validação no checkout:
  `build/validation-runtime/LimitesIA/integration/v1/snapshot.json`.
  O processo de validação foi encerrado; esse arquivo serve como evidência antiga.
- O instalador Inno Setup não foi gerado/instalado neste ambiente, que não
  dispõe do compilador Inno Setup. O executável empacotado foi gerado e testado;
  o script do instalador agora exige também o smoke headless antes de compilar.
- Linux não foi executado localmente; o workflow existente permanece responsável
  por validar essa plataforma. Etapa B do Compasso ainda não implementada.
