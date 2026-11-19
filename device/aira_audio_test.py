#!/usr/bin/env python3
"""
AIRA Audio Test & Wake-Word Loop (Raspberry Pi 3B+)
Runs offline wake-word detection using Vosk, mutes microphone during response,
and plays high-fidelity spoken response via aira_tts (Swara Female Hindi).
"""

from __future__ import annotations

import argparse
import json
import math
import os
import queue
import re
import shutil
import subprocess
import sys
import time
import wave

try:
    import audioop
except ImportError:
    audioop = None

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

try:
    from aira_chat import AiraChatBot, run_chat_loop as aira_chat_run_loop
except ImportError:
    AiraChatBot = None
    aira_chat_run_loop = None

def get_best_vosk_model_path(requested: str | None = None) -> str:
    """Auto-detects the best available Vosk model."""
    if requested and os.path.exists(requested):
        return requested
    env_m = os.environ.get("AIRA_VOSK_MODEL")
    if env_m and os.path.exists(env_m):
        return env_m

    candidates = [
        os.path.expanduser("~/aira/models/vosk-model-small-hi-0.22"),
        os.path.expanduser("~/aira/models/vosk-model-small-en-in-0.4"),
        os.path.expanduser("~/aira/models/vosk-model-small-en-us-0.15"),
        os.path.expanduser("~/Desktop/vosk-model-small-hi-0.22"),
        os.path.expanduser("~/Desktop/vosk-model-small-en-in-0.4"),
        os.path.expanduser("~/Desktop/vosk-model-small-en-us-0.15"),
    ]
    for c in candidates:
        if os.path.isdir(c):
            return c
    return candidates[0]


TARGET_RATE = 16000
DEFAULT_MODEL = get_best_vosk_model_path()
DEFAULT_REPLY = "नमस्ते! आपकी दोपहर की दवा तैयार है, क्या आपने खाना खा लिया?"
DEFAULT_VOICE = "swara"

# Wake-word phonetic variations (English, Hinglish & Devanagari Hindi)
HEADS = ["hey", "hay", "hi", "hello", "ok", "okay", "namaste", "suno", "arey", "he", "oye", "ha"]
STRONG_NAMES = ["aira", "airah", "ayra", "eira", "aaira"]
NAMES = STRONG_NAMES + ["ira", "era", "aria", "arya", "aera", "ayara", "area", "added", "ida"]
DEVANAGARI_WAKE = [
    "आइरा", "आयरा", "ऐरा", "इरा", "ईरा", "एरा", "आएरा", "अयरा", "एयरा", "अइरा", "आरा", "एयर",
    "हे आइरा", "नमस्ते आइरा", "सुनो आइरा", "हाय आइरा", "है आइरा", "हेलो आइरा",
    "नमस्ते", "नमस्कार", "सुनो", "हेलो", "हलो", "प्रणाम",
]


def heard_wake_word(text: str) -> bool:
    """Fuzzy matching for 'Hey Aira' in English, Hinglish, and Devanagari Hindi."""
    raw = text.strip()
    if not raw:
        return False

    # Check 1: Devanagari Hindi direct keywords & compounds
    for w in DEVANAGARI_WAKE:
        if w in raw:
            return True

    # Check 2: Devanagari phonetic combinations (e.g. "है" + "आइरा" / "हे" + "आयरा")
    deva_heads = ["हे", "हाय", "है", "हलो", "हेलो", "नमस्ते", "नमस्कार", "सुनो", "अरे", "ओ"]
    deva_names = ["आइरा", "आयरा", "ऐरा", "इरा", "ईरा", "एरा", "आएरा", "अयरा", "एयरा", "अइरा", "आरा", "एयर"]
    tokens_deva = raw.split()
    for tok in tokens_deva:
        if tok in deva_names:
            return True
    for i, tok in enumerate(tokens_deva):
        if tok in deva_heads and i + 1 < len(tokens_deva) and tokens_deva[i + 1] in deva_names:
            return True

    # Check 3: English / Hinglish Latin words
    cleaned = re.sub(r"[^a-zA-Z\s]", " ", raw.lower())
    cleaned = re.sub(r"\b(i|ay|ai)\s+(ra|rah)\b", "aira", cleaned)
    tokens = [w for w in cleaned.split() if w]

    if not tokens:
        return False

    for i, tok in enumerate(tokens):
        if tok in STRONG_NAMES:
            return True
        if tok in HEADS and i + 1 < len(tokens):
            if tokens[i + 1] in NAMES:
                return True
            if tokens[i + 1].startswith("air") or tokens[i + 1].startswith("ayr"):
                return True

    return False


