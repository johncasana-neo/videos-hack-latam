# Agente P Radiografia

Automatiza la generacion y publicacion diaria de videos verticales de 20 segundos para la serie **Radiografia del Gasto Publico** del proyecto **Agente P : Operaciones Glitch**.

El pipeline detecta red flags en contrataciones publicas peruanas, genera un insight JSON, produce voiceover con ElevenLabs, construye un HTML con una skill de Claude Code, renderiza MP4 con HyperFrames y publica en Instagram Reels via la Graph API de Meta.

## Pipeline

1. `insights_app/main.py` recolecta datos publicos y genera `insights/insight_YYYY_MM_DD.json`.
2. `scripts/generate_audio.sh` convierte `script.voiceover_text_full` en `assets/voiceover.mp3`.
3. La skill `.claude/skills/radiografia` elige una plantilla y genera `index.html`.
4. `npx hyperframes render` produce `output/radiografia-YYYY_MM_DD.mp4`.
5. `scripts/publish_ig.sh` sube el MP4 directamente a Meta (resumable upload) y publica como Reel.
6. GitHub Actions notifica el resultado en Discord.

## Prueba local

```bash
cd agente-p-radiografia
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
npm install
cp .env.example .env
```

Para probar con el fixture MTC:

```bash
cp insights/insight_example_mtc.json insights/insight_2026_05_17.json
bash scripts/generate_audio.sh insights/insight_2026_05_17.json
claude -p "/radiografia procesa el insight de hoy con duracion de audio 20 segundos" --allowedTools "Bash,Read,Write,Edit,Glob" --output-format json
bash scripts/validate_video.sh
npx hyperframes render . --output output/radiografia-local.mp4 --workers auto
bash scripts/validate_video.sh output/radiografia-local.mp4
```

Para correr la app real:

```bash
python insights_app/main.py --output insights/insight_$(date +%Y_%m_%d).json
```

## GitHub Secrets

Configura estos secrets en el repositorio:

- `ANTHROPIC_API_KEY`: API key directa de Anthropic para Claude Code.
- `OPENROUTER_API_KEY`: alternativa si no tienes key directa de Anthropic.
- `ANTHROPIC_BASE_URL`: usa `https://openrouter.ai/api` para OpenRouter.
- `ANTHROPIC_MODEL`: opcional, modelo aceptado por tu gateway, por ejemplo `anthropic/claude-sonnet-4.6`.
- `ELEVENLABS_API_KEY`: API key de ElevenLabs TTS.
- `ELEVENLABS_VOICE_ID`: opcional, ID de voz ElevenLabs.
- `IG_ACCESS_TOKEN`: token de larga duracion de la Instagram Graph API (expira ~60 dias).
- `IG_USER_ID`: ID numerico de la cuenta Instagram Business.
- `DISCORD_WEBHOOK`: webhook de Discord para notificaciones.

## Agregar una red flag

1. Agrega un detector en `insights_app/detector.py` que devuelva `tipo`, `severity`, `evidencia` y `patron_id`.
2. Actualiza `ScriptGenerator.build()` si el nuevo patron necesita textos o metadata distintos.
3. Crea una plantilla en `.claude/skills/radiografia/templates/`.
4. Agrega el mapeo de `patron_detectado` en `.claude/skills/radiografia/SKILL.md`.
5. Prueba con un insight fixture antes de activar publicacion.

## Cambiar horario

El workflow corre a las `08:00 UTC`, equivalente a `03:00 Lima`, en `.github/workflows/daily-video.yml`:

```yaml
schedule:
  - cron: "0 8 * * *"
```

La publicacion se programa via Instagram Graph API desde `scripts/publish_ig.sh`.

## Desactivar publicacion temporal

Ejecuta el workflow manualmente con `workflow_dispatch` y `modo_test=true`. Esto genera insight, audio, HTML, MP4 y artifacts, pero salta la publicacion en Instagram.

## Usar OpenRouter en vez de Anthropic directo

Si no tienes `ANTHROPIC_API_KEY`, configura estos GitHub Secrets:

```text
OPENROUTER_API_KEY=sk-or-v1-...
ANTHROPIC_BASE_URL=https://openrouter.ai/api
ANTHROPIC_MODEL=anthropic/claude-sonnet-4.5
```

El workflow detecta `OPENROUTER_API_KEY`, lo pasa a Claude Code como `ANTHROPIC_AUTH_TOKEN`, limpia `ANTHROPIC_API_KEY` para evitar conflicto, y mantiene HyperFrames igual. HyperFrames no usa LLM: solo renderiza el `index.html` generado.

## Troubleshooting

- `npx hyperframes lint failed`: revisa que `index.html` no tenga placeholders `{{ ... }}` sin resolver y que exista `assets/voiceover.mp3`.
- `voiceover duration must be 15-25s`: ajusta `script.voiceover_text_full` para acercarlo a 20 segundos.
- `ElevenLabs returned HTTP 401`: verifica `ELEVENLABS_API_KEY`.
- `Container reached ERROR`: verifica que el MP4 sea H264, 9:16, con audio AAC y moov atom al frente.
- `IG_ACCESS_TOKEN required`: agrega `IG_ACCESS_TOKEN` e `IG_USER_ID` a `.env` o GitHub Secrets.
- `Token expiry`: renueva el token cada ~55 dias con el grant `ig_refresh_token`.
- `no hay casos suficientes hoy`: la app no encontro red flags con score minimo o evita repetir entidad de los ultimos 7 dias.
- `npm ci` falla localmente: ejecuta primero `npm install` para generar `package-lock.json`.
