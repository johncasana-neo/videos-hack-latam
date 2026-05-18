---
name: radiografia
description: Genera el video diario de Radiografia del Gasto Publico leyendo el insight JSON mas reciente, seleccionando la plantilla HTML segun el patron detectado, llenando los placeholders Jinja2 con datos reales, y validando el resultado antes de renderizar con HyperFrames
---

# Radiografia del Gasto Publico

Usa este skill cuando el usuario pida procesar el insight diario de la serie "Radiografia del Gasto Publico" de Agente P.

**REGLAS OBLIGATORIAS**: leer `STYLE_GUIDE.md` antes de cada render. Las 7 reglas de ese documento son no negociables y el validador las verifica automáticamente.

## Flujo obligatorio

1. Leer el insight mas reciente dentro de `insights/` con nombre `insight_YYYY_MM_DD.json`.
2. Validar que existan los campos criticos:
   - `case.caso_titulo`
   - `case.patron_detectado`
   - `case.confidence`
   - `source.entidad_nombre`
   - `source.codigo_seace`
   - `source.fuente_oficial`
   - `script.voiceover_text_full`
   - `output.width`, `output.height`, `output.fps`
3. Abortarlo si `case.confidence < 0.8` o si falta cualquier campo critico.
4. Mapear `case.patron_detectado` a plantilla:
   - `postor_unico_con_proceso_acelerado` → `templates/postor_unico.html`
   - `proveedor_recurrente` → `templates/proveedor_recurrente.html`
   - `fraccionamiento_contractual` → `templates/fraccionamiento.html`
   - `funcionario_sancionado_activo` → `templates/funcionario_sancionado.html`
   - default → `templates/postor_unico.html`
5. Copiar la plantilla elegida a `index.html` y reemplazar todos los placeholders `{{ variable }}` con datos del insight.
6. Formatear montos como `S/ X,XXX,XXX`.
7. Censurar RUCs con el formato `20••••••XXX`, conservando solo los ultimos 3 digitos.
8. Leer `script.scene_times` del insight JSON. Inyectar los seis tiempos como variables de template:
   - `t_intro`   ← `scene_times.t_intro`
   - `t_facts`   ← `scene_times.t_facts`
   - `t_context` ← `scene_times.t_context`
   - `t_compare` ← `scene_times.t_compare`
   - `t_punch`   ← `scene_times.t_punch`
   - `t_cta`     ← `scene_times.t_cta`
   Si `scene_times` no existe en el JSON, usar fallbacks: `t_intro=0, t_facts=2, t_context=5, t_compare=10, t_punch=14, t_cta=17`.
   `audio_duration` ← `output.duration_seconds`.
   `confidence_pct` ← `round(case.confidence * 100)` (entero, ej: 86).
8.5. Leer `assets/voiceover_timestamps.json`. Si existe y contiene campo `words` con al menos 1 elemento, serializar como JSON compacto y asignarlo a `karaoke_words_json`. Si el campo `words` está ausente o vacío, abortar con `status: "aborted", reason: "word timestamps missing — regenerar audio con generate_audio.py"`.
9. Verificar que el `index.html` generado cumple el checklist de animaciones (ver sección abajo).
10. Ejecutar `npx hyperframes lint index.html`.
11. Si el lint falla por errores corregibles, autocorregir y reintentar hasta 2 veces.
12. Imprimir un JSON final:

```json
{
  "status": "ok",
  "video_path": "output/radiografia-YYYY_MM_DD.mp4",
  "case_title": "Titulo del caso",
  "entity_name": "Entidad",
  "episode": "01/30"
}
```

## Variables esperadas por las plantillas

### Comunes a todos los patrones
- `episode_label`
- `caso_titulo`
- `entidad_nombre`
- `entidad_sigla`
- `entidad_ruc_censurado`
- `monto_adjudicado_formato`
- `objeto_contrato`
- `numero_postores`
- `dias_proceso`
- `promedio_sector`
- `fuente_oficial`
- `audio_duration`
- `t_intro`, `t_facts`, `t_context`, `t_compare`, `t_punch`, `t_cta`
- `codigo_seace`
- `confidence_pct` — entero (ej: 86)
- `karaoke_words_json` — array JSON serializado desde `assets/voiceover_timestamps.json#words`

### Solo para `funcionario_sancionado_activo`
- `funcionario_dni_ultimos` — ultimos 4 digitos del DNI (censurar el resto)
- `sancion_fecha` — fecha de sancion (formato `DD/MM/AAAA`)
- `firma_fecha` — fecha de firma del contrato cuestionado

### Nota para `proveedor_recurrente`
`numero_postores` debe cargarse con el total de contratos ganados por el proveedor en la ventana de 12 meses (campo `total_contratos_ganados` del insight si existe; si no, usar `numero_postores` del contrato). Este valor alimenta el contador animado de la escena de evidencia visual.

## Sistema de animaciones de 3 capas

Las plantillas dependen de dos archivos compartidos que DEBEN existir en `assets/`:
- `assets/animations.css` — keyframes de Capa 1 (ambiente) y Capa 2 (bucles de elemento)
- `assets/animations.js` — helpers de Capa 3 (entradas) + initAmbient()

