/**
 * animations.js — Radiografia del Gasto Publico v1.0
 * Sistema de animaciones de 3 capas modular y reutilizable.
 *
 * Depende de: GSAP 3 (cargado antes que este script)
 * Uso: initAmbient() se llama en DOMContentLoaded (automático al final)
 *      Los helpers de Capa 3 se usan al construir el timeline GSAP
 */

/* ─── CAPA 1: ANIMACIONES AMBIENTE ────────────────────────────────────────── */

function initBinaryRain() {
  const canvas = document.getElementById('binary-rain');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  canvas.width = 1080;
  canvas.height = 1920;

  const COL_W = 28;
  const cols = Math.floor(1080 / COL_W);
  const drops = Array.from({ length: cols }, () => Math.random() * -80);
  let lastTick = 0;

  function tick(now) {
    if (now - lastTick > 85) {
      /* Desvanecer trail suavemente */
      ctx.fillStyle = 'rgba(10,22,40,0.13)';
      ctx.fillRect(0, 0, 1080, 1920);
      ctx.font = '15px "Courier New", monospace';
      for (let i = 0; i < cols; i++) {
        /* Opacidad variable para sensación orgánica */
        const alpha = 0.04 + Math.random() * 0.04;
        ctx.fillStyle = `rgba(74,222,128,${alpha})`;
        ctx.fillText(Math.random() > 0.5 ? '1' : '0', i * COL_W + 5, drops[i] * COL_W);
        if (drops[i] * COL_W > 1920 && Math.random() > 0.974) drops[i] = 0;
        drops[i] += 0.32;
      }
      lastTick = now;
    }
    requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);
}

function initPerryGlitch() {
  const imgs = document.querySelectorAll('.logo-perry');
  if (!imgs.length) return;

  function doGlitch() {
    imgs.forEach(img => {
      gsap.timeline()
        .to(img, { x: -5, filter: 'hue-rotate(180deg) saturate(3) brightness(1.4)', duration: 0.06 })
        .to(img, { x: 5, filter: 'hue-rotate(270deg) saturate(2) brightness(1.2)', duration: 0.06 })
        .to(img, { x: -3, filter: 'hue-rotate(90deg) saturate(1.5)', duration: 0.05 })
        .to(img, { x: 0, filter: 'none', duration: 0.05 });
    });
  }

  /* Primer glitch a 1.5s para que no sea inmediato */
  setTimeout(doGlitch, 1500);
  setInterval(doGlitch, 4000);
}

function initAmbient() {
  initBinaryRain();
  initPerryGlitch();
}

/* ─── CAPA 3: HELPERS DE ENTRADA (integrar en timeline GSAP) ──────────────── */

/**
 * Cuenta desde 0 hasta target con formato numérico.
 * @param {string} selector  CSS selector del elemento
 * @param {number} target    Valor final
 * @param {object} tl        Timeline GSAP
 * @param {number} t         Posición en el timeline
 * @param {number} [dur=1]   Duración en segundos
 * @param {string} [suffix=''] Sufijo después del número (ej: ' días')
 */
function countUp(selector, target, tl, t, dur, suffix) {
  dur = dur || 1;
  suffix = suffix || '';
  const el = document.querySelector(selector);
  if (!el) return;
  const obj = { val: 0 };
  el.textContent = '0' + suffix;
  tl.to(obj, {
    val: target,
    duration: dur,
    ease: 'power2.out',
    onUpdate() {
      el.textContent = Math.floor(obj.val).toLocaleString('es-PE') + suffix;
    }
  }, t);
}

/**
 * Sello cae desde arriba y sacude el padre al impactar.
 * @param {string} selector  CSS selector del sello
 * @param {object} tl        Timeline GSAP
 * @param {number} t         Posición en el timeline
 */
function stampDrop(selector, tl, t) {
  const el = document.querySelector(selector);
  if (!el) return;
  const parent = el.parentElement;

  tl.fromTo(selector,
    { y: -300, rotation: -22, scale: 1.4, opacity: 0 },
    { y: 0, rotation: -4, scale: 1, opacity: 1, duration: 0.38, ease: 'back.out(1.5)' },
    t
  );
  /* Sacudida de pantalla al impactar */
  if (parent) {
    tl.to(parent, { x: -8, duration: 0.04 }, t + 0.38)
      .to(parent, { x: 8,  duration: 0.04 })
      .to(parent, { x: -5, duration: 0.04 })
      .to(parent, { x: 0,  duration: 0.04 });
  }
}

