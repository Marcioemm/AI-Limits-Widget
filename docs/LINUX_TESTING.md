# Validação do Ubuntu

O alvo inicial é Ubuntu 24.04 LTS. A automação cobre Python, scripts de shell e
renderização Tk sob Xvfb; Wayland e Xorg precisam de uma sessão gráfica real.

## Validação automatizada

```bash
sudo apt install python3 python3-tk python3-venv xvfb
python3 -m venv .venv
.venv/bin/python -m pip install --editable .
.venv/bin/python -m compileall src
.venv/bin/python -m unittest discover -s tests -v
bash -n scripts/start.sh scripts/setup.sh
xvfb-run -a env AI_LIMITS_RUN_TK_SMOKE=1 .venv/bin/python -m unittest discover -s tests -p test_tk_smoke.py -v
```

## Wayland

1. Confirme `echo "$XDG_SESSION_TYPE"`; o resultado esperado é `wayland`.
2. Execute `bash scripts/setup.sh` e abra **AI Limits Widget** pelo menu.
3. Verifique abrir, arrastar, recolher, alternar layout, fixar e fechar.
4. Salve **Abrir automaticamente ao iniciar o sistema**, encerre a sessão e entre novamente.
5. Valide separadamente Codex, Claude e AGY quando cada CLI estiver autenticada.

O compositor pode limitar posição absoluta e a preferência de manter a janela
na frente. Isso não deve impedir abertura, atualização ou fechamento.

## Xorg

Na tela de login, escolha **Ubuntu on Xorg** e repita as cinco verificações.
Registre a versão do Ubuntu, `$XDG_SESSION_TYPE`, provedor e mensagem exibida
quando algum comportamento divergir.
