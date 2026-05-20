#!/usr/bin/env bash
# Upload an MP4 to a GitHub Release and print its public download URL.
# Usage: upload_github_release.sh <mp4_path>
# Requires: GITHUB_TOKEN env var with repo scope.
set -euo pipefail

MP4_PATH="${1:?Usage: upload_github_release.sh <mp4_path>}"
[[ -f "$MP4_PATH" ]] || { echo "ERROR: MP4 not found: $MP4_PATH" >&2; exit 1; }

# Load .env from repo root if present and vars not already set
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/../.env"
if [[ -f "$ENV_FILE" && -z "${GITHUB_TOKEN:-}" ]]; then
  set -a; source "$ENV_FILE"; set +a
fi

: "${GITHUB_TOKEN:?GITHUB_TOKEN required (Personal Access Token with repo scope)}"

REPO="johncasana-neo/videos-hack-latam"
FILENAME="$(basename "$MP4_PATH")"
# Extract date from filename like radiografia-2026_05_17.mp4, else use today
DATE_TAG="$(echo "$FILENAME" | grep -oP '\d{4}_\d{2}_\d{2}' | head -1 || date +%Y_%m_%d)"
TAG="video-${DATE_TAG}"
RELEASE_NAME="Video ${DATE_TAG//_/-}"

echo "INFO: repo=$REPO tag=$TAG file=$FILENAME" >&2

# Create release (or get existing one if tag already exists)
create_response=$(curl -sS -X POST \
  -H "Authorization: Bearer ${GITHUB_TOKEN}" \
  -H "Accept: application/vnd.github+json" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  "https://api.github.com/repos/${REPO}/releases" \
  -d "{\"tag_name\":\"${TAG}\",\"name\":\"${RELEASE_NAME}\",\"draft\":false,\"prerelease\":false}")

release_id=$(echo "$create_response" | jq -r '.id // empty')

# If release already exists for this tag, fetch its id
if [[ -z "$release_id" ]]; then
  echo "INFO: Release already exists for tag ${TAG}, fetching..." >&2
  existing=$(curl -sS \
    -H "Authorization: Bearer ${GITHUB_TOKEN}" \
    -H "Accept: application/vnd.github+json" \
    -H "X-GitHub-Api-Version: 2022-11-28" \
    "https://api.github.com/repos/${REPO}/releases/tags/${TAG}")
  release_id=$(echo "$existing" | jq -r '.id // empty')
fi

[[ -n "$release_id" ]] || {
  echo "ERROR: Could not create or fetch release: $create_response" >&2
  exit 1
}
echo "INFO: release_id=${release_id}" >&2

# Delete existing asset with same name if present (allows re-upload)
existing_asset_id=$(curl -sS \
  -H "Authorization: Bearer ${GITHUB_TOKEN}" \
  -H "Accept: application/vnd.github+json" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  "https://api.github.com/repos/${REPO}/releases/${release_id}/assets" \
  | jq -r --arg name "$FILENAME" '.[] | select(.name==$name) | .id // empty' | head -1)

if [[ -n "$existing_asset_id" ]]; then
  echo "INFO: Deleting existing asset id=${existing_asset_id}" >&2
  curl -sS -X DELETE \
    -H "Authorization: Bearer ${GITHUB_TOKEN}" \
    -H "Accept: application/vnd.github+json" \
    -H "X-GitHub-Api-Version: 2022-11-28" \
    "https://api.github.com/repos/${REPO}/releases/assets/${existing_asset_id}"
fi

# Upload asset
echo "INFO: Uploading ${FILENAME} to release ${TAG}..." >&2
upload_response=$(curl -sS -X POST \
  -H "Authorization: Bearer ${GITHUB_TOKEN}" \
  -H "Accept: application/vnd.github+json" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  -H "Content-Type: video/mp4" \
  --data-binary "@${MP4_PATH}" \
  "https://uploads.github.com/repos/${REPO}/releases/${release_id}/assets?name=${FILENAME}")

browser_url=$(echo "$upload_response" | jq -r '.browser_download_url // empty')
[[ -n "$browser_url" ]] || {
  echo "ERROR: Upload failed: $upload_response" >&2
  exit 1
}

echo "INFO: Uploaded. URL: ${browser_url}" >&2
echo "$browser_url"
