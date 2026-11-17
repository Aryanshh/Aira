/**
 * Aira Audio Alert System
 * Synthesizes high-fidelity medicine alarms and emergency SOS sirens
 * using the Web Audio API with automatic suspended-state resumption
 * and mobile vibration support.
 */

let sharedAudioCtx: AudioContext | null = null;
let activeMedicineAlarmTimer: ReturnType<typeof setInterval> | null = null;
let activeSosSirenTimer: ReturnType<typeof setInterval> | null = null;
let activeOscillators: OscillatorNode[] = [];

export function getAudioContext(): AudioContext | null {
  if (typeof window === "undefined") return null;
  try {
    const AudioContextClass =
      window.AudioContext ||
      (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    if (!AudioContextClass) return null;

    if (!sharedAudioCtx || sharedAudioCtx.state === "closed") {
      sharedAudioCtx = new AudioContextClass();
    }
    if (sharedAudioCtx.state === "suspended") {
      sharedAudioCtx.resume().catch(() => {
        // Autoplay policy may suspend until user gesture
      });
    }
    return sharedAudioCtx;
  } catch {
    return null;
  }
}

/**
 * Single chime phrase for Medicine Reminder
 * Bright, melodic 4-note bell chord: E5 -> G#5 -> B5 -> E6
 */
export function playMedicineChime(): void {
  const ctx = getAudioContext();
  if (!ctx) return;
  if (ctx.state === "suspended") {
    ctx.resume().catch(() => {});
  }

  const now = ctx.currentTime;
  const notes = [
    { freq: 659.25, time: 0.0, dur: 0.35 },  // E5
    { freq: 830.61, time: 0.18, dur: 0.35 }, // G#5
    { freq: 987.77, time: 0.36, dur: 0.35 }, // B5
    { freq: 1318.51, time: 0.54, dur: 0.6 }, // E6
  ];

  notes.forEach(({ freq, time, dur }) => {
    try {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();

      osc.type = "sine";
      osc.frequency.setValueAtTime(freq, now + time);

      // Bell envelope (quick attack, exponential decay)
      gain.gain.setValueAtTime(0.001, now + time);
      gain.gain.linearRampToValueAtTime(0.28, now + time + 0.04);
      gain.gain.exponentialRampToValueAtTime(0.001, now + time + dur);

      osc.connect(gain);
      gain.connect(ctx.destination);

      osc.start(now + time);
      osc.stop(now + time + dur);
    } catch {
      // Ignored
    }
  });

  if (typeof navigator !== "undefined" && navigator.vibrate) {
    try {
      navigator.vibrate([200, 100, 200]);
    } catch {
      // Ignored
    }
  }
}

/**
 * Continuous Medicine Alarm:
 * Repeatedly plays the medicine chime every 2.4s until stopped
 */
export function startContinuousMedicineAlarm(): void {
  stopMedicineAlarm();
  playMedicineChime();
  activeMedicineAlarmTimer = setInterval(() => {
    playMedicineChime();
  }, 2400);
}

export function stopMedicineAlarm(): void {
  if (activeMedicineAlarmTimer) {
    clearInterval(activeMedicineAlarmTimer);
    activeMedicineAlarmTimer = null;
  }
}

export function isMedicineAlarmPlaying(): boolean {
  return activeMedicineAlarmTimer !== null;
}

/**
 * Emergency SOS Siren Pulse:
 * Loud, piercing alternating two-tone emergency alarm (880 Hz / 660 Hz)
 */
export function playSosPulse(): void {
  const ctx = getAudioContext();
  if (!ctx) return;
  if (ctx.state === "suspended") {
    ctx.resume().catch(() => {});
  }

  const now = ctx.currentTime;
  try {
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();

    osc.type = "sawtooth";
    // Siren sweep: 880Hz down to 587Hz then back up
    osc.frequency.setValueAtTime(880, now);
    osc.frequency.exponentialRampToValueAtTime(587.33, now + 0.35);
    osc.frequency.exponentialRampToValueAtTime(880, now + 0.7);
    osc.frequency.exponentialRampToValueAtTime(587.33, now + 1.05);

    gain.gain.setValueAtTime(0.01, now);
    gain.gain.linearRampToValueAtTime(0.4, now + 0.08);
    gain.gain.setValueAtTime(0.4, now + 1.0);
    gain.gain.linearRampToValueAtTime(0.01, now + 1.2);

    osc.connect(gain);
    gain.connect(ctx.destination);

    osc.start(now);
    osc.stop(now + 1.2);
    activeOscillators.push(osc);
  } catch {
    // Ignored
  }

  if (typeof navigator !== "undefined" && navigator.vibrate) {
    try {
      navigator.vibrate([400, 150, 400, 150, 600]);
    } catch {
      // Ignored
    }
  }
}

/**
 * Continuous SOS Siren:
 * Repeatedly sounds the emergency siren every 1.3s until stopped
 */
export function startContinuousSosSiren(): void {
  stopSosSiren();
  playSosPulse();
  activeSosSirenTimer = setInterval(() => {
    playSosPulse();
  }, 1300);
}

export function stopSosSiren(): void {
  if (activeSosSirenTimer) {
    clearInterval(activeSosSirenTimer);
    activeSosSirenTimer = null;
  }
  activeOscillators.forEach((osc) => {
    try {
      osc.stop();
    } catch {
      // Already stopped
    }
  });
  activeOscillators = [];
}

export function isSosSirenPlaying(): boolean {
  return activeSosSirenTimer !== null;
}
