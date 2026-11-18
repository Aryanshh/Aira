# AIRA Raspberry Pi: Setup and Audio Test Context

Context file for Antigravity. It records what has been set up on the AIRA device prototype so far and explains the test script `aira_audio_test.py`. Read this before changing anything on the device side.

| | |
|---|---|
| **Project** | AIRA, AI elder-care companion (device + web app) |
| **Date** | 18 November 2026 |
| **Related spec** | `AIRA_WebApp_Spec.md` (web app; device SOS contract in section 7.4) |

---

## 1. Goal of this stage

First hardware test of the AIRA tabletop device:

1. Pi plays a spoken reply through a **Bluetooth speaker**.
2. Pi listens through a **3.5mm microphone (via a USB sound card)**, detects the user saying **"Hey Aira"**, and replies **"Hey, how are you?"**.

Test order: speaker first, then microphone level, then the full wake-and-reply loop.

---

## 2. Hardware and current status

| Item | Detail | Status |
|---|---|---|
| Computer | Raspberry Pi 3B+ (hostname `Aira`, login user `main`) | Running |
| Speaker | Bluetooth speaker shown as **"Stone 620"** | Paired and connected in `bluetoothctl` |
| Microphone | 3.5mm microphone | **Needs a USB sound card or USB mic** (see section 3); mic test not done yet |
| Speaker playback test | `paplay` and `espeak-ng` check | Not yet confirmed by the user |
| Wake-word loop (`listen`) | "Hey Aira" then reply | Not yet run |

---

## 3. Key hardware finding

The Raspberry Pi 3B+ 3.5mm jack is **output only** (audio plus composite video). It has **no microphone input**. A 3.5mm mic will not work in it.

Required: a **USB audio adapter with a MIC jack**, or a **USB microphone**.
- Plain electret or lapel mic goes in the pink MIC jack.
- A 4-contact phone/headset mic needs an adapter that supports that style.

The Bluetooth speaker needs no extra hardware (the 3B+ has built-in Bluetooth).

---

## 4. What was set up (in order)

### 4.1 Operating system
- Raspberry Pi OS (64-bit) with Desktop (Bookworm) recommended: it already includes PipeWire and Bluetooth audio support.
- Headless use over SSH is fine.
- If the Lite image is used, `pactl` may not find a server. PipeWire would then need to be installed separately (not covered yet).

### 4.2 Packages installed (`setup_pi.sh`)
```
python3-venv python3-pip
alsa-utils pulseaudio-utils            # arecord/aplay, pactl/paplay (work with PipeWire)
portaudio19-dev libportaudio2 libasound2-dev
espeak-ng                              # offline text-to-speech
bluez                                  # Bluetooth stack tools
libspa-0.2-bluetooth                   # Bluetooth audio for PipeWire (optional if already present)
wget unzip
```

### 4.3 Python environment
- Location: `~/aira/venv` (created with `python3 -m venv`).
- Python packages: `numpy`, `sounddevice`, `vosk`.

### 4.4 Offline speech model
- `vosk-model-small-en-us-0.15` (about 40 MB), downloaded from `https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip`.
- Location: `~/aira/models/vosk-model-small-en-us-0.15`.
- Override with the environment variable `AIRA_VOSK_MODEL` or `--model`.
- An Indian-English small model also exists on the Vosk models page and can be tried later for better accuracy on Indian accents.

### 4.5 Directory layout on the Pi
```
~/aira/
├─ venv/
├─ models/
│  └─ vosk-model-small-en-us-0.15/
└─ aira_audio_test.py
```

### 4.6 Bluetooth speaker pairing (done)
```bash
bluetoothctl
power on
agent on
default-agent
scan on
pair   <SPEAKER_MAC>
trust  <SPEAKER_MAC>
connect <SPEAKER_MAC>
scan off
exit
```
- `trust` lets the speaker reconnect automatically when powered on.
- Make it the audio output:
  ```bash
  pactl info | grep "Default Sink"          # should start with bluez_
  pactl list short sinks                    # find the bluez_output... name
  pactl set-default-sink <bluez_output_name>
  ```
- Volume: `pactl set-sink-volume @DEFAULT_SINK@ 80%` plus the speaker's own volume.

### 4.7 Speaker-only test (no Python needed)
```bash
paplay /usr/share/sounds/alsa/Front_Center.wav
espeak-ng -v en-us -s 150 -p 55 -w /tmp/aira.wav "Hey, how are you?" && paplay /tmp/aira.wav
```

### 4.8 Microphone setup (to do once the USB sound card is attached)
```bash
arecord -l                      # find the card number
alsamixer -c <card>             # F4 = Capture; press M to unmute; set about 60-80%
```

---

## 5. Files

