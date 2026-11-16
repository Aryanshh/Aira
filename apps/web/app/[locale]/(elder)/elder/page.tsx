"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import {
  AlertCircle,
  Bell,
  Check,
  CheckCircle2,
  Clock,
  Heart,
  LogOut,
  MessageSquare,
  Moon,
  Phone,
  Pill,
  RefreshCw,
  Sun,
  Sunrise,
  Sunset,
  Volume2,
  WifiOff,
} from "lucide-react";
import { AiraLogo } from "@/components/aira-logo";

interface ElderProfile {
  id: string;
  full_name: string;
  preferred_name: string | null;
  language: string;
  timezone: string;
  text_size: number; // 0: normal, 1: large, 2: xlarge
}

interface DoseItem {
  id: string;
  elder_id: string;
  medicine_id: string;
  scheduled_date: string;
  scheduled_time: string;
  scheduled_at: string;
  medicine_name: string;
  dose_label: string;
  instructions: string | null;
  color_tag: string | null;
  status: "scheduled" | "taken" | "missed" | "skipped";
  can_undo: boolean;
  taken_at_timestamp?: number;
}

interface ContactItem {
  id: string;
  full_name: string;
  role: "family" | "doctor" | "neighbour";
  phone_e164: string;
  whatsapp_e164?: string | null;
  escalation_order: number;
}

// Sound synthesized using Web Audio API
function playAlertChime(isSos: boolean = false) {
  try {
    const AudioContextClass = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    if (!AudioContextClass) return;
    const ctx = new AudioContextClass();

    if (isSos) {
      // Urgent two-tone siren
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = "sawtooth";
      osc.frequency.setValueAtTime(880, ctx.currentTime);
      osc.frequency.exponentialRampToValueAtTime(440, ctx.currentTime + 0.3);
      osc.frequency.exponentialRampToValueAtTime(880, ctx.currentTime + 0.6);
      gain.gain.setValueAtTime(0.3, ctx.currentTime);
      gain.gain.linearRampToValueAtTime(0.01, ctx.currentTime + 1.2);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start();
      osc.stop(ctx.currentTime + 1.2);
    } else {
      // Gentle confirmation chime
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = "sine";
      osc.frequency.setValueAtTime(523.25, ctx.currentTime); // C5
      osc.frequency.setValueAtTime(659.25, ctx.currentTime + 0.15); // E5
      gain.gain.setValueAtTime(0.15, ctx.currentTime);
      gain.gain.linearRampToValueAtTime(0.01, ctx.currentTime + 0.5);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start();
      osc.stop(ctx.currentTime + 0.5);
    }
  } catch {
    // Ignore audio autoplay restrictions
  }
}

