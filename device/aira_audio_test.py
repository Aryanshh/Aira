#!/usr/bin/env python3
"""
AIRA Audio Test & Wake-Word Loop (Raspberry Pi 3B+)
Runs offline wake-word detection using Vosk, mutes microphone during response,
and plays high-fidelity spoken response via aira_tts (Swara Female Hindi).
"""

from __future__ import annotations

import argparse
import json
import os
import queue
import re
import shutil
import subprocess
import sys
import time
import wave

try:
    import numpy as np
    import sounddevice as sd
except ImportError:
    np = None
    sd = None

try:
    from vosk import KaldiRecognizer, Model
except ImportError:
    KaldiRecognizer = None
    Model = None

# Import our modular multi-voice TTS engine
try:
    from aira_tts import speak as tts_speak
except ImportError:
    tts_speak = None

TARGET_RATE = 16000
DEFAULT_MODEL = os.environ.get(
    "AIRA_VOSK_MODEL",
    os.path.expanduser("~/aira/models/vosk-model-small-en-us-0.15"),
)
DEFAULT_REPLY = "नमस्ते! आपकी दोपहर की दवा तैयार है, क्या आपने खाना खा लिया?"
DEFAULT_VOICE = "swara"

HEADS = ["hey", "hay", "hi", "hello", "ok", "okay", "namaste", "suno", "arey"]
STRONG_NAMES = ["aira", "airah", "ayra", "eira", "aaira"]
NAMES = STRONG_NAMES + ["ira", "era", "aria", "arya", "aera", "ayara"]


def heard_wake_word(text: str) -> bool:
    """Fuzzy matching for 'Hey Aira' and colloquial variations."""
    cleaned = re.sub(r"[^a-zA-Z\s]", " ", text.lower())
    # Handle split syllables like 'i ra' or 'ay ra'
    cleaned = re.sub(r"\b(i|ay|ai)\s+(ra|rah)\b", "aira", cleaned)
    tokens = [w for w in cleaned.split() if w]

    if not tokens:
        return False

    for i, tok in enumerate(tokens):
        # 1. Any strong name standalone ("aira")
        if tok in STRONG_NAMES:
            return True
        # 2. Head word + any name ("hey aira", "namaste aira", "hi aria")
        if tok in HEADS and i + 1 < len(tokens):
            if tokens[i + 1] in NAMES:
                return True

    return False


def parse_device(value: str | None) -> int | str | None:
    """Convert device argument to integer index if possible, else substring."""
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return value


def to_mono(block: np.ndarray) -> np.ndarray:
    """Averages channels to mono if multichannel."""
    if block.ndim == 1:
        return block
    return np.mean(block, axis=1)


def to_16k(samples: np.ndarray, rate: int) -> np.ndarray:
    """Resample audio block to 16 kHz."""
    if rate == TARGET_RATE:
        return samples
    if rate % TARGET_RATE == 0:
        step = rate // TARGET_RATE
        return samples[: len(samples) - (len(samples) % step) : step]
    # Linear interpolation for non-integer ratios (e.g. 44100 -> 16000)
    dur = len(samples) / rate
    out_len = int(dur * TARGET_RATE)
    if out_len <= 0:
        return np.zeros(0, dtype=samples.dtype)
    orig_idx = np.linspace(0, len(samples) - 1, num=out_len)
    return np.interp(orig_idx, np.arange(len(samples)), samples)


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


def speak(text: str = DEFAULT_REPLY, sink: str | None = None, voice: str = DEFAULT_VOICE) -> None:
    """Speaks text using aira_tts (Swara Neural) with espeak-ng fallback."""
    if tts_speak:
        tts_speak(text, voice_key=voice, sink=sink)
        return

    # Direct fallback if aira_tts module not present
    tmp_raw = "/tmp/aira_reply_raw.wav"
    tmp_pad = "/tmp/aira_reply.wav"
    # Try espeak-ng Hindi female or default
    voice_arg = "hi+f3" if voice in ("swara", "priyamvada", "espeak-hi") else "en-us"
    subprocess.run(["espeak-ng", "-v", voice_arg, "-s", "145", "-p", "60", "-w", tmp_raw, text], check=True)
    pad_wav(tmp_raw, tmp_pad)
    play_audio(tmp_pad, sink=sink)


