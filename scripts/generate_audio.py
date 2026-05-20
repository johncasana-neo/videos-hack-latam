#!/usr/bin/env python3
"""Audio generation via ElevenLabs TTS with sentence-level timestamps."""
import base64
import json
import os
import subprocess
import sys
import urllib.request
import urllib.error

ELEVENLABS_API_URL = "https://api.elevenlabs.io/v1/text-to-speech"
DEFAULT_VOICE_ID = "pNInz6obpgDQGcFmaJgB"
DEFAULT_MODEL = "eleven_multilingual_v2"


def reconstruct_sentence_times(alignment):
    chars = alignment.get("characters", [])
    starts = alignment.get("character_start_times_seconds", [])
    ends = alignment.get("character_end_times_seconds", [])

    if not chars:
        return []

    sentences = []
    current_start = starts[0]
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

    if not last_period_was_final and (not sentences or current_start < starts[-1] - 0.1):
        sentences.append({"start": round(current_start, 3), "end": round(ends[-1], 3)})

    return sentences


def reconstruct_word_times(alignment):
    chars = alignment.get("characters", [])
    starts = alignment.get("character_start_times_seconds", [])
    ends = alignment.get("character_end_times_seconds", [])

    if not chars:
        return []

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
            words.append({
                "word": word_text,
                "start": round(word_start, 3),
                "end": round(ends[-1], 3) if ends else round(word_start + 0.3, 3),
            })

    return words


def map_to_scene_times(sentences, audio_duration):
    n = len(sentences)

    def t(idx):
        return round(sentences[idx]["start"], 2)

    def fb(pct):
        return round(audio_duration * pct, 2)

    scene_times = {
        "t_intro": t(0) if n >= 1 else 0.0,
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

    return scene_times


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/generate_audio.py <insight_json_path>", file=sys.stderr)
        sys.exit(1)

    insight_path = sys.argv[1]
    audio_out = "assets/voiceover.mp3"
    timestamps_out = "assets/voiceover_timestamps.json"

    api_key = os.environ.get("ELEVENLABS_API_KEY", "")
    voice_id = os.environ.get("ELEVENLABS_VOICE_ID", DEFAULT_VOICE_ID)
    model_id = os.environ.get("ELEVENLABS_MODEL", DEFAULT_MODEL)

    if not api_key:
        print("ERROR: ELEVENLABS_API_KEY is required", file=sys.stderr)
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

    word_count = len(voiceover.split())
    if word_count > 50:
        print(f"ERROR: voiceover tiene {word_count} palabras (max 50 — REGLA 1). Acortar el guion.", file=sys.stderr)
        sys.exit(1)

    payload = json.dumps({
        "text": voiceover,
        "model_id": model_id,
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75,
            "style": 0.4,
            "use_speaker_boost": True,
        },
    }).encode("utf-8")

    url = f"{ELEVENLABS_API_URL}/{voice_id}/with-timestamps"
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "xi-api-key": api_key,
            "Content-Type": "application/json",
        },
        method="POST",
    )

    print("INFO: Calling ElevenLabs TTS with timestamps...", file=sys.stderr)
    try:
        with urllib.request.urlopen(req) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"ERROR: ElevenLabs returned HTTP {e.code}: {e.read().decode()}", file=sys.stderr)
        sys.exit(1)

    audio_b64 = body.get("audio_base64", "")
    if not audio_b64:
        print("ERROR: ElevenLabs response missing audio_base64", file=sys.stderr)
        sys.exit(1)

    alignment = body.get("alignment") or body.get("normalized_alignment")
    if not alignment:
        print("ERROR: ElevenLabs response missing alignment data", file=sys.stderr)
        sys.exit(1)

    os.makedirs(os.path.dirname(audio_out) or ".", exist_ok=True)
    with open(audio_out, "wb") as f:
        f.write(base64.b64decode(audio_b64))

    if os.path.getsize(audio_out) == 0:
        print("ERROR: audio file is empty", file=sys.stderr)
        sys.exit(1)

    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", audio_out],
        capture_output=True, text=True
    )
    duration_str = result.stdout.strip()
    if not duration_str:
        print("ERROR: could not determine MP3 duration", file=sys.stderr)
        sys.exit(1)

    audio_duration = float(duration_str)

    if audio_duration > 25:
        print(f"ERROR: audio dura {audio_duration:.2f}s (max 25s — REGLA 1). Acortar el guion.", file=sys.stderr)
        sys.exit(1)

    sentences = reconstruct_sentence_times(alignment)
    scene_times = map_to_scene_times(sentences, audio_duration)
    words = reconstruct_word_times(alignment)

    timestamps_data = {
        "audio_duration": round(audio_duration, 3),
        "sentences": sentences,
        "scene_times": scene_times,
        "words": words,
    }
    with open(timestamps_out, "w", encoding="utf-8") as f:
        json.dump(timestamps_data, f, indent=2)

    print(f"INFO: Audio → {audio_out} ({audio_duration:.2f}s)", file=sys.stderr)
    print(f"INFO: Timestamps → {timestamps_out} | {len(sentences)} oraciones detectadas", file=sys.stderr)
    for k, v in scene_times.items():
        print(f"INFO:   {k} = {v}s", file=sys.stderr)
    print(f"AUDIO_DURATION_SECONDS={duration_str}")


if __name__ == "__main__":
    main()
