#!/usr/bin/env bash
set -euo pipefail

MP4_PATH="${1:-}"
WARNINGS=0
TMP_LINT="$(mktemp)"

# Inherit PYTHON from parent (run_local.sh exports it); fallback for standalone use
if [[ -z "${PYTHON:-}" ]]; then
  if [[ -f "venv/Scripts/python.exe" ]]; then
    PYTHON="$(pwd)/venv/Scripts/python.exe"
  elif [[ -f "venv/bin/python" ]]; then
    PYTHON="$(pwd)/venv/bin/python"
  else
    PYTHON="$(command -v python3 2>/dev/null || command -v python 2>/dev/null || echo "")"
    [[ "$PYTHON" == *"WindowsApps"* ]] && PYTHON=""
  fi
fi
[[ -n "$PYTHON" ]] || { echo "ERROR: python not found. Run: python -m venv venv && pip install -r requirements.txt" >&2; exit 1; }

cleanup() {
  rm -f "$TMP_LINT"
}
trap cleanup EXIT

warn() {
  WARNINGS=$((WARNINGS + 1))
  echo "WARN: $*" >&2
}

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

duration_of() {
  ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$1"
}

# ── index.html checks ────────────────────────────────────────────────────────

[[ -f "index.html" ]] || fail "index.html does not exist"
grep -qi '<!doctype html' "index.html" || warn "index.html has no DOCTYPE"
grep -qi 'data-composition-id\|data-scene' "index.html" || fail "index.html does not look like a HyperFrames composition"

# REGLA 0: no placeholders sin rellenar
if grep -qE '\{\{[^}]+\}\}' "index.html"; then
  fail "index.html still contains unfilled Jinja2 placeholders"
fi

# REGLA 0: no RUCs sin censurar
if grep -qE '20[0-9]{9}' "index.html"; then
  warn "index.html contains uncensored 11-digit RUC-like values"
fi

# REGLA 2: karaoke debe ser palabra a palabra (id=karaoke-word obligatorio)
grep -q 'id="karaoke-word"' "index.html" \
  || fail "REGLA2: #karaoke-word ausente — karaoke debe ser palabra a palabra, no texto fijo"

# REGLA 2: no debe haber texto hardcodeado dentro del div#karaoke
# El div#karaoke solo debe contener el span#karaoke-word vacio
if "$PYTHON" - <<'PYEOF'
import re, sys
html = open("index.html", encoding="utf-8").read()
# find content inside div#karaoke
m = re.search(r'id=["\']karaoke["\'][^>]*>(.*?)</div>', html, re.DOTALL)
if not m:
    sys.exit(0)
inner = m.group(1)
# strip the allowed span#karaoke-word
inner_clean = re.sub(r'<span[^>]*id=["\']karaoke-word["\'][^>]*>.*?</span>', '', inner, flags=re.DOTALL)
inner_clean = re.sub(r'\s+', '', inner_clean)
if inner_clean:
    print(f"STATIC_KARAOKE: {inner_clean[:80]}", file=__import__('sys').stderr)
    sys.exit(1)
sys.exit(0)
PYEOF
then :
else
  fail "REGLA2: texto estatico detectado dentro de #karaoke — usar solo #karaoke-word via JS"
fi

# REGLA 3: hook brutalista obligatorio
grep -q 'id="hook-datum"' "index.html" \
  || fail "REGLA3: #hook-datum ausente — scene-intro debe usar hook brutalista, no titulo corporativo"

# REGLA 5: efectos ambiente obligatorios
grep -q 'id="binary-rain"' "index.html" \
  || fail "REGLA5: <canvas id=binary-rain> ausente — Capa 1 ambiente obligatoria"

grep -q 'class="scanline"' "index.html" \
  || fail "REGLA5: .scanline ausente"

vignette_count=$(grep -c 'corner-vignette' "index.html" || true)
[[ "$vignette_count" -ge 4 ]] \
  || fail "REGLA5: solo $vignette_count .corner-vignette encontradas (se requieren 4)"

# REGLA 6: status-bar obligatorio
grep -q 'id="status-bar"' "index.html" \
  || fail "REGLA6: #status-bar ausente — zona inferior debe tener indicador de caso/confidence"

