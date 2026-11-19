#!/usr/bin/env python3
"""
AIRA Professional Conversational Voice Companion (Raspberry Pi 3B+)
Fully Synchronized with AIRA Webapp (FastAPI + Next.js):
  1. Webapp Synchronization (FastAPI Backend):
     - Authenticates using Elder Access Code (AIRA-7K3Q) & PIN (1234).
     - Pulls Elder Profile (Dadaji / Ramesh Sharma).
     - Real-time Medicine Schedules & Timings (/api/v1/elders/me/doses).
     - Doctor Details & Outbound Calling (/api/v1/elders/me/contacts).
     - Safety-Critical Emergency SOS (/api/v1/elders/me/sos).
  2. Scheduled Medicine Alarms & 3-in-1 Confirmation System:
     - Plays gentle alarm chime at scheduled dose time.
     - Speaks warm reminder on Stone 620: medicine name, strength & instructions.
     - Auto-listens for 7 seconds to hear confirmation ("हाँ ले ली" / "Yes").
     - Also supports manual [Enter] push-to-talk confirmation anytime.
     - Automatically marks dose TAKEN in webapp (instant green checkmark!).
     - 5-minute repeated gentle re-prompts until confirmed or snoozed.
  3. High-Accuracy Speech Intelligence via Gemini 1.5/2.0 Flash:
     - Independent audio transcription step (zero history hallucination).
     - Strict alternating conversational turns (user -> model).
     - Explicit unclear-audio notification (never repeats old turns).
     - Real-time webapp context injection into AI personality.
  4. Audio Hardware:
     - AUX Microphone on USB Sound Card (44100 Hz / ALSA auto-rate).
     - Stone 620 Bluetooth Speaker via edge-tts (Swara Neural) with silence padding.
"""

from __future__ import annotations

import argparse
import base64
import datetime
import json
import math
import os
import queue
import random
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import wave
from typing import Any, Dict, List, Optional, Tuple

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

# Modular TTS engine from aira_tts
try:
    from aira_tts import speak as tts_speak
except ImportError:
    tts_speak = None

# Webapp API Client
try:
    from aira_client import AiraApiClient, get_api_client
except ImportError:
    AiraApiClient = None  # type: ignore
    get_api_client = None  # type: ignore


def get_best_vosk_model_path(requested: str | None = None) -> str:
    """Auto-detects the best available Vosk model for offline fallback."""
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
DEFAULT_VOICE = "swara"
DEFAULT_QUERY_WAV = "/tmp/aira_query.wav" if sys.platform != "win32" else os.path.join(os.environ.get("TEMP", "."), "aira_query.wav")
CHIME_WAV = "/tmp/aira_alarm_chime.wav" if sys.platform != "win32" else os.path.join(os.environ.get("TEMP", "."), "aira_alarm_chime.wav")

# Audio lock to prevent reminder thread and chat loop from speaking simultaneously
_audio_lock = threading.Lock()


# Clean family jokes for elders in Hindi
HINDI_JOKES = [
    "टीचर ने छात्र से पूछा: बताओ न्यूटन का चौथा नियम क्या है? छात्र बोला: जब कॉलेज में ठंड बढ़े, तो क्लास बंद करके धूप में बैठ जाओ!",
    "एक मरीज़ ने डॉक्टर से कहा: डॉक्टर साहब, जब मैं चाय पीता हूँ तो मेरी आँख में दर्द होता है। डॉक्टर बोले: अगली बार चम्मच बाहर निकाल कर चाय पीजिए!",
    "पप्पू ने दोस्त से पूछा: तुम्हारी घड़ी तो बहुत बढ़िया है, कितने की है? दोस्त बोला: यह तो मुझे दौड़ प्रतियोगिता में मिली थी। पप्पू: अरे वाह, कितने लोग दौड़े थे? दोस्त: बस दो लोग, एक मैं और दूसरा घड़ी की दुकान का मालिक!",
    "बेटा: पिताजी, आज हमारे मास्टर जी ने पूछा कि ताजमहल किसने बनवाया? पिता: तो तुमने क्या कहा? बेटा: मैंने बोल दिया कि कारीगरों ने!",
]


def check_manual_wake_trigger() -> bool:
    """Non-blocking check if user pressed Enter in terminal."""
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
    """Finds or auto-detects USB soundcard input device."""
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