/**
 * Texto se corrompe con caracteres aleatorios y resuelve al texto final.
 * El elemento debe tener su texto final como contenido (se usa data-text si existe).
 * @param {string} selector  CSS selector
 * @param {object} tl        Timeline GSAP
 * @param {number} t         Posición en el timeline
 */
function textCorrupt(selector, tl, t) {
  const el = document.querySelector(selector);
  if (!el) return;
  const finalText = el.dataset.text || el.textContent;
  const NOISE = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789#@$%&?!';
  const FRAMES = 16;
  let frame = 0;

  tl.set(selector, { opacity: 1 }, t);
  tl.call(() => {
    el.textContent = finalText; /* reset por si el timeline se busca */
    frame = 0;
    const iv = setInterval(() => {
      frame++;
      if (frame >= FRAMES) { el.textContent = finalText; clearInterval(iv); return; }
      const progress = frame / FRAMES;
      el.textContent = finalText.split('').map((ch, i) => {
        if (ch === ' ' || i / finalText.length < progress) return ch;
        return NOISE[Math.floor(Math.random() * NOISE.length)];
      }).join('');
    }, 52);
  }, [], t);
}

/**
 * Flash RGB glitch sobre un elemento.
 * @param {string} selector  CSS selector
 * @param {object} tl        Timeline GSAP
 * @param {number} t         Posición en el timeline
 */
function rgbGlitch(selector, tl, t) {
  tl.fromTo(selector,
    { filter: 'none', x: 0 },
    {
      keyframes: [
        { filter: 'drop-shadow(5px 0 #EF4444) drop-shadow(-5px 0 #4ADE80)', x: -6, duration: 0.08 },
        { filter: 'drop-shadow(-5px 0 #EF4444) drop-shadow(5px 0 #4ADE80)', x: 6, duration: 0.08 },
        { filter: 'drop-shadow(3px 0 #FBBF24) brightness(1.3)', x: -3, duration: 0.07 },
        { filter: 'none', x: 0, duration: 0.07 }
      ]
    },
    t
  );
}

/**
 * Barra crece de izquierda a derecha hasta ancho objetivo.
 * @param {string} selector   CSS selector de la barra
 * @param {string} targetW    Ancho final (ej: '65%')
 * @param {object} tl
 * @param {number} t
 * @param {number} [dur=0.8]
 */
function growFromLeft(selector, targetW, tl, t, dur) {
  tl.fromTo(selector,
    { width: '0%' },
    { width: targetW, duration: dur || 0.8, ease: 'power3.out' },
    t
  );
}

/**
 * Dibuja un path SVG (stroke-dashoffset 700→0).
 * @param {string} selector  CSS selector del <path> o <line> con .circuit-line
 * @param {object} tl
 * @param {number} t
 * @param {number} [dur=0.7]
 */
function drawPath(selector, tl, t, dur) {
  tl.to(selector, { strokeDashoffset: 0, duration: dur || 0.7, ease: 'power2.inOut' }, t);
}

/**
 * Slide-in desde izquierda o derecha.
 * @param {string}  selector
 * @param {object}  tl
 * @param {number}  t
 * @param {boolean} [fromLeft=true]
 */
function slideIn(selector, tl, t, fromLeft) {
  const x = (fromLeft !== false) ? -130 : 130;
  tl.from(selector, { x, opacity: 0, duration: 0.45, ease: 'back.out(1.6)' }, t);
}

/**
 * Typewriter: aparecen caracteres uno a uno.
 * @param {string} selector
 * @param {object} tl
 * @param {number} t
 * @param {number} [charMs=55] ms entre caracteres
 */
function typeWriter(selector, tl, t, charMs) {
  charMs = charMs || 55;
  const el = document.querySelector(selector);
  if (!el) return;
  const text = el.dataset.text || el.textContent;
  el.textContent = '';
  tl.set(selector, { opacity: 1 }, t);
  tl.call(() => {
    let i = 0;
    const iv = setInterval(() => {
      el.textContent = text.slice(0, ++i);
      if (i >= text.length) clearInterval(iv);
    }, charMs);
  }, [], t);
}

/* ─── AUTO-INIT ─────────────────────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', initAmbient);
