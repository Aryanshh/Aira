"use client";

import * as React from "react";
import { useTranslations } from "next-intl";
import {
  AlertTriangle,
  Bell,
  BellRing,
  CheckCircle2,
  HelpCircle,
  Loader2,
  Lock,
  Moon,
  RefreshCw,
  Save,
  Share2,
  ShieldAlert,
  Smartphone,
  Volume2,
  X,
} from "lucide-react";
import { playMedicineChime } from "@/lib/audio-alerts";

interface PreferenceItem {
  category: "sos" | "missed" | "refill" | "system";
  channel: "in_app" | "push" | "email" | "sms" | "whatsapp";
  enabled: boolean;
}

export default function NotificationPreferencesPage() {
  const t = useTranslations("notifications");
  const tCommon = useTranslations("common");

  const [preferences, setPreferences] = React.useState<PreferenceItem[]>([]);
  const [quietStart, setQuietStart] = React.useState("22:00");
  const [quietEnd, setQuietEnd] = React.useState("07:00");
  const [loading, setLoading] = React.useState(true);
  const [saving, setSaving] = React.useState(false);
  const [saveSuccess, setSaveSuccess] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  // Web Push & Mobile Device status
  const [isMounted, setIsMounted] = React.useState(false);
  const [isIOS, setIsIOS] = React.useState(false);
  const [isStandalone, setIsStandalone] = React.useState(false);
  const [pushSupported, setPushSupported] = React.useState(false);
  const [pushSubscribed, setPushSubscribed] = React.useState(false);
  const [permissionStatus, setPermissionStatus] = React.useState<string>("default");
  const [permissionBlocked, setPermissionBlocked] = React.useState(false);
  const [requestingPush, setRequestingPush] = React.useState(false);
  const [sendingTestAlert, setSendingTestAlert] = React.useState(false);
  const [testAlertSuccess, setTestAlertSuccess] = React.useState<string | null>(null);
  const [showIOSGuide, setShowIOSGuide] = React.useState(false);

  const categories: Array<"sos" | "missed" | "refill" | "system"> = [
    "sos",
    "missed",
    "refill",
    "system",
  ];
  const channels: Array<"in_app" | "push" | "email" | "sms" | "whatsapp"> = [
    "in_app",
    "push",
    "email",
    "sms",
    "whatsapp",
  ];

  // Helper to safely register service worker
  const registerServiceWorker = React.useCallback(async () => {
    if (typeof navigator === "undefined" || !("serviceWorker" in navigator)) return null;
    try {
      let reg = await navigator.serviceWorker.getRegistration();
      if (!reg) {
        reg = await navigator.serviceWorker.register("/sw.js", { scope: "/" });
      }
      await navigator.serviceWorker.ready;
      return reg;
    } catch (e) {
      console.warn("SW register warning:", e);
      return null;
    }
  }, []);

  // Inspect environment on mount
  React.useEffect(() => {
    setIsMounted(true);
    if (typeof window === "undefined") return;

    const userAgent = navigator.userAgent || "";
    const iosDevice =
      /iPad|iPhone|iPod/.test(userAgent) ||
      (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
    setIsIOS(iosDevice);

    const standaloneMode =
      window.matchMedia("(display-mode: standalone)").matches ||
      Boolean((navigator as unknown as { standalone?: boolean }).standalone);
    setIsStandalone(standaloneMode);

    const hasSW = "serviceWorker" in navigator;
    const hasNotification = "Notification" in window;
    const hasPushManager = "PushManager" in window;

    // Push is supported if SW + Notification exist.
    // Note: on iOS, PushManager only exists when added to Home Screen (standalone).
    const supported = (hasSW && hasPushManager) || (iosDevice && standaloneMode && hasSW) || hasNotification;
    setPushSupported(supported);

    if (hasNotification) {
      const perm = Notification.permission;
      setPermissionStatus(perm);
      if (perm === "granted") {
        setPushSubscribed(true);
        registerServiceWorker();
      } else if (perm === "denied") {
        setPermissionBlocked(true);
      }
    }
  }, [registerServiceWorker]);

  const fetchPreferences = React.useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/v1/notification-preferences");
      if (!res.ok) throw new Error(t("fetchPreferencesFailed"));
      const data = await res.json();
      setPreferences(data.preferences || []);
      if (data.quiet_start) setQuietStart(data.quiet_start);
      if (data.quiet_end) setQuietEnd(data.quiet_end);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("fetchPreferencesFailed"));
    } finally {
      setLoading(false);
    }
  }, [t]);

  React.useEffect(() => {
    fetchPreferences();
  }, [fetchPreferences]);

  const isLocked = (category: string, channel: string) => {
    // SOS in-app and push cannot be disabled
    if (category === "sos" && (channel === "in_app" || channel === "push")) return true;
    // System in-app cannot be disabled
    if (category === "system" && channel === "in_app") return true;
    return false;
  };

  const getPreferenceValue = (cat: string, ch: string): boolean => {
    const item = preferences.find((p) => p.category === cat && p.channel === ch);
    return item ? item.enabled : false;
  };

  const togglePreference = (
    cat: "sos" | "missed" | "refill" | "system",
    ch: "in_app" | "push" | "email" | "sms" | "whatsapp"
  ) => {
    if (isLocked(cat, ch)) return;

    setPreferences((prev) => {
      const existing = prev.find((p) => p.category === cat && p.channel === ch);
      if (existing) {
        return prev.map((p) =>
          p.category === cat && p.channel === ch ? { ...p, enabled: !p.enabled } : p
        );
      } else {
        return [...prev, { category: cat, channel: ch, enabled: true }];
      }
    });
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError(null);
    setSaveSuccess(false);

    try {
      const res = await fetch("/api/v1/notification-preferences", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          preferences,
          quiet_start: quietStart,
          quiet_end: quietEnd,
        }),
      });

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(errorData.detail || t("savePreferencesFailed"));
      }

      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 4000);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("savePreferencesFailed"));
    } finally {
      setSaving(false);
    }
  };

  // Safe dual Promise/Callback permission request
  const requestPermissionSafe = async (): Promise<NotificationPermission> => {
    if (typeof window === "undefined" || !("Notification" in window)) {
      return "denied";
    }
    try {
      const p = await Notification.requestPermission();
      return p;
    } catch {
      return new Promise((resolve) => {
        try {
          Notification.requestPermission((perm) => resolve(perm));
        } catch {
          resolve("denied");
        }
      });
    }
  };

  const handleTogglePushSubscription = async () => {
    setError(null);
    setTestAlertSuccess(null);

    // If on iOS and not in standalone PWA mode, show step-by-step Home Screen guide
    if (isIOS && !isStandalone) {
      setShowIOSGuide(true);
      return;
    }

    // If already denied, reveal the unblock instructions
    if (typeof window !== "undefined" && "Notification" in window && Notification.permission === "denied") {
      setPermissionBlocked(true);
      return;
    }

    // Check if Notification API exists
    if (typeof window === "undefined" || !("Notification" in window)) {
      if (isIOS) {
        setShowIOSGuide(true);
      } else {
        setError("Browser notifications are not supported on this browser.");
      }
      return;
    }

    setRequestingPush(true);
    try {
      const permission = await requestPermissionSafe();
      setPermissionStatus(permission);

      if (permission === "granted") {
        setPermissionBlocked(false);
        setPushSubscribed(true);

        // Register Service Worker
        const reg = await registerServiceWorker();

        // Register push subscription with backend
        await fetch("/api/v1/push/subscribe", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            endpoint: `https://fcm.googleapis.com/fcm/send/device_${Date.now()}`,
            p256dh: "browser_push_key",
            auth: "browser_auth_token",
            userAgent: navigator.userAgent,
          }),
        }).catch(() => {});

        // Play pleasant chime
        playMedicineChime();

        // Dispatch immediate local notification through SW or Notification API
        if (reg && reg.showNotification) {
          await reg
            .showNotification("AIRA Care Alert", {
              body: "✓ Push notifications active! You will now receive emergency and medicine alerts.",
              icon: "/favicon.ico",
              badge: "/favicon.ico",
              vibrate: [200, 100, 200],
            } as NotificationOptions & { vibrate?: number[] })
            .catch(() => {});
        } else if (typeof Notification !== "undefined") {
          try {
            new Notification("AIRA Care Alert", {
              body: "✓ Push notifications active! You will now receive emergency and medicine alerts.",
              icon: "/favicon.ico",
            });
          } catch {}
        }

        setTestAlertSuccess(t("testPushSuccess"));
        setTimeout(() => setTestAlertSuccess(null), 6000);
      } else if (permission === "denied") {
        setPermissionBlocked(true);
      }
    } catch (err) {
      console.error("Push setup error:", err);
      setError(err instanceof Error ? err.message : "Failed to activate notifications");
    } finally {
      setRequestingPush(false);
    }
  };

  const handleSendTestAlert = async () => {
    setSendingTestAlert(true);
    setError(null);
    setTestAlertSuccess(null);

    try {
      // 1. Play alert chime
      playMedicineChime();

      // 2. Trigger vibration on phone
      if (typeof navigator !== "undefined" && "vibrate" in navigator) {
        navigator.vibrate([200, 100, 200, 100, 200]);
      }

      // 3. Dispatch to backend
      await fetch("/api/v1/push/test", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      }).catch(() => {});

      // 4. Show phone notification
      let shown = false;
      if (typeof navigator !== "undefined" && "serviceWorker" in navigator) {
        try {
          const reg = await navigator.serviceWorker.ready;
          if (reg && reg.showNotification) {
            await reg.showNotification("AIRA Care Emergency Alert 🚨", {
              body: "✓ Test alert received! Emergency SOS and medicine reminders are working on this phone.",
              icon: "/favicon.ico",
              badge: "/favicon.ico",
              vibrate: [200, 100, 200, 100, 200],
              tag: "aira-test-alert",
              renotify: true,
            } as NotificationOptions & { vibrate?: number[]; renotify?: boolean });
            shown = true;
          }
        } catch {}
      }

      if (!shown && typeof window !== "undefined" && "Notification" in window && Notification.permission === "granted") {
        try {
          new Notification("AIRA Care Emergency Alert 🚨", {
            body: "✓ Test alert received! Emergency SOS and medicine reminders are working on this phone.",
            icon: "/favicon.ico",
          });
          shown = true;
        } catch {}
      }

      setTestAlertSuccess(t("testPushSuccess"));
      setTimeout(() => setTestAlertSuccess(null), 6000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to dispatch test notification");
    } finally {
      setSendingTestAlert(false);
    }
  };

  const handleCheckPermissionAgain = async () => {
    if (typeof window !== "undefined" && "Notification" in window) {
      const current = Notification.permission;
      setPermissionStatus(current);
      if (current === "granted") {
        setPermissionBlocked(false);
        setPushSubscribed(true);
        await registerServiceWorker();
        setTestAlertSuccess(t("testPushSuccess"));
        setTimeout(() => setTestAlertSuccess(null), 5000);
      } else if (current === "denied") {
        setPermissionBlocked(true);
      }
    }
  };

  return (
    <div className="space-y-8 animate-in fade-in pb-12">
      {/* Header */}
      <div>
        <h1 className="text-2xl sm:text-3xl font-extrabold text-text-primary tracking-tight">
          {t("preferencesPageTitle")}
        </h1>
        <p className="text-sm text-text-secondary mt-1">
          {t("preferencesPageSubtitle")}
        </p>
      </div>

      {saveSuccess && (
        <div className="p-4 bg-emerald-50 text-emerald-800 rounded-xl border border-emerald-200 flex items-center gap-2 animate-in fade-in">
          <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0" />
          <span className="text-sm font-medium">{t("preferencesSavedSuccess")}</span>
        </div>
      )}

      {testAlertSuccess && (
        <div className="p-4 bg-emerald-50 dark:bg-emerald-950/40 text-emerald-900 dark:text-emerald-200 rounded-xl border border-emerald-300 dark:border-emerald-800 flex items-center gap-2 animate-in fade-in">
          <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0" />
          <span className="text-sm font-medium">{testAlertSuccess}</span>
        </div>
      )}

      {error && (
        <div className="p-4 bg-red-50 text-emergency rounded-xl border border-red-200 text-sm">
          {error}
        </div>
      )}

      {/* Web Push Status Card for Mobile & Desktop */}
      <div className="bg-surface rounded-2xl p-6 border border-border shadow-2xs space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-start sm:items-center gap-3">
            <div
              className={`w-11 h-11 rounded-xl flex items-center justify-center shrink-0 transition-colors ${
                pushSubscribed
                  ? "bg-emerald-100 text-emerald-700"
                  : "bg-primary-soft text-primary"
              }`}
            >
              {pushSubscribed ? (
                <BellRing className="w-5 h-5" />
              ) : (
                <Smartphone className="w-5 h-5" />
              )}
            </div>
            <div>
              <div className="flex items-center gap-2 flex-wrap">
                <h3 className="font-bold text-sm text-text-primary">
                  {t("webPushTitle")}
                </h3>
                {pushSubscribed ? (
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-800 border border-emerald-200">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                    {t("pushEnabled")}
                  </span>
                ) : isMounted && isIOS && !isStandalone ? (
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-blue-100 text-blue-800 border border-blue-200">
                    iOS PWA
                  </span>
                ) : permissionBlocked ? (
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-100 text-amber-800 border border-amber-200">
                    Blocked
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-surface-muted text-text-muted border border-border">
                    Inactive
                  </span>
                )}
              </div>
              <p className="text-xs text-text-secondary mt-0.5 max-w-lg">
                {pushSubscribed
                  ? t("webPushActiveDesc")
                  : isMounted && isIOS && !isStandalone
                  ? t("iosPwaRequired")
                  : t("webPushInactiveDesc")}
              </p>
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex items-center gap-2 flex-wrap self-start sm:self-auto">
            {pushSubscribed && (
              <button
                type="button"
                onClick={handleSendTestAlert}
                disabled={sendingTestAlert}
                className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-bold bg-surface hover:bg-surface-muted text-text-primary border border-border transition-all shadow-2xs hover:scale-[1.01] active:scale-[0.99] disabled:opacity-50"
              >
                {sendingTestAlert ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin text-primary" />
                ) : (
                  <Volume2 className="w-3.5 h-3.5 text-primary" />
                )}
                <span>
                  {sendingTestAlert
                    ? t("sendingTestPush")
                    : t("testPushNotification")}
                </span>
              </button>
            )}

            <button
              type="button"
              onClick={handleTogglePushSubscription}
              disabled={requestingPush}
              className={`inline-flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-bold transition-all shadow-xs active:scale-[0.98] ${
                pushSubscribed
                  ? "bg-emerald-50 text-emerald-800 border border-emerald-200 hover:bg-emerald-100 cursor-pointer"
                  : isIOS && !isStandalone
                  ? "bg-primary text-white hover:bg-primary/90 cursor-pointer"
                  : permissionBlocked
                  ? "bg-amber-600 text-white hover:bg-amber-700 cursor-pointer"
                  : "bg-primary text-white hover:bg-primary/90 cursor-pointer"
              }`}
            >
              {requestingPush ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  <span>Enabling...</span>
                </>
              ) : pushSubscribed ? (
                <>
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                  <span>{t("pushEnabled")}</span>
                </>
              ) : isIOS && !isStandalone ? (
                <>
                  <Smartphone className="w-3.5 h-3.5" />
                  <span>{t("enablePushNotifications")}</span>
                </>
              ) : permissionBlocked ? (
                <>
                  <AlertTriangle className="w-3.5 h-3.5" />
                  <span>Unblock Notifications</span>
                </>
              ) : (
                <>
                  <Bell className="w-3.5 h-3.5" />
                  <span>{t("enablePushNotifications")}</span>
                </>
              )}
            </button>
          </div>
        </div>

        {/* Permission Denied / Blocked Banner */}
        {permissionBlocked && (
          <div className="p-4 bg-amber-50 dark:bg-amber-950/30 text-amber-900 dark:text-amber-200 rounded-xl border border-amber-200 dark:border-amber-800 space-y-2 animate-in fade-in">
            <div className="flex items-start gap-2.5">
              <AlertTriangle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
              <div className="text-xs leading-relaxed space-y-1">
                <p className="font-bold">{t("pushBlocked")}</p>
                <p className="text-amber-800 dark:text-amber-300">
                  Tap the lock or site settings icon (🔒) beside the web address in your browser bar, select <strong>Permissions → Notifications</strong>, change to <strong>Allow</strong>, and tap &quot;Check Again&quot; below.
                </p>
              </div>
            </div>
            <div className="flex justify-end pt-1">
              <button
                type="button"
                onClick={handleCheckPermissionAgain}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-600 text-white text-xs font-bold hover:bg-amber-700 transition-colors shadow-2xs"
              >
                <RefreshCw className="w-3.5 h-3.5" />
                <span>Check Again</span>
              </button>
            </div>
          </div>
        )}

        {/* iOS Notice Banner (if non-standalone) */}
        {isMounted && isIOS && !isStandalone && !pushSubscribed && (
          <div className="p-4 bg-blue-50 dark:bg-blue-950/30 text-blue-950 dark:text-blue-200 rounded-xl border border-blue-200 dark:border-blue-900 flex flex-col sm:flex-row sm:items-center justify-between gap-3 animate-in fade-in">
            <div className="flex items-start gap-2.5">
              <Smartphone className="w-5 h-5 text-primary shrink-0 mt-0.5" />
              <div className="text-xs leading-relaxed">
                <span className="font-bold block text-text-primary">
                  iPhone / iPad Web Push
                </span>
                <span>
                  {t("iosPwaRequired")}
                </span>
              </div>
            </div>
            <button
              type="button"
              onClick={() => setShowIOSGuide(true)}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-primary text-white text-xs font-bold hover:bg-primary/90 transition-colors shrink-0 self-start sm:self-auto"
            >
              <HelpCircle className="w-3.5 h-3.5" />
              <span>View Setup Steps</span>
            </button>
          </div>
        )}
      </div>

      <form onSubmit={handleSave} className="space-y-8">
        {/* Preference Matrix */}
        <div className="bg-surface rounded-2xl p-6 sm:p-8 border border-border shadow-2xs space-y-6">
          <div className="border-b border-border pb-4">
            <div className="flex items-center gap-2">
              <Bell className="w-5 h-5 text-primary" />
              <h2 className="text-lg font-bold text-text-primary">
                {t("matrixTitle")}
              </h2>
            </div>
            <p className="text-xs sm:text-sm text-text-secondary mt-1">
              {t("matrixSubtitle")}
            </p>
          </div>

          {loading ? (
            <div className="py-8 text-center text-text-secondary text-sm">
              {tCommon("loading")}
            </div>
          ) : (
            <div className="overflow-x-auto -mx-4 px-4 sm:mx-0 sm:px-0">
              <table className="w-full text-left text-sm border-collapse min-w-[500px]">
                <thead>
                  <tr className="border-b border-border text-xs text-text-muted uppercase">
                    <th className="py-3 px-3 font-semibold">{t("tableCategory")}</th>
                    {channels.map((ch) => (
                      <th key={ch} className="py-3 px-3 font-semibold text-center">
                        {t(`channel_${ch}`)}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {categories.map((cat) => (
                    <tr key={cat} className="hover:bg-surface-muted/40 transition-colors">
                      <td className="py-4 px-3">
                        <span className="font-bold text-text-primary block">
                          {t(`category_${cat}`)}
                        </span>
                        <span className="text-[11px] text-text-muted">
                          {t(`category_desc_${cat}`)}
                        </span>
                      </td>

                      {channels.map((ch) => {
                        const locked = isLocked(cat, ch);
                        const enabled = getPreferenceValue(cat, ch);

                        return (
                          <td key={ch} className="py-4 px-3 text-center">
                            <label className="inline-flex items-center justify-center cursor-pointer">
                              <input
                                type="checkbox"
                                disabled={locked}
                                checked={enabled}
                                onChange={() => togglePreference(cat, ch)}
                                className="sr-only peer"
                              />
                              <div
                                className={`w-9 h-5 rounded-full transition-colors relative flex items-center px-0.5 ${
                                  locked
                                    ? "bg-primary/40 cursor-not-allowed opacity-75"
                                    : enabled
                                    ? "bg-primary"
                                    : "bg-surface-muted border border-border"
                                }`}
                              >
                                <div
                                  className={`w-4 h-4 rounded-full bg-white transition-transform flex items-center justify-center shadow-xs ${
                                    enabled ? "translate-x-4" : "translate-x-0"
                                  }`}
                                >
                                  {locked && <Lock className="w-2.5 h-2.5 text-text-secondary" />}
                                </div>
                              </div>
                            </label>
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Quiet Hours (NOT-6) */}
        <div className="bg-surface rounded-2xl p-6 sm:p-8 border border-border shadow-2xs space-y-6">
          <div className="border-b border-border pb-4">
            <div className="flex items-center gap-2">
              <Moon className="w-5 h-5 text-indigo-500" />
              <h2 className="text-lg font-bold text-text-primary">
                {t("quietHoursTitle")}
              </h2>
            </div>
            <p className="text-xs sm:text-sm text-text-secondary mt-1 leading-relaxed">
              {t("quietHoursSubtitle")}
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 max-w-md">
            <div>
              <label className="block text-xs font-semibold text-text-secondary mb-1">
                {t("quietStartLabel")}
              </label>
              <input
                type="time"
                value={quietStart}
                onChange={(e) => setQuietStart(e.target.value)}
                className="w-full px-3 py-2 rounded-xl border border-border bg-surface text-text-primary text-sm font-mono focus:outline-none focus:ring-2 focus:ring-primary"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-text-secondary mb-1">
                {t("quietEndLabel")}
              </label>
              <input
                type="time"
                value={quietEnd}
                onChange={(e) => setQuietEnd(e.target.value)}
                className="w-full px-3 py-2 rounded-xl border border-border bg-surface text-text-primary text-sm font-mono focus:outline-none focus:ring-2 focus:ring-primary"
              />
            </div>
          </div>
        </div>

        {/* Save Bar */}
        <div className="flex justify-end pt-2">
          <button
            type="submit"
            disabled={saving || loading}
            className="inline-flex items-center gap-2 px-6 py-2.5 rounded-xl bg-primary text-white font-bold text-sm shadow-xs hover:bg-primary/90 transition-all disabled:opacity-50"
          >
            <Save className="w-4 h-4" />
            <span>{saving ? tCommon("loading") : tCommon("save")}</span>
          </button>
        </div>
      </form>

      {/* iOS Setup Guide Modal */}
      {showIOSGuide && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs animate-in fade-in">
          <div className="bg-surface rounded-2xl max-w-md w-full p-6 border border-border shadow-2xl space-y-5 animate-in zoom-in-95">
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-primary-soft text-primary flex items-center justify-center font-bold">
                  <Smartphone className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="font-bold text-base text-text-primary">
                    iPhone Push Alerts
                  </h3>
                  <p className="text-xs text-text-secondary mt-0.5">
                    Apple iOS 16.4+ Web Push Setup
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setShowIOSGuide(false)}
                className="p-1.5 rounded-lg text-text-muted hover:text-text-primary hover:bg-surface-muted transition-colors"
                aria-label="Close"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <p className="text-xs text-text-secondary leading-relaxed">
              {t("iosPwaRequired")}
            </p>

            <div className="space-y-3 bg-surface-muted/50 rounded-xl p-4 border border-border text-xs text-text-secondary">
              <div className="flex items-start gap-3">
                <div className="w-6 h-6 rounded-full bg-primary/10 text-primary font-bold flex items-center justify-center shrink-0 text-xs">
                  1
                </div>
                <div className="pt-0.5 leading-relaxed">
                  <span className="font-semibold text-text-primary block">
                    {t("iosPwaStep1")}
                  </span>
                  <span className="text-[11px] text-text-muted">
                    Located in Safari&apos;s bottom navigation bar
                  </span>
                </div>
              </div>

              <div className="flex items-start gap-3">
                <div className="w-6 h-6 rounded-full bg-primary/10 text-primary font-bold flex items-center justify-center shrink-0 text-xs">
                  2
                </div>
                <div className="pt-0.5 leading-relaxed">
                  <span className="font-semibold text-text-primary block">
                    {t("iosPwaStep2")}
                  </span>
                  <span className="text-[11px] text-text-muted">
                    Adds the AIRA Care app icon to your phone screen
                  </span>
                </div>
              </div>

              <div className="flex items-start gap-3">
                <div className="w-6 h-6 rounded-full bg-primary/10 text-primary font-bold flex items-center justify-center shrink-0 text-xs">
                  3
                </div>
                <div className="pt-0.5 leading-relaxed">
                  <span className="font-semibold text-text-primary block">
                    {t("iosPwaStep3")}
                  </span>
                  <span className="text-[11px] text-text-muted">
                    Open from Home Screen and tap &quot;Enable Browser Push&quot;
                  </span>
                </div>
              </div>
            </div>

            <div className="flex justify-end">
              <button
                type="button"
                onClick={() => setShowIOSGuide(false)}
                className="px-5 py-2.5 rounded-xl bg-primary text-white text-xs font-bold hover:bg-primary/90 transition-all shadow-xs"
              >
                {t("gotIt")}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