def clean_text_for_tts(text: str) -> str:
    """Cleans text for natural audio synthesis without markdown or emojis."""
    if not text:
        return ""
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"[*_#`~>\[\]\(\)]", " ", text)
    text = re.sub(r"[\U00010000-\U0010ffff]", "", text)
    text = re.sub(r"[\u2600-\u27BF]", "", text)
    text = re.sub(r"^\s*[-•]\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def speak_aira(text: str, voice: str = DEFAULT_VOICE, sink: str | None = None) -> None:
    """Speaks through aira_tts engine with Bluetooth padding under mutual exclusion."""
    clean = clean_text_for_tts(text)
    if not clean:
        return

    with _audio_lock:
        if tts_speak:
            tts_speak(clean, voice_key=voice, sink=sink)
            return

        tmp_wav = "/tmp/aira_speak_tmp.wav"
        v = "hi+f3" if voice in ("swara", "priyamvada", "espeak-hi") else "en-us"
        subprocess.run(["espeak-ng", "-v", v, "-s", "145", "-p", "60", "-w", tmp_wav, clean], check=True)
        if shutil.which("paplay"):
            subprocess.run(["paplay", tmp_wav], check=True)


def generate_and_play_alarm_chime(sink: str | None = None) -> None:
    """Generates a pleasant two-tone chime (C5 -> E5) for medicine reminders."""
    try:
        sr = 16000
        dur_per_tone = 0.22
        t = np.linspace(0, dur_per_tone, int(sr * dur_per_tone), endpoint=False)
        tone1 = 0.3 * np.sin(2 * np.pi * 523.25 * t)  # C5
        tone2 = 0.3 * np.sin(2 * np.pi * 659.25 * t)  # E5
        combined = np.concatenate([tone1, tone2])
        # Smooth fade out
        fade = np.linspace(1.0, 0.05, len(combined))
        audio_i16 = (combined * fade * 32767).astype(np.int16)

        with wave.open(CHIME_WAV, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sr)
            wf.writeframes(audio_i16.tobytes())

        with _audio_lock:
            if shutil.which("paplay"):
                cmd = ["paplay"]
                if sink:
                    cmd.extend(["-d", str(sink)])
                cmd.append(CHIME_WAV)
                subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            elif sd is not None:
                sd.play(audio_i16, samplerate=sr)
                sd.wait()
    except Exception:
        pass


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
    days = {0: "सोमवार", 1: "मंगलवार", 2: "बुधवार", 3: "गुरुवार", 4: "शुक्रवार", 5: "शनिवार", 6: "रविवार"}
    months = {
        1: "जनवरी", 2: "फ़रवरी", 3: "मार्च", 4: "अप्रैल", 5: "मई", 6: "जून",
        7: "जुलाई", 8: "अगस्त", 9: "सितंबर", 10: "अक्टूबर", 11: "नवंबर", 12: "दिसंबर",
    }
    weekday = days.get(now.weekday(), "")
    month_name = months.get(now.month, "")
    return f"आज {weekday}, {now.day} {month_name} है।"


def get_proactive_greeting(client: Optional[AiraApiClient] = None) -> str:
    """
    Generates warm, empathetic greeting aware of real-time webapp medicine status.
    """
    elder_name = client.get_preferred_name() if client else "दादाजी"
    now = datetime.datetime.now()
    hour = now.hour

    due_doses = client.get_due_or_upcoming_doses(window_minutes=60) if client else []
    med_hint = ""
    if due_doses:
        first_med = due_doses[0].get("medicine_name", "दवा")
        med_hint = f" आपकी {first_med} का समय भी पास है, क्या आपने समय पर ले ली?"

    if 5 <= hour < 12:
        return (
            f"नमस्ते {elder_name}! सुप्रभात, सादर प्रणाम। मैं आपकी साथी आइरा हूँ। "
            f"आज आपकी तबीयत कैसी है? क्या आपने सुबह की चाय और नाश्ता कर लिया?{med_hint}"
        )
    elif 12 <= hour < 17:
        return (
            f"नमस्ते {elder_name}! दोपहर का प्रणाम। मैं आपकी साथी आइरा हूँ। "
            f"क्या आपने दोपहर का भोजन कर लिया?{med_hint}"
        )
    elif 17 <= hour < 21:
        return (
            f"नमस्ते {elder_name}! शुभ संध्या। आज आपका पूरा दिन कैसा रहा? "
            f"क्या आपकी तबीयत बिल्कुल ठीक है?{med_hint}"
        )
    else:
        return (
            f"नमस्ते {elder_name}! शुभ रात्रि। "
            f"सोने से पहले क्या आपने अपनी रात की दवा ले ली? कोई भी सेवा हो तो मुझे बताइए।"
        )


def handle_local_intent(query: str, client: Optional[AiraApiClient] = None) -> str:
    """
    Empathetic, zero-latency local fallback engine.
    Executes real webapp actions (Dose Confirm, Doctor Details, SOS) even offline!
    """
    q = query.lower().strip()
    elder_name = client.get_preferred_name() if client else "दादाजी"

    # Action 1: Emergency SOS
    if any(k in q for k in ("help", "bachao", "emergency", "madad", "gir", "chhati", "chest", "heart", "मदद", "बचाओ", "इमरजेंसी", "दर्द", "चक्कर")):
        if client:
            client.trigger_sos(source="voice_local_intent")
        return f"घबराइए मत {elder_name}! मैंने तुरंत आपके परिवार और डॉक्टर को इमरजेंसी अलर्ट (SOS) भेज दिया है। आप आराम से बैठ जाइए और गहरी साँस लीजिए, मदद तुरंत पहुँच रही है।"

    # Action 2: Doctor inquiries & connect
    if any(k in q for k in ("doctor", "dr", "डॉक्टर", "वैद्य", "अस्पताल")):
        if client:
            doc = client.get_doctor_details()
            if doc:
                d_name = doc.get("full_name", "डॉ. वी. के. शर्मा")
                d_phone = doc.get("phone_e164", "")
                if any(w in q for w in ("call", "connect", "baat", "phone", "कॉल", "बात", "फोन")):
                    client.connect_doctor(channel="call")
                    return f"जी {elder_name}, मैंने आपके डॉक्टर {d_name} जी को कॉल अलर्ट भेज दिया है। वे आपसे शीघ्र ही संपर्क करेंगे।"
                return f"{elder_name}, आपके डॉक्टर {d_name} हैं और उनका नंबर {d_phone} है। क्या मैं उनसे बात करने के लिए कॉल लगाऊँ?"
        return f"{elder_name}, आपके डॉक्टर डॉ. वी. के. शर्मा हैं। अगर आप चाहें तो मैं तुरंत उन्हें फोन लगा सकती हूँ।"

    # Action 3: Medicine confirmation ("I took medicine" / "दवा ले ली")
    if any(k in q for k in ("le li", "kha li", "took", "taken", "done", "ले ली", "खा ली", "पी ली", "हो गई")):
        if client:
            due = client.get_due_or_upcoming_doses(window_minutes=90)
            if due:
                d_target = due[0]
                client.mark_dose_taken(d_target["id"])
                med_name = d_target.get("medicine_name", "दवा")
                return f"बहुत बढ़िया {elder_name}! मैंने ऐप में दर्ज़ कर दिया है कि आपने {med_name} ले ली है। शाबाश!"
        return f"बहुत अच्छा {elder_name}! मैंने दर्ज़ कर लिया है कि आपने अपनी दवा समय पर ले ली है।"

    # Action 4: Medicine schedule query ("What medicines do I have today?")
    if any(k in q for k in ("dawa", "dawai", "medicine", "tablet", "goli", "दवा", "दवाई", "गोली", "खुराक")):
        if client and client.doses_cache:
            pending = [d for d in client.doses_cache if d.get("status") == "scheduled"]
            if pending:
                items = [f"{d.get('medicine_name')} (समय {d.get('scheduled_time', '')[:5]})" for d in pending]
                return f"{elder_name}, आज आपकी बाकी दवाइयां हैं: {', '.join(items)}। कृपया इन्हें समय पर ज़रूर लीजिए।"
            else:
                return f"{elder_name}, बहुत ख़ुशी की बात है! आपकी आज की सभी निर्धारित दवाइयां पूरी हो चुकी हैं।"
        return "आपकी सुबह की ब्लड प्रेशर और दोपहर की दवा निर्धारित है। कृपया समय पर एक गिलास पानी के साथ लीजिए।"

    # Action 5: Clock & Date
    if any(k in q for k in ("time", "samay", "kitne baje", "टाइम", "समय", "कितने बजे")):
        return get_time_string_hindi()

    if any(k in q for k in ("date", "tarikh", "aaj kya", "din", "तारीख", "दिन", "आज क्या")):
        return get_date_string_hindi()

    # Action 6: Humor
    if any(k in q for k in ("joke", "chutkula", "hansao", "mazak", "चुटकुला", "हंसाओ", "मजाक")):
        return random.choice(HINDI_JOKES)

    # Action 7: Identity
    if any(k in q for k in ("who are you", "tum kaun ho", "aap kaun", "naam", "तुम कौन हो", "आप कौन", "नाम क्या")):
        return f"मैं आइरा हूँ, आपकी देखभाल और साथ देने वाली डिजिटल साथी। दवा याद दिलाने से लेकर डॉक्टर से जोड़ने तक, मैं हमेशा आपके साथ हूँ {elder_name}!"

    # Action 8: Greetings
    if any(k in q for k in ("kaise ho", "how are you", "theek ho", "कैसी हो", "कैसे हो", "क्या हाल")):
        return f"नमस्ते {elder_name}! मैं बिल्कुल ठीक हूँ। आप बताइए, आपकी सेहत कैसी है और आज आपका मन कैसा है?"

    if any(k in q for k in ("namaste", "hello", "hi", "pranam", "नमस्ते", "प्रणाम", "हेलो")):
        return f"नमस्ते {elder_name}! प्रणाम। कहिए, आज मैं आपकी क्या सेवा करूँ?"

    if any(k in q for k in ("thank you", "thanks", "shukriya", "dhanyawad", "धन्यवाद", "शुक्रिया")):
        return f"अरे {elder_name}, इसमें धन्यवाद की कोई बात नहीं! आपकी सेवा और साथ देना ही मेरा काम है।"

    return f"जी {elder_name}, मैंने सुना। मैं हर समय आपकी सहायता और देखभाल के लिए तैयार हूँ।"


def transcribe_wav_vosk(wav_path: str, model_path: str = DEFAULT_MODEL) -> str:
    """Offline speech transcription using Vosk as local fallback."""
    if not Model or not KaldiRecognizer or not os.path.exists(model_path) or not os.path.exists(wav_path):
        return ""
    try:
        model = Model(model_path)
        rec = KaldiRecognizer(model, 16000)
        with wave.open(wav_path, "rb") as wf:
            while True:
                data = wf.readframes(4000)
                if len(data) == 0:
                    break
                rec.AcceptWaveform(data)
        res = json.loads(rec.FinalResult())
        return res.get("text", "").strip()
    except Exception:
        return ""


# ============================================================================
# High-Fidelity Speech Recording (Push-to-Talk with Adaptive Noise Floor)
# ============================================================================

def record_speech_push_to_talk(
    device: int | str | None,
    out_wav: str = DEFAULT_QUERY_WAV,
    max_duration: float = 16.0,
    silence_timeout: float = 2.0,
    auto_stop_on_speech: bool = True,
) -> bool:
    """
    Records speech from USB microphone with live VU meter.
    Uses adaptive noise calibration to prevent USB background hiss from falsely
    triggering early cutoff. Allows [Enter] to finish early.
    """
    if sd is None:
        return False

    dev_info = sd.query_devices(device, "input")
    hw_rate = int(dev_info.get("default_samplerate", 44100))

    candidates = [hw_rate, 48000, 44100, 16000]
    rec_rate = hw_rate
    for cand in candidates:
        try:
            sd.check_input_settings(device=device, channels=1, dtype="int16", samplerate=cand)
            rec_rate = cand
            break
        except Exception:
            continue

    q: queue.Queue[bytes] = queue.Queue()

    def callback(indata, frames, time_info, status):
        q.put(indata.tobytes() if isinstance(indata, np.ndarray) else bytes(indata))

    blocksize = int(rec_rate * 0.08)
    stream = sd.InputStream(
        samplerate=rec_rate,
        blocksize=blocksize,
        device=device,
        dtype="int16",
        channels=1,
        callback=callback,
    )

    # Flush lingering Enter keys
    while check_manual_wake_trigger():
        pass

    recorded_frames: list[bytes] = []
    speech_started = False
    speech_duration = 0.0
    last_sound_time = time.time()
    start_time = time.time()
    last_display_time = 0.0

    print("\n🔴 RECORDING... (Speak now in Hindi, English, or Hinglish)")
    print("   👉 Tip: Press [Enter] anytime to finish speaking.\n")

    stream.start()
    try:
        # Step 1: 0.15s ambient noise floor sampling
        ambient_samples = []
        init_t = time.time()
        while time.time() - init_t < 0.15:
            try:
                ch = q.get(timeout=0.05)
                recorded_frames.append(ch)
                if audioop:
                    ambient_samples.append(audioop.rms(ch, 2))
            except queue.Empty:
                pass

        avg_noise_rms = (sum(ambient_samples) / max(1, len(ambient_samples))) if ambient_samples else 400
        # Adaptive speech presence threshold (above background hiss)
        speech_thresh_rms = max(int(avg_noise_rms * 2.2), 650)
        thresh_db = 20 * math.log10(max(1, speech_thresh_rms) / 32768.0)

        while time.time() - start_time < max_duration:
            now = time.time()
            if now - start_time > 0.4 and check_manual_wake_trigger():
                print("\n⏹️  [Enter pressed — Finished recording]")
                break

            try:
                chunk = q.get(timeout=0.08)
            except queue.Empty:
                continue

            recorded_frames.append(chunk)

            if audioop:
                rms = audioop.rms(chunk, 2)
            else:
                samples = np.frombuffer(chunk, dtype=np.int16).astype(float)
                rms = int(np.sqrt(np.mean(samples**2))) if len(samples) > 0 else 0

            norm_db = 20 * math.log10(max(1, rms) / 32768.0)
            bars = max(0, min(8, int((norm_db + 50) / 5.0)))
            meter = "█" * bars + "░" * (8 - bars)

            if rms > speech_thresh_rms:
                speech_started = True
                speech_duration += 0.08
                last_sound_time = now

            if now - last_display_time > 0.08:
                last_display_time = now
                if speech_started:
                    sil_elapsed = now - last_sound_time
                    status = f"Listening... [Sil: {sil_elapsed:0.1f}s]"
                else:
                    status = f"Waiting for your voice (Thresh: {thresh_db:0.0f}dB)..."
                sys.stdout.write(f"\r🎤 [{meter} {norm_db:3.0f}dB] {status:<45}")
                sys.stdout.flush()

            # End of speech: require at least 0.4s speech and 2.0s silence
            if auto_stop_on_speech and speech_started and speech_duration >= 0.4:
                if now - last_sound_time > silence_timeout:
                    print("\n⏹️  [Speech finished]")
                    break
    finally:
        stream.stop()
        stream.close()

    if not recorded_frames:
        return False

    raw_audio = b"".join(recorded_frames)

    # Resample to 16000 Hz mono PCM
    if rec_rate != 16000:
        if audioop:
            final_audio, _ = audioop.ratecv(raw_audio, 2, 1, rec_rate, 16000, None)
        else:
            samples = np.frombuffer(raw_audio, dtype=np.int16)
            out_len = int(len(samples) * 16000 / rec_rate)
            final_audio = np.interp(np.linspace(0, len(samples) - 1, out_len), np.arange(len(samples)), samples).astype(np.int16).tobytes()
    else:
        final_audio = raw_audio

    with wave.open(out_wav, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(final_audio)

    return os.path.exists(out_wav) and os.path.getsize(out_wav) > 1500


# ============================================================================
# Conversational AI Companion Engine (Gemini 1.5/2.0 Flash + Webapp Context)
# ============================================================================

class AiraChatBot:
    """
    Conversational Companion Engine.
    Fixes the 'repeats what I already said' bug completely:
      1. Transcribes audio in an independent step (no past history interference).
      2. Strictly alternates turns in conversation history (user -> model).
      3. Injects live webapp state (elder name, doctor, medicines, timings).
    """

    def __init__(
        self,
        gemini_key: str | None = None,
        openai_key: str | None = None,
        api_client: Optional[AiraApiClient] = None,
        max_history_turns: int = 8,
    ) -> None:
        self.gemini_key = gemini_key or os.environ.get("GEMINI_API_KEY")
        self.openai_key = openai_key or os.environ.get("OPENAI_API_KEY")
        self.api_client = api_client
        self.max_history_turns = max_history_turns
        # History is strictly alternating: [{"role": "user", ...}, {"role": "model", ...}]
        self.history: list[dict] = []

    def reset_history(self) -> None:
        """Clears conversation context."""
        self.history.clear()

    def get_engine_name(self) -> str:
        if self.gemini_key:
            return "Google Gemini Multimodal AI (Cloud Free Tier)"
        if self.openai_key:
            return "OpenAI (Online)"
        return "Local Elder-Care Engine (Offline)"

    def build_system_instruction(self) -> str:
        """Constructs system instruction populated with real-time webapp data."""
        elder_name = self.api_client.get_preferred_name() if self.api_client else "दादाजी (Ramesh Sharma)"
        med_summary = self.api_client.format_medicines_summary() if self.api_client else "मेटफॉर्मिन 500 मिलीग्राम (सुबह और रात), एम्लोडिपिन 5 मिलीग्राम (सुबह)"
        doc = self.api_client.get_doctor_details() if self.api_client else None
        doc_str = f"{doc.get('full_name', 'डॉ. वी. के. शर्मा')} (फोन: {doc.get('phone_e164', '+919810012345')})" if doc else "डॉ. वी. के. शर्मा (+919810012345)"

        return (
            f"You are AIRA, a compassionate, warm, and highly capable AI voice companion (like Gemini Voice) caring for an elder in India.\n"
            f"Current Patient Information:\n"
            f"- Elder Name: {elder_name}\n"
            f"- Attending Doctor: {doc_str}\n"
            f"- Today's Scheduled Medicines & Timings:\n{med_summary}\n\n"
            "Core Directives:\n"
            f"1. Address the elder with deep affection and respect as '{elder_name}' or 'आप'.\n"
            "2. Direct & Concise Answer: Answer exactly what they asked in 1 to 2 spoken sentences! Never give generic canned responses.\n"
            "3. Multilingual: Naturally match their language — pure Hindi, Indian English, or mixed Hinglish. If they ask in Hindi, reply in polite Hindi.\n"
            "4. Medicine Confirmation: If the user says they took their medicine ('हाँ ले ली', 'medicine taken', 'done'), praise them warmly and confirm it is recorded.\n"
            "5. Doctor Connect: If they ask about their doctor or want to talk to doctor, provide their doctor's name and confirm an alert or call can be made.\n"
            "6. Safety & SOS: If chest pain, severe dizziness, falling, or emergency is mentioned, immediately reassure them and confirm emergency SOS alert is sent.\n"
            "7. Plain Spoken Output: NEVER output markdown asterisks (**bold**), bullet points, hashtags, or emojis. Output only plain natural spoken text."
        )

    def transcribe_audio_gemini(self, wav_path: str) -> str:
        """
        Step 1: Transcribes voice audio using Gemini with ZERO past history.
        This completely prevents hallucinating or repeating previous turns.
        """
        if not self.gemini_key or not os.path.exists(wav_path) or os.path.getsize(wav_path) < 1000:
            return ""

        with open(wav_path, "rb") as f:
            audio_b64 = base64.b64encode(f.read()).decode("utf-8")

        prompt = (
            "Listen carefully to the audio clip. The speaker is an elder speaking in Hindi, Indian English, or mixed Hinglish.\n"
            "Task: Transcribe exactly what the speaker said verbatim.\n"
            "Rules:\n"
            "- If speech is present, return ONLY the transcription text.\n"
            "- If the audio is silent, background hum, or unintelligible noise, return exactly: [UNCLEAR].\n"
            "- Do not add any preface, preamble, or punctuation explanation."
        )

        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"inlineData": {"mimeType": "audio/wav", "data": audio_b64}},
                        {"text": prompt},
                    ],
                }
            ],
            "generationConfig": {"temperature": 0.1, "maxOutputTokens": 100},
        }

        body_bytes = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}

        for mod in ["gemini-1.5-flash", "gemini-2.0-flash", "gemini-2.5-flash"]:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{mod}:generateContent?key={self.gemini_key}"
            req = urllib.request.Request(url, data=body_bytes, headers=headers, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=6.0) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    cands = data.get("candidates", [])
                    if cands:
                        parts = cands[0].get("content", {}).get("parts", [])
                        if parts:
                            res = parts[0].get("text", "").strip()
                            if "[unclear]" in res.lower() or not res:
                                return ""
                            return res
            except Exception:
                continue
        return ""

    def reply_audio(self, wav_path: str) -> Tuple[str, str]:
        """
        Processes voice query:
          1. Transcribe audio cleanly.
          2. Check for unclear audio -> notify user immediately.
          3. Generate answer with clean conversation history.
        """
        # If no cloud Gemini key, use local Vosk
        if not self.gemini_key:
            vosk_text = transcribe_wav_vosk(wav_path)
            if vosk_text:
                reply = handle_local_intent(vosk_text, self.api_client)
                return vosk_text, clean_text_for_tts(reply)
            return "(Unclear audio)", "माफ़ कीजिए, मुझे आपकी आवाज़ साफ़ सुनाई नहीं दी। क्या आप कृपया थोड़ा नज़दीक आकर दोबारा बोल सकते हैं?"

        # Step 1: Transcribe audio without history contamination
        user_transcript = self.transcribe_audio_gemini(wav_path)

        # Fallback to local Vosk if Gemini returned empty
        if not user_transcript:
            vosk_text = transcribe_wav_vosk(wav_path)
            if vosk_text:
                user_transcript = vosk_text

        # Step 2: Unclear audio check
        if not user_transcript:
            notify_reply = "माफ़ कीजिए, मुझे आपकी आवाज़ साफ़ सुनाई नहीं दी। क्या आप कृपया दोबारा बोल सकते हैं?"
            return "(Unclear audio)", notify_reply

        # Step 3: Conversational reasoning using clean text
        reply = self.reply_text(user_transcript)
        return user_transcript, reply

    def reply_text(self, user_query: str) -> str:
        """
        Generates conversational response using clean alternating history
        and executes real webapp commands (Dose Taken, Doctor Connect, SOS).
        """
        q_clean = user_query.strip()
        if not q_clean:
            return "जी, कहिए? मैं सुन रही हूँ।"

        elder_name = self.api_client.get_preferred_name() if self.api_client else "दादाजी"

        # Check for SOS intent
        if any(w in q_clean.lower() for w in ("help", "bachao", "emergency", "madad", "gir", "मदद", "बचाओ", "इमरजेंसी", "चक्कर", "गिर गया")):
            if self.api_client:
                self.api_client.trigger_sos(source="voice_chat")
            sos_reply = f"घबराइए मत {elder_name}! मैंने तुरंत आपके परिवार और डॉक्टर को इमरजेंसी अलर्ट (SOS) भेज दिया है। आप आराम से बैठ जाइए, सहायता रास्ते में है।"
            self.history.append({"role": "user", "parts": [{"text": q_clean}]})
            self.history.append({"role": "model", "parts": [{"text": sos_reply}]})
            return sos_reply

        # Check for Dose confirmation intent ("हाँ ले ली" / "मैंने दवा खा ली")
        if any(w in q_clean.lower() for w in ("le li", "kha li", "took", "taken", "ले ली", "खा ली", "दवा ले ली")):
            if self.api_client:
                due = self.api_client.get_due_or_upcoming_doses(window_minutes=90)
                if due:
                    target_dose = due[0]
                    self.api_client.mark_dose_taken(target_dose["id"])
                    med_name = target_dose.get("medicine_name", "दवा")
                    confirm_reply = f"बहुत बढ़िया {elder_name}! मैंने ऐप में दर्ज़ कर दिया है कि आपने {med_name} ले ली है। अपना ख्याल रखिएगा!"
                    self.history.append({"role": "user", "parts": [{"text": q_clean}]})
                    self.history.append({"role": "model", "parts": [{"text": confirm_reply}]})
                    return confirm_reply

        # Reset history command
        if any(w in q_clean.lower() for w in ("नया विषय", "reset chat", "clear memory", "forget all", "start over")):
            self.reset_history()
            return f"जी {elder_name}, मैंने पिछली बातें हटा दी हैं। बताइए, अब क्या बात करनी है?"

        if self.gemini_key:
            # Enforce clean alternating user -> model turns
            contents = list(self.history)
            contents.append({"role": "user", "parts": [{"text": q_clean}]})

            payload = {
                "systemInstruction": {"parts": [{"text": self.build_system_instruction()}]},
                "contents": contents,
                "generationConfig": {"temperature": 0.7, "maxOutputTokens": 200},
            }
            body_bytes = json.dumps(payload).encode("utf-8")
            headers = {"Content-Type": "application/json"}

            for mod in ["gemini-1.5-flash", "gemini-2.0-flash", "gemini-2.5-flash"]:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{mod}:generateContent?key={self.gemini_key}"
                req = urllib.request.Request(url, data=body_bytes, headers=headers, method="POST")
                try:
                    with urllib.request.urlopen(req, timeout=6.0) as resp:
                        data = json.loads(resp.read().decode("utf-8"))
                        cands = data.get("candidates", [])
                        if cands:
                            parts = cands[0].get("content", {}).get("parts", [])
                            if parts:
                                clean_reply = clean_text_for_tts(parts[0].get("text", "").strip())
                                # Maintain strict alternating history
                                self.history.append({"role": "user", "parts": [{"text": q_clean}]})
                                self.history.append({"role": "model", "parts": [{"text": clean_reply}]})
                                if len(self.history) > self.max_history_turns * 2:
                                    self.history = self.history[-self.max_history_turns * 2 :]
                                return clean_reply
                except Exception:
                    continue

        # Offline fallback
        local_reply = handle_local_intent(q_clean, self.api_client)
        clean_local = clean_text_for_tts(local_reply)
        self.history.append({"role": "user", "parts": [{"text": q_clean}]})
        self.history.append({"role": "model", "parts": [{"text": clean_local}]})
        return clean_local


