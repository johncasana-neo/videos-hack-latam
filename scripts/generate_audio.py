#!/usr/bin/env python3
"""Windows-compatible audio generation via MiniMax TTS."""
import json
import os
import subprocess
import sys
import tempfile
import urllib.request
import urllib.error

def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/generate_audio.py <insight_json_path>", file=sys.stderr)
        sys.exit(1)

    insight_path = sys.argv[1]
    audio_out = "assets/voiceover.mp3"

    api_key = os.environ.get("MINIMAX_API_KEY", "")
    group_id = os.environ.get("MINIMAX_GROUP_ID", "")

    if not api_key:
        print("ERROR: MINIMAX_API_KEY is required", file=sys.stderr)
        sys.exit(1)
    if not group_id:
        print("ERROR: MINIMAX_GROUP_ID is required", file=sys.stderr)
        sys.exit(1)
    if not os.path.isfile(insight_path):
        print(f"ERROR: insight not found: {insight_path}", file=sys.stderr)
        sys.exit(1)

    with open(insight_path, encoding="utf-8") as f:
        insight = json.load(f)

    voiceover = (
        insight.get("script", {}).get("voiceover_text_full")
        or insight.get("voiceover_text_full", "")
    )
    if not voiceover:
        print("ERROR: script.voiceover_text_full missing", file=sys.stderr)
        sys.exit(1)

    payload = json.dumps({
        "model": "speech-2.6-hd",
        "text": voiceover,
        "stream": False,
        "language_boost": "Spanish",
        "output_format": "hex",
        "voice_setting": {
            "voice_id": "Spanish_CaptivatingStoryteller",
            "speed": 1.05,
            "pitch": -1,
            "emotion": "neutral"
        },
        "audio_setting": {
            "format": "mp3",
            "sample_rate": 32000,
            "bitrate": 128000,
            "channel": 1
        }
    }).encode("utf-8")

    url = f"https://api.minimax.io/v1/t2a_v2?GroupId={group_id}"
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    print("INFO: Calling MiniMax TTS...", file=sys.stderr)
    try:
        with urllib.request.urlopen(req) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"ERROR: MiniMax returned HTTP {e.code}: {e.read().decode()}", file=sys.stderr)
        sys.exit(1)

    api_status = body.get("base_resp", {}).get("status_code", -1)
    if api_status != 0:
        msg = body.get("base_resp", {}).get("status_msg", "unknown")
        print(f"ERROR: MiniMax status_code={api_status}: {msg}", file=sys.stderr)
        sys.exit(1)

    hex_audio = body.get("data", {}).get("audio") or body.get("audio_file", "")
    if not hex_audio:
        print("ERROR: MiniMax response did not include hex audio", file=sys.stderr)
        sys.exit(1)

    os.makedirs(os.path.dirname(audio_out) or ".", exist_ok=True)
    with open(audio_out, "wb") as f:
        f.write(bytes.fromhex(hex_audio))

    if os.path.getsize(audio_out) == 0:
        print("ERROR: decoded MP3 is empty", file=sys.stderr)
        sys.exit(1)

    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", audio_out],
        capture_output=True, text=True
    )
    duration = result.stdout.strip()
    if not duration:
        print("ERROR: could not determine MP3 duration", file=sys.stderr)
        sys.exit(1)

    print(f"INFO: Audio saved to {audio_out} ({duration}s)", file=sys.stderr)
    print(f"AUDIO_DURATION_SECONDS={duration}")

if __name__ == "__main__":
    main()
