"use client";

import * as React from "react";
import { useLocale, useTranslations } from "next-intl";
import { Bell, BellOff, CheckCircle2, Clock, Pill, Volume2, VolumeX, X } from "lucide-react";

import { ElderContext } from "@/components/elder-context";
import {
  getAudioContext,
  isMedicineAlarmPlaying,
  playMedicineChime,
  startContinuousMedicineAlarm,
  stopMedicineAlarm,
} from "@/lib/audio-alerts";
import { Button } from "@/components/ui/button";

interface DueAlarmData {
  id: string;
  medicine_name: string;
  dose_label?: string;
  instructions?: string | null;
  scheduled_time?: string;
  color_tag?: string;
  isTest?: boolean;
}

export function MedicineAlarmBanner() {
  const elderContext = React.useContext(ElderContext);
  const selectedElder = elderContext?.selectedElder ?? null;
  const locale = useLocale();

  const [activeAlarm, setActiveAlarm] = React.useState<DueAlarmData | null>(null);
  const [snoozedIds, setSnoozedIds] = React.useState<Record<string, number>>({});
  const [isMuted, setIsMuted] = React.useState(false);
  const handledIdsRef = React.useRef<Set<string>>(new Set());

  // Listen for custom trigger events (e.g. from "Test Alarm" button on medicine card)
  React.useEffect(() => {
    const handleCustomTrigger = (e: Event) => {
      const customEvent = e as CustomEvent<DueAlarmData>;
      if (customEvent.detail) {
        // Unlock audio context on user click
        getAudioContext();
        setActiveAlarm(customEvent.detail);
        setIsMuted(false);
        startContinuousMedicineAlarm();
      }
    };

    window.addEventListener("aira:trigger-medicine-alarm", handleCustomTrigger);
    return () => {
      window.removeEventListener("aira:trigger-medicine-alarm", handleCustomTrigger);
    };
  }, []);

  // Periodic check for due medicines (every 20 seconds)
  React.useEffect(() => {
    const checkDueMedicines = async () => {
      try {
        const url = selectedElder
          ? `/api/v1/elders/${selectedElder.id}/doses`
          : `/api/v1/elders/me/doses`;
        const res = await fetch(url);
        if (!res.ok) return;
        const doses = await res.json();
        if (!Array.isArray(doses)) return;

        const now = new Date();
        const currentHour = now.getHours();
        const currentMinute = now.getMinutes();
        const currentTimeMinutes = currentHour * 60 + currentMinute;

        for (const dose of doses) {
          if (dose.status !== "scheduled") continue;
          if (handledIdsRef.current.has(dose.id)) continue;

          // Check if snoozed
          const snoozeExpiry = snoozedIds[dose.id];
          if (snoozeExpiry && Date.now() < snoozeExpiry) continue;

          const [dHour, dMinute] = (dose.scheduled_time || "08:00").split(":").map(Number);
          const doseTimeMinutes = dHour * 60 + dMinute;

          // Alarm triggers if current time matches dose time or is within 25 minutes after
          const timeDiff = currentTimeMinutes - doseTimeMinutes;
          if (timeDiff >= 0 && timeDiff <= 25) {
            setActiveAlarm({
              id: dose.id,
              medicine_name: dose.medicine_name,
              dose_label: dose.dose_label,
              instructions: dose.instructions,
              scheduled_time: dose.scheduled_time,
              color_tag: dose.color_tag,
              isTest: false,
            });
            startContinuousMedicineAlarm();
            break;
          }
        }
      } catch {
        // Ignored
      }
    };

    checkDueMedicines();
    const interval = setInterval(checkDueMedicines, 20000);
    return () => clearInterval(interval);
  }, [selectedElder, snoozedIds]);

  // Clean up alarm sound when unmounted
  React.useEffect(() => {
    return () => {
      stopMedicineAlarm();
    };
  }, []);

  const handleStopAlarm = () => {
    stopMedicineAlarm();
    setIsMuted(true);
  };

  const handleDismiss = () => {
    stopMedicineAlarm();
    if (activeAlarm) {
      handledIdsRef.current.add(activeAlarm.id);
    }
    setActiveAlarm(null);
  };

  const handleSnooze = () => {
    stopMedicineAlarm();
    if (activeAlarm) {
      setSnoozedIds((prev) => ({
        ...prev,
        [activeAlarm.id]: Date.now() + 10 * 60 * 1000, // 10 minutes
      }));
    }
    setActiveAlarm(null);
  };

  const handleMarkTaken = async () => {
    stopMedicineAlarm();
    if (activeAlarm) {
      handledIdsRef.current.add(activeAlarm.id);
      if (!activeAlarm.isTest) {
        try {
          await fetch(`/api/v1/doses/${activeAlarm.id}/take`, { method: "POST" });
        } catch {
          // Ignored
        }
      }
    }
    setActiveAlarm(null);
  };

  if (!activeAlarm) return null;

  return (
    <div
      role="alert"
      aria-live="assertive"
      className="fixed inset-x-3 bottom-20 sm:bottom-6 sm:right-6 sm:left-auto sm:w-[420px] z-50 bg-surface border-2 border-primary shadow-2xl rounded-2xl p-4 sm:p-5 animate-in slide-in-from-bottom-5 duration-200"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="relative w-11 h-11 rounded-2xl bg-primary text-white flex items-center justify-center shrink-0 shadow-md">
            <Pill className="w-6 h-6 animate-pulse" />
            <span className="absolute -top-1 -right-1 flex h-4 w-4">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emergency opacity-75" />
              <span className="relative inline-flex rounded-full h-4 w-4 bg-emergency text-[9px] font-bold text-white items-center justify-center">
                !
              </span>
            </span>
          </div>

          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-black tracking-wider uppercase px-2 py-0.5 rounded-md bg-primary-soft text-primary">
                {locale === "hi" ? "दवा अलार्म ⏰" : "Medicine Alarm ⏰"}
              </span>
              {activeAlarm.scheduled_time && (
                <span className="text-xs font-mono font-bold text-text-secondary flex items-center gap-1">
                  <Clock className="w-3.5 h-3.5" />
                  {activeAlarm.scheduled_time}
                </span>
              )}
            </div>
            <h3 className="text-base sm:text-lg font-extrabold text-text-primary mt-1 leading-tight">
              {activeAlarm.medicine_name}
            </h3>
          </div>
        </div>

        <button
          type="button"
          onClick={handleDismiss}
          className="p-1 rounded-lg text-text-secondary hover:text-text-primary hover:bg-surface-muted transition-colors"
          title={locale === "hi" ? "बंद करें" : "Dismiss"}
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      {activeAlarm.dose_label && (
        <p className="text-xs sm:text-sm font-semibold text-text-secondary mt-2">
          {activeAlarm.dose_label}
        </p>
      )}

      {activeAlarm.instructions && (
        <p className="text-xs text-text-secondary italic mt-1 bg-surface-muted p-2 rounded-lg border border-border">
          "{activeAlarm.instructions}"
        </p>
      )}

      {/* Alarm Sound Status & Controls */}
      <div className="mt-3 flex items-center justify-between p-2 rounded-xl bg-primary-soft/40 border border-primary/20 text-xs">
        <div className="flex items-center gap-2 text-primary font-bold">
          <Volume2 className="w-4 h-4 animate-bounce" />
          <span>{locale === "hi" ? "अलार्म बज रहा है..." : "Alarm ringing..."}</span>
        </div>
        <button
          type="button"
          onClick={handleStopAlarm}
          className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-surface text-text-primary border border-border hover:bg-surface-muted font-semibold transition-colors"
        >
          <VolumeX className="w-3.5 h-3.5 text-text-secondary" />
          <span>{locale === "hi" ? "म्यूट करें" : "Mute Sound"}</span>
        </button>
      </div>

      {/* Action Buttons */}
      <div className="mt-4 grid grid-cols-2 gap-2">
        <Button
          type="button"
          variant="outline"
          onClick={handleSnooze}
          className="text-xs font-bold py-2.5 flex items-center justify-center gap-1.5"
        >
          <BellOff className="w-3.5 h-3.5" />
          <span>{locale === "hi" ? "स्नूज़ (10 मिनट)" : "Snooze (10m)"}</span>
        </Button>

        <Button
          type="button"
          onClick={handleMarkTaken}
          className="text-xs font-bold py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white flex items-center justify-center gap-1.5 shadow-sm"
        >
          <CheckCircle2 className="w-4 h-4" />
          <span>{locale === "hi" ? "दवा ले ली" : "Mark Taken"}</span>
        </Button>
      </div>
    </div>
  );
}
