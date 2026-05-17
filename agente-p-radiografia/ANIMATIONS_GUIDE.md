# ANIMATIONS_GUIDE.md
## Sistema de Animaciones — Radiografia del Gasto Publico

Guía de diseño para el sistema de animaciones de 3 capas. Aplica a esta serie y a cualquier serie futura que reutilice la biblioteca.

---

## Principio rector

> En cualquier frame del video, en cualquier momento de los 20 segundos, debe haber AL MENOS UN ELEMENTO en movimiento sutil. Frame completamente estático = frame que aburre.

---

## Archivos de la biblioteca

```
assets/
├── animations.css    # Keyframes CSS + clases de Capa 1 y Capa 2
└── animations.js     # Funciones JS de Capa 1 (ambient) y helpers de Capa 3
```

Ambos archivos son series-agnósticos. Para una nueva serie, duplicar y ajustar solo las variables CSS.

---

## Las 3 Capas

### Capa 1 — Ambiente (siempre corriendo, fondo)

Elementos que dan sensación de "video vivo" sin llamar la atención:

| Elemento | Implementación | Velocidad | Ajuste para nueva serie |
|----------|---------------|-----------|------------------------|
| Lluvia binaria 0/1 | `canvas#binary-rain` + `initBinaryRain()` JS | 80ms/tick | Cambiar color `rgba(74,222,128,α)` |
| Scanline horizontal | `.scanline` CSS keyframe | 4s loop | Ajustar opacidad en CSS |
| Grid pulse | `.grid-pulse` CSS keyframe | 6s loop | Cambiar color del radial |
| Viñetas de esquina | `.corner-vignette` x4 CSS | 3s loop | Cambiar color del gradient |
| REC parpadeante | `.rec-dot-anim` CSS | 1s step | Cambiar color si no es grabación |
| Glitch Perry | `initPerryGlitch()` JS | 4s interval | Cambiar a otro logo con misma función |

**Adición al HTML (mismo bloque en todas las plantillas):**
```html
<canvas id="binary-rain" style="position:absolute;inset:0;pointer-events:none;"></canvas>
<div class="grid-pulse"></div>
<!-- ... escenas ... -->
<div class="scanline"></div>
<div class="rec-indicator"><div class="rec-dot-anim"></div>REC</div>
<div class="corner-vignette tl"></div>
<div class="corner-vignette tr"></div>
<div class="corner-vignette bl"></div>
<div class="corner-vignette br"></div>
```

### Capa 2 — Bucles de elemento (mientras el elemento está en pantalla)

Clases CSS que se aplican a elementos ya visibles para mantenerlos "vivos":

| Clase CSS | Efecto | Duración loop | Úsalo en |
|-----------|--------|--------------|----------|
| `.anim-breathe` | scale 1→1.03 | 2s | Tarjetas de datos `.fact` |
| `.anim-glow` | text-shadow expansivo amarillo | 1.5s | Número crítico `<b>` |
| `.anim-wiggle` | rotación -3°/+3° | 0.9s | Flecha del CTA |
| `.anim-cursor` | cursor `|` parpadeante | 0.65s | Karaoke |
| `.anim-survivor-glow` | drop-shadow rojo pulsante | 1.2s | Postor sobreviviente SVG |
| `.anim-flow-line` | stroke-dashoffset flujo | 0.75s | Líneas SVG conectoras |
| `.anim-stamp-idle` | scale + glow sutil | 2s | Sello después de caer |
| `.anim-node-pulse` | ring expansion | 1.6s | Nodos de timeline |
| `.anim-hot` | background pulso | 1.4s | Celdas calientes heatmap |
| `.anim-conflict-line` | stroke alternado rojo/amarillo | 0.9s | Línea SVG contradictoria |

**Regla:** Las clases de Capa 2 se añaden mediante `tl.call(() => el.classList.add('...'))` después de que la animación de entrada terminó (no antes).

### Capa 3 — Entradas (helpers GSAP, one-shot)

Funciones en `animations.js` que se usan al construir el timeline:

```javascript
// Contar de 0 al valor
countUp('#id', valorNumerico, tl, tiempoInicio, duracion, sufijo);

// Sello cae + sacude
stampDrop('#badge', tl, tiempoInicio);

// Texto se corrompe y resuelve
textCorrupt('#punch', tl, tiempoInicio);

// Flash RGB glitch
rgbGlitch('#titulo', tl, tiempoInicio);

// Barra horizontal crece
growFromLeft('#barra', '65%', tl, tiempoInicio, duracion);

// Path SVG se dibuja (requiere .circuit-line en el elemento)
drawPath('#linea', tl, tiempoInicio, duracion);

// Slide desde izquierda o derecha
slideIn('#elemento', tl, tiempoInicio, true); // true=izquierda

// Typewriter caracter a caracter
typeWriter('#texto', tl, tiempoInicio, charMs);
```

---

## Reglas de composición

