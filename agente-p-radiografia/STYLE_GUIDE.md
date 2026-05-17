# STYLE_GUIDE — Radiografia del Gasto Publico

Reglas de generacion obligatorias para la serie y cualquier serie futura basada en este sistema.
Referenciadas desde `.claude/skills/radiografia/SKILL.md`.
El validador `scripts/validate_video.sh` aplica estas reglas como gate de publicacion.

---

## REGLA 1: DURACION ESTRICTA DE 20 SEGUNDOS

- Rango aceptable: **19.5 s – 20.5 s** (audio y video)
- El guion tiene **maximo 50 palabras** totales
- `generate_audio.py` verifica word count antes de llamar ElevenLabs; aborta si > 50 palabras
- `generate_audio.py` aborta si MP3 resultante > 19.5 s
- `validate_video.sh` aborta publicacion si duracion del MP4 esta fuera de [19.5, 20.5]
- Si el SKILL detecta audio > 19 s: comprimir segmento `context` primero, luego `facts`; nunca comprimir `punch` ni `cta`

## REGLA 2: KARAOKE PALABRA POR PALABRA OBLIGATORIO

- Una sola palabra visible a la vez, sincronizada con timestamps de ElevenLabs
- Posicion fija: `top:1248px` (y ≈ 65%), centrada horizontalmente
- Tipografia: Inter Black 84px, `-webkit-text-stroke:4px #000`, `text-shadow:5px 5px 0 #000`
- Color blanco (`#FFFFFF`) por defecto
- Color amarillo (`#FBBF24`) para palabras que coincidan con: `/[\d,./]+|inhabilitado|postor|u[ní]nico|solo|sancionado|fraccionamiento|millones|mil/i`
- Animacion de entrada: `scale 0.8 → 1.0` en 100ms (`gsap.fromTo`)
- La palabra desaparece 40ms antes del inicio de la siguiente
- `karaoke_words_json` se inyecta en cada plantilla desde `assets/voiceover_timestamps.json` → campo `words`
- **PROHIBIDO**: texto hardcodeado dentro del div karaoke. Si `#karaoke-word` no existe en `index.html`, abortar.

## REGLA 3: HOOK BRUTALISTA EN PRIMERO 1.5 SEGUNDOS

- `#scene-intro`: fondo negro puro (`background:#000`), padding:0, display:flex centrado
- UN solo elemento `#hook-datum` centrado, 180px, Inter Black
- Sin logo, sin titulo de serie, sin subtitulo en este frame
- Dato por patron:
  - `postor_unico`: `{{ monto_adjudicado_formato }}` (blanco)
  - `proveedor_recurrente`: `{{ numero_postores }}` + "CONTRATOS" en 72px
  - `fraccionamiento`: `{{ monto_adjudicado_formato }}` (blanco)
  - `funcionario_sancionado`: "INHABILITADO" en `#EF4444`
- Animacion: `rgbGlitch('#hook-datum', tl, T.intro)` — glitch RGB durante 200ms
- Titulo de la serie y episodio: SOLO en `#scene-cta`. Nunca en intro.

## REGLA 4: SIN FRAMES IDENTICOS CONSECUTIVOS

- Ningun segmento de mas de 1 segundo puede tener frames visualmente identicos
- Todo elemento en pantalla > 1s debe tener animacion Capa 2 activa (breathe, glow, pulse)
- Si el checklist del SKILL detecta bloque de evidencia sin Capa 2, reportar falla
- `validate_video.sh` puede muestrear frames con ffmpeg cada 0.5s y reportar advertencia

## REGLA 5: EFECTOS AMBIENTE SIEMPRE PRESENTES (CAPA 1)

- `<canvas id="binary-rain">` activo durante el 100% de la duracion
- `.scanline`, `.grid-pulse`, 4x `.corner-vignette` presentes todo el tiempo
- `.rec-indicator` visible durante todo el video
- Si alguno falla en cargarse, el render se aborta antes de publicar
- `validate_video.sh` verifica presencia en `index.html`

## REGLA 6: ESPACIO VERTICAL SIEMPRE OCUPADO

- Contenido principal: `y=10%` a `y=60%` (0px–1152px)
- Karaoke: `top:1248px` (≈ y=65%)
- Zona inferior `top:1450px` en adelante: `#status-bar` siempre visible
  - Contenido: `CASO #{{ episode_label }} · CONFIDENCE {{ confidence_pct }}%`
  - Estilo: Inter 32px bold, `color:rgba(255,255,255,0.6)`, `letter-spacing:3px`
- `#scene-cta` es la unica escena donde el espacio inferior puede estar vacio
- `validate_video.sh` verifica que `#status-bar` existe en `index.html`

## REGLA 7: TRES CAPAS DE ANIMACION SIMULTANEAS

- **Capa 1** (ambiente): activa durante 100% del video (binary-rain, scanlines, grid, REC)
- **Capa 2** (elementos vivos): todo elemento en pantalla > 1s tiene animacion sutil (`anim-breathe`, `anim-glow`, `anim-node-pulse`, etc.)
- **Capa 3** (entradas): sincronizadas con el voiceover via timestamps
- Si checklist detecta solo una capa activa en el bloque `scene-compare` (8.5–13s), reportar falla

---

## Tabla de checks para validate_video.sh

| Check                              | Regla | Abortar si...                          |
|-----------------------------------|-------|----------------------------------------|
| Duracion audio                    | R1    | < 19.5 s o > 20.5 s                   |
| Duracion video MP4                | R1    | < 19.5 s o > 20.5 s                   |
| `id="karaoke-word"` en index.html | R2    | ausente                                |
| Sin texto hardcodeado en `#karaoke` | R2  | texto estatico dentro del contenedor  |
| `id="hook-datum"` en index.html   | R3    | ausente                                |
| `<canvas id="binary-rain">`       | R5    | ausente                                |
| `.scanline` en index.html         | R5    | ausente                                |
| 4x `corner-vignette` en index.html | R5   | < 4 ocurrencias                        |
| `id="status-bar"` en index.html   | R6    | ausente                                |
| Placeholders sin rellenar `{{ }}` | —     | cualquier match                        |
| RUC sin censurar                  | —     | patron `20[0-9]{9}`                    |
