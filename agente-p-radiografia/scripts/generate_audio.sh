#!/usr/bin/env bash
set -euo pipefail

INSIGHT_JSON="${1:?Usage: scripts/generate_audio.sh <insight_json_path>}"
AUDIO_OUT="assets/voiceover.mp3"
TMP_RESPONSE="$(mktemp)"

cleanup() {
  rm -f "$TMP_RESPONSE"
}
trap cleanup EXIT

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "ERROR: required command not found: $1" >&2
    exit 1
  }
}

require_cmd curl
require_cmd jq
require_cmd xxd
require_cmd ffprobe

[[ -f "$INSIGHT_JSON" ]] || { echo "ERROR: insight not found: $INSIGHT_JSON" >&2; exit 1; }
[[ -n "${MINIMAX_API_KEY:-}" ]] || { echo "ERROR: MINIMAX_API_KEY is required" >&2; exit 1; }
[[ -n "${MINIMAX_GROUP_ID:-}" ]] || { echo "ERROR: MINIMAX_GROUP_ID is required" >&2; exit 1; }

VOICEOVER_TEXT="$(jq -r '.script.voiceover_text_full // .voiceover_text_full // empty' "$INSIGHT_JSON")"
[[ -n "$VOICEOVER_TEXT" ]] || { echo "ERROR: script.voiceover_text_full missing" >&2; exit 1; }

REQUEST_BODY="$(jq -n --arg text "$VOICEOVER_TEXT" '{
  model: "speech-2.6-hd",
  text: $text,
  stream: false,
  language_boost: "Spanish",
  output_format: "hex",
  voice_setting: {
    voice_id: "Spanish_CaptivatingStoryteller",
    speed: 1.15,
    pitch: -1,
    emotion: "neutral"
  },
  audio_setting: {
    format: "mp3",
    sample_rate: 32000,
    bitrate: 128000,
    channel: 1
  }
}')"

HTTP_STATUS="$(curl -sS -w "%{http_code}" -o "$TMP_RESPONSE" \
  -X POST "https://api.minimax.io/v1/t2a_v2?GroupId=${MINIMAX_GROUP_ID}" \
  -H "Authorization: Bearer ${MINIMAX_API_KEY}" \
  -H "Content-Type: application/json" \
  -d "$REQUEST_BODY")"

if [[ "$HTTP_STATUS" != "200" ]]; then
  echo "ERROR: MiniMax returned HTTP $HTTP_STATUS" >&2
  cat "$TMP_RESPONSE" >&2
  exit 1
fi

API_STATUS="$(jq -r '.base_resp.status_code // -1' "$TMP_RESPONSE")"
if [[ "$API_STATUS" != "0" ]]; then
  echo "ERROR: MiniMax status_code=$API_STATUS: $(jq -r '.base_resp.status_msg // "unknown"' "$TMP_RESPONSE")" >&2
  exit 1
fi

HEX_AUDIO="$(jq -r '.data.audio // .audio_file // empty' "$TMP_RESPONSE")"
[[ -n "$HEX_AUDIO" ]] || { echo "ERROR: MiniMax response did not include hex audio" >&2; exit 1; }

mkdir -p "$(dirname "$AUDIO_OUT")"
printf "%s" "$HEX_AUDIO" | xxd -r -p > "$AUDIO_OUT"
[[ -s "$AUDIO_OUT" ]] || { echo "ERROR: decoded MP3 is empty" >&2; exit 1; }

DURATION="$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$AUDIO_OUT")"
[[ "$DURATION" =~ ^[0-9]+(\.[0-9]+)?$ ]] || { echo "ERROR: invalid MP3 duration: $DURATION" >&2; exit 1; }

echo "AUDIO_DURATION_SECONDS=$DURATION"