### Capa 1: Ambiente (siempre corriendo)
- Lluvia binaria 0/1: canvas `#binary-rain` + `initBinaryRain()`
- Scanline: `.scanline` CSS loop 4s
- Grid pulse: `.grid-pulse` CSS loop 6s
- Esquinas: `.corner-vignette` CSS loop 3s
- REC: `.rec-indicator` + `.rec-dot-anim` CSS loop 1s
- Glitch de Perry: `initPerryGlitch()` cada 4s

### Capa 2: Elementos en pantalla (bucles CSS)
- Tarjetas de facts: `.anim-breathe` (scale 1→1.03, 2s loop)
- Monto crítico: `.anim-glow` en `<b#monto-val>` (text-shadow expansivo, 1.5s loop)
- Flecha CTA: `.anim-wiggle` (rotación -3°/+3°, 0.9s loop)
- Karaoke: `.anim-cursor` (cursor parpadeante `|`)
- Sobreviviente postor: `.anim-survivor-glow` (añadido vía `tl.call`)
- Sello badge: `.anim-stamp-idle` (añadido vía `tl.call` tras `stampDrop`)
- Celdas calientes: `.anim-hot` (añadido vía `tl.call`)
- Nodos timeline: `.anim-node-pulse`
- Línea contradictoria: `.anim-conflict-line` (añadido vía `tl.call`)

### Capa 3: Entradas (helpers GSAP en animations.js)
- `countUp(sel, target, tl, t, dur, suffix)` — número cuenta de 0 al valor
- `stampDrop(sel, tl, t)` — sello cae + sacude padre
- `textCorrupt(sel, tl, t)` — texto corrupción → resolución
- `rgbGlitch(sel, tl, t)` — flash RGB en elemento
- `growFromLeft(sel, targetW, tl, t, dur)` — barra crece
- `drawPath(sel, tl, t, dur)` — path SVG se dibuja (circuit-line)
- `slideIn(sel, tl, t, fromLeft)` — slide-in lateral
- `typeWriter(sel, tl, t, charMs)` — texto aparece caracter a caracter

## Escenas animadas por patron

| Patron | Escena en `scene-compare` |
|--------|--------------------------|
| `postor_unico` | 5 stickmen SVG: 4 desaparecen con glitch, 1 queda con aura roja pulsante + barras dias_proceso vs promedio |
| `fraccionamiento` | Timeline vertical con circuito animado + 4 eventos slide-in + banner umbral |
| `funcionario_sancionado` | Stamp drop "INHABILITADO" + DNI glitch + timeline contradictorio con línea parpadeante |
| `proveedor_recurrente` | Contador sube de 0 al total + heatmap 12 meses con celdas hot pulsando |

## Checklist de validacion de animaciones (paso 9)

Antes de hacer lint, verificar visualmente en el `index.html` generado:

- [ ] `<canvas id="binary-rain">` presente en el root (REGLA 5)
- [ ] `.scanline`, `.grid-pulse`, `.rec-indicator` presentes (REGLA 5)
- [ ] 4 `.corner-vignette` (tl, tr, bl, br) presentes (REGLA 5)
- [ ] `<link href="assets/animations.css">` en el `<head>`
- [ ] `<script src="assets/animations.js">` antes del inline script
- [ ] `#monto-val` tiene clase `anim-glow`
- [ ] `.anim-wiggle` aplicado al `↑` del CTA
- [ ] `#hook-datum` presente dentro de `#scene-intro` (REGLA 3 — no titulo corporativo)
- [ ] `#scene-intro` tiene `background:#000` (REGLA 3)
- [ ] `#karaoke-word` presente (REGLA 2 — no texto fijo en karaoke)
- [ ] `const KWORDS = ` presente en el script (REGLA 2 — karaoke word-by-word)
- [ ] `#status-bar` presente fuera de las escenas (REGLA 6)
- [ ] La escena `scene-compare` contiene el elemento SVG/visual del patron
- [ ] El timeline GSAP incluye al menos una llamada a `countUp`, `stampDrop`, `textCorrupt` o `rgbGlitch`
- [ ] Ningun segmento de >1.5s queda sin animacion visible (verificar tiempos T.*) (REGLA 4 y 7)
- [ ] `scene-cta` contiene episodio y nombre de la serie (REGLA 3)

Si algún item falla: corregir el `index.html` antes de continuar con el lint.

## Reglas estrictas

- Nunca publicar nombres propios sin censura si no hay sentencia firme.
- El frame final (scene-cta) es solo marca: "@agente_p" + "Siguenos en Agente P". Sin fuentes ni disclaimers.
- Si `confidence < 0.8` o falta algun campo critico, abortar y reportar `status: "aborted"`.
- No inventar datos. Si falta un dato no critico, usar una etiqueta neutra como `No reportado`.
- No exponer RUCs completos, DNI completos, telefonos, correos personales ni direcciones personales.
- El resultado debe ser 1080x1920, 30 fps y duracion final entre **19.5 y 20.5 segundos** (REGLA 1). Si el audio supera 19 s, comprimir segmento `context` primero; si sigue largo, comprimir `facts`; nunca comprimir `punch` ni `cta`.
- Los archivos `assets/animations.css` y `assets/animations.js` deben existir antes de renderizar.
