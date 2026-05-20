# Agente Perry — Radiografia del Gasto Publico

> **Pipeline 100% automatizado** que convierte datos crudos de contrataciones publicas peruanas en un Reel de Instagram de 20 segundos — sin intervencion humana, todos los dias.

**Siguenos en Instagram:** [@agenteperrylatam](https://www.instagram.com/agenteperrylatam/)

---

## El problema que resuelve

Peru publica millones de registros de contrataciones publicas en SEACE, OECE y Contraloria. Los periodistas y ciudadanos no tienen tiempo ni herramientas para detectar patrones anomalos en esos datos. Agente Perry los detecta, los narra y los difunde automaticamente cada manana.

---

## Como funciona: pipeline completo

```
03:00 Lima (08:00 UTC)
GitHub Actions dispara el workflow diario
        │
        ▼
┌─────────────────────────────────────────────────────┐
│  ETAPA 1: SCRAPING                                  │
│  SeaceCollector + OeceCollector + ContraloriaChecker│
│  Normalizan registros a schema comun               │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│  ETAPA 2: DETECCION (detector.py)                   │
│  Corre 4 detectores de red flags sobre cada         │
│  licitacion del dia. Cada flag tiene severity 7-10. │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│  ETAPA 3: SELECCION (selector.py)                   │
│  Score = max_severity + amount_bonus + confidence-1 │
│  Minimo score 7. Excluye entidades vistas en 7 dias.│
│  Si no hay caso: pipeline termina limpiamente.      │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│  ETAPA 4: INSIGHT JSON (script_generator.py)        │
│  Genera insight_YYYY_MM_DD.json con:                │
│  guion narrado, segmentos de tiempo, specs de video │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│  ETAPA 5: AUDIO (ElevenLabs TTS)                    │
│  voiceover_text_full → assets/voiceover.mp3         │
│  Objetivo: 15-25 segundos. Rechaza fuera del rango. │
│  Genera voiceover_timestamps.json con timings       │
│  palabra-por-palabra para karaoke sincronizado.     │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│  ETAPA 6: HTML (Claude Code skill /radiografia)     │
│  Lee insight JSON → elige plantilla segun patron    │
│  → llena placeholders Jinja2 → valida (sin {{ }})  │
│  Auto-corrige hasta 2 veces si falla lint.          │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│  ETAPA 7: RENDER (HyperFrames + Chromium)           │
│  index.html + voiceover.mp3 → MP4 1080x1920 30fps  │
│  Animaciones GSAP sincronizadas con timestamps.     │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│  ETAPA 8: VALIDACION (validate_video.sh)            │
│  11 checks: duracion 19.5-20.5s, H264, 9:16,       │
│  moov atom al frente, stream de audio presente,    │
│  sin placeholders, specs de exportacion.            │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│  ETAPA 9: PUBLICACION (Instagram Graph API)         │
│  Resumable upload → container → publish como Reel  │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│  ETAPA 10: NOTIFICACION (Discord Webhook)           │
│  Exito / fallo / sin casos — con link al run y     │
│  artifacts descargables por 30 dias.               │
└─────────────────────────────────────────────────────┘
```

---

## Red flags detectadas

| Patron | Severity | Logica de deteccion |
|--------|----------|---------------------|
| `funcionario_sancionado_activo` | **10** | Funcionario con inhabilitacion vigente (VIGENTE/ACTIVA o `fecha_fin >= hoy`) activo en contratacion |
| `postor_unico_con_proceso_acelerado` | **9** | Un solo postor + proceso en < 50% del promedio del sector (MTC=45d, MINSA=38d, etc.) |
| `fraccionamiento_contractual` | **8** | Mismo proveedor + misma entidad: 2+ contratos en 30 dias que suman > S/400,000 |
| `proveedor_recurrente` | **7** | Mismo proveedor gana > 5 contratos con misma entidad en los ultimos 12 meses |

### Formula de scoring

```
score = max_severity + min(monto / 10,000,000, 1.5) + confidence - 1
```

- `score < 7` → caso descartado
- Entidad vista en ultimos 7 dias → saltada (evita repeticion)
- `confidence < 0.8` → pipeline aborta

---

## El video: reglas de produccion

Cada Reel sigue 11 reglas forzadas por `validate_video.sh`:

| Regla | Especificacion |
|-------|----------------|
| Duracion | 19.5 – 20.5 segundos exactos |
| Formato | 1080 × 1920 px, 9:16, H264, 30fps |
| Karaoke | Palabra por palabra sincronizado con timestamps de ElevenLabs |
| Hook brutalista | Dato duro sobre fondo negro puro en los primeros 1.5s |
| Animaciones | 3 capas simultaneas: ambiente (binary-rain/scanlines), elementos vivos (breathe/glow), entradas sincronizadas con voiceover |
| Perry | Aparece solo en 3 momentos: intro, reaccion, CTA |
| Privacidad | RUCs censurados (`20••••••XXX`), DNIs censurados (`***XXX`) |
| Disclaimer | `Datos publicos · Fuente: [fuente]` siempre presente |
| Cierre | Guion termina con `no es sentencia, son datos publicos` |
| Frame final | Limpio, listo para screenshot |
| Placeholders | Cero `{{ ... }}` sin resolver — lint falla si queda alguno |

---

## Plantillas por patron

| `patron_detectado` | Template HTML |
|---|---|
| `postor_unico_con_proceso_acelerado` | `templates/postor_unico.html` |
| `proveedor_recurrente` | `templates/proveedor_recurrente.html` |
| `fraccionamiento_contractual` | `templates/fraccionamiento.html` |
| `funcionario_sancionado_activo` | `templates/funcionario_sancionado.html` |

Cada plantilla tiene: hook-screen, fact-cards, contexto, comparacion, punch-line, CTA.

---

## Estructura del proyecto

```
agente-p-radiografia/
├── .github/workflows/daily-video.yml     # GitHub Actions — 08:00 UTC diario
├── .claude/skills/radiografia/
│   ├── SKILL.md                          # Instrucciones para Claude Code skill
│   └── templates/                        # 4 plantillas HTML (una por patron)
├── insights_app/
│   ├── scrapers/
│   │   ├── seace.py                      # Colector SEACE (licitaciones)
│   │   ├── oece.py                       # Colector OECE (proveedores)
│   │   ├── contraloria.py                # Verificador de sanciones
│   │   └── sunat.py                      # Verificador RUC activo
│   ├── detector.py                       # 4 detectores de red flags
│   ├── selector.py                       # Ranking + deduplicacion de entidades
│   ├── script_generator.py               # Genera insight JSON con guion narrado
│   └── main.py                           # Orquestador del pipeline de datos
├── scripts/
│   ├── generate_audio.sh                 # ElevenLabs TTS → assets/voiceover.mp3
│   ├── publish_ig.sh                     # Resumable upload → Meta Graph API
│   └── validate_video.sh                 # Gate de calidad: 11 checks
├── assets/
│   ├── animations.css                    # Biblioteca compartida de animaciones
│   └── voiceover_timestamps.json         # Timestamps por palabra (ElevenLabs)
├── insights/
│   ├── insight_YYYY_MM_DD.json           # Insight del dia (auto-generado)
│   └── insight_example_mtc.json          # Fixture de prueba
└── output/
    └── radiografia-YYYY_MM_DD.mp4        # Video final
```

---

## Prueba local

```bash
cd agente-p-radiografia
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
npm install
cp .env.example .env
# editar .env con tus API keys
```

### Test rapido sin scraping real (fixture MTC)

```bash
cp insights/insight_example_mtc.json insights/insight_$(date +%Y_%m_%d).json
bash scripts/generate_audio.sh insights/insight_$(date +%Y_%m_%d).json
claude -p "/radiografia procesa el insight de hoy con duracion de audio 20 segundos" \
  --allowedTools "Bash,Read,Write,Edit,Glob" --output-format json
bash scripts/validate_video.sh
npx hyperframes render . --output output/radiografia-local.mp4 --workers auto
bash scripts/validate_video.sh output/radiografia-local.mp4
```

### Con scraping real

```bash
python insights_app/main.py --output insights/insight_$(date +%Y_%m_%d).json
```

---

## GitHub Secrets requeridos

| Secret | Descripcion |
|--------|-------------|
| `OPENROUTER_API_KEY` | Gateway para Claude Code (claude-sonnet-4.6 via OpenRouter) |
| `ELEVENLABS_API_KEY` | TTS en espanol — genera voiceover + timestamps de palabras |
| `ELEVENLABS_VOICE_ID` | ID de voz (opcional; default: `pNInz6obpgDQGcFmaJgB`) |
| `IG_ACCESS_TOKEN` | Token de larga duracion de Instagram Graph API (renueva ~55 dias) |
| `IG_USER_ID` | ID numerico de la cuenta Instagram Business |
| `DISCORD_WEBHOOK` | Notificaciones de exito / fallo / sin casos |

---

## Controles manuales (workflow_dispatch)

| Input | Efecto |
|-------|--------|
| `modo_test=true` | Genera insight + audio + HTML + MP4, pero **no publica** en Instagram |
| `usar_ejemplo=true` | Usa `insight_example_mtc.json` en lugar de scraping real |
| `skip_audio=true` | Genera 20s de silencio en lugar de llamar a ElevenLabs |

---

## Agregar un nuevo patron de red flag

1. Agrega detector en `insights_app/detector.py` retornando `tipo`, `severity`, `evidencia`, `patron_id`.
2. Actualiza `script_generator.py` si el patron requiere textos o metadata distintos.
3. Crea plantilla HTML en `.claude/skills/radiografia/templates/`.
4. Agrega el mapeo `patron_detectado → template` en `.claude/skills/radiografia/SKILL.md`.
5. Prueba con un fixture local antes de activar publicacion.

---

## Troubleshooting

| Sintoma | Causa | Fix |
|---------|-------|-----|
| `npx hyperframes lint failed` | Placeholders `{{ ... }}` sin resolver en HTML | Verificar que el skill llenó todos los campos |
| `voiceover duration must be 15-25s` | Guion muy largo o corto | Ajustar `voiceover_text_full` en `script_generator.py` |
| `ElevenLabs returned HTTP 401` | API key invalida | Verificar `ELEVENLABS_API_KEY` |
| `ElevenLabs returned HTTP 422` | Voice ID no existe | Verificar `ELEVENLABS_VOICE_ID` en la cuenta |
| `Container reached ERROR` | Specs de video incorrectas | Verificar H264, 9:16, moov atom al frente, stream de audio |
| `IG_ACCESS_TOKEN required` | Secret no configurado | Agregar `IG_ACCESS_TOKEN` e `IG_USER_ID` a GitHub Secrets |
| Token expirado | Token de 60 dias vencido | Renovar con grant `ig_refresh_token` antes del vencimiento |
| `no hay casos suficientes hoy` | Sin red flags con score >= 7 | Comportamiento esperado — pipeline termina con exit 1 limpio |
| `npm ci` falla localmente | Sin `package-lock.json` | Correr `npm install` primero |
| `confidence < 0.8` | Caso descartado por baja confianza | Revisar calidad del scraping o ajustar umbral en `main.py` |

---

## Stack tecnologico

| Capa | Tecnologia |
|------|-----------|
| Orquestacion | GitHub Actions (cron diario) |
| Scraping | Python 3.12 + requests/BeautifulSoup |
| Deteccion | Python (logica stateless, sin ML) |
| Generacion de guion | Python + templates de texto |
| TTS | ElevenLabs Multilingual v2 |
| Generacion de HTML | Claude Code (claude-sonnet-4.6) via OpenRouter |
| Render de video | HyperFrames + Chromium headless + GSAP |
| Publicacion | Instagram Graph API (resumable upload) |
| Notificaciones | Discord Webhook |