1. **Una escena protagonista por bloque temporal** — la escena de evidencia visual (T.compare → T.punch) tiene UN elemento visual animado central, no múltiples compitiendo.
2. **Zona de escena** — contenido visual en el rango y=250px a y=1200px. La zona y=1248px+ es del karaoke.
3. **Capa 1 siempre corre** — los elementos de ambiente viven fuera de los `<div class="scene">`, en el root.
4. **Capa 2 inicia +0.3s después de entrada** — añadir la clase CSS con `tl.call` al terminar la entrada.
5. **Capa 3 alineada con audio** — usar `T.compare + offset` basado en `voiceover_timestamps.json`.
6. **Rango de duración** — ninguna animación de Capa 3 < 200ms (se pierde) ni > 2s por paso individual.

---

## Escenas animadas por patrón

### `postor_unico` — "Aislamiento del postor"
- SVG inline: 5 stickmen
- GSAP: 4 fantasmas desaparecen con glitch en stagger 0.28s
- Sobreviviente: aura SVG crece (attr.r), luego `.anim-survivor-glow`
- Barras comparativas: `growFromLeft` con porcentajes calculados en runtime

### `fraccionamiento` — "Timeline + Suma reveladora"
- SVG vertical: espina del circuito con `.circuit-line` → `drawPath`
- Eventos: `slideIn` en cascada
- Nodos: `.anim-node-pulse` (CSS)
- Flujo continuo: `.anim-flow-line` en segunda línea SVG superpuesta
- Banner umbral: fade-in al final

### `funcionario_sancionado` — "Stamp drop + Timeline contradictorio"
- `stampDrop` para el badge INHABILITADO
- `rgbGlitch` en el DNI
- Línea SVG contradictoria: `drawPath` → luego `.anim-conflict-line`
- Nodos fecha: scale-pop stagger

### `proveedor_recurrente` — "Contador acumulativo + Heatmap"
- `countUp` del 0 al total de contratos
- Celdas heatmap: `tl.to('.cell', { opacity:1, stagger: {from:'center'} })`
- Celdas hot: `.anim-hot` añadida vía `tl.call`

---

## Escenas universales (reutilizables en cualquier plantilla)

Estas escenas pueden insertarse en cualquier plantilla que las necesite:

| Escena | Descripción | Útil para |
|--------|-------------|-----------|
| Lupa escaneando | Lupa SVG sobre documento, circulo amplifica detalle | Cualquier patrón |
| Grafo de nodos | 3-5 círculos + líneas dibujándose | Relaciones entidad-proveedor |
| Pila de monedas | Monedas cayendo hasta representar el monto | Contratos de obra |
| Comparativa lado a lado | "LO NORMAL" vs "LO DE HOY" con columnas SVG | Cualquier atipicidad |

Para implementar: crear como `templates/partials/escena_lupa.html` e incluir via Jinja2 `{% include %}`.

---

## Cómo crear una nueva serie

**Ejemplo: "Radiografía Municipal"**

### Paso 1: Duplicar biblioteca
```bash
cp assets/animations.css assets/animations_municipal.css
```
Cambiar en el CSS:
- `rgba(74,222,128, …)` → nuevo color acento (ej: naranja `rgba(251,146,60, …)`)
- Colores de variables en plantillas: ajustar `--green`, `--red`, `--yellow`

### Paso 2: Reutilizar Capa 1 y Capa 2 (100%)
Sin cambios en `animations.js`. Capa 1 y Capa 2 son color-agnósticas excepto por el verde de la lluvia (ajustar en CSS).

### Paso 3: Reutilizar helpers de Capa 3 (100%)
`countUp`, `stampDrop`, `textCorrupt`, `rgbGlitch`, `growFromLeft`, `drawPath`, `slideIn`, `typeWriter` funcionan sin cambios.

### Paso 4: Reutilizar escenas universales (100%)
Copiar los bloques SVG de las escenas universales sin modificar.

### Paso 5: Crear escenas específicas del nuevo nicho
Solo el bloque `scene-compare` de cada plantilla nueva necesita una escena diferente. Crear en `templates/nueva-serie/` como archivos independientes.

### Paso 6: Nuevas plantillas
```
.claude/skills/radiografia-municipal/templates/
├── alcalde_investigado.html   # (escena specific)
├── obra_sobrecosteada.html    # (escena specific)
└── ...
```
Las escenas de Capa 1 y Capa 2 son copy-paste exacto de esta serie.

---

## Checklist de QA visual (post-render)

Verificar en el MP4 generado:

- [ ] Lluvia binaria y scanline presentes durante toda la duración
- [ ] Logo Perry con micro-glitch visible (aprox. al segundo 1.5 y 5.5)
- [ ] Al menos una escena SVG animada en el bloque T.compare → T.punch
- [ ] Tarjetas de datos con respiración visible (scale sutil)
- [ ] Número crítico con glow pulsante amarillo
- [ ] CTA "SIGUEME ↑" con flecha wiggling
- [ ] Karaoke con cursor parpadeante mientras está visible
- [ ] Ningún segmento de >1.5s con pantalla completamente estática
- [ ] `● REC` parpadeando en esquina superior izquierda en todo momento
- [ ] Viñetas de esquina respiran (muy sutil)

---

*Última actualización: 2026-05-17*