def cmd_devices() -> None:
    """Lists audio input and output devices."""
    if sd is None:
        print("sounddevice is not installed. Run: pip install sounddevice", file=sys.stderr)
        return

    print("=== Audio Devices ===")
    devices = sd.query_devices()
    for idx, dev in enumerate(devices):
        in_ch = dev.get("max_input_channels", 0)
        out_ch = dev.get("max_output_channels", 0)
        marker = ""
        if idx == sd.default.device[0]:
            marker += " [Default IN]"
        if idx == sd.default.device[1]:
            marker += " [Default OUT]"
        kind = []
        if in_ch > 0:
            kind.append(f"IN:{in_ch}")
        if out_ch > 0:
            kind.append(f"OUT:{out_ch}")
        print(f"  [{idx:2d}] {dev['name']:<42} ({', '.join(kind)}){marker}")
    print()


def cmd_speaker(reply: str = DEFAULT_REPLY, sink: str | None = None, voice: str = DEFAULT_VOICE) -> None:
    """Speaks the response through the default audio output (Bluetooth speaker)."""
    print(f"🔊 Playing reply through speaker (Voice: {voice})...")
    speak(reply, sink=sink, voice=voice)
    print("✅ Playback finished.")


def cmd_mic(device: int | str | None = None, seconds: int = 8) -> None:
    """Live microphone level VU meter."""
    if sd is None or np is None:
        print("numpy and sounddevice are required. Run: pip install numpy sounddevice", file=sys.stderr)
        return

    print(f"🎤 Testing microphone level for {seconds} seconds (Press Ctrl+C to stop)...")
    dev_info = sd.query_devices(device, "input")
    rate = int(dev_info.get("default_samplerate", 44100))

    def callback(indata, frames, time_info, status):
        mono = to_mono(indata)
        rms = np.sqrt(np.mean(mono**2))
        db = 20 * np.log10(rms + 1e-6)
        bar_len = int(max(0, min(40, (db + 50) * 0.8)))
        bar = "█" * bar_len + "░" * (40 - bar_len)
        sys.stdout.write(f"\rLevel: [{bar}] {db:5.1f} dB  ")
        sys.stdout.flush()

    with sd.InputStream(device=device, channels=1, samplerate=rate, callback=callback):
        time.sleep(seconds)
    print("\n✅ Mic level check complete.")


def cmd_listen(
    device: int | str | None = None,
    model_path: str = DEFAULT_MODEL,
    reply: str = DEFAULT_REPLY,
    sink: str | None = None,
    voice: str = DEFAULT_VOICE,
) -> None:
    """Listens for 'Hey Aira' or 'Aira', mutes mic, and speaks Hindi response."""
    if sd is None or np is None or Model is None or KaldiRecognizer is None:
        print("sounddevice, numpy, and vosk are required. Run: pip install sounddevice numpy vosk", file=sys.stderr)
        return

    if not os.path.exists(model_path):
        print(f"❌ Vosk model not found at: {model_path}", file=sys.stderr)
        print("Please download it as specified in AIRA_RaspberryPi_Setup_Context.md", file=sys.stderr)
        return

    print(f"⏳ Loading Vosk speech recognition model from {model_path}...")
    model = Model(model_path)
    audio_q: queue.Queue[bytes] = queue.Queue()

    dev_info = sd.query_devices(device, "input")
    rate = int(dev_info.get("default_samplerate", 44100))

    def mic_callback(indata, frames, time_info, status):
        mono = to_mono(indata)
        pcm_16k = to_16k(mono, rate)
        int16_bytes = (pcm_16k * 32767).astype(np.int16).tobytes()
        audio_q.put(int16_bytes)

    print("\n" + "=" * 55)
    print("🟢 AIRA is listening! Say: 'Hey Aira' or 'Aira'...")
    print(f"   Reply configured: \"{reply}\" ({voice})")
    print("=" * 55 + "\n")

    while True:
        try:
            recognizer = KaldiRecognizer(model, TARGET_RATE)
            with sd.InputStream(device=device, channels=1, samplerate=rate, callback=mic_callback):
                while True:
                    data = audio_q.get()
                    if recognizer.AcceptWaveform(data):
                        res = json.loads(recognizer.Result())
                        heard_text = res.get("text", "")
                        if heard_text:
                            print(f"\n[Heard full]: {heard_text}")
                            if heard_wake_word(heard_text):
                                print(f"🎯 WAKE-WORD DETECTED! Responding...")
                                break
                    else:
                        partial = json.loads(recognizer.PartialResult()).get("partial", "")
                        if partial:
                            sys.stdout.write(f"\r[Listening...]: {partial:<40}")
                            sys.stdout.flush()
                            if heard_wake_word(partial):
                                print(f"\n🎯 WAKE-WORD DETECTED in partial! Responding...")
                                break

            # MIC STREAM IS NOW CLOSED to prevent echo loop
            speak(reply, sink=sink, voice=voice)

            # Flush queue and brief pause before reopening mic
            while not audio_q.empty():
                audio_q.get_nowait()
            time.sleep(0.5)
            print("\n🟢 Listening again for 'Hey Aira'...")

        except KeyboardInterrupt:
            print("\n🛑 Stopped by user.")
            break


