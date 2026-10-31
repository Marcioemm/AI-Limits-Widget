# AI Limits Widget

[🇺🇸 English](README.en.md) · 🇪🇸 Español · [🇧🇷 Português](../../README.md)

Widget ligero para Windows y Ubuntu que muestra en el escritorio los límites de uso
restantes de Codex, Claude Code y Gemini mediante AGY.

> Este proyecto es independiente y no está afiliado, aprobado ni mantenido por
> OpenAI, Anthropic o Google.

## Qué hace

- Muestra los porcentajes restantes de las ventanas de uso, sin inventar una
  conversión a «tokens restantes».
- Actualiza Codex, Claude Code y la caché de Gemini en intervalos configurables (cinco minutos de
  forma predeterminada).
- Funciona localmente y puede permanecer siempre visible.
- Conserva el último valor válido de Claude durante una limitación temporal.
- Indica claramente una sesión vencida, una herramienta ausente o un servicio
  no disponible.

## Qué no hace

- No crea, aumenta ni elude los límites de las cuentas.
- No envía datos a un servidor de este proyecto.
- No almacena contraseñas, claves de API ni tokens de autenticación.
- No exige una suscripción adicional a las cuentas que ya tienes.

## Requisitos

- Windows 10 u 11, o Ubuntu 24.04 LTS.
- Para ejecutar desde el código fuente: Python 3.10 o posterior con Tkinter.
- Opcional: Codex CLI autenticado, para mostrar Codex.
- Opcional: Claude Code autenticado, para mostrar Claude Code.
- Opcional: Antigravity CLI (`agy`) autenticado, para mostrar el modelo Gemini activo.

Instala únicamente las integraciones que quieras usar. Si una CLI no está
instalada o autenticada, el widget seguirá funcionando e indicará el motivo en
la sección del proveedor correspondiente.

## Instalación en Windows

