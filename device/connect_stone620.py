#!/usr/bin/env python3
"""
AIRA Audio Connect Helper
Connects the 'Stone 620' Bluetooth speaker, sets it as the default output sink,
and verifies the USB soundcard microphone.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time

try:
    from aira_tts import auto_connect_stone620, find_stone620_sink, speak
except ImportError:
    auto_connect_stone620 = None
    find_stone620_sink = None
    speak = None


def main() -> None:
    print("=" * 60)
    print("🔊 AIRA Hardware Audio Setup (Stone 620 + USB Mic)")
    print("=" * 60)

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

    # 2. Connect Stone 620
    print("\n[2/3] Connecting to Stone 620 Bluetooth Speaker...")
    sink = None
    if auto_connect_stone620:
        sink = auto_connect_stone620()
    else:
        # Direct fallback
        res = subprocess.run(["bluetoothctl", "devices"], capture_output=True, text=True)
        mac = None
        for line in res.stdout.splitlines():
            if "stone 620" in line.lower() or "stone" in line.lower():
                parts = line.split()
                if len(parts) >= 3 and parts[0] == "Device":
                    mac = parts[1]
                    break
        if mac:
            print(f"  Connecting to {mac}...")
            subprocess.run(["bluetoothctl", "connect", mac], capture_output=True, text=True, timeout=10)
            time.sleep(2)

    # 3. Verify PipeWire sink
    print("\n[3/3] Setting Stone 620 as Default Audio Output...")
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
            print("  ⚠️ Stone 620 Bluetooth sink not yet visible. Make sure the speaker is ON and paired.")
    except Exception as e:
        print(f"  ⚠️ pactl error: {e}")

    # 4. Speak confirmation through Stone 620
    print("\n📢 Playing confirmation audio through Stone 620...")
    confirmation_text = "नमस्ते! आपका स्टोन 620 स्पीकर और यूएसबी माइक तैयार हैं।"
    if speak:
        speak(confirmation_text, voice_key="swara")
    else:
        subprocess.run(["espeak-ng", "-v", "hi+f3", "-s", "145", confirmation_text])

    print("\n" + "=" * 60)
    print("✨ Audio setup complete!")
    print("👉 Now simply run: python device/aira_chat.py")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
