# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Automated daily pipeline that detects red flags in Peruvian public procurement (SEACE/OECE data), generates a 20-second vertical video with Spanish TTS voiceover, and publishes to TikTok, Instagram Reels, and YouTube Shorts.

## Commands

### Python (insights generation)
```bash
pip install -r requirements.txt
python insights_app/main.py --output insights/insight_$(date +%Y_%m_%d).json
```

### Node (video rendering)
```bash
npm install          # first time (generates package-lock.json)
npm ci               # CI / subsequent installs
npx hyperframes lint # validate index.html composition
npx hyperframes render . # render index.html + assets/voiceover.mp3 → output/
```

### Audio generation
```bash
bash scripts/generate_audio.sh \
  "$(jq -r '.script.voiceover_text_full' insights/insight_YYYY_MM_DD.json)" \
  "$MINIMAX_API_KEY" "$MINIMAX_GROUP_ID"
# outputs assets/voiceover.mp3
```

### Publishing
```bash
bash scripts/publish_ig.sh output/radiografia-YYYY_MM_DD.mp4 insights/insight_YYYY_MM_DD.json
```

### Validation
```bash
bash scripts/validate_video.sh   # checks placeholders, audio duration, MP4 size
```

### Local end-to-end test (no real scraping)
```bash
cp insights/insight_example_mtc.json insights/insight_$(date +%Y_%m_%d).json
bash scripts/generate_audio.sh ...
# then invoke Claude skill:
# /radiografia procesa el insight de hoy con duracion de audio 20 segundos
npx hyperframes render .
```

## Architecture

### Pipeline stages (in order)

1. **Scraping** (`insights_app/scrapers/`) — SeaceCollector, OeceCollector, ContraloriaChecker collect and normalize procurement records to a common dict schema.

2. **Detection** (`insights_app/detector.py`) — Four red flag patterns ranked by severity:
   - `funcionario_sancionado_activo` (10) — sanctioned official active
   - `postor_unico_con_proceso_acelerado` (9) — single bidder + <50% sector avg process time
   - `fraccionamiento_contractual` (8) — same supplier 2+ contracts in 30 days >S/400k
   - `proveedor_recurrente` (7) — same supplier >5 wins with same entity in 12 months

3. **Selection** (`insights_app/selector.py`) — Ranks cases by `max_severity + amount_bonus + confidence - 1`, minimum score 7, deduplicates entities seen in last 7 days.

4. **Insight JSON** (`insights_app/script_generator.py`) — Builds the canonical `insights/insight_YYYY_MM_DD.json` with case data, voiceover script, segment timings, and output specs.

5. **Audio** (`scripts/generate_audio.sh`) — MiniMax TTS → hex MP3 → `assets/voiceover.mp3`. Target 15–25s; rejects outside that window.

6. **HTML** (Claude Code skill `/radiografia`) — Reads insight JSON, maps `patron_detectado` → one of four templates in `.claude/skills/radiografia/templates/`, fills Jinja2 placeholders, lints, auto-fixes up to 2×.

7. **Render** (`npx hyperframes render .`) — HyperFrames + Chromium renders HTML+GSAP animations synced to voiceover → `output/radiografia-YYYY_MM_DD.mp4` (1080×1920, 30fps, 18–22s).

8. **Publish** (`scripts/publish_buffer.sh`) — Buffer API schedules at 19:00 Lima time to TikTok/Instagram/YouTube.

### Insight JSON shape (critical fields)

```json
{
  "case": {
    "caso_titulo": "",
    "patron_detectado": "<enum — selects template>",
    "confidence": "<float, abort if < 0.8>"
  },
  "source": { "entidad_nombre": "", "codigo_seace": "" },
  "script": { "voiceover_text_full": "<15-25s when read aloud>" }
}
```

### Template mapping

| `patron_detectado` | Template |
|---|---|
| `postor_unico_con_proceso_acelerado` | `templates/postor_unico.html` |
| `proveedor_recurrente` | `templates/proveedor_recurrente.html` |
| `fraccionamiento_contractual` | `templates/fraccionamiento.html` |
| `funcionario_sancionado_activo` | `templates/funcionario_sancionado.html` |

## Claude Skill

Invoke with: `/radiografia procesa el insight de hoy con duracion de audio 20 segundos`

Skill definition: `.claude/skills/radiografia/SKILL.md`

Mandatory rules enforced by skill:
- Currency format: `S/ X,XXX,XXX`
- Censor RUCs (`20••••••XXX`) and DNIs (`***XXX`)
- Only name officials with "sentencia firme"
- Always include disclaimer: `Datos públicos · Fuente: [fuente]`
- Voiceover must end with `no es sentencia, son datos públicos`
- No unfilled `{{ ... }}` placeholders allowed before lint

## Environment Variables

See `.env.example`. Required:
- `MINIMAX_API_KEY`, `MINIMAX_GROUP_ID`
- `IG_ACCESS_TOKEN`, `IG_USER_ID` (Instagram Graph API — long-lived token, expira 60 días)
- `DISCORD_WEBHOOK`
- `TZ=America/Lima`
- `ANTHROPIC_API_KEY` (or `OPENROUTER_API_KEY` + `ANTHROPIC_BASE_URL`)

GitHub Actions schedule: daily `08:00 UTC`. Manual trigger supports `modo_test=true` to skip publishing.

## Common Failures

| Symptom | Cause | Fix |
|---|---|---|
| `npx hyperframes lint failed` | Unfilled `{{ ... }}` in HTML | Check skill placeholder replacement |
| `voiceover duration must be 15-25s` | Script too short/long | Adjust `voiceover_text_full` in `script_generator.py` |
| `MiniMax status_code != 0` | Bad API key or quota | Verify `MINIMAX_API_KEY` and account limits |
| `IG_ACCESS_TOKEN required` | Secret not set in GitHub | Add `IG_ACCESS_TOKEN` and `IG_USER_ID` secrets |
| `Container reached ERROR` | Video specs wrong | Verify H264, 9:16, moov atom at front |
| Token expiry after 60 days | Long-lived token expired | Run `ig_refresh_token` grant before expiry |
| `no hay casos suficientes hoy` | No cases above threshold | Expected — pipeline exits 1 gracefully, no action needed |
| `npm ci` fails locally | No `package-lock.json` | Run `npm install` first |