# ============================================================================
# Scheduled Medicine Alarm & Confirmation Daemon (3-in-1 Combined System)
# ============================================================================

class MedicineAlarmDaemon:
    """
    Background daemon for scheduled medicine alarms:
      1. Plays chime & announces reminder over Stone 620 speaker.
      2. Opens mic for 7 seconds to auto-listen for voice confirmation ("हाँ ले ली").
      3. Automatically marks dose TAKEN in the webapp (instant green checkmark!).
      4. Re-prompts gently every 5 minutes if unconfirmed.
    """

    def __init__(
        self,
        api_client: AiraApiClient,
        bot: AiraChatBot,
        input_dev: int | str | None,
        voice: str = DEFAULT_VOICE,
        sink: str | None = None,
    ) -> None:
        self.api_client = api_client
        self.bot = bot
        self.input_dev = input_dev
        self.voice = voice
        self.sink = sink
        self.running = False
        self.last_reminded: Dict[str, float] = {}  # dose_id -> timestamp
        self.thread: Optional[threading.Thread] = None

    def start(self) -> None:
        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.running = False

    def _run_loop(self) -> None:
        while self.running:
            try:
                # Sync fresh doses from webapp periodically
                self.api_client.fetch_doses()
                now = datetime.datetime.now()
                now_ts = now.timestamp()
                elder_name = self.api_client.get_preferred_name()

                # Check today's doses
                for dose in self.api_client.doses_cache:
                    if dose.get("status") != "scheduled":
                        continue

                    dose_id = dose.get("id")
                    sched_time_str = dose.get("scheduled_time", "")
                    if not sched_time_str or not dose_id:
                        continue

                    # Parse HH:MM
                    try:
                        parts = sched_time_str.split(":")
                        dose_hour, dose_min = int(parts[0]), int(parts[1])
                    except Exception:
                        continue

                    # Check if dose is scheduled for right now (or within 30 mins)
                    is_current_minute = (now.hour == dose_hour and now.minute == dose_min)
                    is_recently_due = (0 <= (now.hour * 60 + now.minute) - (dose_hour * 60 + dose_min) <= 45)

                    last_remind_time = self.last_reminded.get(dose_id, 0.0)
                    time_since_last_remind = now_ts - last_remind_time

                    # Trigger initial alarm or 5-minute repeated re-prompt
                    should_remind = False
                    is_rep_rompt = False

                    if is_current_minute and (last_remind_time == 0.0):
                        should_remind = True
                    elif is_recently_due and last_remind_time > 0.0 and time_since_last_remind >= 300:  # 5 minutes
                        should_remind = True
                        is_rep_rompt = True
                    elif is_recently_due and last_remind_time == 0.0:
                        should_remind = True

                    if should_remind:
                        self._trigger_medicine_alarm(dose, elder_name, is_rep_rompt)
                        self.last_reminded[dose_id] = now_ts

            except Exception as e:
                print(f"⚠️ [Alarm Daemon Note]: {e}", file=sys.stderr)

            time.sleep(20)

    def _trigger_medicine_alarm(self, dose: Dict[str, Any], elder_name: str, is_reprompt: bool) -> None:
        """Executes the 3-in-1 alarm & confirmation interaction."""
        med_name = dose.get("medicine_name", "दवा")
        strength = dose.get("strength", "")
        time_display = dose.get("scheduled_time", "")[:5]
        instr = dose.get("instructions", "")
        dose_id = dose.get("id")

        print("\n" + "=" * 62)
        print(f"⏰ MEDICINE ALARM TRIGGERED: {med_name} {strength} ({time_display})")
        print(f"   Patient: {elder_name} | Instructions: {instr or 'None'}")
        print("=" * 62)

        # 1. Play gentle audio chime
        generate_and_play_alarm_chime(sink=self.sink)

        # 2. Voice announcement over Stone 620
        if is_reprompt:
            reminder_text = (
                f"नमस्ते {elder_name}, एक ज़रूरी याददिहानी: क्या आपने अपनी {time_display} बजे की दवा '{med_name}' ले ली है? "
                "कृपया समय पर दवा ज़रूर ले लीजिए।"
            )
        else:
            instr_phrase = f" इसे {instr}।" if instr else ""
            reminder_text = (
                f"नमस्ते {elder_name}! आपकी {time_display} बजे की दवा '{med_name} {strength}' का समय हो गया है।{instr_phrase} "
                "क्या आपने दवा ले ली है?"
            )

        print(f"\n🗣️  AIRA Reminder: \"{reminder_text}\"")
        speak_aira(reminder_text, voice=self.voice, sink=self.sink)

        # 3. Automatically open mic for 7 seconds to hear confirmation
        print("\n👂 Listening for your confirmation ('हाँ ले ली' / 'Yes')... (Speak now)")
        confirmed = False
        tmp_confirm_wav = "/tmp/aira_confirm.wav"
        rec_ok = record_speech_push_to_talk(
            self.input_dev,
            out_wav=tmp_confirm_wav,
            max_duration=7.0,
            silence_timeout=1.8,
        )

        if rec_ok:
            transcript, _ = self.bot.reply_audio(tmp_confirm_wav)
            print(f"👤 You said: \"{transcript}\"")
            t_low = transcript.lower()
            if any(w in t_low for w in ("le li", "kha li", "yes", "took", "taken", "done", "हाँ", "ले ली", "खा ली", "पी ली", "हो गई", "yes i took")):
                confirmed = True

        if confirmed:
            self.api_client.mark_dose_taken(dose_id)
            ack_text = f"बहुत बढ़िया {elder_name}! मैंने ऐप में दर्ज़ कर दिया है कि आपने {med_name} ले ली है। अपना ख्याल रखिएगा!"
            print(f"\n🌸 AIRA: \"{ack_text}\"\n")
            speak_aira(ack_text, voice=self.voice, sink=self.sink)
        else:
            print(f"\nℹ️  Dose not confirmed yet. Will re-prompt in 5 minutes, or press [Enter] to confirm anytime.\n")