| File | Purpose |
|---|---|
| `setup_pi.sh` | One-time installer: packages, venv, Vosk model, copies the test script into `~/aira` |
| `aira_audio_test.py` | Test tool with four commands: `devices`, `speaker`, `mic`, `listen` |
| `aira_tts.py` | Multi-voice synthesizer for Female English, Hindi, and Hinglish |

Run (inside the venv):
```bash
source ~/aira/venv/bin/activate
cd ~/aira
python aira_audio_test.py devices
python aira_audio_test.py speaker
python aira_audio_test.py mic    --device "USB"
python aira_audio_test.py listen --device "USB"

# Test Voice Models (Female English, Hindi, Hinglish):
python aira_tts.py voices
python aira_tts.py test-all
python aira_tts.py speak --voice swara --text "Namaste Dadi! Aapki BP ki medicine lene ka time ho gaya hai."
python aira_tts.py speak --voice neerja --text "Hello! It is time for your afternoon walk."
python aira_tts.py speak --voice priyamvada --text "नमस्ते, आपकी दवा का समय हो गया है।"
```
`--device` accepts an index number or part of the device name (see `devices`).

---

## 6. `aira_audio_test.py` reference

### 6.1 Commands
| Command | What it does | Options |
|---|---|---|
| `devices` | Lists audio devices and defaults | none |
| `speaker` | Speaks the reply through the default output (Bluetooth) | `--reply`, `--sink` |
| `mic` | Live level meter for N seconds; reports quiet, clipping or OK | `--device`, `--seconds` (default 8) |
| `listen` | Waits for "Hey Aira", then replies | `--device`, `--model`, `--reply`, `--sink` |

### 6.2 Constants
| Name | Value | Meaning |
|---|---|---|
| `TARGET_RATE` | 16000 | Sample rate the speech model needs |
| `DEFAULT_MODEL` | `~/aira/models/vosk-model-small-en-us-0.15` (or `AIRA_VOSK_MODEL`) | Speech model path |
| `DEFAULT_REPLY` | `"Hey, how are you?"` | Reply text |
| `HEADS` | hey, hay, hi, hello, ok, okay | Words that can start the wake phrase |
| `STRONG_NAMES` | aira, airah, ayra, eira, aaira | Accepted alone |
| `NAMES` | strong names plus ira, era, aria, arya, aera, ayara | Accepted after a head word |

### 6.3 Functions
| Function | Role |
|---|---|
| `heard_wake_word(text)` | Fuzzy match for "Hey Aira" in recognised text (handles splits like "i ra" and variants like "aria") |
| `parse_device(value)` | Converts `--device` to an int or leaves a name string |
| `to_mono(block)` | Averages channels to mono |
| `to_16k(samples, rate)` | Resamples to 16 kHz (block-average for integer ratios such as 48000, linear interpolation otherwise) |
| `open_mic(device, callback)` | Opens the mic trying 16000, device default, 48000, 44100 Hz and 1 then 2 channels |
| `pad_wav(src, dst, lead, tail)` | Adds 0.6 s silence before and 0.4 s after speech so Bluetooth speakers do not clip it |
| `play(path, sink)` | Plays WAV with `paplay` (PipeWire/Pulse), falls back to `aplay` |
| `speak(text, sink)` | `espeak-ng` to WAV, pad, play |
| `cmd_devices / cmd_speaker / cmd_mic / cmd_listen` | The four commands |

### 6.4 `listen` flow
1. Load the Vosk model, open the mic stream (0.1 s blocks), put audio in a queue.
2. Convert each block to mono 16 kHz and feed the recogniser. Print changing partial text as `heard: ...`.
3. When `heard_wake_word()` is true: **stop the mic stream** (so the Pi does not hear its own reply), speak the reply, clear the queue, create a fresh recogniser, wait 0.5 s, restart the stream.
4. Ctrl+C stops cleanly.

### 6.5 Design decisions
- **Fully offline.** Vosk and `espeak-ng` run on the Pi; no audio leaves the device.
- **Mic is muted while speaking** to avoid a self-trigger loop.
- **Silence padding** because Bluetooth speakers often clip the start of audio.
- **Sample-rate fallback** because USB adapters often support only 44.1 or 48 kHz.
- **Fuzzy wake matching** because ordinary speech recognition spells a made-up word like "Aira" in many ways.
- Works on Python 3.9+ (`from __future__ import annotations`); the target OS ships Python 3.11.

### 6.6 Verified so far
Logic tests run off-device passed: wake-word matching (accepted "hey aira", "hey ira", "hey i ra", "hi aira", "hey aria", "hello aira"; rejected "hello there", "what is the area", "hey how are you"), 48 kHz and 44.1 kHz to 16 kHz conversion, WAV padding. **Real microphone, Bluetooth and Vosk accuracy have not been tested on the device yet.**

