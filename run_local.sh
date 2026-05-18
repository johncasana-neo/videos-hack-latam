#!/usr/bin/env bash
# Local end-to-end pipeline: audio → html → render → publish IG → notify Discord
# Run from agente-p-radiografia/ directory.
#
# Flags:
#   --skip-audio    Use 20s silent placeholder instead of calling ElevenLabs
#   --skip-publish  Skip IG upload (test mode)
#   --use-example   Copy insight_example_mtc.json instead of scraping
set -euo pipefail

cd "$(dirname "$0")"

[[ -f .env ]] && { set -a; source .env; set +a; }

# Activate venv so Python works in all subprocesses (fixes Windows Store alias issue)
if [[ -f "venv/Scripts/activate" ]]; then
  source venv/Scripts/activate
elif [[ -f "venv/bin/activate" ]]; then
  source venv/bin/activate
fi

# Detect Python - prefer venv by path, reject Windows Store aliases
if [[ -f "venv/Scripts/python.exe" ]]; then
  PYTHON="$(pwd)/venv/Scripts/python.exe"
elif [[ -f "venv/bin/python" ]]; then
  PYTHON="$(pwd)/venv/bin/python"
else
  PYTHON="$(command -v python3 2>/dev/null || command -v python 2>/dev/null || echo "")"
  [[ "$PYTHON" == *"WindowsApps"* ]] && PYTHON=""
fi
[[ -n "$PYTHON" ]] || { echo "ERROR: Python not found. Run: python -m venv venv && pip install -r requirements.txt" >&2; exit 1; }
export PYTHON

SKIP_AUDIO=false
SKIP_PUBLISH=false
USE_EXAMPLE=false

for arg in "$@"; do
  case $arg in
    --skip-audio)   SKIP_AUDIO=true  ;;
    --skip-publish) SKIP_PUBLISH=true ;;
    --use-example)  USE_EXAMPLE=true  ;;
  esac
done

TODAY="$(TZ=America/Lima date +%Y_%m_%d)"
INSIGHT_PATH="insights/insight_${TODAY}.json"
MP4_PATH="output/radiografia-${TODAY}.mp4"
STATUS="ok"
CASE_TITLE="Radiografia del Gasto Publico"
ENTITY_NAME="Entidad publica"

mkdir -p insights assets output

# ── Step 1: Insight ─────────────────────────────────────────────────────────
echo ""
echo "=== [1/7] Insight ==="
if [[ "$USE_EXAMPLE" == "true" ]]; then
  cp insights/insight_example_mtc.json "$INSIGHT_PATH"
  echo "Using example insight."
elif [[ ! -f "$INSIGHT_PATH" ]]; then
  "$PYTHON" insights_app/main.py --output "$INSIGHT_PATH" || {
    echo "No actionable cases today. Exiting."
    exit 1
  }
else
  echo "Insight already exists: $INSIGHT_PATH"
fi

# ── Step 2: Audio ────────────────────────────────────────────────────────────
echo ""
echo "=== [2/7] Audio ==="
if [[ "$SKIP_AUDIO" == "true" ]]; then
  echo "Generating 20s silent placeholder..."
  ffmpeg -f lavfi -i anullsrc=channel_layout=mono:sample_rate=44100 \
    -t 20 -c:a libmp3lame -b:a 128k -y assets/voiceover.mp3
  AUDIO_DURATION=20
else
  : "${ELEVENLABS_API_KEY:?ELEVENLABS_API_KEY required}"
  raw_output="$("$PYTHON" scripts/generate_audio.py "$INSIGHT_PATH")"
  echo "$raw_output"
  AUDIO_DURATION="$(echo "$raw_output" | awk -F= '/AUDIO_DURATION_SECONDS=/{print $2}' | tail -1)"
  [[ -n "$AUDIO_DURATION" ]] || { echo "ERROR: could not parse AUDIO_DURATION_SECONDS" >&2; exit 1; }
fi
echo "Audio duration: ${AUDIO_DURATION}s"

# ── Step 2b: Patch insight JSON with timestamps ──────────────────────────────
echo ""
echo "=== [2b/7] Patch timestamps ==="
"$PYTHON" - "$INSIGHT_PATH" "$AUDIO_DURATION" <<'PYEOF'
import json, math, sys

insight_path, duration_str = sys.argv[1], sys.argv[2]
audio_duration = float(duration_str)
dur_ceil = math.ceil(audio_duration)

with open(insight_path, encoding="utf-8") as f:
    insight = json.load(f)

