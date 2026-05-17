#!/usr/bin/env bash
set -euo pipefail

INSIGHT_JSON="${1:?Usage: scripts/generate_audio.sh <insight_json_path>}"
AUDIO_OUT="assets/voiceover.mp3"
TIMESTAMPS_OUT="assets/voiceover_timestamps.json"
VOICE_ID="${ELEVENLABS_VOICE_ID:-pNInz6obpgDQGcFmaJgB}"
MODEL_ID="${ELEVENLABS_MODEL:-eleven_multilingual_v2}"
TMP_RESPONSE="$(mktemp)"

cleanup() { rm -f "$TMP_RESPONSE"; }
trap cleanup EXIT

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || { echo "ERROR: $1 not found" >&2; exit 1; }
}

require_cmd curl
require_cmd jq
require_cmd python3
require_cmd ffprobe

[[ -f "$INSIGHT_JSON" ]] || { echo "ERROR: insight not found: $INSIGHT_JSON" >&2; exit 1; }
[[ -n "${ELEVENLABS_API_KEY:-}" ]] || { echo "ERROR: ELEVENLABS_API_KEY required" >&2; exit 1; }

VOICEOVER_TEXT="$(jq -r '.script.voiceover_text_full // .voiceover_text_full // empty' "$INSIGHT_JSON")"
[[ -n "$VOICEOVER_TEXT" ]] || { echo "ERROR: script.voiceover_text_full missing" >&2; exit 1; }

WORD_COUNT=$(echo "$VOICEOVER_TEXT" | wc -w | tr -d ' ')
if [[ "$WORD_COUNT" -gt 50 ]]; then
  echo "ERROR: voiceover tiene $WORD_COUNT palabras (max 50 — REGLA 1). Acortar el guion." >&2
  exit 1
fi

REQUEST_BODY="$(jq -n --arg text "$VOICEOVER_TEXT" --arg model "$MODEL_ID" '{
  text: $text,
  model_id: $model,
  voice_settings: {
    stability: 0.5,
    similarity_boost: 0.75,
    style: 0.4,
    use_speaker_boost: true
  }
}')"

mkdir -p "$(dirname "$AUDIO_OUT")"

HTTP_STATUS="$(curl -sS -w "%{http_code}" -o "$TMP_RESPONSE" \
  -X POST "https://api.elevenlabs.io/v1/text-to-speech/${VOICE_ID}/with-timestamps" \
  -H "xi-api-key: ${ELEVENLABS_API_KEY}" \
  -H "Content-Type: application/json" \
  -d "$REQUEST_BODY")"

if [[ "$HTTP_STATUS" != "200" ]]; then
  echo "ERROR: ElevenLabs returned HTTP $HTTP_STATUS" >&2
  cat "$TMP_RESPONSE" >&2
  exit 1
fi

jq -r '.audio_base64' "$TMP_RESPONSE" | base64 -d > "$AUDIO_OUT"
[[ -s "$AUDIO_OUT" ]] || { echo "ERROR: audio file is empty" >&2; exit 1; }

DURATION="$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$AUDIO_OUT")"
[[ "$DURATION" =~ ^[0-9]+(\.[0-9]+)?$ ]] || { echo "ERROR: invalid MP3 duration: $DURATION" >&2; exit 1; }

# REGLA 1: audio no puede superar 19.5 s
awk -v d="$DURATION" 'BEGIN { exit !(d > 19.5) }' \
  && { echo "ERROR: audio dura ${DURATION}s (max 19.5s — REGLA 1). Acortar el guion." >&2; exit 1; } || true

python - "$TMP_RESPONSE" "$DURATION" "$TIMESTAMPS_OUT" <<'PYEOF'
import json, sys

response_file, duration_str, out_file = sys.argv[1], sys.argv[2], sys.argv[3]
audio_duration = float(duration_str)

with open(response_file) as f:
    body = json.load(f)

alignment = body.get("alignment") or body.get("normalized_alignment") or {}
chars  = alignment.get("characters", [])
starts = alignment.get("character_start_times_seconds", [])
ends   = alignment.get("character_end_times_seconds", [])

# --- sentences ---
sentences = []
current_start = starts[0] if starts else 0.0
last_period_was_final = False
for i, (char, t_end) in enumerate(zip(chars, ends)):
    if char == ".":
        next_idx = i + 1
        while next_idx < len(chars) and chars[next_idx] == " ":
            next_idx += 1
        sentences.append({"start": round(current_start, 3), "end": round(t_end, 3)})
        if next_idx < len(chars):
            current_start = starts[next_idx]
        else:
            last_period_was_final = True

if not last_period_was_final and (not sentences or current_start < (starts[-1] if starts else 0) - 0.1):
    sentences.append({"start": round(current_start, 3), "end": round(ends[-1] if ends else audio_duration, 3)})

# --- scene times ---
n = len(sentences)
def t(idx): return round(sentences[idx]["start"], 2)
def fb(pct): return round(audio_duration * pct, 2)

scene_times = {
    "t_intro": t(0)  if n >= 1 else 0.0,
    "t_punch": t(-2) if n >= 3 else fb(0.70),
    "t_cta":   t(-1) if n >= 2 else fb(0.85),
}
middle = sentences[1:-2] if n > 3 else []
if len(middle) >= 3:
    scene_times["t_facts"]   = round(middle[0]["start"], 2)
    scene_times["t_context"] = round(middle[1]["start"], 2)
    scene_times["t_compare"] = round(middle[2]["start"], 2)
elif len(middle) == 2:
    scene_times["t_facts"]   = round(middle[0]["start"], 2)
    scene_times["t_compare"] = round(middle[1]["start"], 2)
    scene_times["t_context"] = round((middle[0]["start"] + middle[1]["start"]) / 2, 2)
elif len(middle) == 1:
    scene_times["t_facts"]   = round(middle[0]["start"], 2)
    scene_times["t_context"] = round(middle[0]["start"], 2)
    scene_times["t_compare"] = round((middle[0]["start"] + scene_times["t_punch"]) / 2, 2)
else:
    scene_times["t_facts"]   = fb(0.12)
    scene_times["t_context"] = fb(0.35)
    scene_times["t_compare"] = fb(0.55)

# --- word timestamps (REGLA 2: karaoke palabra a palabra) ---
words = []
current_chars = []
word_start = None
for char, t_start, t_end in zip(chars, starts, ends):
    if char in (' ', '\n', '\r', '\t'):
        if current_chars and word_start is not None:
            word_text = "".join(current_chars).strip('.,;:!?¡¿-"\'()')
            if word_text:
                words.append({"word": word_text, "start": round(word_start, 3), "end": round(t_end, 3)})
            current_chars = []
            word_start = None
    else:
        if word_start is None:
            word_start = t_start
        current_chars.append(char)
if current_chars and word_start is not None:
    word_text = "".join(current_chars).strip('.,;:!?¡¿-"\'()')
    if word_text:
        words.append({"word": word_text, "start": round(word_start, 3),
                      "end": round(ends[-1], 3) if ends else round(word_start + 0.3, 3)})

result = {
    "audio_duration": round(audio_duration, 3),
    "sentences": sentences,
    "scene_times": scene_times,
    "words": words,
}
with open(out_file, "w") as f:
    json.dump(result, f, indent=2)

print(f"INFO: {n} oraciones, {len(words)} palabras detectadas", file=sys.stderr)
for k, v in scene_times.items():
    print(f"INFO:   {k} = {v}s", file=sys.stderr)
PYEOF

echo "INFO: Audio → $AUDIO_OUT (${DURATION}s)" >&2
echo "AUDIO_DURATION_SECONDS=$DURATION"
