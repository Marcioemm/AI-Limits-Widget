# Histórico de alterações

Este arquivo registra as mudanças relevantes para quem usa o AI Limits Widget.
As alterações ainda não publicadas ficam em **Não lançado**; ao preparar uma
release, elas devem ser movidas para uma seção com a versão e a data de
publicação. As versões seguem o formato `MAIOR.MENOR.CORREÇÃO`.

## Não lançado

Sem alterações pendentes.

## 1.1.16 — 2026-11-03

### Adicionado

- Opção **Funcionar em segundo plano** nas configurações do Windows, com
  publicação automática do JSON e ícone na bandeja para abrir o widget ou sair.

- Snapshot público JSON v1, coletor compartilhado e modo `--integration` sem
  janela, com heartbeat e produtor único por diretório de dados.

- Consulta da cota semanal do Grok usando uma sessão existente do Grok CLI.
- Consulta ao vivo da cota do Gemini pelo Antigravity CLI, com o cache da
  statusline como alternativa.
- Suporte ao Ubuntu, com scripts de instalação e pacote `.deb`.
- Descoberta automática de contas locais adicionais do Claude Code.
- Opção de iniciar o widget junto com o sistema.

### Alterado

- O coletor do widget respeita backoff também em atualizações manuais e solicita
  login manual do Claude quando a sessão expira, sem executar `/usage` para renová-la.

- A ilha compacta exibe até três baterias e revela os detalhes dos perfis ao
  passar o cursor, ajustando a expansão ao espaço disponível na tela.
- O código foi organizado em módulos de provedores, interface e configuração.
- A documentação e os testes foram ampliados para Windows e Ubuntu.

### Corrigido

- A checagem de tipos distingue chamadas exclusivas do Windows para validar
  corretamente o coletor e os provedores também no Ubuntu.

- A descoberta de contas do Claude preserva perfis manuais e evita duplicar
  diretórios já configurados.
- O processo de geração do instalador Windows verifica a inicialização do
  executável empacotado e inclui a integração do AGY.

## Base atual

Este histórico começou a partir da versão `0.1.15`; não foram reconstruídas
notas de releases anteriores.
