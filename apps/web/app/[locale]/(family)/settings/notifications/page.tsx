"use client";

import * as React from "react";
import { useTranslations } from "next-intl";
import {
  Bell,
  CheckCircle2,
  Lock,
  Moon,
  Save,
  ShieldAlert,
  Smartphone,
} from "lucide-react";

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

  // Web Push status
  const [pushSupported, setPushSupported] = React.useState(false);
  const [pushSubscribed, setPushSubscribed] = React.useState(false);

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

  React.useEffect(() => {
    if (typeof window !== "undefined" && "serviceWorker" in navigator && "PushManager" in window) {
      setPushSupported(true);
      if (Notification.permission === "granted") {
        setPushSubscribed(true);
      }
    }
  }, []);

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

  const togglePreference = (cat: "sos" | "missed" | "refill" | "system", ch: "in_app" | "push" | "email" | "sms" | "whatsapp") => {
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

  const handleTogglePushSubscription = async () => {
    if (!pushSupported) return;
    try {
      const permission = await Notification.requestPermission();
      if (permission === "granted") {
        setPushSubscribed(true);
        // Register mock/live push endpoint
        await fetch("/api/v1/push/subscribe", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            endpoint: `https://fcm.googleapis.com/fcm/send/mock_${Date.now()}`,
            p256dh: "mock_p256dh_key",
            auth: "mock_auth_secret",
          }),
        });
      }
    } catch {
      // Permission rejected
    }
  };

  return (
    <div className="space-y-8 animate-in fade-in">
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

      {error && (
        <div className="p-4 bg-red-50 text-emergency rounded-xl border border-red-200 text-sm">
          {error}
        </div>
      )}

      {/* Web Push Status Card */}
      <div className="bg-surface rounded-2xl p-6 border border-border shadow-2xs flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-primary-soft flex items-center justify-center text-primary shrink-0">
            <Smartphone className="w-5 h-5" />
          </div>
          <div>
            <h3 className="font-bold text-sm text-text-primary">
              {t("webPushTitle")}
            </h3>
            <p className="text-xs text-text-secondary mt-0.5">
              {pushSubscribed
                ? t("webPushActiveDesc")
                : t("webPushInactiveDesc")}
            </p>
          </div>
        </div>

        <button
          type="button"
          onClick={handleTogglePushSubscription}
          disabled={!pushSupported || pushSubscribed}
          className={`px-4 py-2 rounded-xl text-xs font-bold transition-all shadow-xs ${
            pushSubscribed
              ? "bg-emerald-100 text-emerald-800 border border-emerald-200 cursor-default"
              : "bg-primary text-white hover:bg-primary/90"
          }`}
        >
          {pushSubscribed ? `✓ ${t("pushEnabled")}` : t("enablePushNotifications")}
        </button>
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
            <div className="overflow-x-auto">
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
    </div>
  );
}
