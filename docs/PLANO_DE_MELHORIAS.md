# Plano de melhorias técnicas

Este documento organiza a evolução estrutural do AI Limits Widget sem alterar
o comportamento aprovado da interface. As etapas devem ser executadas na ordem
descrita, com testes passando ao final de cada fase.

## Objetivos

- Reduzir o acoplamento do arquivo `app.py`.
- Proteger o comportamento atual com testes confiáveis.
- Separar interface, provedores, configuração e integração com o Windows.
- Substituir dicionários genéricos por modelos tipados gradualmente.
- Automatizar verificações de qualidade no CI.

## Regras da refatoração

1. Não alterar o design ou o comportamento da Ilha Dinâmica.
2. Fazer uma fase por vez, em mudanças pequenas e revisáveis.
3. Manter todos os testes existentes passando.
4. Adicionar testes antes de mover lógica com risco de regressão.
5. Não adicionar dependências em tempo de execução sem necessidade comprovada.

## Situação inicial

- `src/ai_limits_widget/app.py` concentra interface, configuração, provedores,
  integração com Windows, atualização e animações.
- Os testes gráficos dependem de `AI_LIMITS_RUN_TK_SMOKE=1` e não são ativados
  pelo workflow atual.
- Um teste importa o pacote apenas porque outro teste modifica `sys.path`
  anteriormente; sua execução isolada falha.
- Não existem verificações automáticas de lint, formatação, tipagem ou cobertura.
- Perfis e limites usam principalmente `dict[str, Any]`.

## Fase 1 — Corrigir testes e CI

**Estimativa:** 1 a 2 horas  
**Risco:** baixo  
**Objetivo:** criar uma rede de segurança antes da separação dos módulos.

### Tarefas

- [x] Instalar o projeto no workflow com `python -m pip install -e .`.
- [x] Remover alterações manuais de `sys.path` dos testes.
- [x] Garantir que cada arquivo de teste execute isoladamente.
- [x] Extrair cálculos de direção, geometria e easing para funções puras.
- [x] Executar esses testes puros sempre no CI, sem depender de uma janela Tk.
- [x] Manter um teste gráfico separado e explicitamente identificado como smoke.
- [x] Documentar como executar testes comuns e gráficos localmente.

### Critérios de conclusão

- [x] `python -m unittest discover -s tests -v` passa em ambiente limpo.
- [x] Cada módulo de teste passa quando executado isoladamente.
- [x] Nenhuma regra essencial da Ilha Dinâmica depende apenas de teste ignorado.
- [x] O workflow do GitHub instala o pacote antes de executar os testes.

## Fase 2 — Extrair configuração e modelos

**Estimativa:** 2 a 4 horas  
**Risco:** médio  
**Objetivo:** remover regras de dados e persistência da interface.

### Tarefas

- [x] Criar `models.py` com modelos tipados para perfil, janela e limite.
- [x] Criar `config.py` para leitura, validação e gravação das preferências.
- [x] Centralizar valores padrão e validações da configuração.
- [x] Usar gravação atômica para evitar JSON incompleto.
- [x] Manter compatibilidade com configurações antigas.
- [x] Adicionar testes de migração, valores inválidos e arquivo corrompido.

### Critérios de conclusão

- [x] A interface não lê nem grava `CONFIG_FILE` diretamente.
- [x] Configuração antiga continua sendo carregada corretamente.
- [x] Uma falha durante a gravação não destrói a configuração anterior.
- [x] Os modelos principais não dependem de Tkinter.

## Fase 3 — Separar provedores

**Estimativa:** 3 a 5 horas  
**Risco:** médio  
**Objetivo:** isolar comunicação e normalização de cada CLI.

### Tarefas