def check_manual_wake_trigger() -> bool:
    """Non-blocking check if user pressed Enter or Space in terminal to trigger wake."""
    try:
        if sys.platform != "win32":
            import select
            if sys.stdin in select.select([sys.stdin], [], [], 0.0)[0]:
                sys.stdin.readline()
                return True
        else:
            import msvcrt
            if msvcrt.kbhit():
                ch = msvcrt.getch()
                if ch in (b"\r", b"\n", b" "):
                    return True
    except Exception:
        pass
    return False


def ensure_alsa_mic_volume() -> None:
    """Best-effort ALSA mixer volume un-mute and boost for USB card on Linux."""
    if sys.platform == "win32" or not shutil.which("amixer"):
        return
    for card in (2, 1, 0, "Device", "Audio"):
        try:
            for ctrl in ("Mic", "Capture", "Internal Mic"):
                subprocess.run(
                    ["amixer", "-c", str(card), "sset", ctrl, "100%", "unmute"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
        except Exception:
            pass


def find_usb_input_device(hint: str | int | None = None) -> int | str | None:
    """Finds or auto-detects USB soundcard input device (USB PnP Sound Device)."""
    if hint is not None:
        try:
            return int(hint)
        except ValueError:
            return hint
    if sd is None:
        return None

    devices = sd.query_devices()
    for idx, dev in enumerate(devices):
        if dev.get("max_input_channels", 0) > 0:
            name = dev.get("name", "").lower()
            if any(k in name for k in ("usb", "c-media", "sound card", "mic", "audio")):
                return idx

    default_in = sd.default.device[0]
    return default_in if default_in >= 0 else None


def parse_device(value: str | None) -> int | str | None:
    """Resolve input device to USB sound card by default, or specific index/name."""
    return find_usb_input_device(value)


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


# Clean family jokes for elders in Hindi
HINDI_JOKES = [
    "टीचर ने छात्र से पूछा: बताओ न्यूटन का चौथा नियम क्या है? छात्र बोला: जब कॉलेज में ठंड बढ़े, तो क्लास बंद करके धूप में बैठ जाओ!",
    "एक मरीज़ ने डॉक्टर से कहा: डॉक्टर साहब, जब मैं चाय पीता हूँ तो मेरी आँख में दर्द होता है। डॉक्टर बोले: अगली बार चम्मच बाहर निकाल कर चाय पीजिए!",
    "पप्पू ने दोस्त से पूछा: तुम्हारी घड़ी तो बहुत बढ़िया है, कितने की है? दोस्त बोला: यह तो मुझे दौड़ प्रतियोगिता में मिली थी। पप्पू: अरे वाह, कितने लोग दौड़े थे? दोस्त: बस दो लोग, एक मैं और दूसरा घड़ी की दुकान का मालिक!",
    "बेटा: पिताजी, आज हमारे मास्टर जी ने पूछा कि ताजमहल किसने बनवाया? पिता: तो तुमने क्या कहा? बेटा: मैंने बोल दिया कि कारीगरों ने!",
]


def get_time_string_hindi() -> str:
    """Formats current local time in conversational Hindi."""
    import datetime
    now = datetime.datetime.now()
    hour = now.hour
    minute = now.minute

    period = "सुबह"
    if 12 <= hour < 16:
        period = "दोपहर"
    elif 16 <= hour < 20:
        period = "शाम"
    elif hour >= 20 or hour < 4:
        period = "रात"

    display_hour = hour % 12
    if display_hour == 0:
        display_hour = 12

    if minute == 0:
        return f"अभी {period} के पूरे {display_hour} बजे हैं।"
    elif minute == 15:
        return f"अभी {period} के सवा {display_hour} बजे हैं।"
    elif minute == 30:
        return f"अभी {period} के साढ़े {display_hour} बजे हैं।"
    elif minute == 45:
        next_hour = (display_hour % 12) + 1
        return f"अभी {period} के पौने {next_hour} बजे हैं।"
    else:
        return f"अभी {period} के {display_hour} बजकर {minute} मिनट हुए हैं।"


def get_date_string_hindi() -> str:
    """Formats today's date and weekday in Hindi."""
    import datetime
    now = datetime.datetime.now()
    days = {0: "सोमवार", 1: "मंगलवार", 2: "बुधवार", 3: "गुरुवार", 4: "शुक्रवार", 5: "शनिवार", 6: "रविवार"}
    months = {
        1: "जनवरी", 2: "फ़रवरी", 3: "मार्च", 4: "अप्रैल", 5: "मई", 6: "जून",
        7: "जुलाई", 8: "अगस्त", 9: "सितंबर", 10: "अक्टूबर", 11: "नवंबर", 12: "दिसंबर",
    }
    weekday = days.get(now.weekday(), "")
    month_name = months.get(now.month, "")
    return f"आज {weekday}, {now.day} {month_name} है।"


def handle_local_intent(query: str) -> str:
    """
    Empathetic, local, zero-latency elder-care response engine.
    Supports both Devanagari Hindi and Romanized Hinglish/English keywords.
    """
    import random
    q = query.lower().strip()

    # 1. Critical Emergency / SOS / Immediate Distress
    if any(k in q for k in (
        "help", "bachao", "emergency", "madad", "gir", "chhati", "chest", "heart", "behosh", "accident",
        "मदद", "बचाओ", "इमरजेंसी", "गिर", "छाती", "दिल", "बेहोश", "तबीयत खराब", "सांस"
    )):
        return (
            "घबराइए मत! मैं तुरंत आपके परिवार और केयरगिवर को अलर्ट भेज रही हूँ। "
            "आप आराम से एक जगह बैठ जाइए और गहरी साँस लीजिए।"
        )

    # 2. Medicine / Schedule
    if any(k in q for k in (
        "dawa", "dawai", "medicine", "tablet", "goli", "khurak", "schedule",
        "दवा", "दवाई", "गोली", "खुराक", "मेडिसिन", "दवाइयां"
    )):
        return (
            "आपकी दोपहर की दवा का समय हो चुका है। "
            "कृपया एक गिलास ताज़ा पानी के साथ समय पर अपनी दवा ज़रूर ले लीजिए।"
        )

    # 3. Symptoms / Aches & Health Complaints
    if any(k in q for k in (
        "headache", "sar dard", "sir dard", "bukhar", "fever", "chakkar", "thakan", "tired", "dard", "pain", "kamar", "ghutn",
        "सर दर्द", "सिर दर्द", "बुखार", "चक्कर", "थकान", "कमर दर्द", "घुटने", "दर्द"
    )):
        return (
            "अरे, आप थोड़ा पानी पीकर आराम कर लीजिए। "
            "अगर बेचैनी या दर्द ज़्यादा महसूस हो तो मुझे बताइए, मैं परिवार को सूचित कर दूँगी।"
        )

    if any(k in q for k in (
        "bp", "blood pressure", "sugar", "diabetes",
        "ब्लड प्रेशर", "बीपी", "शुगर", "डायबिटीज"
    )):
        return (
            "अपना ब्लड प्रेशर और शुगर नियमित रूप से मापते रहें। "
            "तनाव बिल्कुल न लें, समय पर पौष्टिक खाना खाएँ और डॉक्टर की सलाह का पालन करें।"
        )

    # 4. Time & Date
    if any(k in q for k in (
        "time", "samay", "baje", "kitna time", "ghadi",
        "समय", "टाइम", "बजे", "कितने बजे", "घड़ी"
    )):
        return get_time_string_hindi()

    if any(k in q for k in (
        "tarikh", "date", "din", "aaj kya hai",
        "तारीख", "दिनांक", "दिन", "आज क्या दिन"
    )):
        return get_date_string_hindi()

    # 5. Jokes & Fun
    if any(k in q for k in (
        "joke", "chutkula", "hasao", "kuch sunao", "kahani",
        "जोक", "चुटकुला", "हंसाओ", "कुछ सुनाओ", "कहानी"
    )):
        return random.choice(HINDI_JOKES)

    # 6. Loneliness / Boredom
    if any(k in q for k in (
        "bore", "boring", "akele", "mann nahi", "mann kharab", "akela",
        "बोर", "अकेले", "मन नहीं लग रहा", "उदास"
    )):
        return (
            "मैं हमेशा आपके साथ हूँ! आप बिल्कुल अकेले नहीं हैं। "
            "क्या आप कोई पुराना किस्सा या भजन सुनना पसंद करेंगे?"
        )

    # 7. Meal / Appetite
    if any(k in q for k in (
        "khana", "lunch", "dinner", "breakfast", "nashta", "bhookh", "chai",
        "खाना", "लंच", "डिनर", "नाश्ता", "भूख", "चाय", "रोटी"
    )):
        return (
            "समय पर हल्का और ताज़ा भोजन करना सेहत के लिए बहुत ज़रूरी है। "
            "क्या आपने आज का खाना और पानी अच्छे से लिया?"
        )

    # 8. Greetings & Daily Pleasantries
    if any(k in q for k in ("good morning", "suprabhat", "subah", "सुप्रभात", "सुबह")):
        return "सुप्रभात! आपका आज का दिन बहुत सुखद और मंगलमय रहे। क्या आपने सुबह की चाय या दूध ले लिया?"

    if any(k in q for k in ("good night", "shubh ratri", "so raha", "sone ja", "शुभ रात्रि", "सोने")):
        return "शुभ रात्रि! निश्चिंत होकर आराम से सोइए। कोई भी ज़रूरत हो तो बस 'हे आइरा' बोल दीजिएगा, मैं यहीं हूँ।"

    if any(k in q for k in ("who are you", "tum kaun ho", "kya ho", "aap kaun ho", "naam", "तुम कौन हो", "आप कौन हो", "नाम क्या है")):
        return "मैं आइरा हूँ, आपकी निजी सेहत और देखभाल की साथी। दवा की याद दिलाने से लेकर आपसे बातें करने तक, मैं हमेशा आपके साथ हूँ!"

    if any(k in q for k in ("kaise ho", "kaisa chal", "how are you", "theek ho", "namaste", "pranam", "नमस्ते", "प्रणाम", "कैसे हो", "कैसी हो", "क्या हाल")):
        return "नमस्ते जी! मैं बिल्कुल ठीक हूँ। आप बताइए, आपकी सेहत कैसी है और आज आपका मन कैसा है?"

    if any(k in q for k in ("radhe", "ram ram", "जय श्री राम", "राधे राधे")):
        return "जय श्री राम! राधे राधे जी। आपका दिन बहुत शुभ और आनंदमय हो।"

    if any(k in q for k in ("dhanyawad", "thank you", "thanks", "shukriya")):
        return "अरे, इसमें धन्यवाद की कोई बात नहीं! आपकी सेवा और साथ देना ही मेरा काम है।"

    return (
        "जी, मैंने आपकी बात सुनी। आपकी हर ज़रूरत और सेहत का ख्याल रखना मेरी प्राथमिकता है। "
        "क्या आप दवा, समय, या किसी अन्य विषय पर बात करना चाहते हैं?"
    )


def cmd_chat_loop(
    device: int | str | None = None,
    sink: str | None = None,
    model_path: str = DEFAULT_MODEL,
    voice: str = DEFAULT_VOICE,
    gemini_key: str | None = None,
    openai_key: str | None = None,
) -> None:
    """Self-contained conversational companion loop."""
    if sd is None or np is None or Model is None or KaldiRecognizer is None:
        print("sounddevice, numpy, and vosk are required. Run: pip install sounddevice numpy vosk", file=sys.stderr)
        return

    if not os.path.exists(model_path):
        print(f"❌ Vosk model not found at: {model_path}", file=sys.stderr)
        print("Please download it as specified in AIRA_RaspberryPi_Setup_Context.md", file=sys.stderr)
        return

    ensure_alsa_mic_volume()
    chosen_dev = parse_device(device)
    dev_info = sd.query_devices(chosen_dev, "input")
    dev_name = dev_info.get("name", "Default")

    bot = AiraChatBot(gemini_key=gemini_key, openai_key=openai_key) if AiraChatBot else None
    engine_name = bot.get_engine_name() if bot else "Local Elder-Care Engine (Offline)"

    audio_q: queue.Queue[bytes] = queue.Queue()
    stream, mode_desc = create_clean_mic_stream(chosen_dev, audio_q)

    print("\n" + "=" * 65)
    print("🌸 AIRA Full-Scale Conversational Voice Companion")
    print(f"   Input Mic  : [{chosen_dev}] {dev_name} ({mode_desc})")
    print(f"   Output TTS : Voice '{voice}' (hi-IN-SwaraNeural on Stone 620)")
    print(f"   AI Engine  : {engine_name}")
    print("=" * 65)
    print("👉 Say: 'Hey Aira' (or 'Aira', 'Namaste Aira', 'नमस्ते', 'सुनो') to begin chatting!")
    print("👉 Or press [ENTER] in this terminal anytime to speak immediately!\n")

    print(f"⏳ Loading Vosk speech model from {model_path}...")
    model = Model(model_path)

    while True:
        try:
            # STATE 1: Passive Wake Word with Live VU Meter
            print("👂 Listening for 'Hey Aira' (or 'नमस्ते', 'Aira', 'सुनो')...")
            recognizer = KaldiRecognizer(model, TARGET_RATE)
            stream.start()
            try:
                wake_detected = False
                last_display_time = 0.0
                last_heard = ""

                while not wake_detected:
                    if check_manual_wake_trigger():
                        print(f"\n🎯 [Manual Wake Triggered via Enter key!]")
                        wake_detected = True
                        break

                    try:
                        data = audio_q.get(timeout=0.08)
                    except queue.Empty:
                        continue

                    if audioop:
                        rms = audioop.rms(data, 2)
                    else:
                        samples = np.frombuffer(data, dtype=np.int16).astype(float)
                        rms = int(np.sqrt(np.mean(samples**2))) if len(samples) > 0 else 0

                    norm_db = 20 * math.log10(max(1, rms) / 32768.0)
                    bars = max(0, min(8, int((norm_db + 50) / 5.0)))
                    meter = "█" * bars + "░" * (8 - bars)

                    if recognizer.AcceptWaveform(data):
                        res = json.loads(recognizer.Result())
                        heard_text = res.get("text", "").strip()
                        if heard_text:
                            last_heard = heard_text
                            if heard_wake_word(heard_text):
                                wake_detected = True
                                print(f"\n🎯 [Wake Word Detected in Full]: '{heard_text}'")
                                break
                    else:
                        partial = json.loads(recognizer.PartialResult()).get("partial", "").strip()
                        if partial:
                            last_heard = partial
                            if heard_wake_word(partial):
                                wake_detected = True
                                print(f"\n🎯 [Wake Word Detected in Partial]: '{partial}'")
                                break

                    now = time.time()
                    if now - last_display_time > 0.08:
                        last_display_time = now
                        disp = f"Hearing: '{last_heard}'" if last_heard else "Listening... (Say 'Hey Aira' or 'नमस्ते')"
                        if len(disp) > 42:
                            disp = disp[:39] + "..."
                        sys.stdout.write(f"\r👂 [{meter} {norm_db:3.0f}dB] {disp:<45}")
                        sys.stdout.flush()
            finally:
                stream.stop()

            # STATE 2: Acknowledgment Prompt (Mic Muted)
            ack_prompt = "हाँ जी, बताइए?" if voice in ("swara", "priyamvada", "espeak-hi") else "Yes, I'm listening!"
            print(f"\n🗣️  AIRA: \"{ack_prompt}\"")
            speak(ack_prompt, voice=voice, sink=sink)

            while not audio_q.empty():
                try:
                    audio_q.get_nowait()
                except queue.Empty:
                    break

            # STATE 3: Query Speech Capture with Live VU Meter
            print("🎤 Listening to your query (Speak now)...")
            query_recognizer = KaldiRecognizer(model, TARGET_RATE)
            user_query = ""
            start_time = time.time()
            speech_detected_time = None
            max_wait_sec = 8.0
            silence_timeout_sec = 1.6
            last_display_time = 0.0
            live_text = ""

            stream.start()
            try:
                while time.time() - start_time < max_wait_sec:
                    try:
                        data = audio_q.get(timeout=0.08)
                    except queue.Empty:
                        continue

                    if audioop:
                        rms = audioop.rms(data, 2)
                    else:
                        samples = np.frombuffer(data, dtype=np.int16).astype(float)
                        rms = int(np.sqrt(np.mean(samples**2))) if len(samples) > 0 else 0

                    norm_db = 20 * math.log10(max(1, rms) / 32768.0)
                    bars = max(0, min(8, int((norm_db + 50) / 5.0)))
                    meter = "█" * bars + "░" * (8 - bars)

                    if query_recognizer.AcceptWaveform(data):
                        res = json.loads(query_recognizer.Result())
                        t = res.get("text", "").strip()
                        if t:
                            user_query = f"{user_query} {t}".strip()
                            live_text = user_query
                            speech_detected_time = time.time()
                    else:
                        partial = json.loads(query_recognizer.PartialResult()).get("partial", "").strip()
                        if partial:
                            live_text = f"{user_query} {partial}".strip()
                            speech_detected_time = time.time()

                    now = time.time()
                    if now - last_display_time > 0.08:
                        last_display_time = now
                        elapsed_silence = (now - speech_detected_time) if speech_detected_time else 0.0
                        disp = f"\"{live_text}\"" if live_text else "Waiting for your voice..."
                        if len(disp) > 38:
                            disp = disp[:35] + "..."
                        sil_str = f" [Sil: {elapsed_silence:0.1f}s]" if speech_detected_time else ""
                        sys.stdout.write(f"\r🎤 [{meter} {norm_db:3.0f}dB] {disp:<38}{sil_str}")
                        sys.stdout.flush()

                    if speech_detected_time and (time.time() - speech_detected_time > silence_timeout_sec):
                        print("\n   [End of speech detected]")
                        break
            finally:
                stream.stop()

            final_res = json.loads(query_recognizer.FinalResult())
            final_text = final_res.get("text", "").strip()
            if final_text:
                user_query = f"{user_query} {final_text}".strip()

            print()
            if not user_query:
                print("⚠️  No speech heard within timeout.")
                silent_reply = "कोई बात नहीं, जब भी कुछ चाहिए तो 'हे आइरा' कहिए।" if "hi" in voice or voice == "swara" else "No problem, call me whenever you need."
                speak(silent_reply, voice=voice, sink=sink)
                continue

            print(f"👤 User: \"{user_query}\"")

            # STATE 4 & 5: Generate & Speak Response
            reply = bot.reply(user_query) if bot else handle_local_intent(user_query)
            print(f"🌸 AIRA: \"{reply}\"\n")
            speak(reply, voice=voice, sink=sink)

            while not audio_q.empty():
                try:
                    audio_q.get_nowait()
                except queue.Empty:
                    break
            time.sleep(0.5)

        except KeyboardInterrupt:
            print("\n🛑 Stopped by user.")
            break


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


def create_clean_mic_stream(device: int | str | None, audio_q: queue.Queue[bytes]):
    """
    Creates clean, artifact-free 16kHz mono int16 stream for Vosk.
    Auto-detects the hardware sample rate supported by the USB soundcard.
    Uses C-level audioop.ratecv with continuous filter state to eliminate
    phase distortion, robotic jitter, and block-boundary clicks.
    """
    dev_info = sd.query_devices(device, "input")
    hw_rate = int(dev_info.get("default_samplerate", 44100))

    # Probe which rate the hardware accepts without throwing ALSA errors
    candidates = [hw_rate, 48000, 44100, 16000]
    candidates = list(dict.fromkeys(candidates))

    supported_rate = hw_rate
    for cand in candidates:
        try:
            sd.check_input_settings(device=device, channels=1, dtype="int16", samplerate=cand)
            supported_rate = cand
            break
        except Exception:
            continue

    # Case 1: Native 16000 Hz if hardware supports it directly
    if supported_rate == 16000:
        try:
            def raw_cb(indata, frames, time_info, status):
                audio_q.put(bytes(indata))

            stream = sd.RawInputStream(
                samplerate=16000,
                blocksize=4000,
                device=device,
                dtype="int16",
                channels=1,
                callback=raw_cb,
            )
            return stream, "16000 Hz (Native ALSA)"
        except Exception:
            pass

    # Case 2: 48000 Hz with 3:1 integer decimation (anti-aliased boxcar)
    if supported_rate == 48000:
        try:
            def cb_48k(indata, frames, time_info, status):
                mono = indata[:, 0] if indata.ndim > 1 else indata
                dec = (mono[0::3].astype(np.int32) + mono[1::3].astype(np.int32) + mono[2::3].astype(np.int32)) // 3
                audio_q.put(dec.astype(np.int16).tobytes())

            stream = sd.InputStream(
                samplerate=48000,
                blocksize=4800,  # 100ms blocks
                device=device,
                dtype="int16",
                channels=1,
                callback=cb_48k,
            )
            return stream, "48000 Hz (Clean 3:1 Decimation to 16kHz)"
        except Exception:
            pass

    # Case 3: 44100 Hz (or arbitrary rate) using Python's built-in C audioop.ratecv
    if audioop is not None:
        state = None

        def cb_audioop(indata, frames, time_info, status):
            nonlocal state
            raw_bytes = indata.tobytes() if isinstance(indata, np.ndarray) else bytes(indata)
            resampled, state = audioop.ratecv(raw_bytes, 2, 1, supported_rate, 16000, state)
            audio_q.put(resampled)

        blocksize = int(supported_rate * 0.1)  # 100ms buffer
        stream = sd.InputStream(
            samplerate=supported_rate,
            blocksize=blocksize,
            device=device,
            dtype="int16",
            channels=1,
            callback=cb_audioop,
        )
        return stream, f"{supported_rate} Hz (Continuous C-Resample to 16kHz)"

    # Case 4: Pure numpy phase-accumulating fallback
    phase_acc = 0.0
    step = supported_rate / 16000.0

    def cb_phase(indata, frames, time_info, status):
        nonlocal phase_acc
        mono = indata[:, 0] if indata.ndim > 1 else indata
        in_len = len(mono)
        indices = []
        curr = phase_acc
        while curr < in_len:
            indices.append(curr)
            curr += step
        phase_acc = curr - in_len

        if indices:
            idx_arr = np.array(indices)
            resampled = np.interp(idx_arr, np.arange(in_len), mono)
            audio_q.put(resampled.astype(np.int16).tobytes())

    blocksize = int(supported_rate * 0.1)
    stream = sd.InputStream(
        samplerate=supported_rate,
        blocksize=blocksize,
        device=device,
        dtype="int16",
        channels=1,
        callback=cb_phase,
    )
    return stream, f"{supported_rate} Hz (Continuous Phase-Preserving to 16kHz)"


def cmd_test_mic(device: int | str | None = None, seconds: int = 5, sink: str | None = None) -> None:
    """Records audio from the microphone at its native rate and plays it back through the speaker."""
    chosen_dev = parse_device(device)
    dev_info = sd.query_devices(chosen_dev, "input")
    dev_name = dev_info.get("name", "Default")
    out_wav = "/tmp/aira_mic_playback_test.wav"

    # Auto-detect supported hardware rate
    hw_rate = int(dev_info.get("default_samplerate", 44100))
    candidates = [hw_rate, 48000, 44100, 16000]
    candidates = list(dict.fromkeys(candidates))

    rec_rate = hw_rate
    for cand in candidates:
        try:
            sd.check_input_settings(device=chosen_dev, channels=1, dtype="int16", samplerate=cand)
            rec_rate = cand
            break
        except Exception:
            continue

    print("=" * 60)
    print("🎤 MICROPHONE LOOPBACK TEST (Hear What The Pi Hears)")
    print(f"   Input device: [{chosen_dev}] {dev_name}")
    print(f"   Hardware Rate: {rec_rate} Hz | Duration: {seconds} seconds")
    print("=" * 60)
    print("\n👉 Speak into your AUX microphone now! Recording starts in 1 second...")
    time.sleep(1)
    print("🔴 RECORDING...")

    try:
        rec_data = sd.rec(int(seconds * rec_rate), samplerate=rec_rate, channels=1, dtype="int16", device=chosen_dev)
        for i in range(seconds):
            time.sleep(1)
            sys.stdout.write(f"\r   Recording... {i + 1}/{seconds}s [{'█' * (i + 1) * 6}{'░' * (seconds - i - 1) * 6}]")
            sys.stdout.flush()
        sd.wait()
        print("\n⏹️  Recording finished!")
    except Exception as err:
        print(f"\n❌ Recording failed: {err}", file=sys.stderr)
        return

    with wave.open(out_wav, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rec_rate)
        wf.writeframes(rec_data.tobytes())

    print("\n🔊 Playing back your recording through Stone 620 speaker...")
    pad_test_wav = "/tmp/aira_mic_playback_padded.wav"
    pad_wav(out_wav, pad_test_wav, lead_sec=0.6, tail_sec=0.4)
    play_audio(pad_test_wav, sink=sink)
    print("✅ Playback finished! Did your voice sound clear?")


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

    ensure_alsa_mic_volume()
    chosen_dev = parse_device(device)
    dev_info = sd.query_devices(chosen_dev, "input")
    print(f"⏳ Loading Vosk speech recognition model from {model_path}...")
    model = Model(model_path)
    audio_q: queue.Queue[bytes] = queue.Queue()

    stream, mode_desc = create_clean_mic_stream(chosen_dev, audio_q)

    print("\n" + "=" * 55)
    print("🟢 AIRA is listening! Say: 'Hey Aira' or 'Aira', 'नमस्ते', 'सुनो'...")
    print(f"   Audio Stream: {mode_desc} on [{chosen_dev}] {dev_info.get('name')}")
    print(f"   Reply configured: \"{reply}\" ({voice})")
    print("   👉 Tip: Speak into mic, or press [Enter] to trigger manually!")
    print("=" * 55 + "\n")

    while True:
        try:
            recognizer = KaldiRecognizer(model, TARGET_RATE)
            stream.start()
            wake_detected = False
            last_display_time = 0.0
            last_heard = ""

            try:
                while not wake_detected:
                    if check_manual_wake_trigger():
                        print(f"\n🎯 [Manual Wake Triggered via Enter key!]")
                        wake_detected = True
                        break

                    try:
                        data = audio_q.get(timeout=0.08)
                    except queue.Empty:
                        continue

                    if audioop:
                        rms = audioop.rms(data, 2)
                    else:
                        samples = np.frombuffer(data, dtype=np.int16).astype(float)
                        rms = int(np.sqrt(np.mean(samples**2))) if len(samples) > 0 else 0

                    norm_db = 20 * math.log10(max(1, rms) / 32768.0)
                    bars = max(0, min(8, int((norm_db + 50) / 5.0)))
                    meter = "█" * bars + "░" * (8 - bars)

                    if recognizer.AcceptWaveform(data):
                        res = json.loads(recognizer.Result())
                        heard_text = res.get("text", "").strip()
                        if heard_text:
                            last_heard = heard_text
                            if heard_wake_word(heard_text):
                                print(f"\n🎯 WAKE-WORD DETECTED in full: '{heard_text}'! Responding...")
                                wake_detected = True
                                break
                    else:
                        partial = json.loads(recognizer.PartialResult()).get("partial", "").strip()
                        if partial:
                            last_heard = partial
                            if heard_wake_word(partial):
                                print(f"\n🎯 WAKE-WORD DETECTED in partial: '{partial}'! Responding...")
                                wake_detected = True
                                break

                    now = time.time()
                    if now - last_display_time > 0.08:
                        last_display_time = now
                        disp = f"Hearing: '{last_heard}'" if last_heard else "Listening... (Say 'Hey Aira' or 'नमस्ते')"
                        if len(disp) > 42:
                            disp = disp[:39] + "..."
                        sys.stdout.write(f"\r👂 [{meter} {norm_db:3.0f}dB] {disp:<45}")
                        sys.stdout.flush()
            finally:
                stream.stop()

            # MIC STREAM IS NOW STOPPED to prevent echo loop
            speak(reply, sink=sink, voice=voice)

            # Flush queue and brief pause before reopening mic
            while not audio_q.empty():
                try:
                    audio_q.get_nowait()
                except queue.Empty:
                    break
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

    tmic_cmd = subparsers.add_parser("test-mic", help="Record 5s from mic and play back through speaker to check quality")
    tmic_cmd.add_argument("--device", help="Input device index or name (e.g. 'USB')")
    tmic_cmd.add_argument("--seconds", type=int, default=5, help="Seconds to record")
    tmic_cmd.add_argument("--sink", help="PulseAudio/PipeWire sink name")

    lis_cmd = subparsers.add_parser("listen", help="Run full wake-word and response loop")
    lis_cmd.add_argument("--device", help="Input device index or name (e.g. 'USB')")
    lis_cmd.add_argument("--model", default=DEFAULT_MODEL, help="Path to Vosk speech model")
    lis_cmd.add_argument("--reply", default=DEFAULT_REPLY, help="Response text")
    lis_cmd.add_argument("--voice", default=DEFAULT_VOICE, help="Voice profile (swara, neerja, priyamvada)")
    lis_cmd.add_argument("--sink", help="PulseAudio/PipeWire sink name")

    chat_cmd = subparsers.add_parser("chat", help="Run conversational voice companion with Webapp Sync & Alarms")
    chat_cmd.add_argument("--device", help="Input device index or name (e.g. 'USB')")
    chat_cmd.add_argument("--model", default=DEFAULT_MODEL, help="Path to Vosk speech model")
    chat_cmd.add_argument("--voice", default=DEFAULT_VOICE, help="Voice profile (swara, neerja, priyamvada)")
    chat_cmd.add_argument("--sink", help="PulseAudio/PipeWire sink name")
    chat_cmd.add_argument("--gemini-key", default=os.environ.get("GEMINI_API_KEY"), help="Google Gemini API key")
    chat_cmd.add_argument("--openai-key", default=os.environ.get("OPENAI_API_KEY"), help="OpenAI API key")
    chat_cmd.add_argument("--api-url", default=os.environ.get("AIRA_API_URL") or "http://localhost:8000", help="AIRA FastAPI backend URL")
    chat_cmd.add_argument("--access-code", default=os.environ.get("AIRA_ACCESS_CODE") or "AIRA-7K3Q", help="Elder access code")
    chat_cmd.add_argument("--pin", default=os.environ.get("AIRA_PIN") or "1234", help="Elder 4-digit PIN")
    chat_cmd.add_argument("--text-mode", action="store_true", help="Run interactive terminal text chat")

    args = parser.parse_args()

    if args.command == "devices":
        cmd_devices()
    elif args.command == "speaker":
        cmd_speaker(reply=args.reply, sink=args.sink, voice=args.voice)
    elif args.command == "mic":
        cmd_mic(device=parse_device(args.device), seconds=args.seconds)
    elif args.command == "test-mic":
        cmd_test_mic(device=args.device, seconds=args.seconds, sink=args.sink)
    elif args.command == "listen":
        cmd_listen(
            device=parse_device(args.device),
            model_path=args.model,
            reply=args.reply,
            sink=args.sink,
            voice=args.voice,
        )
    elif args.command == "chat":
        if aira_chat_run_loop:
            aira_chat_run_loop(
                device_hint=args.device,
                sink=args.sink,
                model_path=args.model,
                voice=args.voice,
                gemini_key=args.gemini_key,
                openai_key=args.openai_key,
                api_url=getattr(args, "api_url", None),
                access_code=getattr(args, "access_code", None),
                pin=getattr(args, "pin", None),
            )
        else:
            cmd_chat_loop(
                device=args.device,
                sink=args.sink,
                model_path=args.model,
                voice=args.voice,
                gemini_key=args.gemini_key,
                openai_key=args.openai_key,
            )
    else:
        print("\n" + "=" * 62)
        print("🌸 AIRA Audio Test & Diagnostics Tool")
        print("=" * 62)
        print("Available commands:")
        print("  python aira_audio_test.py chat       -> Start conversational voice companion ('Hey Aira')")
        print("  python aira_audio_test.py test-mic   -> Record 5s from AUX mic & play back on Stone 620")
        print("  python aira_audio_test.py devices    -> List all audio input/output devices")
        print("  python aira_audio_test.py speaker    -> Test Stone 620 speaker playback")
        print("  python aira_audio_test.py mic        -> Check microphone volume meter")
        print("=" * 62 + "\n")
        parser.print_help()


# Alias for compatibility in case file is imported or named aira_chat.py
run_chat_loop = cmd_chat_loop


if __name__ == "__main__":
    main()
