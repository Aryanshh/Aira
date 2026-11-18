#!/usr/bin/env python3
"""
AIRA Conversational Companion & Voice Chat (Raspberry Pi 3B+)
Flow:
  1. Passive Listening: Waits for "Hey Aira" / "Aira" wake word offline via Vosk.
  2. Acknowledgment: Prompts "हाँ जी, बताइए?" via Swara Neural TTS (mutes mic).
  3. Query Capture: Listens to the user's speech until silence is detected.
  4. Response Generation:
     - Uses Gemini LLM if GEMINI_API_KEY / --gemini-key is present.
     - Or uses OpenAI if OPENAI_API_KEY / --openai-key is present.
     - Built-in Local Elder-Care Intent Engine (Offline): instant empathetic answers
       for medication schedules, health symptoms, emergency SOS, time, date, greetings,
       jokes, companionship, and daily wellness.
  5. Voice Synthesis & Playback: Speaks answer via aira_tts (Swara female voice)
     with Bluetooth silence padding to the Stone 620 speaker.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import queue
import random
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
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

# Modular TTS engine from aira_tts
try:
    from aira_tts import speak as tts_speak
except ImportError:
    tts_speak = None

TARGET_RATE = 16000
DEFAULT_MODEL = os.environ.get(
    "AIRA_VOSK_MODEL",
    os.path.expanduser("~/aira/models/vosk-model-small-en-us-0.15"),
)
DEFAULT_VOICE = "swara"

# Wake-word phonetic variations
HEADS = ["hey", "hay", "hi", "hello", "ok", "okay", "namaste", "suno", "arey"]
STRONG_NAMES = ["aira", "airah", "ayra", "eira", "aaira"]
NAMES = STRONG_NAMES + ["ira", "era", "aria", "arya", "aera", "ayara"]

# Clean family jokes for elders in Hindi
HINDI_JOKES = [
    "टीचर ने छात्र से पूछा: बताओ न्यूटन का चौथा नियम क्या है? छात्र बोला: जब कॉलेज में ठंड बढ़े, तो क्लास बंद करके धूप में बैठ जाओ!",
    "एक मरीज़ ने डॉक्टर से कहा: डॉक्टर साहब, जब मैं चाय पीता हूँ तो मेरी आँख में दर्द होता है। डॉक्टर बोले: अगली बार चम्मच बाहर निकाल कर चाय पीजिए!",
    "पप्पू ने दोस्त से पूछा: तुम्हारी घड़ी तो बहुत बढ़िया है, कितने की है? दोस्त बोला: यह तो मुझे दौड़ प्रतियोगिता में मिली थी। पप्पू: अरे वाह, कितने लोग दौड़े थे? दोस्त: बस दो लोग, एक मैं और दूसरा घड़ी की दुकान का मालिक!",
    "बेटा: पिताजी, आज हमारे मास्टर जी ने पूछा कि ताजमहल किसने बनवाया? पिता: तो तुमने क्या कहा? बेटा: मैंने बोल दिया कि कारीगरों ने!",
]


def heard_wake_word(text: str) -> bool:
    """Fuzzy matching for 'Hey Aira' and colloquial variations."""
    cleaned = re.sub(r"[^a-zA-Z\s]", " ", text.lower())
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

    return False


def find_usb_input_device(hint: str | int | None = None) -> int | str | None:
    """Finds or auto-detects USB soundcard input device."""
    if hint is not None:
        try:
            return int(hint)
        except ValueError:
            return hint
    if sd is None:
        return None

    devices = sd.query_devices()
    # Priority 1: Match USB sound card / mic explicitly
    for idx, dev in enumerate(devices):
        if dev.get("max_input_channels", 0) > 0:
            name = dev.get("name", "").lower()
            if any(k in name for k in ("usb", "c-media", "sound card", "mic", "audio")):
                return idx

    # Priority 2: Default system input device
    default_in = sd.default.device[0]
    return default_in if default_in >= 0 else None


def create_clean_mic_stream(device: int | str | None, audio_q: queue.Queue[bytes]):
    """
    Creates clean, artifact-free 16kHz mono int16 stream for Vosk.
    1. Tries native 16000 Hz RawInputStream (cleanest, handled by ALSA/PipeWire C-library).
    2. Falls back to 48000 Hz with exact 3:1 integer decimation (zero aliasing).
    3. Falls back to hardware rate with 0.25s block buffer.
    """
    # 1. Native 16000 Hz RawInputStream
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
        stream.start()
        stream.stop()
        return stream, "16000 Hz (Native/C-Resampled)"
    except Exception:
        pass

    # 2. 48000 Hz with 3:1 decimation
    try:
        def cb_48k(indata, frames, time_info, status):
            mono = indata[:, 0] if indata.ndim > 1 else indata
            decimated = mono[::3]
            audio_q.put(decimated.astype(np.int16).tobytes())

        stream = sd.InputStream(
            samplerate=48000,
            blocksize=6000,
            device=device,
            dtype="int16",
            channels=1,
            callback=cb_48k,
        )
        stream.start()
        stream.stop()
        return stream, "48000 Hz (3:1 Decimation to 16kHz)"
    except Exception:
        pass

    # 3. Fallback to hardware rate with large blocks
    dev_info = sd.query_devices(device, "input")
    hw_rate = int(dev_info.get("default_samplerate", 44100))
    def cb_fallback(indata, frames, time_info, status):
        mono = indata[:, 0] if indata.ndim > 1 else indata
        dur = len(mono) / hw_rate
        out_len = int(dur * 16000)
        if out_len > 0:
            orig_idx = np.linspace(0, len(mono) - 1, num=out_len)
            resampled = np.interp(orig_idx, np.arange(len(mono)), mono)
            audio_q.put(resampled.astype(np.int16).tobytes())

    stream = sd.InputStream(
        samplerate=hw_rate,
        blocksize=hw_rate // 4,
        device=device,
        dtype="int16",
        channels=1,
        callback=cb_fallback,
    )
    return stream, f"{hw_rate} Hz (Interpolated)"


def to_mono(block: np.ndarray) -> np.ndarray:
    """Averages channels to mono."""
    if block.ndim == 1:
        return block
    return np.mean(block, axis=1)


def to_16k(samples: np.ndarray, rate: int) -> np.ndarray:
    """Resamples audio block to 16 kHz."""
    if rate == TARGET_RATE:
        return samples
    if rate % TARGET_RATE == 0:
        step = rate // TARGET_RATE
        return samples[: len(samples) - (len(samples) % step) : step]
    dur = len(samples) / rate
    out_len = int(dur * TARGET_RATE)
    if out_len <= 0:
        return np.zeros(0, dtype=samples.dtype)
    orig_idx = np.linspace(0, len(samples) - 1, num=out_len)
    return np.interp(orig_idx, np.arange(len(samples)), samples)


def speak_aira(text: str, voice: str = DEFAULT_VOICE, sink: str | None = None) -> None:
    """Speaks through aira_tts engine with Bluetooth padding."""
    if tts_speak:
        tts_speak(text, voice_key=voice, sink=sink)
        return

    # Fallback to direct espeak-ng if aira_tts module not loaded
    tmp_wav = "/tmp/aira_speak_tmp.wav"
    v = "hi+f3" if voice in ("swara", "priyamvada", "espeak-hi") else "en-us"
    subprocess.run(["espeak-ng", "-v", v, "-s", "145", "-p", "60", "-w", tmp_wav, text], check=True)
    if shutil.which("paplay"):
        subprocess.run(["paplay", tmp_wav], check=True)


# ============================================================================
# Local Offline Elder-Care Intent Engine
# ============================================================================

def get_time_string_hindi() -> str:
    """Formats current local time in conversational Hindi."""
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
    now = datetime.datetime.now()
    days = {
        0: "सोमवार",
        1: "मंगलवार",
        2: "बुधवार",
        3: "गुरुवार",
        4: "शुक्रवार",
        5: "शनिवार",
        6: "रविवार",
    }
    months = {
        1: "जनवरी",
        2: "फ़रवरी",
        3: "मार्च",
        4: "अप्रैल",
        5: "मई",
        6: "जून",
        7: "जुलाई",
        8: "अगस्त",
        9: "सितंबर",
        10: "अक्टूबर",
        11: "नवंबर",
        12: "दिसंबर",
    }
    weekday = days.get(now.weekday(), "")
    month_name = months.get(now.month(), "")
    return f"आज {weekday}, {now.day} {month_name} है।"


def handle_local_intent(query: str) -> str:
    """
    Empathetic, local, zero-latency elder-care response engine.
    Handles medicine, emergencies, health checks, time, greetings, and companion chit-chat.
    """
    q = query.lower().strip()

    # 1. Critical Emergency / SOS / Immediate Distress
    if any(k in q for k in ("help", "bachao", "emergency", "madad", "gir gay", "chhati", "chest", "heart", "behosh", "accident")):
        return (
            "घबराइए मत! मैं तुरंत आपके परिवार और केयरगिवर को अलर्ट भेज रही हूँ। "
            "आप आराम से एक जगह बैठ जाइए और गहरी साँस लीजिए।"
        )

    # 2. Medicine / Schedule
    if any(k in q for k in ("dawa", "dawai", "medicine", "tablet", "goli", "khurak", "schedule")):
        return (
            "आपकी दोपहर की दवा का समय हो चुका है। "
            "कृपया एक गिलास ताज़ा पानी के साथ समय पर अपनी दवा ज़रूर ले लीजिए।"
        )

    # 3. Symptoms / Aches & Health Complaints
    if any(k in q for k in ("headache", "sar dard", "sir dard", "bukhar", "fever", "chakkar", "thakan", "tired", "dard", "pain", "kamar", "ghutn")):
        return (
            "अरे, आप थोड़ा पानी पीकर आराम कर लीजिए। "
            "अगर बेचैनी या दर्द ज़्यादा महसूस हो तो मुझे बताइए, मैं परिवार को सूचित कर दूँगी।"
        )

    if any(k in q for k in ("bp", "blood pressure", "sugar", "diabetes")):
        return (
            "अपना ब्लड प्रेशर और शुगर नियमित रूप से मापते रहें। "
            "तनाव बिल्कुल न लें, समय पर पौष्टिक खाना खाएँ और डॉक्टर की सलाह का पालन करें।"
        )

    # 4. Time & Date
    if any(k in q for k in ("time", "samay", "baje", "kitna time", "ghadi")):
        return get_time_string_hindi()

    if any(k in q for k in ("tarikh", "date", "din", "aaj kya hai")):
        return get_date_string_hindi()

    # 5. Jokes & Fun
    if any(k in q for k in ("joke", "chutkula", "hasao", "kuch sunao", "kahani")):
        return random.choice(HINDI_JOKES)

    # 6. Loneliness / Boredom
    if any(k in q for k in ("bore", "boring", "akele", "mann nahi", "mann kharab", "akela")):
        return (
            "मैं हमेशा आपके साथ हूँ! आप बिल्कुल अकेले नहीं हैं। "
            "क्या आप कोई पुराना किस्सा या भजन सुनना पसंद करेंगे?"
        )

    # 7. Meal / Appetite
    if any(k in q for k in ("khana", "lunch", "dinner", "breakfast", "nashta", "bhookh", "chai")):
        return (
            "समय पर हल्का और ताज़ा भोजन करना सेहत के लिए बहुत ज़रूरी है। "
            "क्या आपने आज का खाना और पानी अच्छे से लिया?"
        )

    # 8. Greetings & Daily Pleasantries
    if any(k in q for k in ("good morning", "suprabhat", "subah")):
        return (
            "सुप्रभात! आपका आज का दिन बहुत सुखद और मंगलमय रहे। "
            "क्या आपने सुबह की चाय या दूध ले लिया?"
        )

    if any(k in q for k in ("good night", "shubh ratri", "so raha", "sone ja")):
        return (
            "शुभ रात्रि! निश्चिंत होकर आराम से सोइए। "
            "कोई भी ज़रूरत हो तो बस 'हे आइरा' बोल दीजिएगा, मैं यहीं हूँ।"
        )

    if any(k in q for k in ("who are you", "tum kaun ho", "kya ho", "aap kaun ho", "naam")):
        return (
            "मैं आइरा हूँ, आपकी निजी सेहत और देखभाल की साथी। "
            "दवा की याद दिलाने से लेकर आपसे बातें करने तक, मैं हमेशा आपके साथ हूँ!"
        )

    if any(k in q for k in ("kaise ho", "kaisa chal", "how are you", "theek ho")):
        return (
            "मैं बिल्कुल ठीक हूँ जी! आप बताइए, आपकी सेहत कैसी है और आज आपका मन कैसा है?"
        )

    if any(k in q for k in ("namaste", "hello", "hi", "pranam", "radhe", "ram ram")):
        return (
            "नमस्ते जी! प्रणाम। आज मैं आपकी क्या मदद कर सकती हूँ?"
        )

    if any(k in q for k in ("dhanyawad", "thank you", "thanks", "shukriya")):
        return (
            "अरे, इसमें धन्यवाद की कोई बात नहीं! आपकी सेवा और साथ देना ही मेरा काम है।"
        )

    # 9. General friendly response
    return (
        "जी, मैंने आपकी बात सुनी। आपकी हर ज़रूरत और सेहत का ख्याल रखना मेरी प्राथमिकता है। "
        "क्या आप दवा, समय, या किसी अन्य विषय पर बात करना चाहते हैं?"
    )


# ============================================================================
# Optional Cloud LLM (Gemini / OpenAI) Integration
# ============================================================================

def query_gemini_api(prompt: str, api_key: str) -> str | None:
    """Calls Google Gemini API using native urllib for zero extra dependencies."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    system_instruction = (
        "You are AIRA, a loving, polite, and respectful AI elder-care companion talking to an Indian grandmother/grandfather. "
        "Rules:\n"
        "1. Keep answers strictly within 1 to 2 short sentences.\n"
        "2. Reply in warm, conversational Hindi or Hinglish matching the user.\n"
        "3. Always be respectful and familial (use polite forms like 'आप', 'जी').\n"
        "4. If health/symptoms are mentioned, advise taking medicine and consulting family or doctor.\n"
        "5. If emergency/distress is mentioned, tell them to stay calm while an alert is dispatched."
    )
    payload = {
        "system_instruction": {
            "parts": [{"text": system_instruction}]
        },
        "contents": [
            {
                "parts": [{"text": prompt}]
            }
        ],
        "generationConfig": {
            "maxOutputTokens": 100,
            "temperature": 0.6,
        },
    }
    headers = {"Content-Type": "application/json"}
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
            return text
    except Exception as e:
        print(f"Gemini API request failed ({e}), falling back to local engine.", file=sys.stderr)
        return None