insight["output"]["duration_seconds"] = dur_ceil

try:
    with open("assets/voiceover_timestamps.json", encoding="utf-8") as f:
        ts = json.load(f)
    st = ts["scene_times"]
    scene_order = ["t_intro","t_facts","t_context","t_compare","t_punch","t_cta"]
    labels      = ["intro","facts","context","compare","punch","cta"]
    times = [st[k] for k in scene_order]
    segments = []
    for i, (label, start) in enumerate(zip(labels, times)):
        end = times[i+1] if i+1 < len(times) else dur_ceil
        segments.append({"start": round(start, 2), "end": round(end, 2), "label": label})
    insight["script"]["segments"] = segments
    insight["script"]["scene_times"] = st
    print(f"INFO: Patched duration={dur_ceil}s + {len(segments)} scene timestamps from ElevenLabs")
except FileNotFoundError:
    insight["output"]["duration_seconds"] = dur_ceil
    print("WARNING: voiceover_timestamps.json not found, only duration patched")

with open(insight_path, "w", encoding="utf-8") as f:
    json.dump(insight, f, indent=2, ensure_ascii=False)
PYEOF

# ── Step 3: index.html via Claude Code skill ─────────────────────────────────
echo ""
echo "=== [3/7] Generate index.html ==="
# Claude Code uses its stored session (~/.claude). No key override needed locally.
# In CI, set ANTHROPIC_API_KEY secret directly (real Anthropic key, not OpenRouter).
  claude -p "/radiografia procesa el insight de hoy con duracion de audio ${AUDIO_DURATION} segundos" \
  --allowedTools "Bash,Read,Write,Edit,Glob,Skill" \
  --output-format json | tee .claude_run_local.json
CASE_TITLE="$("$PYTHON" -c "
import json, re, sys
raw = json.load(open('.claude_run_local.json')).get('result','')
m = re.search(r'\"case_title\":\s*\"([^\"]+)\"', raw)
print(m.group(1) if m else 'Radiografia del Gasto Publico')
" 2>/dev/null || echo "Radiografia del Gasto Publico")"
ENTITY_NAME="$("$PYTHON" -c "
import json, re, sys
raw = json.load(open('.claude_run_local.json')).get('result','')
m = re.search(r'\"entity_name\":\s*\"([^\"]+)\"', raw)
print(m.group(1) if m else 'Entidad publica')
" 2>/dev/null || echo "Entidad publica")"

# ── Step 4: Validate pre-render ───────────────────────────────────────────────
echo ""
echo "=== [4/7] Validate pre-render ==="
bash scripts/validate_video.sh

# ── Step 5: Render MP4 ────────────────────────────────────────────────────────
echo ""
echo "=== [5/7] Render ==="
npx hyperframes render . --output "$MP4_PATH"

# ── Step 6: Validate MP4 ──────────────────────────────────────────────────────
echo ""
echo "=== [6/7] Validate MP4 ==="
bash scripts/validate_video.sh "$MP4_PATH"

# ── Step 7: Publish to Instagram ──────────────────────────────────────────────
echo ""
echo "=== [7/7] Instagram ==="
if [[ "$SKIP_PUBLISH" == "false" ]]; then
  : "${IG_ACCESS_TOKEN:?IG_ACCESS_TOKEN required}"
  : "${IG_USER_ID:?IG_USER_ID required}"
  bash scripts/publish_ig.sh "$MP4_PATH" "$INSIGHT_PATH"
  STATUS="Publicado"
else
  echo "Skipped (--skip-publish)"
  STATUS="Test local"
fi

# ── Discord notification ───────────────────────────────────────────────────────
if [[ -n "${DISCORD_WEBHOOK:-}" ]]; then
  COLOR=$([[ "$STATUS" == "Publicado" ]] && echo 4906624 || echo 16776960)
  curl -sS -X POST "$DISCORD_WEBHOOK" \
    -H "Content-Type: application/json" \
    -d "$(jq -n \
      --arg title "$CASE_TITLE" \
      --arg status "$STATUS" \
      --arg entity "$ENTITY_NAME" \
      --arg mp4 "$MP4_PATH" \
      --argjson color "$COLOR" \
      '{embeds:[{title:$title,color:$color,fields:[
        {name:"Estado",value:$status,inline:true},
        {name:"Entidad",value:$entity,inline:true},
        {name:"MP4",value:$mp4,inline:false}
      ]}]}')"
  echo "Discord notificado."
fi

echo ""
echo "DONE. MP4: $MP4_PATH"