Descarga `AI-Limits-Widget-Setup-<versión>.exe` en la página de
[Releases](https://github.com/Marcioemm/AI-Limits-Widget/releases), ejecútalo y
elige el acceso directo en el escritorio si lo deseas. El instalador incluye el
runtime necesario para el widget; no necesitas Python para utilizarlo.

Codex CLI, Claude Code y Antigravity CLI (`agy`) siguen siendo opcionales y deben estar instalados y
autenticados en la misma cuenta de Windows para que aparezcan sus límites. El
instalador no copia ni solicita credenciales.

La aplicación de escritorio Codex por sí sola no proporciona la integración
local que usa el widget: instala también [Codex CLI](https://learn.chatgpt.com/docs/codex/cli)
para supervisar tus límites. Para Claude, sigue la guía oficial de
[instalación de Claude Code](https://docs.anthropic.com/en/docs/claude-code/getting-started).
Para Gemini, instala [Antigravity CLI](https://antigravity.google/docs/cli/) y
activa **Gemini (AGY)** en Configuración. El widget instala un puente local de
statusline que recibe la cuota oficial del modelo Gemini activo.
Si ninguna CLI está disponible, el widget muestra los enlaces de instalación y
el botón **Comprobar de nuevo**; no es necesario reiniciar la aplicación.

## Instalación en Ubuntu

Descarga `ai-limits-widget_<versión>_amd64.deb` y su archivo `.sha256` desde
[Releases](https://github.com/Marcioemm/AI-Limits-Widget/releases) y ejecuta:

```bash
sha256sum --check ai-limits-widget_<versión>_amd64.deb.sha256
sudo apt install ./ai-limits-widget_<versión>_amd64.deb
```

Abre **AI Limits Widget** desde el menú de aplicaciones o ejecuta
`ai-limits-widget`. El paquete incluye el runtime del widget; las CLI de los
proveedores siguen siendo opcionales y se buscan en el `PATH` de la cuenta Linux.

## Instalación desde el código fuente

1. Clona el repositorio en Windows o Ubuntu:

   ```powershell
   git clone https://github.com/Marcioemm/AI-Limits-Widget.git
   cd ai-limits-widget
   ```

2. En Windows, inicia el widget:

   ```powershell
   .\scripts\start.ps1
   ```

   En Ubuntu, instala las dependencias y crea la entrada del menú:

   ```bash
   sudo apt install python3 python3-venv python3-tk
   bash scripts/setup.sh
   ```

   Abre **⚙ Configuración** en el widget para elegir proveedores, cambiar el
   intervalo de actualización, indicar un ejecutable fuera de `PATH` y añadir
   perfiles adicionales. No se solicitan ni guardan credenciales.

3. En Windows, detén solo este widget:

   ```powershell
   .\scripts\stop.ps1
   ```

Puedes arrastrar el widget desde la barra superior. Sus controles permiten
actualizar o comprobar de nuevo, abrir Configuración, copiar un diagnóstico
seguro, fijar, contraer y cerrar. Coloca el cursor sobre cualquier icono de la
barra para ver una breve descripción de su acción.

Usa el botón de diseño (`⊟`/`⊞`) junto al título **LÍMITES DE IA** para alternar
entre **Tarjetas** y **Compacto**. La elección se guarda solo en este equipo.
En modo compacto, cada perfil se representa mediante una batería segmentada con
celdas de carga y el porcentaje en su interior; se muestran hasta dos baterías
por fila. Representa la ventana de cinco horas y, cuando la CLI no proporciona
esa ventana, la ventana semanal. El modo compacto no muestra pie de página ni
hora de actualización. Deja el cursor sobre una batería durante un segundo
para expandir el widget y ver rápidamente el perfil, la ventana seguida, la
renovación y la última actualización, sin hacer otra consulta.

El widget siempre se abre en el monitor principal. Puedes moverlo libremente
durante el uso, pero volverá al monitor principal la próxima vez que se abra.

### Configuración mediante script (opcional)

Para automatizar la instalación, pasa las opciones directamente:

```powershell
.\scripts\setup.ps1 -Providers both -RefreshMinutes 5 -CreateDesktopShortcut -Start
```

Los valores aceptados en `-Providers` son `codex`, `claude`, `gemini`, `both` y `all`. Si la CLI
no está en `PATH`, indica su ejecutable; por ejemplo,
`-ClaudePath 'D:\herramientas\claude.cmd'` o `-AgyPath 'D:\herramientas\agy.exe'`. Las rutas son opcionales: el widget
intentará encontrar las herramientas de nuevo cada vez que se abra.

En Ubuntu, `bash scripts/setup.sh` crea el entorno virtual y registra el widget
en el menú de aplicaciones.

### Varias cuentas

El widget muestra una tarjeta para cada perfil local que logra identificar. El
instalador crea los perfiles predeterminados y permite añadir otros en modo
guiado. Para una segunda cuenta, proporciona un nombre visible y el directorio
de configuración que utiliza:

- Codex: el directorio definido como `CODEX_HOME` para ese perfil.
- Claude Code: el directorio definido como `CLAUDE_CONFIG_DIR` para ese perfil,
  que contiene el archivo de credenciales local.

Si una CLI o la configuración de un perfil no existe, queda oculta: no hay una
barra vacía para proveedores no disponibles. La aplicación nunca busca
credenciales en carpetas arbitrarias: utiliza solo el perfil predeterminado o
los directorios indicados explícitamente mediante el instalador.

## Configuración de proveedores

### Codex

Instala y autentica Codex CLI en la misma cuenta del sistema. El widget inicia
el proceso local de Codex solo durante la consulta y lo detiene enseguida para
reducir el consumo de memoria en reposo.

### Claude Code

Instala y autentica Claude Code en la misma cuenta del sistema. Si la sesión
vence, el widget pide a la propia CLI que la renueve localmente. Ante respuestas
temporales de límite de solicitudes, se conserva el último saldo válido y se
programa automáticamente un nuevo intento.

### Gemini mediante Antigravity CLI

El widget usa la integración oficial de statusline de AGY. El colector conserva
solamente el nombre del modelo Gemini activo, el porcentaje semanal, la
renovación y la hora de captura. Los modelos Claude o GPT activos en AGY se
ignoran, y una statusline personalizada existente nunca se sobrescribe
automáticamente.

Las integraciones dependen de las interfaces ofrecidas por las CLI y pueden
requerir ajustes cuando estas cambien.

## Privacidad y seguridad

La aplicación consulta únicamente los procesos y servicios necesarios para los
proveedores activados. No hay analítica, base de datos remota ni envío de
credenciales a este repositorio. En Windows, los datos locales se guardan en
`%LOCALAPPDATA%\LimitesIA`. En Linux, la configuración se guarda en
`~/.config/ai-limits-widget` y la caché en `~/.cache/ai-limits-widget`. Estos
archivos contienen solo preferencias, porcentajes y horas de actualización.

Antes de abrir una issue, lee [SECURITY.md](../../SECURITY.md). Nunca envíes
archivos de autenticación, tokens, registros completos ni capturas con
información privada. El botón `?` del widget copia un diagnóstico que contiene
solo versiones de las CLI, configuración de actualización y las ventanas
disponibles; no incluye tokens, identificadores de cuenta ni rutas locales.

## Diagnóstico

Para consultar sin abrir la ventana:

```text
python src/ai_limits_widget/app.py --once
```

Si Claude Code indica que la sesión venció, ejecuta:

```powershell
claude login
```

Si no se encuentra Codex, comprueba que el comando `codex` funcione en
PowerShell y reinicia el widget.

## Desarrollo

El proyecto no usa dependencias de terceros. Para una validación básica:

```powershell
python -m pip install --editable .
python -m compileall .\src
python -m unittest discover -s .\tests -v
python .\src\ai_limits_widget\app.py --once
```

Las contribuciones son bienvenidas. Consulta [CONTRIBUTING.md](../../CONTRIBUTING.md)
para el flujo de fork y pull request, y usa `git commit -s` para firmar los
commits conforme al [DCO](../../DCO.md).

## Licencia

Copyright © 2026 Marcio Emmanuel. Distribuido bajo la [licencia MIT](../../LICENSE).
Consulta también los [avisos de componentes de terceros](../../THIRD_PARTY_NOTICES.md).
