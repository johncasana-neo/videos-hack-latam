#!/usr/bin/env bash
set -euo pipefail

MP4_PATH="${1:?Usage: scripts/publish_buffer.sh <mp4_path> <insight_json_path>}"
INSIGHT_JSON="${2:?Usage: scripts/publish_buffer.sh <mp4_path> <insight_json_path>}"
TMP_RESPONSE="$(mktemp)"

cleanup() {
  rm -f "$TMP_RESPONSE"
}
trap cleanup EXIT

[[ -f "$MP4_PATH" ]] || { echo "ERROR: MP4 not found: $MP4_PATH" >&2; exit 1; }
[[ -f "$INSIGHT_JSON" ]] || { echo "ERROR: insight not found: $INSIGHT_JSON" >&2; exit 1; }

for name in BUFFER_ACCESS_TOKEN BUFFER_IG_PROFILE_ID; do
  [[ -n "${!name:-}" ]] || { echo "ERROR: $name is required" >&2; exit 1; }
done

TITLE="$(jq -r '.metadata.title // .case.caso_titulo // "Radiografia del Gasto Publico"' "$INSIGHT_JSON")"
DESCRIPTION="$(jq -r '.metadata.description // ""' "$INSIGHT_JSON")"
HASHTAGS="$(jq -r '.metadata.hashtags // [] | join(" ")' "$INSIGHT_JSON")"
POST_TEXT="${TITLE}

${DESCRIPTION}

${HASHTAGS}"

SCHEDULED_AT="$(TZ=America/Lima date -d '19:00 today' +%s)"
if [[ "$SCHEDULED_AT" -le "$(date +%s)" ]]; then
  SCHEDULED_AT="$(TZ=America/Lima date -d '19:00 tomorrow' +%s)"
fi

declare -A PROFILES=(
  ["Instagram"]="$BUFFER_IG_PROFILE_ID"
)

failures=()
for platform in "${!PROFILES[@]}"; do
  profile_id="${PROFILES[$platform]}"
  echo "INFO: scheduling $platform profile=$profile_id at unix=$SCHEDULED_AT" >&2

  http_status="$(curl -sS -w "%{http_code}" -o "$TMP_RESPONSE" \
    -X POST "https://api.bufferapp.com/1/updates/create.json" \
    -F "access_token=${BUFFER_ACCESS_TOKEN}" \
    -F "profile_ids[]=${profile_id}" \
    -F "text=${POST_TEXT}" \
    -F "scheduled_at=${SCHEDULED_AT}" \
    -F "media[video]=@${MP4_PATH};type=video/mp4")"

  if [[ "$http_status" != "200" ]]; then
    echo "ERROR: Buffer HTTP $http_status for $platform" >&2
    cat "$TMP_RESPONSE" >&2
    failures+=("$platform")
    continue
  fi

  success="$(jq -r '.success // false' "$TMP_RESPONSE" 2>/dev/null)"
  if [[ "$success" != "true" ]]; then
    echo "ERROR: Buffer rejected $platform: $(jq -r '.message // "unknown"' "$TMP_RESPONSE" 2>/dev/null)" >&2
    cat "$TMP_RESPONSE" >&2
    failures+=("$platform")
    continue
  fi

  echo "INFO: Buffer scheduled $platform: $(jq -c '.updates // .update // .' "$TMP_RESPONSE")" >&2
done

if [[ "${#failures[@]}" -gt 0 ]]; then
  echo "ERROR: Buffer publishing failed for: ${failures[*]}" >&2
  exit 1
fi

echo "INFO: Buffer publishing completed"
