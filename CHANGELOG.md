# Histórico de alterações

Este arquivo registra as mudanças relevantes para quem usa o AI Limits Widget.
As alterações ainda não publicadas ficam em **Não lançado**; ao preparar uma
release, elas devem ser movidas para uma seção com a versão e a data de
publicação. As versões seguem o formato `MAIOR.MENOR.CORREÇÃO`.

## Não lançado

### Adicionado

- Consulta da cota semanal do Grok usando uma sessão existente do Grok CLI.
- Consulta ao vivo da cota do Gemini pelo Antigravity CLI, com o cache da
  statusline como alternativa.
- Suporte ao Ubuntu, com scripts de instalação e pacote `.deb`.
- Descoberta automática de contas locais adicionais do Claude Code.
- Opção de iniciar o widget junto com o sistema.

### Alterado

- A ilha compacta exibe até três baterias e revela os detalhes dos perfis ao
  passar o cursor, ajustando a expansão ao espaço disponível na tela.
- O código foi organizado em módulos de provedores, interface e configuração.
- A documentação e os testes foram ampliados para Windows e Ubuntu.

### Corrigido

- A descoberta de contas do Claude preserva perfis manuais e evita duplicar
  diretórios já configurados.
- O processo de geração do instalador Windows verifica a inicialização do
  executável empacotado e inclui a integração do AGY.

## Base atual

O código declara a versão `0.1.15`. Este histórico começa com o estado atual do
projeto; não foram reconstruídas notas de releases anteriores. As entradas acima
serão associadas a uma versão quando a próxima release for preparada.