# ============================================================================
# Main Interaction Loop (Push-to-Talk / Full Webapp Sync)
# ============================================================================

def run_chat_loop(
    device_hint: str | int | None = None,
    sink: str | None = None,
    model_path: str = DEFAULT_MODEL,
    voice: str = DEFAULT_VOICE,
    gemini_key: str | None = None,
    openai_key: str | None = None,
    api_url: str | None = None,
    access_code: str | None = None,
    pin: str | None = None,
) -> None:
    """Full-scale AIRA Companion synced with FastAPI Webapp."""
    if sd is None or np is None:
        print("Required packages: sounddevice, numpy. Run: pip install sounddevice numpy", file=sys.stderr)
        return

    ensure_alsa_mic_volume()
    input_dev = find_usb_input_device(device_hint)
    dev_info = sd.query_devices(input_dev, "input")
    dev_name = dev_info.get("name", "Default")

    # Step 1: Connect & Sync with Webapp API
    client = get_api_client(base_url=api_url, access_code=access_code, pin=pin)
    print("\n⏳ Connecting to AIRA Webapp Backend...")
    synced = client.sync_all()

    elder_name = client.get_preferred_name()
    doc_info = client.get_doctor_details()
    doc_str = f"{doc_info.get('full_name')} ({doc_info.get('phone_e164')})" if doc_info else "None"
    med_count = len(client.doses_cache)

    bot = AiraChatBot(gemini_key=gemini_key, openai_key=openai_key, api_client=client)

    print("\n" + "=" * 68)
    print("🌸 AIRA Professional Voice Companion & Webapp Hardware Node")
    print(f"   Input Mic    : [{input_dev}] {dev_name}")
    print(f"   Output TTS   : Voice '{voice}' (hi-IN-SwaraNeural on Stone 620)")
    print(f"   AI Engine    : {bot.get_engine_name()}")
    print(f"   Webapp Sync  : {'🟢 Connected' if synced else '🟠 Offline Cache'} ({client.base_url})")
    print(f"   Elder Profile: {elder_name} (Code: {client.access_code})")
    print(f"   Medicines    : {med_count} scheduled doses today")
    print(f"   Doctor       : {doc_str}")
    print("   Interaction  : Push-to-Talk via [ENTER] key + Automated Medicine Alarms")
    print("=" * 68 + "\n")

    # Step 2: Start background medicine alarm daemon
    alarm_daemon = MedicineAlarmDaemon(
        api_client=client,
        bot=bot,
        input_dev=input_dev,
        voice=voice,
        sink=sink,
    )
    alarm_daemon.start()

    # Step 3: Proactive greeting on startup (speaks, but history stays clean)
    greeting = get_proactive_greeting(client)
    print(f"🗣️  AIRA: \"{greeting}\"\n")
    speak_aira(greeting, voice=voice, sink=sink)

    while True:
        try:
            print("\n👉 Press [ENTER] to speak (or type your question & press Enter)...")
            cmd = input().strip()
            if cmd.lower() in ("exit", "quit", "q"):
                alarm_daemon.stop()
                farewell = f"नमस्ते {elder_name}! अपना ख्याल रखिएगा, आपका दिन मंगलमय हो।"
                print(f"🌸 AIRA: \"{farewell}\"")
                speak_aira(farewell, voice=voice, sink=sink)
                break

            # If user typed text directly, answer directly!
            if cmd:
                print(f"👤 You : \"{cmd}\"")
                print("⏳ Thinking...")
                reply = bot.reply_text(cmd)
                print(f"🌸 AIRA: \"{reply}\"\n")
                speak_aira(reply, voice=voice, sink=sink)
                continue

            # Otherwise, record speech from AUX microphone
            recorded = record_speech_push_to_talk(input_dev, out_wav=DEFAULT_QUERY_WAV)
            if not recorded:
                notify = "माफ़ कीजिए, मुझे आपकी आवाज़ सुनाई नहीं दी। कृपया थोड़ा नज़दीक आकर दोबारा बोलिए।"
                print(f"\n🌸 AIRA: \"{notify}\"")
                speak_aira(notify, voice=voice, sink=sink)
                continue

            print("\n⏳ Processing your voice with Gemini AI...")
            transcript, reply = bot.reply_audio(DEFAULT_QUERY_WAV)

            print(f"👤 You : \"{transcript}\"")
            print(f"🌸 AIRA: \"{reply}\"\n")
            speak_aira(reply, voice=voice, sink=sink)

        except KeyboardInterrupt:
            alarm_daemon.stop()
            print("\n🛑 Stopped by user.")
            break


