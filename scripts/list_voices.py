#!/usr/bin/env python3
"""List available MiniMax voices for current account."""
import json
import os
import sys
import urllib.request

api_key = os.environ.get("MINIMAX_API_KEY", "")
group_id = os.environ.get("MINIMAX_GROUP_ID", "")

if not api_key or not group_id:
    print("ERROR: MINIMAX_API_KEY and MINIMAX_GROUP_ID required", file=sys.stderr)
    sys.exit(1)

url = f"https://api.minimax.io/v1/get_voice?GroupId={group_id}"
req = urllib.request.Request(
    url,
    data=json.dumps({"voice_type": "all"}).encode("utf-8"),
    headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    },
    method="POST",
)

with urllib.request.urlopen(req) as resp:
    body = json.loads(resp.read().decode("utf-8"))

system_voices = body.get("system_voice", [])
print(f"Total system voices: {len(system_voices)}\n")

spanish = [v for v in system_voices if "spanish" in v.get("voice_id", "").lower()
           or "spanish" in v.get("voice_name", "").lower()]

print(f"Spanish voices ({len(spanish)}):")
for v in spanish:
    print(f"  - {v.get('voice_id')} | {v.get('voice_name')}")

print(f"\nFirst 20 voice IDs (all languages):")
for v in system_voices[:20]:
    print(f"  - {v.get('voice_id')} | {v.get('voice_name')}")