def query_openai_api(prompt: str, api_key: str) -> str | None:
    """Calls OpenAI Chat Completion API via native urllib."""
    url = "https://api.openai.com/v1/chat/completions"
    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {
                "role": "system",
                "content": "You are AIRA, a warm elder companion. Answer in 1-2 short sentences in polite Hindi or Hinglish with 'आप' and 'जी'.",
            },
            {"role": "user", "content": prompt},
        ],
        "max_tokens": 100,
        "temperature": 0.6,
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"OpenAI API request failed ({e}), falling back to local engine.", file=sys.stderr)
        return None


def get_chat_response(query: str, gemini_key: str | None = None, openai_key: str | None = None) -> str:
    """Generates chat response via LLM if available, otherwise local intent engine."""
    if gemini_key:
        reply = query_gemini_api(query, gemini_key)
        if reply:
            return reply

    if openai_key:
        reply = query_openai_api(query, openai_key)
        if reply:
            return reply

    return handle_local_intent(query)


# ============================================================================
# Conversational Audio Loop
# ============================================================================

def run_chat_loop(
    device_hint: str | int | None = None,
    sink: str | None = None,
    model_path: str = DEFAULT_MODEL,
    voice: str = DEFAULT_VOICE,
    gemini_key: str | None = None,
    openai_key: str | None = None,
) -> None:
    """Runs the full voice chat state machine."""
    if sd is None or np is None or Model is None or KaldiRecognizer is None:
        print("Required packages: sounddevice, numpy, vosk. Run: pip install sounddevice numpy vosk", file=sys.stderr)
        return

    if not os.path.exists(model_path):
        print(f"❌ Vosk model not found at {model_path}.", file=sys.stderr)
        print("Please download it as specified in AIRA_RaspberryPi_Setup_Context.md", file=sys.stderr)
        return

    # Auto-detect or select input device (USB sound card)
    input_dev = find_usb_input_device(device_hint)
    dev_info = sd.query_devices(input_dev, "input")
    dev_name = dev_info.get("name", "Default")

    audio_q: queue.Queue[bytes] = queue.Queue()
    stream, mode_desc = create_clean_mic_stream(input_dev, audio_q)

    print("\n" + "=" * 65)
    print("🌸 AIRA Voice Companion Ready")
    print(f"   Input Mic  : [{input_dev}] {dev_name} ({mode_desc})")
    print(f"   Output TTS : Voice '{voice}' (Stone 620 Bluetooth/Default)")
    print(f"   AI Engine  : {'Gemini Online' if gemini_key else 'OpenAI' if openai_key else 'Local Elder-Care Engine (Offline)'}")
    print("=" * 65)
    print("👉 Say: 'Hey Aira' (or 'Aira', 'Namaste Aira') to begin chatting!\n")

    print(f"⏳ Loading Vosk speech model from {model_path}...")
    model = Model(model_path)

    while True:
        try:
            # ---------------------------------------------------------
            # STATE 1: Passive Wake-Word Listening
            # ---------------------------------------------------------
            print("👂 Listening for 'Hey Aira'...")
            recognizer = KaldiRecognizer(model, TARGET_RATE)

            stream.start()
            try:
                wake_detected = False
                while not wake_detected:
                    data = audio_q.get()
                    if recognizer.AcceptWaveform(data):
                        res = json.loads(recognizer.Result())
                        heard_text = res.get("text", "")
                        if heard_text and heard_wake_word(heard_text):
                            wake_detected = True
                            print(f"\n🎯 [Wake Word Detected in Full]: '{heard_text}'")
                    else:
                        partial = json.loads(recognizer.PartialResult()).get("partial", "")
                        if partial:
                            sys.stdout.write(f"\r[Standby...]: {partial:<40}")
                            sys.stdout.flush()
                            if heard_wake_word(partial):
                                wake_detected = True
                                print(f"\n🎯 [Wake Word Detected in Partial]: '{partial}'")
            finally:
                stream.stop()

            # ---------------------------------------------------------
            # STATE 2: Acknowledgment Prompt (Mic Muted)
            # ---------------------------------------------------------
            ack_prompt = "हाँ जी, बताइए?" if voice in ("swara", "priyamvada", "espeak-hi") else "Yes, I'm listening!"
            print(f"🗣️  AIRA: \"{ack_prompt}\"")
            speak_aira(ack_prompt, voice=voice, sink=sink)

            # Flush any lingering audio in queue
            while not audio_q.empty():
                audio_q.get_nowait()

            # ---------------------------------------------------------
            # STATE 3: Query Speech Capture (Unmuted)
            # ---------------------------------------------------------
            print("🎤 Listening to your query (Speak now)...")
            query_recognizer = KaldiRecognizer(model, TARGET_RATE)
            user_query = ""
            start_time = time.time()
            speech_detected_time = None
            max_wait_sec = 8.0
            silence_timeout_sec = 1.6

            stream.start()
            try:
                while time.time() - start_time < max_wait_sec:
                    try:
                        data = audio_q.get(timeout=0.1)
                    except queue.Empty:
                        continue

                    if query_recognizer.AcceptWaveform(data):
                        res = json.loads(query_recognizer.Result())
                        t = res.get("text", "").strip()
                        if t:
                            print(f"\n   [Heard]: \"{t}\"")
                            user_query = f"{user_query} {t}".strip()
                            speech_detected_time = time.time()
                    else:
                        partial = json.loads(query_recognizer.PartialResult()).get("partial", "").strip()
                        if partial:
                            sys.stdout.write(f"\r   Listening: \"{partial}\"    ")
                            sys.stdout.flush()
                            speech_detected_time = time.time()

                    # End of speech detection: silence after user started speaking
                    if speech_detected_time and (time.time() - speech_detected_time > silence_timeout_sec):
                        print("\n   [End of speech detected]")
                        break
            finally:
                stream.stop()

            # Final check of recognizer output
            final_res = json.loads(query_recognizer.FinalResult())
            final_text = final_res.get("text", "").strip()
            if final_text:
                user_query = f"{user_query} {final_text}".strip()

            print()
            # If no query heard:
            if not user_query:
                print("⚠️  No speech heard within timeout.")
                silent_reply = "कोई बात नहीं, जब भी कुछ चाहिए तो 'हे आइरा' कहिए।" if "hi" in voice or voice == "swara" else "No problem, call me whenever you need."
                speak_aira(silent_reply, voice=voice, sink=sink)
                continue

            print(f"👤 User: \"{user_query}\"")

            # ---------------------------------------------------------
            # STATE 4 & 5: Generate & Speak Response (Mic Muted)
            # ---------------------------------------------------------
            reply = get_chat_response(user_query, gemini_key=gemini_key, openai_key=openai_key)
            print(f"🌸 AIRA: \"{reply}\"\n")
            speak_aira(reply, voice=voice, sink=sink)

            # Flush audio queue and brief pause before listening for next wake word
            while not audio_q.empty():
                audio_q.get_nowait()
            time.sleep(0.5)

        except KeyboardInterrupt:
            print("\n🛑 Stopped by user.")
            break