### 6.7 Voice models for English, Hindi, and Hinglish (`aira_tts.py`)
| Profile Key | Voice / Model | Language | Type | Why chosen for AIRA |
|---|---|---|---|---|
| `swara` | `hi-IN-SwaraNeural` | Hindi & Hinglish | Online Neural | **Gold standard for elder companion.** Flawlessly speaks colloquial Hinglish ("Dadi, BP medicine ka time ho gaya") and pure Hindi with warm, polite inflection. |
| `neerja` | `en-IN-NeerjaNeural` | English (India) | Online Neural | Clear, respectful Indian English female voice for alerts and daily summaries. |
| `priyamvada` | `hi_IN-priyamvada-medium` | Hindi | Offline Neural (Piper) | ~60 MB ONNX model running locally on the Pi 3B+ without internet (real-time factor ~0.25x). |
| `espeak-hi` | `hi+f3` | Hindi | Offline Fallback | Built-in espeak-ng female voice. 0 MB RAM, 0 latency, guaranteed offline safety net. |
| `espeak-en` | `en-in+f2` | English (India) | Offline Fallback | Built-in espeak-ng Indian English female voice. |

---

## 7. Known limitations and troubleshooting

| Problem | Cause / fix |
|---|---|
| No sound | Speaker not the default sink: `pactl set-default-sink ...`; reconnect in `bluetoothctl` |
| Connected but no `bluez_output` sink | `systemctl --user restart pipewire pipewire-pulse wireplumber`, reconnect speaker |
| `pactl` cannot connect to server | Probably Lite OS without PipeWire |
| First word cut off | Padding in `pad_wav` can be increased |
| `mic` says very quiet | Mic not in MIC jack, muted, or Capture level too low (alsamixer F4) |
| `mic` says clipping | Lower Capture |
| "Could not open the microphone" | Use the index from `devices`, e.g. `--device 2` |
| Hears words but ignores "Hey Aira" | Read the `heard:` line, add that spelling to `NAMES` |
| Stutter | Wi-Fi and Bluetooth share one chip on the 3B+; use 5 GHz Wi-Fi or Ethernet |
| Robotic voice | `espeak-ng` is only a placeholder voice |
| Bluetooth delay/drops | Acceptable for tests; use a wired speaker for the final SOS alert tone |

---

## 8. Next steps (suggested order)

1. **Confirm speaker output** (section 4.7), then run `python aira_audio_test.py speaker`.
2. **Attach the USB sound card**, set Capture level, run `mic`, then `listen`.
3. **Replace fuzzy text matching with a real wake-word model** trained for "Hey Aira" (a dedicated engine is more accurate and uses much less CPU than running speech recognition continuously).
4. **Natural voice:** replace `espeak-ng` with a better offline or cloud text-to-speech with Hindi and English.
5. **Speech to text and conversation:** after the wake word, capture the user's sentence, transcribe, send to the AIRA service, speak the answer (see the device and AI parts of the concept document).
6. **Physical controls on GPIO:** SOS button, hardware mute switch, status LEDs, as separate processes so SOS never depends on the AI process.
7. **SOS to the web app:** send a signed `POST /api/v1/device/sos` (headers `X-Device-Id`, `X-Timestamp`, `X-Nonce`, `X-Signature` = HMAC-SHA256 of `timestamp.nonce.body`, body `{"client_event_id": "...", "occurred_at": "..."}`) as defined in `AIRA_WebApp_Spec.md` section 7.4.
8. **Run as a service:** systemd unit with automatic restart and a watchdog, boot-to-ready behaviour, clear status when Wi-Fi or the AI service is unreachable.

---

## 9. Rules for Antigravity when extending the device code

- Target hardware: Raspberry Pi 3B+ (1 GB RAM, Cortex-A53). Keep CPU and memory use low.
- Target OS: Raspberry Pi OS Bookworm, Python 3.11, PipeWire audio. Use `paplay`/`pactl` for playback and Bluetooth routing.
- Use the venv at `~/aira/venv`; list new dependencies in `requirements.txt` and in `setup_pi.sh`.
- **The Pi 3.5mm jack is never the microphone input.** Capture comes from a USB audio device.
- Keep listening **local and offline** by default. Do not stream or store raw audio without explicit design and consent.
- Mute the mic stream while the device is speaking.
- Safety-critical behaviour (SOS button, mute switch, alerts) must be a separate minimal process that works without the AI components or internet, and must never claim an alert was sent until delivery is confirmed.
- No AI model may directly trigger emergency actions; use deterministic rules.
- Keep all user-facing phrases in one place so they can be translated into Hindi later.
- Add type hints, small functions and tests for logic that can run off-device (matching, resampling, state machines).
- Do not change the test script's command names or options without updating this file.