export default function ElderSimpleViewPage() {
  const t = useTranslations("elder");
  const tCommon = useTranslations("common");
  const locale = useLocale();
  const router = useRouter();

  const [activeTab, setActiveTab] = React.useState<"medicines" | "contacts">("medicines");
  const [profile, setProfile] = React.useState<ElderProfile | null>(null);
  const [doses, setDoses] = React.useState<DoseItem[]>([]);
  const [contacts, setContacts] = React.useState<ContactItem[]>([]);
  const [textSize, setTextSize] = React.useState<number>(1); // Default large
  const [loading, setLoading] = React.useState(true);
  const [isOnline, setIsOnline] = React.useState(true);
  const [currentTime, setCurrentTime] = React.useState("");
  const [currentDate, setCurrentDate] = React.useState("");

  // SOS hold state (2-second hold required)
  const [sosProgress, setSosProgress] = React.useState(0);
  const [isHoldingSos, setIsHoldingSos] = React.useState(false);
  const [sosActive, setSosActive] = React.useState(false);
  const [sosOfflineAlert, setSosOfflineAlert] = React.useState(false);
  const holdTimerRef = React.useRef<NodeJS.Timeout | null>(null);
  const progressIntervalRef = React.useRef<NodeJS.Timeout | null>(null);

  // Undo countdown timers for taken doses
  const [undoTimeLeft, setUndoTimeLeft] = React.useState<Record<string, number>>({});

  // Clock tick
  React.useEffect(() => {
    const updateClock = () => {
      const now = new Date();
      setCurrentTime(
        now.toLocaleTimeString(locale === "hi" ? "hi-IN" : "en-US", {
          hour: "2-digit",
          minute: "2-digit",
        })
      );
      setCurrentDate(
        now.toLocaleDateString(locale === "hi" ? "hi-IN" : "en-US", {
          weekday: "long",
          day: "numeric",
          month: "long",
          year: "numeric",
        })
      );
    };
    updateClock();
    const timer = setInterval(updateClock, 1000);
    return () => clearInterval(timer);
  }, [locale]);

  // Online / Offline status
  React.useEffect(() => {
    setIsOnline(navigator.onLine);
    const handleOnline = () => {
      setIsOnline(true);
      syncOfflineQueue();
      fetchElderData();
    };
    const handleOffline = () => setIsOnline(false);

    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);
    return () => {
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
    };
  }, []);

  // Register PWA Service Worker (ELD-V5)
  React.useEffect(() => {
    if ("serviceWorker" in navigator) {
      navigator.serviceWorker.register("/sw.js").catch(() => {
        // Soft fail
      });
    }
  }, []);

  // Sync queued offline dose markings when back online
  const syncOfflineQueue = async () => {
    try {
      const rawQueue = localStorage.getItem("aira_offline_dose_queue");
      if (!rawQueue) return;
      const queue: Array<{ doseId: string; action: "take" | "undo" }> = JSON.parse(rawQueue);
      if (!queue.length) return;

      for (const item of queue) {
        if (item.action === "take") {
          await fetch(`/api/v1/doses/${item.doseId}/take`, { method: "POST" });
        } else if (item.action === "undo") {
          await fetch(`/api/v1/doses/${item.doseId}/undo`, { method: "POST" });
        }
      }
      localStorage.removeItem("aira_offline_dose_queue");
    } catch {
      // Ignored
    }
  };

  // Fetch Elder Profile, Doses and Contacts
  const fetchElderData = React.useCallback(async () => {
    try {
      // 1. Profile
      const profRes = await fetch("/api/v1/elders/me/profile");
      if (profRes.ok) {
        const profData: ElderProfile = await profRes.json();
        setProfile(profData);
        setTextSize(profData.text_size ?? 1);
        localStorage.setItem("aira_elder_profile", JSON.stringify(profData));
      } else if (!navigator.onLine) {
        const cachedProf = localStorage.getItem("aira_elder_profile");
        if (cachedProf) setProfile(JSON.parse(cachedProf));
      } else {
        // Not authenticated as elder
        router.push(`/${locale}/login`);
        return;
      }

      // 2. Doses
      const dosesRes = await fetch("/api/v1/elders/me/doses");
      if (dosesRes.ok) {
        const dosesData: DoseItem[] = await dosesRes.json();
        setDoses(dosesData);
        localStorage.setItem("aira_elder_doses", JSON.stringify(dosesData));

        // Initialize undo countdowns for taken doses within 10 minutes
        const initialUndos: Record<string, number> = {};
        dosesData.forEach((d) => {
          if (d.status === "taken" && d.can_undo) {
            initialUndos[d.id] = 600; // 10 minutes default
          }
        });
        setUndoTimeLeft(initialUndos);
      } else if (!navigator.onLine) {
        const cachedDoses = localStorage.getItem("aira_elder_doses");
        if (cachedDoses) setDoses(JSON.parse(cachedDoses));
      }

      // 3. Contacts
      const contactsRes = await fetch("/api/v1/elders/me/contacts");
      if (contactsRes.ok) {
        const contactsData: ContactItem[] = await contactsRes.json();
        setContacts(contactsData);
        localStorage.setItem("aira_elder_contacts", JSON.stringify(contactsData));
      } else if (!navigator.onLine) {
        const cachedContacts = localStorage.getItem("aira_elder_contacts");
        if (cachedContacts) setContacts(JSON.parse(cachedContacts));
      }
    } catch {
      // Load offline fallback cache
      const cachedProf = localStorage.getItem("aira_elder_profile");
      if (cachedProf) setProfile(JSON.parse(cachedProf));
      const cachedDoses = localStorage.getItem("aira_elder_doses");
      if (cachedDoses) setDoses(JSON.parse(cachedDoses));
      const cachedContacts = localStorage.getItem("aira_elder_contacts");
      if (cachedContacts) setContacts(JSON.parse(cachedContacts));
    } finally {
      setLoading(false);
    }
  }, [locale, router]);

  React.useEffect(() => {
    fetchElderData();
  }, [fetchElderData]);

  // Undo countdown tick
  React.useEffect(() => {
    const timer = setInterval(() => {
      setUndoTimeLeft((prev) => {
        let changed = false;
        const next = { ...prev };
        Object.keys(next).forEach((id) => {
          if (next[id] > 0) {
            next[id] -= 1;
            changed = true;
          } else {
            delete next[id];
            changed = true;
          }
        });
        return changed ? next : prev;
      });
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  // Update text size preference
  const handleChangeTextSize = async (newSize: number) => {
    setTextSize(newSize);
    if (navigator.onLine) {
      try {
        await fetch("/api/v1/elders/me/preferences", {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text_size: newSize }),
        });
      } catch {
        // Ignored
      }
    }
  };

  // Switch Language
  const handleSwitchLanguage = (targetLocale: string) => {
    if (targetLocale === locale) return;
    router.push(`/${targetLocale}/elder`);
  };

  // Sign out
  const handleSignOut = async () => {
    if (window.confirm(t("confirmSignOut"))) {
      try {
        await fetch("/api/v1/auth/logout", { method: "POST" });
      } catch {
        // Ignored
      }
      router.push(`/${locale}/login`);
    }
  };

  // Mark dose as Taken (ELD-V2)
  const handleTakeDose = async (doseId: string) => {
    playAlertChime(false);
    if (navigator.vibrate) navigator.vibrate(80);

    // Optimistic update
    setDoses((prev) =>
      prev.map((d) => (d.id === doseId ? { ...d, status: "taken", can_undo: true } : d))
    );
    setUndoTimeLeft((prev) => ({ ...prev, [doseId]: 600 })); // 10 minutes

    if (!navigator.onLine) {
      // Queue offline action
      const queue = JSON.parse(localStorage.getItem("aira_offline_dose_queue") || "[]");
      queue.push({ doseId, action: "take" });
      localStorage.setItem("aira_offline_dose_queue", JSON.stringify(queue));
      return;
    }

    try {
      const res = await fetch(`/api/v1/doses/${doseId}/take`, { method: "POST" });
      if (!res.ok) fetchElderData(); // revert on failure
    } catch {
      // Queue on network failure
      const queue = JSON.parse(localStorage.getItem("aira_offline_dose_queue") || "[]");
      queue.push({ doseId, action: "take" });
      localStorage.setItem("aira_offline_dose_queue", JSON.stringify(queue));
    }
  };

  // Undo Taken Dose (10-minute window)
  const handleUndoDose = async (doseId: string) => {
    // Optimistic revert
    setDoses((prev) =>
      prev.map((d) => (d.id === doseId ? { ...d, status: "scheduled", can_undo: false } : d))
    );
    setUndoTimeLeft((prev) => {
      const next = { ...prev };
      delete next[doseId];
      return next;
    });

    if (!navigator.onLine) {
      const queue = JSON.parse(localStorage.getItem("aira_offline_dose_queue") || "[]");
      queue.push({ doseId, action: "undo" });
      localStorage.setItem("aira_offline_dose_queue", JSON.stringify(queue));
      return;
    }

    try {
      const res = await fetch(`/api/v1/doses/${doseId}/undo`, { method: "POST" });
      if (!res.ok) fetchElderData();
    } catch {
      const queue = JSON.parse(localStorage.getItem("aira_offline_dose_queue") || "[]");
      queue.push({ doseId, action: "undo" });
      localStorage.setItem("aira_offline_dose_queue", JSON.stringify(queue));
    }
  };

  const touchStartPos = React.useRef<{ x: number; y: number } | null>(null);

  // 2-Second Hold-to-Activate SOS Logic (ELD-V4)
  const startSosHold = () => {
    setIsHoldingSos(true);
    setSosProgress(0);
    if (typeof navigator !== "undefined" && navigator.vibrate) navigator.vibrate(30);

    const startTime = Date.now();
    const duration = 2000; // 2 seconds

    progressIntervalRef.current = setInterval(() => {
      const elapsed = Date.now() - startTime;
      const progress = Math.min(100, Math.round((elapsed / duration) * 100));
      setSosProgress(progress);
    }, 40);

    holdTimerRef.current = setTimeout(() => {
      triggerSosNow();
    }, duration);
  };

  const handleTouchStartSos = (e: React.TouchEvent) => {
    const touch = e.touches[0];
    touchStartPos.current = { x: touch.clientX, y: touch.clientY };
    startSosHold();
  };

  const handleTouchMoveSos = (e: React.TouchEvent) => {
    if (!touchStartPos.current) return;
    const touch = e.touches[0];
    const dx = Math.abs(touch.clientX - touchStartPos.current.x);
    const dy = Math.abs(touch.clientY - touchStartPos.current.y);
    if (dx > 12 || dy > 12) {
      cancelSosHold();
    }
  };

  const cancelSosHold = () => {
    if (holdTimerRef.current) clearTimeout(holdTimerRef.current);
    if (progressIntervalRef.current) clearInterval(progressIntervalRef.current);
    setIsHoldingSos(false);
    setSosProgress(0);
  };

  const triggerSosNow = async () => {
    cancelSosHold();
    playAlertChime(true);
    if (navigator.vibrate) navigator.vibrate([200, 100, 200, 100, 400]);

    if (!navigator.onLine) {
      setSosOfflineAlert(true);
      return;
    }

    try {
      const res = await fetch("/api/v1/elders/me/sos", { method: "POST" });
      if (res.ok) {
        setSosActive(true);
      } else {
        setSosOfflineAlert(true);
      }
    } catch {
      setSosOfflineAlert(true);
    }
  };

  // Segment Doses into 4 Periods (ELD-V2)
  const getPeriodDoses = () => {
    const periods: {
      morning: DoseItem[];
      afternoon: DoseItem[];
      evening: DoseItem[];
      night: DoseItem[];
    } = { morning: [], afternoon: [], evening: [], night: [] };

    doses.forEach((d) => {
      const hour = parseInt(d.scheduled_time.split(":")[0], 10);
      if (hour >= 5 && hour < 12) {
        periods.morning.push(d);
      } else if (hour >= 12 && hour < 17) {
        periods.afternoon.push(d);
      } else if (hour >= 17 && hour < 21) {
        periods.evening.push(d);
      } else {
        periods.night.push(d);
      }
    });

    return periods;
  };

  const periodDoses = getPeriodDoses();

  // Typography scale based on elder text_size (0: normal, 1: large, 2: xlarge)
  const fontScale = {
    title: textSize === 2 ? "text-3xl sm:text-4xl" : textSize === 1 ? "text-2xl sm:text-3xl" : "text-xl sm:text-2xl",
    time: textSize === 2 ? "text-4xl sm:text-5xl font-black" : textSize === 1 ? "text-3xl sm:text-4xl font-extrabold" : "text-2xl sm:text-3xl font-bold",
    medName: textSize === 2 ? "text-2xl sm:text-3xl font-black" : textSize === 1 ? "text-xl sm:text-2xl font-bold" : "text-lg sm:text-xl font-bold",
    body: textSize === 2 ? "text-lg sm:text-xl" : textSize === 1 ? "text-base sm:text-lg" : "text-sm sm:text-base",
    button: textSize === 2 ? "text-xl sm:text-2xl py-5 px-8" : textSize === 1 ? "text-lg sm:text-xl py-4 px-6" : "text-base sm:text-lg py-3 px-5",
  };

  const formatSeconds = (sec: number) => {
    const m = Math.floor(sec / 60);
    const s = sec % 60;
    return `${m}:${s < 10 ? "0" : ""}${s}`;
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-bg-app flex flex-col items-center justify-center p-6 text-center">
        <AiraLogo size="lg" animateHeartbeat={true} className="mb-4" />
        <p className="text-xl font-bold text-text-primary">{tCommon("loading")}</p>
      </div>
    );
  }

  const primaryContact = contacts[0] || null;

  return (
    <div className="min-h-screen bg-[#FFF9F3] text-stone-900 flex flex-col font-sans select-none pb-[calc(5rem+env(safe-area-inset-bottom,0px))]">
      {/* Top Header Bar with Safe Area Support */}
      <header className="sticky top-0 z-30 bg-[#FFF9F3]/95 backdrop-blur-md border-b border-amber-200/60 px-3 sm:px-8 py-2.5 sm:py-3.5 shadow-2xs pt-[max(0.75rem,env(safe-area-inset-top,0px))]">
        <div className="max-w-4xl mx-auto flex items-center justify-between gap-2 sm:gap-4">
          {/* Brand & Greeting */}
          <div className="flex items-center gap-2.5 sm:gap-3 min-w-0">
            <AiraLogo size="md" className="shadow-xs shrink-0" />
            <div className="min-w-0">
              <h1 className="text-base sm:text-xl font-black tracking-tight text-stone-900 truncate">
                {t("greeting")},{" "}
                <span className="text-primary font-black">
                  {profile?.preferred_name || profile?.full_name || "Care"}
                </span>
              </h1>
              <p className="text-[11px] sm:text-sm font-medium text-stone-600 truncate">{currentDate}</p>
            </div>
          </div>

          {/* Accessibility Controls: Text Size & Language */}
          <div className="flex items-center gap-1.5 sm:gap-3 shrink-0">
            {/* Offline Pill if offline */}
            {!isOnline && (
              <div className="hidden sm:flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-amber-100 text-amber-900 border border-amber-300 text-xs font-bold">
                <WifiOff className="w-4 h-4 text-amber-700" />
                <span>{t("offlineNotice")}</span>
              </div>
            )}

            {/* Text Size Stepper (A / A+ / A++) */}
            <div className="flex items-center bg-stone-100 rounded-xl p-0.5 sm:p-1 border border-stone-200">
              <button
                type="button"
                onClick={() => handleChangeTextSize(0)}
                className={`px-2 py-1 sm:px-2.5 sm:py-1 rounded-lg text-xs font-bold transition-all ${
                  textSize === 0 ? "bg-white text-stone-900 shadow-xs" : "text-stone-500 hover:text-stone-900"
                }`}
                title="Normal text"
              >
                A
              </button>
              <button
                type="button"
                onClick={() => handleChangeTextSize(1)}
                className={`px-2 py-1 sm:px-2.5 sm:py-1 rounded-lg text-xs sm:text-sm font-bold transition-all ${
                  textSize === 1 ? "bg-white text-stone-900 shadow-xs" : "text-stone-500 hover:text-stone-900"
                }`}
                title="Large text"
              >
                A+
              </button>
              <button
                type="button"
                onClick={() => handleChangeTextSize(2)}
                className={`px-2 py-1 sm:px-2.5 sm:py-1 rounded-lg text-xs sm:text-base font-bold transition-all ${
                  textSize === 2 ? "bg-white text-stone-900 shadow-xs" : "text-stone-500 hover:text-stone-900"
                }`}
                title="Extra large text"
              >
                A++
              </button>
            </div>

            {/* Language Toggle */}
            <div className="flex items-center bg-stone-100 rounded-xl p-0.5 sm:p-1 border border-stone-200 text-xs font-bold">
              <button
                type="button"
                onClick={() => handleSwitchLanguage("hi")}
                className={`px-2 py-1 sm:px-2.5 sm:py-1 rounded-lg transition-all ${
                  locale === "hi" ? "bg-primary text-white shadow-xs" : "text-stone-600 hover:text-stone-900"
                }`}
              >
                हिन्दी
              </button>
              <button
                type="button"
                onClick={() => handleSwitchLanguage("en")}
                className={`px-2 py-1 sm:px-2.5 sm:py-1 rounded-lg transition-all ${
                  locale === "en" ? "bg-primary text-white shadow-xs" : "text-stone-600 hover:text-stone-900"
                }`}
              >
                EN
              </button>
            </div>

            {/* Sign Out */}
            <button
              type="button"
              onClick={handleSignOut}
              title={t("signOut")}
              className="p-2 sm:p-2.5 rounded-xl text-stone-500 hover:text-stone-800 hover:bg-stone-100 transition-colors active:scale-95"
            >
              <LogOut className="w-4 h-4 sm:w-5 sm:h-5" />
            </button>
          </div>
        </div>
      </header>

      {/* Main Container */}
      <main className="max-w-4xl w-full mx-auto px-4 sm:px-6 pt-5 space-y-6">
        {/* Offline Banner for Elder */}
        {!isOnline && (
          <div className="sm:hidden p-3 bg-amber-50 rounded-2xl border border-amber-300 flex items-center justify-between text-xs font-bold text-amber-900">
            <div className="flex items-center gap-2">
              <WifiOff className="w-4 h-4 text-amber-700 shrink-0" />
              <span>{t("offlineNotice")}</span>
            </div>
            <span className="text-[11px] text-amber-700 font-normal">
              {t("todaySubtitle")}
            </span>
          </div>
        )}

        {/* LARGE EMERGENCY SOS BUTTON (ELD-V4, Section 7) */}
        <div className="bg-white rounded-3xl p-5 sm:p-6 border-2 border-red-200 shadow-md">
          {sosActive ? (
            <div className="p-6 bg-red-50 rounded-2xl border-2 border-red-500 text-center space-y-3 animate-in fade-in">
              <div className="w-16 h-16 rounded-full bg-red-600 text-white flex items-center justify-center mx-auto shadow-lg animate-pulse">
                <Heart className="w-9 h-9 fill-current" />
              </div>
              <h2 className={`font-black text-red-900 ${fontScale.title}`}>
                {t("sosSent")}
              </h2>
              {primaryContact && (
                <div className="pt-2 flex flex-col sm:flex-row items-center justify-center gap-3">
                  <a
                    href={`tel:${primaryContact.phone_e164}`}
                    className="inline-flex items-center justify-center gap-3 px-6 py-3.5 rounded-2xl bg-emerald-600 text-white font-bold text-lg shadow-md hover:bg-emerald-700 active:scale-95 transition-all w-full sm:w-auto"
                  >
                    <Phone className="w-6 h-6 fill-current" />
                    <span>{primaryContact.full_name}: {t("call")}</span>
                  </a>
                  <a
                    href={`https://wa.me/${(primaryContact.whatsapp_e164 || primaryContact.phone_e164).replace(/[^\d]/g, "")}?text=${encodeURIComponent("EMERGENCY SOS: I need urgent help! Please contact me immediately.")}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center justify-center gap-3 px-6 py-3.5 rounded-2xl bg-[#25D366] text-white font-bold text-lg shadow-md hover:bg-[#128C7E] active:scale-95 transition-all w-full sm:w-auto"
                  >
                    <MessageSquare className="w-6 h-6 shrink-0" />
                    <span>{t("sosWhatsappPrimary")}</span>
                  </a>
                </div>
              )}
            </div>
          ) : sosOfflineAlert ? (
            <div className="p-5 bg-amber-50 rounded-2xl border-2 border-amber-400 text-center space-y-3">
              <div className="w-14 h-14 rounded-full bg-amber-500 text-white flex items-center justify-center mx-auto shadow-md">
                <AlertCircle className="w-8 h-8" />
              </div>
              <h2 className="text-xl font-bold text-amber-950">
                {t("sosOffline")}
              </h2>
              {primaryContact && (
                <div className="pt-2 flex flex-col sm:flex-row items-center justify-center gap-3">
                  <a
                    href={`tel:${primaryContact.phone_e164}`}
                    className="inline-flex items-center justify-center gap-3 px-8 py-4 rounded-2xl bg-emerald-600 text-white font-extrabold text-xl shadow-lg hover:bg-emerald-700 active:scale-95 transition-all w-full sm:w-auto"
                  >
                    <Phone className="w-6 h-6 fill-current" />
                    <span>{t("call")} {primaryContact.full_name}</span>
                  </a>
                  <a
                    href={`sms:${primaryContact.phone_e164}?body=${encodeURIComponent("EMERGENCY: Please call me immediately!")}`}
                    className="inline-flex items-center justify-center gap-3 px-6 py-4 rounded-2xl bg-amber-700 text-white font-bold text-lg shadow-md hover:bg-amber-800 active:scale-95 transition-all w-full sm:w-auto"
                  >
                    <MessageSquare className="w-6 h-6 shrink-0" />
                    <span>{t("sms")}</span>
                  </a>
                </div>
              )}
            </div>
          ) : (
            <div className="space-y-3 text-center">
              <button
                type="button"
                onMouseDown={startSosHold}
                onMouseUp={cancelSosHold}
                onMouseLeave={cancelSosHold}
                onTouchStart={handleTouchStartSos}
                onTouchMove={handleTouchMoveSos}
                onTouchEnd={cancelSosHold}
                onTouchCancel={cancelSosHold}
                className={`relative w-full overflow-hidden rounded-2xl transition-all shadow-md active:scale-[0.98] select-none ${
                  isHoldingSos ? "bg-red-700 ring-4 ring-red-400" : "bg-red-600 hover:bg-red-700"
                }`}
                style={{ minHeight: "84px", touchAction: "none", userSelect: "none", WebkitUserSelect: "none" }}
              >
                {/* Visual Fill Progress for 2-second hold */}
                <div
                  className="absolute left-0 top-0 bottom-0 bg-red-800/80 transition-all duration-75 ease-linear pointer-events-none"
                  style={{ width: `${sosProgress}%` }}
                />

                <div className="relative z-10 py-5 px-6 flex items-center justify-center gap-3.5 text-white">
                  <div className="w-10 h-10 rounded-full bg-white/20 flex items-center justify-center shrink-0">
                    <Heart className="w-6 h-6 fill-current text-white" />
                  </div>
                  <div className="text-left">
                    <p className="font-black text-xl sm:text-2xl tracking-tight leading-tight">
                      {isHoldingSos ? t("sosHolding") : t("sosButton")}
                    </p>
                    <p className="text-xs sm:text-sm text-red-100 font-medium mt-0.5">
                      {t("callPrompt")}
                    </p>
                  </div>
                </div>
              </button>
            </div>
          )}
        </div>

        {/* Section Tabs: Today's Medicines vs Family & Contacts */}
        <div className="grid grid-cols-2 p-1.5 bg-stone-200/80 rounded-2xl gap-1">
          <button
            type="button"
            onClick={() => setActiveTab("medicines")}
            className={`py-3.5 px-4 rounded-xl font-black transition-all flex items-center justify-center gap-2.5 ${fontScale.body} ${
              activeTab === "medicines"
                ? "bg-white text-stone-900 shadow-sm"
                : "text-stone-600 hover:text-stone-900"
            }`}
          >
            <Pill className="w-5 h-5 text-primary" />
            <span>{t("tabMedicines")}</span>
          </button>

          <button
            type="button"
            onClick={() => setActiveTab("contacts")}
            className={`py-3.5 px-4 rounded-xl font-black transition-all flex items-center justify-center gap-2.5 ${fontScale.body} ${
              activeTab === "contacts"
                ? "bg-white text-stone-900 shadow-sm"
                : "text-stone-600 hover:text-stone-900"
            }`}
          >
            <Phone className="w-5 h-5 text-emerald-600" />
            <span>{t("tabContacts")}</span>
          </button>
        </div>

        {/* TAB 1: TODAY'S MEDICINES (ELD-V2) */}
        {activeTab === "medicines" && (
          <div className="space-y-6 animate-in fade-in">
            {/* Period 1: Morning (सुबह, 05:00 - 11:59) */}
            <PeriodCard
              title={t("morning")}
              timeRange="05:00 - 11:59"
              icon={Sunrise}
              iconColor="text-amber-500"
              bgColor="bg-amber-50/70"
              borderColor="border-amber-200"
              doses={periodDoses.morning}
              fontScale={fontScale}
              t={t}
              undoTimeLeft={undoTimeLeft}
              formatSeconds={formatSeconds}
              onTake={handleTakeDose}
              onUndo={handleUndoDose}
            />

            {/* Period 2: Afternoon (दोपहर, 12:00 - 16:59) */}
            <PeriodCard
              title={t("afternoon")}
              timeRange="12:00 - 16:59"
              icon={Sun}
              iconColor="text-orange-500"
              bgColor="bg-orange-50/70"
              borderColor="border-orange-200"
              doses={periodDoses.afternoon}
              fontScale={fontScale}
              t={t}
              undoTimeLeft={undoTimeLeft}
              formatSeconds={formatSeconds}
              onTake={handleTakeDose}
              onUndo={handleUndoDose}
            />

            {/* Period 3: Evening (शाम, 17:00 - 20:59) */}
            <PeriodCard
              title={t("evening")}
              timeRange="17:00 - 20:59"
              icon={Sunset}
              iconColor="text-indigo-500"
              bgColor="bg-indigo-50/70"
              borderColor="border-indigo-200"
              doses={periodDoses.evening}
              fontScale={fontScale}
              t={t}
              undoTimeLeft={undoTimeLeft}
              formatSeconds={formatSeconds}
              onTake={handleTakeDose}
              onUndo={handleUndoDose}
            />

            {/* Period 4: Night (रात, 21:00 - 04:59) */}
            <PeriodCard
              title={t("night")}
              timeRange="21:00 - 04:59"
              icon={Moon}
              iconColor="text-blue-500"
              bgColor="bg-blue-50/70"
              borderColor="border-blue-200"
              doses={periodDoses.night}
              fontScale={fontScale}
              t={t}
              undoTimeLeft={undoTimeLeft}
              formatSeconds={formatSeconds}
              onTake={handleTakeDose}
              onUndo={handleUndoDose}
            />

            {/* Medical Disclaimer Note (MED-9) */}
            <div className="p-4 rounded-2xl bg-amber-50/80 border border-amber-200/80 text-center text-xs sm:text-sm text-stone-600 leading-relaxed">
              {tCommon("disclaimer")}
            </div>
          </div>
        )}

        {/* TAB 2: FAMILY & CONTACTS (ELD-V3) */}
        {activeTab === "contacts" && (
          <div className="space-y-4 animate-in fade-in">
            <div className="bg-white rounded-3xl p-6 sm:p-8 border border-stone-200 shadow-sm space-y-6">
              <div>
                <h2 className={`font-black text-stone-900 ${fontScale.title}`}>
                  {t("tabContacts")}
                </h2>
                <p className={`text-stone-600 mt-1 ${fontScale.body}`}>
                  {t("callPrompt")}
                </p>
              </div>

              <div className="divide-y divide-stone-100">
                {contacts.length === 0 ? (
                  <div className="py-8 text-center text-stone-500">
                    {tCommon("loading")}
                  </div>
                ) : (
                  contacts.map((contact, idx) => (
                    <div
                      key={contact.id}
                      className="py-4.5 flex flex-col sm:flex-row sm:items-center justify-between gap-4"
                    >
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <span className={`font-black text-stone-900 ${fontScale.medName}`}>
                            {contact.full_name}
                          </span>
                          {idx === 0 && (
                            <span className="px-2.5 py-0.5 rounded-full bg-red-100 text-red-800 text-xs font-bold border border-red-200">
                              {t("primaryContactBadge")}
                            </span>
                          )}
                        </div>
                        <p className="text-sm font-semibold text-stone-500 capitalize">
                          {t(`role_${contact.role}`)} • {contact.phone_e164}
                        </p>
                      </div>

                      {/* Communication Actions: Call, WhatsApp, SMS */}
                      <div className="flex items-center gap-2 flex-wrap">
                        {/* Tap to Call */}
                        <a
                          href={`tel:${contact.phone_e164}`}
                          className={`inline-flex items-center justify-center gap-2 rounded-2xl bg-emerald-600 text-white font-black shadow-md hover:bg-emerald-700 active:scale-[0.98] transition-all px-4 py-2.5 ${fontScale.button}`}
                          title={`${t("call")} ${contact.full_name}`}
                        >
                          <Phone className="w-5 h-5 fill-current shrink-0" />
                          <span>{t("call")}</span>
                        </a>

                        {/* WhatsApp */}
                        <a
                          href={`https://wa.me/${(contact.whatsapp_e164 || contact.phone_e164).replace(/[^\d]/g, "")}?text=${encodeURIComponent("Namaste! Thinking of you.")}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className={`inline-flex items-center justify-center gap-2 rounded-2xl bg-[#25D366] text-white font-black shadow-md hover:bg-[#128C7E] active:scale-[0.98] transition-all px-4 py-2.5 ${fontScale.button}`}
                          title={`${t("whatsapp")} ${contact.full_name}`}
                        >
                          <MessageSquare className="w-5 h-5 shrink-0" />
                          <span>{t("whatsapp")}</span>
                        </a>

                        {/* SMS */}
                        <a
                          href={`sms:${contact.phone_e164}?body=${encodeURIComponent("Namaste! Thinking of you.")}`}
                          className={`inline-flex items-center justify-center gap-2 rounded-2xl bg-stone-700 text-white font-bold shadow-md hover:bg-stone-800 active:scale-[0.98] transition-all px-4 py-2.5 ${fontScale.button}`}
                          title={`${t("sms")} ${contact.full_name}`}
                        >
                          <span>{t("sms")}</span>
                        </a>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

// Period Sub-Component
function PeriodCard({
  title,
  timeRange,
  icon: Icon,
  iconColor,
  bgColor,
  borderColor,
  doses,
  fontScale,
  t,
  undoTimeLeft,
  formatSeconds,
  onTake,
  onUndo,
}: {
  title: string;
  timeRange: string;
  icon: React.ComponentType<{ className?: string }>;
  iconColor: string;
  bgColor: string;
  borderColor: string;
  doses: DoseItem[];
  fontScale: {
    title: string;
    time: string;
    medName: string;
    body: string;
    button: string;
  };
  t: (key: string) => string;
  undoTimeLeft: Record<string, number>;
  formatSeconds: (sec: number) => string;
  onTake: (id: string) => void;
  onUndo: (id: string) => void;
}) {
  return (
    <div className={`rounded-3xl p-5 sm:p-6 border-2 ${bgColor} ${borderColor} shadow-xs space-y-4`}>
      {/* Period Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-2xl bg-white flex items-center justify-center shadow-xs shrink-0">
            <Icon className={`w-6 h-6 ${iconColor}`} />
          </div>
          <div>
            <h3 className={`font-black text-stone-900 ${fontScale.title}`}>{title}</h3>
            <span className="text-xs font-semibold text-stone-500">{timeRange}</span>
          </div>
        </div>

        {doses.length > 0 && (
          <span className="text-xs font-bold px-3 py-1 rounded-full bg-white text-stone-700 border border-stone-200">
            {doses.filter((d) => d.status === "taken").length} / {doses.length} {t("takenState")}
          </span>
        )}
      </div>

      {/* Doses List */}
      {doses.length === 0 ? (
        <p className="text-xs sm:text-sm text-stone-400 font-medium italic py-2">
          {t("noMedicinesPeriod")}
        </p>
      ) : (
        <div className="space-y-3">
          {doses.map((dose) => {
            const isTaken = dose.status === "taken";
            const secondsLeft = undoTimeLeft[dose.id] ?? 0;
            const canUndo = isTaken && secondsLeft > 0;

            return (
              <div
                key={dose.id}
                className={`p-4 sm:p-5 rounded-2xl bg-white border-2 transition-all flex flex-col sm:flex-row sm:items-center justify-between gap-4 shadow-xs ${
                  isTaken ? "border-emerald-300 bg-emerald-50/30" : "border-stone-200"
                }`}
                style={{
                  borderLeftWidth: dose.color_tag ? "8px" : undefined,
                  borderLeftColor: dose.color_tag || undefined,
                }}
              >
                {/* Medicine info */}
                <div className="space-y-1 min-w-0 flex-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-xs font-bold px-2 py-0.5 rounded-md bg-stone-100 text-stone-700 font-mono shrink-0">
                      {dose.scheduled_time.slice(0, 5)}
                    </span>
                    <h4 className={`text-stone-900 truncate ${fontScale.medName}`}>
                      {dose.medicine_name}
                    </h4>
                  </div>

                  <p className={`text-stone-600 font-semibold break-words ${fontScale.body}`}>
                    {dose.dose_label}
                    {dose.instructions && ` • ${dose.instructions}`}
                  </p>
                </div>

                {/* State Button (Take / Taken / Undo) */}
                <div className="flex items-center gap-2 shrink-0">
                  {isTaken ? (
                    <div className="flex items-center gap-2 w-full sm:w-auto">
                      <div className="flex-1 sm:flex-none flex items-center justify-center gap-2 px-5 py-3 rounded-2xl bg-emerald-100 text-emerald-800 font-black text-base border border-emerald-300">
                        <Check className="w-5 h-5 stroke-[3]" />
                        <span>{t("takenState")}</span>
                      </div>

                      {canUndo && (
                        <button
                          type="button"
                          onClick={() => onUndo(dose.id)}
                          className="px-4 py-3 rounded-2xl bg-stone-100 hover:bg-stone-200 text-stone-700 font-bold text-xs border border-stone-300 transition-colors"
                          title="Undo within 10 minutes"
                        >
                          {t("undo")} ({formatSeconds(secondsLeft)})
                        </button>
                      )}
                    </div>
                  ) : (
                    <button
                      type="button"
                      onClick={() => onTake(dose.id)}
                      className={`w-full sm:w-auto flex items-center justify-center gap-2.5 rounded-2xl bg-emerald-600 hover:bg-emerald-700 active:scale-[0.98] text-white font-black shadow-md transition-all ${fontScale.button}`}
                      style={{ minHeight: "54px" }}
                    >
                      <Check className="w-6 h-6 stroke-[3]" />
                      <span>{t("takenButton")}</span>
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