# ── REGLAS ANTI-REGRESION (aprendidas del caso MTC) ──────────────────────────

# R-AR1: Perry watermark eliminado — NO debe volver al DOM
if grep -q 'id="perry-watermark"' "index.html"; then
  fail "ANTI-REGRESION: #perry-watermark encontrado en index.html — Perry solo aparece en M1, M2, M3. Eliminar el elemento."
fi

# R-AR2: karaoke debe limpiarse al inicio del frame final (CTA)
if ! grep -q "KWORD_EL.textContent = ''.*T\.cta\|T\.cta.*KWORD_EL.textContent = ''" "index.html"; then
  # busqueda alternativa: la linea de limpieza del karaoke con T.cta como argumento de tiempo
  if ! grep -qP "KWORD_EL\.textContent\s*=\s*''\s*\}\s*,\s*\[\]\s*,\s*T\.cta" "index.html" 2>/dev/null; then
    warn "R-AR2: no se encontro limpieza del karaoke en T.cta — el karaoke puede solaparse con el frame final"
  fi
fi

# R-AR3: status-bar debe ocultarse en el frame final
grep -q "status-bar.*opacity.*0\|opacity.*0.*status-bar" "index.html" \
  || warn "R-AR3: #status-bar no tiene animacion de ocultamiento — puede solaparse con el frame CTA"

# R-AR4: handle de marca correcto (@agente_p, no @agente_pe ni @AGENTE_PE)
if grep -qiE '@agente_pe|@AGENTE_PE|Agente Pe' "index.html"; then
  fail "R-AR4: handle incorrecto encontrado — debe ser '@agente_p' y 'Agente P' (sin 'e' al final)"
fi

# ── audio checks ──────────────────────────────────────────────────────────────

[[ -f "assets/voiceover.mp3" ]] || fail "assets/voiceover.mp3 does not exist"
audio_duration="$(duration_of "assets/voiceover.mp3")"

# REGLA 1: duracion audio 15–22 s
"$PYTHON" -c "import sys; d=float('${audio_duration}'); sys.exit(0 if 15.0<=d<=22.0 else 1)" \
  || fail "REGLA1: duracion audio fuera de rango: ${audio_duration}s (requerido: 15–22s)"

# ── word timestamps check ─────────────────────────────────────────────────────

if [[ -f "assets/voiceover_timestamps.json" ]]; then
  words_count=$("$PYTHON" -c "
import json, sys
d = json.load(open('assets/voiceover_timestamps.json'))
words = d.get('words', [])
print(len(words))
" 2>/dev/null || echo 0)
  [[ "$words_count" -gt 0 ]] \
    || warn "REGLA2: voiceover_timestamps.json no contiene campo 'words' — karaoke sin datos"
else
  warn "assets/voiceover_timestamps.json no existe — karaoke sin datos"
fi

# ── HyperFrames lint ──────────────────────────────────────────────────────────

if command -v npx >/dev/null 2>&1; then
  if ! npx hyperframes lint . >"$TMP_LINT" 2>&1; then
    cat "$TMP_LINT" >&2
    fail "npx hyperframes lint failed"
  fi
else
  warn "npx not found; skipped hyperframes lint"
fi

# ── MP4 checks ────────────────────────────────────────────────────────────────

if [[ -n "$MP4_PATH" ]]; then
  [[ -f "$MP4_PATH" ]] || fail "MP4 does not exist: $MP4_PATH"
  size_bytes="$(wc -c < "$MP4_PATH" | tr -d ' ')"
  [[ "$size_bytes" -gt 512000 ]] || fail "MP4 must be >500KB, got ${size_bytes} bytes"
  video_duration="$(duration_of "$MP4_PATH")"
  # REGLA 1: duracion video 15–22 s
  "$PYTHON" -c "import sys; d=float('${video_duration}'); sys.exit(0 if 15.0<=d<=22.0 else 1)" \
    || fail "REGLA1: duracion video fuera de rango: ${video_duration}s (requerido: 15–22s)"
fi

echo "VALIDATION_OK warnings=$WARNINGS audio_duration=$audio_duration"