- [x] Criar o pacote `providers/`.
- [x] Mover `CodexClient` para `providers/codex.py`.
- [x] Mover `ClaudeClient` para `providers/claude.py`.
- [x] Adaptar a integração Gemini para `providers/gemini.py`.
- [x] Definir uma interface comum para leitura e encerramento dos clientes.
- [x] Normalizar resultados antes que cheguem à interface.
- [x] Adicionar testes para sucesso, erro, cache e respostas incompletas.

### Critérios de conclusão

- [x] A interface não conhece formatos de resposta específicos das CLIs.
- [x] Cada provedor pode ser testado sem criar a janela principal.
- [x] Erros de provedor possuem contexto e mensagem previsível.
- [x] Inclusão de um novo provedor não exige modificar os existentes.

## Fase 4 — Separar interface e Ilha Dinâmica

**Estimativa:** 4 a 7 horas  
**Risco:** médio a alto  
**Objetivo:** reduzir o tamanho e as responsabilidades de `UsageWidget`.

### Tarefas

- [x] Criar o pacote `ui/`.
- [x] Mover os medidores para `ui/meters.py`.
- [x] Mover a janela de configurações para `ui/settings.py`.
- [x] Mover hover, arraste, animação e expansão para `ui/dynamic_island.py`.
- [x] Manter `ui/app.py` responsável apenas pela composição da aplicação.
- [x] Preservar tamanhos, cores, tempos e comportamento já aprovados.
- [x] Adicionar testes para os estados compacta, expandindo e recolhendo.

### Critérios de conclusão

- [x] A Ilha Dinâmica pode ser testada sem iniciar provedores reais.
- [x] `UsageWidget` deixa de controlar diretamente todos os temporizadores.
- [x] Alterações visuais não exigem modificar clientes ou configuração.
- [x] Todos os cenários de expansão, direção e arraste continuam funcionando.

## Fase 5 — Automatizar qualidade

**Estimativa:** 1 a 2 horas  
**Risco:** baixo  
**Objetivo:** impedir que novos problemas estruturais sejam introduzidos.

### Tarefas

- [x] Configurar Ruff para lint e formatação.
- [x] Adicionar verificação gradual de tipos com Pyright ou mypy.
- [x] Medir cobertura e definir uma meta inicial realista.
- [x] Executar as verificações no workflow do GitHub.
- [x] Documentar os comandos em `CONTRIBUTING.md`.
- [x] Fixar versões das ferramentas usadas no CI.

### Critérios de conclusão

- [x] Pull requests verificam compilação, testes, lint e formatação.
- [x] A cobertura não pode cair silenciosamente.
- [x] Erros novos de tipagem são bloqueados nas áreas já migradas.
- [x] Os mesmos comandos funcionam localmente e no CI.

## Estrutura de destino

```text
src/ai_limits_widget/
├── __init__.py
├── __main__.py
├── config.py
├── models.py
├── platform/
│   ├── __init__.py
│   └── windows.py
├── providers/
│   ├── __init__.py
│   ├── base.py
│   ├── codex.py
│   ├── claude.py
│   └── gemini.py
├── services/
│   ├── __init__.py
│   └── refresh.py
└── ui/
    ├── __init__.py
    ├── app.py
    ├── dynamic_island.py
    ├── meters.py
    └── settings.py
```

## Ordem de execução

| Ordem | Fase | Dependência | Estado |
|---:|---|---|---|
| 1 | Testes e CI | Nenhuma | Concluída |
| 2 | Configuração e modelos | Fase 1 | Concluída |
| 3 | Provedores | Fases 1 e 2 | Concluída |
| 4 | Interface e Ilha Dinâmica | Fases 1 a 3 | Concluída |
| 5 | Qualidade automatizada | Fases anteriores | Concluída |

## Validação obrigatória por fase

```powershell
python -m compileall -q src tests
python -m unittest discover -s tests -v
git diff --check
```

Quando uma fase for concluída, seus itens devem ser marcados e a coluna
`Estado` deve mudar de `Pendente` para `Concluída` antes do início da próxima.