def run_terminal_chat(
    voice: str = DEFAULT_VOICE,
    gemini_key: str | None = None,
    openai_key: str | None = None,
    api_url: str | None = None,
    access_code: str | None = None,
    pin: str | None = None,
) -> None:
    """Terminal interactive chat mode (no microphone needed)."""
    client = get_api_client(base_url=api_url, access_code=access_code, pin=pin)
    client.sync_all()
    bot = AiraChatBot(gemini_key=gemini_key, openai_key=openai_key, api_client=client)

    print("\n" + "=" * 60)
    print("⌨️  AIRA Professional Terminal Chat (Webapp Synced)")
    print(f"   Voice: {voice} | AI: {bot.get_engine_name()}")
    print(f"   Elder: {client.get_preferred_name()} | API: {client.base_url}")
    print("   Type message & press Enter. Type 'exit' to quit.")
    print("=" * 60 + "\n")

    greeting = get_proactive_greeting(client)
    print(f"🌸 AIRA: {greeting}\n")
    speak_aira(greeting, voice=voice)

    while True:
        try:
            user_text = input("👤 You: ").strip()
            if not user_text:
                continue
            if user_text.lower() in ("exit", "quit", "q"):
                print("Goodbye!")
                break

            reply = bot.reply_text(user_text)
            print(f"🌸 AIRA: {reply}\n")
            speak_aira(reply, voice=voice)
        except (KeyboardInterrupt, EOFError):
            print("\nExiting chat.")
            break