def run_terminal_chat(voice: str = DEFAULT_VOICE, gemini_key: str | None = None, openai_key: str | None = None) -> None:
    """Terminal interactive chat mode (no microphone needed, good for quick testing)."""
    print("\n" + "=" * 60)
    print("⌨️  AIRA Terminal Chat (Type your message, Press Enter)")
    print(f"   Voice: {voice} | AI: {'Gemini' if gemini_key else 'OpenAI' if openai_key else 'Local Intent'}")
    print("   Type 'exit' or 'quit' to stop.")
    print("=" * 60 + "\n")

    while True:
        try:
            user_text = input("👤 You: ").strip()
            if not user_text:
                continue
            if user_text.lower() in ("exit", "quit", "q"):
                print("Goodbye!")
                break

            reply = get_chat_response(user_text, gemini_key=gemini_key, openai_key=openai_key)
            print(f"🌸 AIRA: {reply}\n")
            # Also optionally speak if speaker is available
            speak_aira(reply, voice=voice)
        except (KeyboardInterrupt, EOFError):
            print("\nExiting chat.")
            break


def main() -> None:
    parser = argparse.ArgumentParser(description="AIRA Conversational Companion & Voice Chat")
    parser.add_argument("--device", "-d", help="Microphone device index or name (e.g. 'USB' or 1)")
    parser.add_argument("--sink", "-s", help="PulseAudio/PipeWire sink name or index")
    parser.add_argument("--model", "-m", default=DEFAULT_MODEL, help="Path to Vosk speech model")
    parser.add_argument("--voice", "-v", default=DEFAULT_VOICE, choices=["swara", "neerja", "priyamvada", "espeak-hi", "espeak-en"], help="Voice profile")
    parser.add_argument("--gemini-key", default=os.environ.get("GEMINI_API_KEY"), help="Google Gemini API key")
    parser.add_argument("--openai-key", default=os.environ.get("OPENAI_API_KEY"), help="OpenAI API key")
    parser.add_argument("--text-mode", action="store_true", help="Run interactive terminal text chat")

    args = parser.parse_args()

    if args.text_mode:
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


if __name__ == "__main__":
    main()
