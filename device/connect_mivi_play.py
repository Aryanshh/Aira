#!/usr/bin/env python3
"""
AIRA Audio Connect Helper - Mivi Play Edition
Connects the 'Mivi Play' Bluetooth speaker, sets it as the default output sink,
and verifies the USB soundcard microphone on Raspberry Pi 3B+.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time

try:
    from aira_tts import auto_connect_speaker, find_bluetooth_sink, speak
except ImportError:
    auto_connect_speaker = None
    find_bluetooth_sink = None
    speak = None


def main() -> None:
    print("=" * 62)
    print("🔊 AIRA Hardware Audio Setup (Mivi Play + USB Mic)")
    print("=" * 62)

    # 1. Check USB Microphone
    print("\n[1/3] Checking USB Microphone...")
    try:
        import sounddevice as sd
        devices = sd.query_devices()
        usb_in = None
        for idx, dev in enumerate(devices):
            if dev.get("max_input_channels", 0) > 0 and "usb" in dev.get("name", "").lower():
                usb_in = (idx, dev["name"])
                break

        if usb_in:
            print(f"  ✅ Found USB Mic: [{usb_in[0]}] {usb_in[1]}")
        else:
            print("  ⚠️ USB Mic not explicitly found, will use default system input.")
    except Exception as e:
        print(f"  ⚠️ Could not inspect audio input: {e}")

    # 2. Connect Mivi Play Bluetooth Speaker
    print("\n[2/3] Connecting to Mivi Play Bluetooth Speaker...")
    sink = None
    if auto_connect_speaker:
        sink = auto_connect_speaker(preferred_keywords=("mivi play", "mivi", "stone 620", "stone"))
    else:
        # Fallback direct bluetoothctl check
        res = subprocess.run(["bluetoothctl", "devices"], capture_output=True, text=True)
        mac = None
        speaker_name = "Mivi Play"
        for keyword in ("mivi play", "mivi", "stone 620", "stone"):
            for line in res.stdout.splitlines():
                if keyword in line.lower():
                    parts = line.split()
                    if len(parts) >= 3 and parts[0] == "Device":
                        mac = parts[1]
                        speaker_name = " ".join(parts[2:])
                        break
            if mac:
                break

        if mac:
            print(f"  Connecting to {speaker_name} ({mac})...")
            subprocess.run(["bluetoothctl", "connect", mac], capture_output=True, text=True, timeout=12)
            time.sleep(2)

    # 3. Verify PipeWire sink & set as default
    print("\n[3/3] Setting Mivi Play as Default Audio Output...")
    try:
        p = subprocess.run(["pactl", "list", "short", "sinks"], capture_output=True, text=True)
        target_sink = None
        for line in p.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 2 and "bluez_output" in parts[1].lower():
                target_sink = parts[1]
                break

        if target_sink:
            subprocess.run(["pactl", "set-default-sink", target_sink], check=True)
            subprocess.run(["pactl", "set-sink-volume", target_sink, "85%"], check=True)
            print(f"  ✅ Default Sink set to: {target_sink} (Volume: 85%)")
        else:
            print("  ⚠️ Mivi Play Bluetooth sink not yet visible.")
            print("     Make sure Mivi Play is turned ON, in pairing mode, or paired via bluetoothctl.")
    except Exception as e:
        print(f"  ⚠️ pactl error: {e}")

    # 4. Speak confirmation through Mivi Play
    print("\n📢 Playing confirmation audio through Mivi Play...")
    confirmation_text = "नमस्ते! आपका मिवी प्ले स्पीकर और यूएसबी माइक तैयार हैं।"
    if speak:
        speak(confirmation_text, voice_key="swara")
    else:
        subprocess.run(["espeak-ng", "-v", "hi+f3", "-s", "145", confirmation_text])

    print("\n" + "=" * 62)
    print("✨ Audio setup complete!")
    print("👉 Now start AIRA: python device/aira_chat.py")
    print("=" * 62 + "\n")


if __name__ == "__main__":
    main()
