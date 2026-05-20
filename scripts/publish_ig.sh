#!/usr/bin/env bash
set -euo pipefail

MP4_PATH="${1:?Usage: publish_ig.sh <mp4_path> <insight_json_path>}"
INSIGHT_JSON="${2:?Usage: publish_ig.sh <mp4_path> <insight_json_path>}"

: "${IG_ACCESS_TOKEN:?IG_ACCESS_TOKEN required}"
: "${IG_USER_ID:?IG_USER_ID required}"

[[ -f "$MP4_PATH" ]]     || { echo "ERROR: MP4 not found: $MP4_PATH" >&2; exit 1; }
[[ -f "$INSIGHT_JSON" ]] || { echo "ERROR: insight not found: $INSIGHT_JSON" >&2; exit 1; }

API="https://graph.facebook.com/v22.0"
FILE_SIZE=$(stat -c%s "$MP4_PATH")

TITLE=$(jq -r '.metadata.title // .case.caso_titulo // "Radiografia del Gasto Publico"' "$INSIGHT_JSON")
DESCRIPTION=$(jq -r '.metadata.description // ""' "$INSIGHT_JSON")
HASHTAGS=$(jq -r '.metadata.hashtags // [] | join(" ")' "$INSIGHT_JSON")
CAPTION="${TITLE}

${DESCRIPTION}

${HASHTAGS}

Datos públicos · No es sentencia."

# Step 1: Create media container → Graph API returns upload_url
echo "INFO: Creating Reels container..." >&2
container_response=$(curl -sS -X POST "${API}/${IG_USER_ID}/media" \
  -F "media_type=REELS" \
  -F "share_to_feed=true" \
  -F "access_token=${IG_ACCESS_TOKEN}" \
  -F "caption=${CAPTION}")

container_id=$(echo "$container_response" | jq -r '.id // empty')
upload_url=$(echo "$container_response"   | jq -r '.upload_url // empty')
[[ -n "$container_id" ]] || { echo "ERROR: Container creation failed: $container_response" >&2; exit 1; }
echo "INFO: container_id=$container_id" >&2

# Step 2: Upload binary to upload_url (resumable, single chunk)
if [[ -n "$upload_url" ]]; then
  echo "INFO: Uploading video to upload_url (${FILE_SIZE} bytes)..." >&2
  curl -sS -X POST "$upload_url" \
    -H "Authorization: OAuth ${IG_ACCESS_TOKEN}" \
    -H "X-Entity-Length: ${FILE_SIZE}" \
    -H "X-Entity-Offset: 0" \
    --data-binary "@${MP4_PATH}" >&2
  echo "INFO: Upload complete." >&2
else
  echo "INFO: No upload_url returned — container will process asynchronously." >&2
fi

# Step 3: Poll until FINISHED (max 5 min)
echo "INFO: Waiting for processing..." >&2
status="IN_PROGRESS"
for i in $(seq 1 30); do
  sleep 10
  status=$(curl -sS "${API}/${container_id}?fields=status_code&access_token=${IG_ACCESS_TOKEN}" \
    | jq -r '.status_code // "UNKNOWN"')
  echo "INFO: attempt=${i} status=${status}" >&2
  [[ "$status" == "FINISHED" ]] && break
  [[ "$status" == "ERROR" || "$status" == "EXPIRED" ]] && {
    echo "ERROR: Container reached ${status}" >&2; exit 1
  }
done
[[ "$status" == "FINISHED" ]] || { echo "ERROR: Timed out waiting (last: ${status})" >&2; exit 1; }

# Step 4: Publish
echo "INFO: Publishing Reel..." >&2
publish_response=$(curl -sS -X POST "${API}/${IG_USER_ID}/media_publish" \
  -d "creation_id=${container_id}" \
  -d "access_token=${IG_ACCESS_TOKEN}")

media_id=$(echo "$publish_response" | jq -r '.id // empty')
[[ -n "$media_id" ]] || { echo "ERROR: Publish failed: $publish_response" >&2; exit 1; }
echo "INFO: Published. media_id=${media_id}"
