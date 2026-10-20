# Como contribuir

Obrigado pelo interesse em melhorar o AI Limits Widget. Contribuições de
código, documentação, testes, traduções e relatos bem reproduzíveis são bem-vindas.

## Primeiro passo

Antes de começar uma mudança grande, abra uma issue de ideia ou funcionalidade
para alinhar o escopo. Para correções pequenas, um pull request direto é bem-vindo.

Nunca publique tokens, arquivos de credenciais, caches locais ou capturas com
dados pessoais. Para vulnerabilidades, siga [SECURITY.md](SECURITY.md).

## Fluxo recomendado

1. Faça um *fork* do repositório e crie uma branch a partir de `main`.
2. Faça uma alteração pequena e focada.
3. Execute a validação local:

   ```powershell
   python -m pip install --editable .
   python -m compileall .\src
   python -m unittest discover -s .\tests -v
   ```

4. Faça commits claros e assine-os com o DCO:

   ```powershell
   git commit -s -m "fix: descreve a correção"
   ```

5. Abra um pull request para `main`, usando o modelo disponível no GitHub.

Quem tem acesso de escrita também deve trabalhar em branches e abrir pull
requests; `main` é a linha de código revisada e distribuída.

## Developer Certificate of Origin (DCO)

Ao enviar um pull request, cada commit de autoria própria deve conter uma linha
`Signed-off-by`. O comando `git commit -s` adiciona essa linha automaticamente.
Ela certifica que você pode submeter a contribuição sob a licença MIT do
projeto; leia [DCO.md](DCO.md) para o texto completo.

Caso sua contribuição tenha vários autores, cada autor deve assinar o commit
correspondente. Não envie código copiado de fontes incompatíveis com a licença
MIT ou sem permissão clara de reutilização.

## Critérios de revisão

- Mantenha as mudanças pequenas, legíveis e focadas.
- Preserve o funcionamento sem dependências de terceiros em tempo de execução,
  quando possível.
- Inclua ou atualize testes ao mudar regras de cálculo, cache, retentativa ou
  interpretação das respostas das CLIs.
- Atualize README, avisos de licença ou notas de distribuição quando necessário.
- Não inclua executáveis gerados, arquivos de build ou credenciais.

Pull requests podem receber pedidos de ajuste. A aprovação de um pull request
não transfere sua autoria: a contribuição continua atribuída a quem a enviou e
é licenciada sob MIT conforme o DCO.

## Proteção da `main` (mantenedor)

Depois de este arquivo chegar à `main`, configure uma regra de proteção ou
*ruleset* no GitHub para a branch `main` e exija:

- pull request antes do merge;
- uma aprovação do proprietário de código;
- os status **Testes (Windows)** e **Testes (Ubuntu)** concluídos com sucesso;
- conversa resolvida antes do merge.

O arquivo [.github/CODEOWNERS](.github/CODEOWNERS) designa `@Marcioemm` como
responsável pelo código, e o workflow de testes executa compilação e testes em
cada pull request.

## Conduta e escopo

Trate as pessoas com respeito e mantenha as discussões técnicas e construtivas.
O projeto mostra limites disponibilizados pelas ferramentas instaladas pelo
usuário; ele não tenta burlar limites, automatizar contas ou armazenar
credenciais.

