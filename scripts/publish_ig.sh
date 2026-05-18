#!/usr/bin/env bash
# Publish a local MP4 to Instagram Reels using the resumable upload API.
# No public video URL required — the file is uploaded directly to Meta.
# Usage: publish_ig.sh <mp4_path> <insight_json_path>
set -euo pipefail

MP4_PATH="${1:?Usage: publish_ig.sh <mp4_path> <insight_json_path>}"
INSIGHT_JSON="${2:?Usage: publish_ig.sh <mp4_path> <insight_json_path>}"

# Load .env from repo root if present and vars not already set
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/../.env"
if [[ -f "$ENV_FILE" && -z "${IG_ACCESS_TOKEN:-}" ]]; then
  set -a; source "$ENV_FILE"; set +a
fi

: "${IG_ACCESS_TOKEN:?IG_ACCESS_TOKEN required}"
: "${IG_USER_ID:?IG_USER_ID required}"

[[ -f "$MP4_PATH" ]] || { echo "ERROR: MP4 not found: $MP4_PATH" >&2; exit 1; }
[[ -f "$INSIGHT_JSON" ]] || { echo "ERROR: insight not found: $INSIGHT_JSON" >&2; exit 1; }

API="https://graph.facebook.com/v22.0"

TITLE=$(jq -r '.metadata.title // .case.caso_titulo // "Radiografia del Gasto Publico"' "$INSIGHT_JSON")
DESCRIPTION=$(jq -r '.metadata.description // ""' "$INSIGHT_JSON")
HASHTAGS=$(jq -r '.metadata.hashtags // [] | join(" ")' "$INSIGHT_JSON")
CAPTION="${TITLE}

${DESCRIPTION}

${HASHTAGS}

Datos publicos - No es sentencia."

FILE_SIZE=$(wc -c < "$MP4_PATH" | tr -d ' ')

# Step 1: Initialize resumable upload session
echo "INFO: Initializing resumable upload session..." >&2
init_response=$(curl -sS -X POST "${API}/${IG_USER_ID}/media" \
  -H "Authorization: OAuth ${IG_ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d "$(jq -n \
    --arg caption "$CAPTION" \
    '{media_type:"REELS", upload_type:"resumable", caption:$caption, share_to_feed:"true"}')")

container_id=$(echo "$init_response" | jq -r '.id // empty')
upload_uri=$(echo "$init_response" | jq -r '.uri // empty')

[[ -n "$container_id" && -n "$upload_uri" ]] || {
  echo "ERROR: Failed to initialize upload session: $init_response" >&2
  exit 1
}
echo "INFO: container_id=${container_id}" >&2
echo "INFO: upload_uri=${upload_uri}" >&2

# Step 2: Upload the video file directly to Meta
echo "INFO: Uploading ${MP4_PATH} (${FILE_SIZE} bytes)..." >&2
upload_response=$(curl -sS -X POST "$upload_uri" \
  -H "Authorization: OAuth ${IG_ACCESS_TOKEN}" \
  -H "offset: 0" \
  -H "file_size: ${FILE_SIZE}" \
  -H "Content-Type: video/mp4" \
  --data-binary "@${MP4_PATH}")

upload_success=$(echo "$upload_response" | jq -r '.success // .h // empty')
[[ -n "$upload_success" ]] || {
  echo "ERROR: Upload failed: $upload_response" >&2
  exit 1
}
echo "INFO: Upload complete: $upload_response" >&2

# Step 3: Wait for Meta to process the uploaded video
echo "INFO: Waiting for processing..." >&2
status="IN_PROGRESS"
for i in $(seq 1 30); do
  sleep 10
  status_response=$(curl -sS "${API}/${container_id}?fields=status_code&access_token=${IG_ACCESS_TOKEN}")
  status=$(echo "$status_response" | jq -r '.status_code // "UNKNOWN"')
  echo "INFO: attempt=${i} status=${status}" >&2
  [[ "$status" == "FINISHED" ]] && break
  [[ "$status" == "ERROR" || "$status" == "EXPIRED" ]] && {
    echo "ERROR: Container reached ${status}: ${status_response}" >&2
    exit 1
  }
done
[[ "$status" == "FINISHED" ]] || {
  echo "ERROR: Timed out waiting for Instagram processing (last: ${status})" >&2
  exit 1
}

# Step 4: Publish the processed container
echo "INFO: Publishing Reel..." >&2
publish_response=$(curl -sS -X POST "${API}/${IG_USER_ID}/media_publish" \
  -d "creation_id=${container_id}" \
  -d "access_token=${IG_ACCESS_TOKEN}")

media_id=$(echo "$publish_response" | jq -r '.id // empty')
[[ -n "$media_id" ]] || {
  echo "ERROR: Publish failed: $publish_response" >&2
  exit 1
}
echo "INFO: Published. media_id=${media_id}"