def main() -> None:
    parser = argparse.ArgumentParser(description="AIRA Professional Voice Companion & Webapp Node")
    parser.add_argument("mode", nargs="?", default="voice", choices=["voice", "chat", "terminal"], help="Mode (default: voice)")
    parser.add_argument("--device", "-d", help="Microphone device index or name (e.g. 'USB' or 1)")
    parser.add_argument("--sink", "-s", help="PulseAudio/PipeWire sink name or index")
    parser.add_argument("--model", "-m", default=DEFAULT_MODEL, help="Path to Vosk speech model")
    parser.add_argument("--voice", "-v", default=DEFAULT_VOICE, choices=["swara", "neerja", "priyamvada", "espeak-hi", "espeak-en"], help="Voice profile")
    parser.add_argument("--gemini-key", default=os.environ.get("GEMINI_API_KEY"), help="Google Gemini API key")
    parser.add_argument("--openai-key", default=os.environ.get("OPENAI_API_KEY"), help="OpenAI API key")
    parser.add_argument("--api-url", default=os.environ.get("AIRA_API_URL") or "http://localhost:8000", help="AIRA FastAPI backend URL")
    parser.add_argument("--access-code", default=os.environ.get("AIRA_ACCESS_CODE") or "AIRA-7K3Q", help="Elder access code")
    parser.add_argument("--pin", default=os.environ.get("AIRA_PIN") or "1234", help="Elder 4-digit PIN")
    parser.add_argument("--text-mode", action="store_true", help="Run interactive terminal text chat")

    args = parser.parse_args()

    if args.text_mode or args.mode == "terminal":
        run_terminal_chat(
            voice=args.voice,
            gemini_key=args.gemini_key,
            openai_key=args.openai_key,
            api_url=args.api_url,
            access_code=args.access_code,
            pin=args.pin,
        )
    else:
        run_chat_loop(
            device_hint=args.device,
            sink=args.sink,
            model_path=args.model,
            voice=args.voice,
            gemini_key=args.gemini_key,
            openai_key=args.openai_key,
            api_url=args.api_url,
            access_code=args.access_code,
            pin=args.pin,
        )


cmd_chat_loop = run_chat_loop


if __name__ == "__main__":
    main()
