#!/usr/bin/env python3
"""
AIRA TTS Voice Engine (Raspberry Pi 3B+ Compatible)
Supports:
  1. Female Hindi & Hinglish: "hi-IN-SwaraNeural" (Neural, online, warm conversational elder-care tone)
  2. Female Indian English:   "en-IN-NeerjaNeural" (Neural, online, polite clear Indian accent)
  3. Female Hindi (Offline):  "hi_IN-priyamvada-medium" (Piper ONNX offline neural)
  4. Female Hindi (Fallback): "hi+f3" (espeak-ng offline, 0MB RAM)
  5. Female Eng-IN (Fallback): "en-in+f2" (espeak-ng offline, 0MB RAM)

Includes Bluetooth speaker silence padding (0.6s lead, 0.4s tail) so Bluetooth sinks (like Stone 620)
do not clip initial syllables.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import shutil
import subprocess
import sys
import wave

VOICE_PROFILES = {
    "swara": {
        "engine": "edge",
        "voice": "hi-IN-SwaraNeural",
        "lang": "hi-IN / Hinglish",
        "description": "Female Hindi & Hinglish - Gold standard for conversational elder companion",
    },
    "neerja": {
        "engine": "edge",
        "voice": "en-IN-NeerjaNeural",
        "lang": "en-IN",
        "description": "Female Indian English - Clear, polite, natural cadence",
    },
    "priyamvada": {
        "engine": "piper",
        "model": "hi_IN-priyamvada-medium",
        "lang": "hi-IN",
        "description": "Female Hindi - Local offline neural ONNX model (~60MB)",
    },
    "espeak-hi": {
        "engine": "espeak",
        "voice": "hi+f3",
        "lang": "hi",
        "description": "Female Hindi - Offline zero-dependency instant fallback",
    },
    "espeak-en": {
        "engine": "espeak",
        "voice": "en-in+f2",
        "lang": "en-IN",
        "description": "Female Indian English - Offline zero-dependency instant fallback",
    },
}

DEFAULT_TMP_WAV = "/tmp/aira_tts_output.wav"
DEFAULT_PAD_WAV = "/tmp/aira_tts_padded.wav"


def pad_wav(src_path: str, dst_path: str, lead_sec: float = 0.6, tail_sec: float = 0.4) -> None:
    """Add silence before and after speech so Bluetooth speakers do not clip audio."""
    with wave.open(src_path, "rb") as src:
        params = src.getparams()
        nchannels = params.nchannels
        sampwidth = params.sampwidth
        framerate = params.framerate
        src_frames = src.readframes(params.nframes)

    lead_frames = int(framerate * lead_sec)
    tail_frames = int(framerate * tail_sec)
    silence_byte = b"\x00" * sampwidth * nchannels

    with wave.open(dst_path, "wb") as dst:
        dst.setparams(params)
        dst.writeframes(silence_byte * lead_frames)
        dst.writeframes(src_frames)
        dst.writeframes(silence_byte * tail_frames)


def play_audio(wav_path: str, sink: str | None = None) -> None:
    """Plays audio through PipeWire/Pulse (paplay) or ALSA (aplay)."""
    if shutil.which("paplay"):
        cmd = ["paplay"]
        if sink:
            cmd.extend(["-d", sink])
        cmd.append(wav_path)
    elif shutil.which("aplay"):
        cmd = ["aplay", wav_path]
    else:
        print(f"Error: Neither paplay nor aplay is available to play {wav_path}", file=sys.stderr)
        return

    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as err:
        print(f"Audio playback error: {err}", file=sys.stderr)


async def synth_edge_tts(text: str, voice: str, out_wav: str) -> bool:
    """Synthesize speech using Microsoft Neural Edge TTS."""
    try:
        import edge_tts
    except ImportError:
        print("edge-tts is not installed. Run: pip install edge-tts", file=sys.stderr)
        return False

    out_mp3 = out_wav.replace(".wav", ".mp3")
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(out_mp3)

    # Convert MP3 to 16kHz/22kHz WAV for low-latency playback on PipeWire
    if shutil.which("ffmpeg"):
        subprocess.run(
            ["ffmpeg", "-y", "-i", out_mp3, "-ar", "22050", "-ac", "1", out_wav],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
    elif shutil.which("mpg123"):
        subprocess.run(
            ["mpg123", "-w", out_wav, out_mp3],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
    else:
        # If ffmpeg/mpg123 not available, paplay can often play mp3 directly
        shutil.copy(out_mp3, out_wav)

    return os.path.exists(out_wav)


def synth_piper_tts(text: str, model_name: str, out_wav: str) -> bool:
    """Synthesize speech using Piper local ONNX model."""
    models_dir = os.path.expanduser("~/aira/models")
    onnx_path = os.path.join(models_dir, f"{model_name}.onnx")

    if not os.path.exists(onnx_path):
        print(f"Piper model not found at {onnx_path}.", file=sys.stderr)
        print(f"Download with: python aira_tts.py download-piper --model {model_name}", file=sys.stderr)
        return False

    # Check for piper CLI or python piper
    if shutil.which("piper"):
        p = subprocess.Popen(
            ["piper", "--model", onnx_path, "--output_file", out_wav],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
        _, err = p.communicate(input=text)
        return p.returncode == 0
    else:
        # Fallback to python piper module
        try:
            from piper import PiperVoice
            voice = PiperVoice.load(onnx_path)
            with wave.open(out_wav, "wb") as wav_file:
                voice.synthesize(text, wav_file)
            return True
        except ImportError:
            print("Piper CLI or python module not installed. Run: pip install piper-tts", file=sys.stderr)
            return False


def synth_espeak(text: str, voice_code: str, out_wav: str) -> bool:
    """Synthesize speech using lightweight local espeak-ng."""
    cmd = ["espeak-ng", "-v", voice_code, "-s", "145", "-p", "65", "-w", out_wav, text]
    try:
        subprocess.run(cmd, check=True)
        return True
    except subprocess.CalledProcessError as err:
        print(f"espeak-ng error: {err}", file=sys.stderr)
        return False


def speak(
    text: str,
    voice_key: str = "swara",
    sink: str | None = None,
    lead_sec: float = 0.6,
    tail_sec: float = 0.4,
) -> bool:
    """Synthesizes text and plays it through the Bluetooth speaker."""
    profile = VOICE_PROFILES.get(voice_key.lower())
    if not profile:
        print(f"Unknown voice profile '{voice_key}'. Available: {list(VOICE_PROFILES.keys())}", file=sys.stderr)
        return False

    engine = profile["engine"]
    raw_wav = DEFAULT_TMP_WAV
    pad_wav_path = DEFAULT_PAD_WAV
    success = False

    print(f"🔊 Synthesizing [{profile['lang']}] using '{voice_key}'...")
    print(f"   Text: \"{text}\"")

    if engine == "edge":
        try:
            success = asyncio.run(synth_edge_tts(text, profile["voice"], raw_wav))
        except Exception as e:
            print(f"Edge TTS online synthesis failed ({e}). Falling back to local offline...", file=sys.stderr)
            # Automatic fallback to local offline voice
            fallback_voice = "espeak-hi" if "hi" in profile["lang"].lower() or "hinglish" in profile["lang"].lower() else "espeak-en"
            return speak(text, voice_key=fallback_voice, sink=sink, lead_sec=lead_sec, tail_sec=tail_sec)
    elif engine == "piper":
        success = synth_piper_tts(text, profile["model"], raw_wav)
    elif engine == "espeak":
        success = synth_espeak(text, profile["voice"], raw_wav)

    if not success or not os.path.exists(raw_wav):
        print("Synthesis failed to create audio file.", file=sys.stderr)
        return False

    # Pad with silence for Bluetooth speaker connection wake
    try:
        pad_wav(raw_wav, pad_wav_path, lead_sec=lead_sec, tail_sec=tail_sec)
        play_audio(pad_wav_path, sink=sink)
    except Exception as e:
        print(f"Playback error: {e}", file=sys.stderr)
        play_audio(raw_wav, sink=sink)

    return True


def download_piper_model(model_name: str = "hi_IN-priyamvada-medium") -> bool:
    """Downloads the Priyamvada Hindi Female ONNX model from Hugging Face."""
    models_dir = os.path.expanduser("~/aira/models")
    os.makedirs(models_dir, exist_ok=True)

    base_url = "https://huggingface.co/rhasspy/piper-voices/resolve/main"
    if model_name == "hi_IN-priyamvada-medium":
        subpath = "hi/hi_IN/priyamvada/medium"
    else:
        print(f"Unknown model name {model_name}", file=sys.stderr)
        return False

    onnx_file = f"{model_name}.onnx"
    json_file = f"{model_name}.onnx.json"

    onnx_url = f"{base_url}/{subpath}/{onnx_file}"
    json_url = f"{base_url}/{subpath}/{json_file}"

    out_onnx = os.path.join(models_dir, onnx_file)
    out_json = os.path.join(models_dir, json_file)

    print(f"📥 Downloading {onnx_file} to {models_dir}...")
    subprocess.run(["wget", "-q", "--show-progress", "-O", out_onnx, onnx_url], check=True)
    print(f"📥 Downloading {json_file}...")
    subprocess.run(["wget", "-q", "--show-progress", "-O", out_json, json_url], check=True)

    print(f"✅ Successfully downloaded {model_name} to {models_dir}!")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="AIRA Voice Synthesis & Audio Test Tool")
    subparsers = parser.add_subparsers(dest="command")

    # List voices command
    subparsers.add_parser("voices", help="List available female English, Hindi, and Hinglish voice profiles")

    # Speak command
    speak_cmd = subparsers.add_parser("speak", help="Speak text through the speaker")
    speak_cmd.add_argument("--voice", "-v", default="swara", choices=list(VOICE_PROFILES.keys()), help="Voice profile name")
    speak_cmd.add_argument("--text", "-t", required=True, help="Text to speak")
    speak_cmd.add_argument("--sink", "-s", help="PulseAudio/PipeWire sink name or index")

    # Test demo command
    test_cmd = subparsers.add_parser("test-all", help="Test demo phrases in English, Hindi, and Hinglish")
    test_cmd.add_argument("--sink", "-s", help="PulseAudio/PipeWire sink name or index")

    # Download Piper command
    down_cmd = subparsers.add_parser("download-piper", help="Download offline Piper Hindi female model")
    down_cmd.add_argument("--model", default="hi_IN-priyamvada-medium", help="Piper model name")

    args = parser.parse_args()

    if args.command == "voices":
        print("\n=== AIRA Female Voice Profiles ===")
        for key, info in VOICE_PROFILES.items():
            print(f"• {key:12} [{info['lang']:18}] : {info['description']}")
        print()
    elif args.command == "download-piper":
        download_piper_model(args.model)
    elif args.command == "test-all":
        print("\n--- 1. Testing English (Female: Neerja) ---")
        speak("Hello! I am Aira, your personal health and companion assistant.", voice_key="neerja", sink=args.sink)

        print("\n--- 2. Testing Hindi (Female: Swara) ---")
        speak("नमस्ते! मैं आइरा हूँ, आपकी देखभाल और सेहत की साथी।", voice_key="swara", sink=args.sink)

        print("\n--- 3. Testing Hinglish (Female: Swara) ---")
        speak("Good morning Dadi! Aapki BP ki medicine lene ka time ho gaya hai.", voice_key="swara", sink=args.sink)
    elif args.command == "speak":
        speak(args.text, voice_key=args.voice, sink=args.sink)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
