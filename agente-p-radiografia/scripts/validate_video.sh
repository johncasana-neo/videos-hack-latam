#!/usr/bin/env bash
set -euo pipefail

MP4_PATH="${1:-}"
WARNINGS=0
TMP_LINT="$(mktemp)"

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

[[ -f "index.html" ]] || fail "index.html does not exist"
grep -qi '<!doctype html' "index.html" || warn "index.html has no DOCTYPE"
grep -qi 'data-composition-id\|data-scene' "index.html" || fail "index.html does not look like a HyperFrames composition"

if grep -qE '\{\{[^}]+\}\}' "index.html"; then
  fail "index.html still contains unfilled Jinja2 placeholders"
fi

if grep -qE '20[0-9]{9}' "index.html"; then
  warn "index.html contains uncensored 11-digit RUC-like values"
fi

grep -qi 'Datos publicos\|Datos públicos' "index.html" || warn "final disclaimer not detected"

[[ -f "assets/voiceover.mp3" ]] || fail "assets/voiceover.mp3 does not exist"
audio_duration="$(duration_of "assets/voiceover.mp3")"
awk -v d="$audio_duration" 'BEGIN { exit !(d >= 15 && d <= 28) }' || fail "voiceover duration must be 15-28s, got ${audio_duration}s"

if command -v npx >/dev/null 2>&1; then
  if ! npx hyperframes lint . >"$TMP_LINT" 2>&1; then
    cat "$TMP_LINT" >&2
    fail "npx hyperframes lint failed"
  fi
else
  warn "npx not found; skipped hyperframes lint"
fi

if [[ -n "$MP4_PATH" ]]; then
  [[ -f "$MP4_PATH" ]] || fail "MP4 does not exist: $MP4_PATH"
  size_bytes="$(wc -c < "$MP4_PATH" | tr -d ' ')"
  [[ "$size_bytes" -gt 512000 ]] || fail "MP4 must be >500KB, got ${size_bytes} bytes"
  video_duration="$(duration_of "$MP4_PATH")"
  awk -v d="$video_duration" 'BEGIN { exit !(d >= 15 && d <= 30) }' || fail "MP4 duration must be 15-30s, got ${video_duration}s"
fi

echo "VALIDATION_OK warnings=$WARNINGS audio_duration=$audio_duration"