def main() -> None:
    parser = argparse.ArgumentParser(description="AIRA Raspberry Pi Hardware & Audio Test Tool")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("devices", help="List audio input and output devices")

    spk_cmd = subparsers.add_parser("speaker", help="Test speaker output")
    spk_cmd.add_argument("--reply", default=DEFAULT_REPLY, help="Text to speak")
    spk_cmd.add_argument("--voice", default=DEFAULT_VOICE, help="Voice profile (swara, neerja, priyamvada)")
    spk_cmd.add_argument("--sink", help="PulseAudio/PipeWire sink name")

    mic_cmd = subparsers.add_parser("mic", help="Test microphone input level")
    mic_cmd.add_argument("--device", help="Input device index or name (e.g. 'USB')")
    mic_cmd.add_argument("--seconds", type=int, default=8, help="Seconds to run meter")

    lis_cmd = subparsers.add_parser("listen", help="Run full wake-word and response loop")
    lis_cmd.add_argument("--device", help="Input device index or name (e.g. 'USB')")
    lis_cmd.add_argument("--model", default=DEFAULT_MODEL, help="Path to Vosk speech model")
    lis_cmd.add_argument("--reply", default=DEFAULT_REPLY, help="Response text")
    lis_cmd.add_argument("--voice", default=DEFAULT_VOICE, help="Voice profile (swara, neerja, priyamvada)")
    lis_cmd.add_argument("--sink", help="PulseAudio/PipeWire sink name")

    chat_cmd = subparsers.add_parser("chat", help="Run conversational voice companion with 'Hey Aira' wake word")
    chat_cmd.add_argument("--device", help="Input device index or name (e.g. 'USB')")
    chat_cmd.add_argument("--model", default=DEFAULT_MODEL, help="Path to Vosk speech model")
    chat_cmd.add_argument("--voice", default=DEFAULT_VOICE, help="Voice profile (swara, neerja, priyamvada)")
    chat_cmd.add_argument("--sink", help="PulseAudio/PipeWire sink name")
    chat_cmd.add_argument("--gemini-key", default=os.environ.get("GEMINI_API_KEY"), help="Google Gemini API key")
    chat_cmd.add_argument("--openai-key", default=os.environ.get("OPENAI_API_KEY"), help="OpenAI API key")
    chat_cmd.add_argument("--text-mode", action="store_true", help="Run interactive terminal text chat")

    args = parser.parse_args()

    if args.command == "devices":
        cmd_devices()
    elif args.command == "speaker":
        cmd_speaker(reply=args.reply, sink=args.sink, voice=args.voice)
    elif args.command == "mic":
        cmd_mic(device=parse_device(args.device), seconds=args.seconds)
    elif args.command == "listen":
        cmd_listen(
            device=parse_device(args.device),
            model_path=args.model,
            reply=args.reply,
            sink=args.sink,
            voice=args.voice,
        )
    elif args.command == "chat":
        try:
            from aira_chat import run_chat_loop, run_terminal_chat
            if getattr(args, "text_mode", False):
                run_terminal_chat(voice=args.voice, gemini_key=args.gemini_key, openai_key=args.openai_key)
            else:
                run_chat_loop(
                    device_hint=args.device,
                    sink=args.sink,
                    model_path=args.model,
                    voice=args.voice,
                    gemini_key=args.gemini_key,
                    openai_key=args.openai_key,
                )
        except ImportError as err:
            print(f"Could not load aira_chat: {err}", file=sys.stderr)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
