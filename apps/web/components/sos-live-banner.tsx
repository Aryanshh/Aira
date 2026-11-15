"use client";

import * as React from "react";
import { useLocale, useTranslations } from "next-intl";
import { AlertCircle, CheckCircle2, Clock, Volume2, X } from "lucide-react";

import { useElder } from "@/components/elder-context";

interface SosAttempt {
  id: string;
  contact_name: string;
  channel: string;
  round: number;
  status: string;
  sent_at: string | null;
}

interface ActiveSosEvent {
  id: string;
  elder_id: string;
  source: string;
  client_event_id: string;
  status: string;
  escalation_state: string;
  press_count: number;
  triggered_at: string;
  handled_at: string | null;
  handled_by: string | null;
  attempts: SosAttempt[];
}

export function SosLiveBanner() {
  const { selectedElder } = useElder();
  const locale = useLocale();
  const t = useTranslations("sos");
  const tCommon = useTranslations("common");

  const [activeSos, setActiveSos] = React.useState<ActiveSosEvent | null>(null);
  const [isResolving, setIsResolving] = React.useState(false);
  const [showResolveModal, setShowResolveModal] = React.useState(false);
  const [resolveNote, setResolveNote] = React.useState("");
  const [resolveError, setResolveError] = React.useState<string | null>(null);
  const prevSosIdRef = React.useRef<string | null>(null);

  // Sound alert using Web Audio API
  const playAlertChime = React.useCallback(() => {
    try {
      const AudioContextClass = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      if (!AudioContextClass) return;
      const ctx = new AudioContextClass();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = "sine";
      osc.frequency.setValueAtTime(587.33, ctx.currentTime); // D5
      osc.frequency.setValueAtTime(880.0, ctx.currentTime + 0.15); // A5
      gain.gain.setValueAtTime(0.2, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.4);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start();
      osc.stop(ctx.currentTime + 0.4);
    } catch {
      // Audio context might be restricted before user interaction
    }
  }, []);

  const fetchActiveSos = React.useCallback(async () => {
    if (!selectedElder) {
      setActiveSos(null);
      return;
    }
    try {
      const res = await fetch(`/api/v1/elders/${selectedElder.id}/sos/active`);
      if (res.ok) {
        const data = await res.json();
        if (data && data.status === "active") {
          setActiveSos(data);
          // Play chime if this is a newly arrived active SOS
          if (prevSosIdRef.current !== data.id) {
            prevSosIdRef.current = data.id;
            playAlertChime();
          }
        } else {
          setActiveSos(null);
          prevSosIdRef.current = null;
        }
      }
    } catch {
      // Ignore background network transient
    }
  }, [selectedElder, playAlertChime]);

  React.useEffect(() => {
    fetchActiveSos();
    const interval = setInterval(fetchActiveSos, 8000);
    return () => clearInterval(interval);
  }, [fetchActiveSos]);

  const handleResolve = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeSos) return;

    setIsResolving(true);
    setResolveError(null);
    try {
      const res = await fetch(`/api/v1/sos/${activeSos.id}/resolve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ note: resolveNote.trim() || undefined }),
      });

      if (!res.ok) {
        throw new Error(t("resolveFailed"));
      }

      setShowResolveModal(false);
      setResolveNote("");
      setActiveSos(null);
      prevSosIdRef.current = null;
    } catch (err) {
      setResolveError(err instanceof Error ? err.message : t("resolveFailed"));
    } finally {
      setIsResolving(false);
    }
  };

  if (!activeSos) return null;

  const triggeredTimeStr = new Date(activeSos.triggered_at).toLocaleTimeString(
    locale === "hi" ? "hi-IN" : "en-US",
    { hour: "2-digit", minute: "2-digit" }
  );

  return (
    <>
      <div
        role="alert"
        aria-live="assertive"
        className="w-full bg-emergency text-white px-4 py-3 shadow-md border-b-2 border-red-700 animate-pulse-gentle sticky top-16 z-30"
      >
        <div className="max-w-6xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-full bg-white/20 flex items-center justify-center shrink-0 animate-bounce">
              <AlertCircle className="w-6 h-6 text-white" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-extrabold tracking-wide uppercase text-sm sm:text-base">
                  {t("liveBannerTitle")}
                </span>
                <span className="bg-white/25 text-white font-mono text-xs px-2 py-0.5 rounded-full font-semibold">
                  {t("pressCountBadge", { count: activeSos.press_count })}
                </span>
              </div>
              <p className="text-xs sm:text-sm text-white/90">
                {t("liveBannerSubtitle", {
                  name: selectedElder?.preferred_name || selectedElder?.full_name || "",
                  time: triggeredTimeStr,
                  source: activeSos.source === "device" ? t("sourceDevice") : t("sourceWeb"),
                })}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 self-end sm:self-center shrink-0">
            <button
              type="button"
              onClick={playAlertChime}
              title={t("soundTestTooltip")}
              aria-label={t("soundTestTooltip")}
              className="p-2 rounded-lg bg-white/10 hover:bg-white/20 text-white transition-colors"
            >
              <Volume2 className="w-5 h-5" />
            </button>
            <button
              type="button"
              onClick={() => setShowResolveModal(true)}
              className="bg-white text-emergency hover:bg-red-50 font-bold text-sm px-4 py-2 rounded-xl shadow-xs transition-all active:scale-95 flex items-center gap-1.5"
            >
              <CheckCircle2 className="w-4 h-4" />
              <span>{t("markHandledButton")}</span>
            </button>
          </div>
        </div>
      </div>

      {/* Modal: Mark SOS as Handled */}
      {showResolveModal && (
        <div
          role="dialog"
          aria-modal="true"
          className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4 animate-in fade-in"
        >
          <div className="bg-surface rounded-2xl max-w-md w-full p-6 shadow-2xl border border-border">
            <div className="flex items-start justify-between gap-4 mb-4">
              <div className="flex items-center gap-2 text-emergency">
                <CheckCircle2 className="w-6 h-6" />
                <h2 className="text-lg font-bold text-text-primary">
                  {t("resolveModalTitle")}
                </h2>
              </div>
              <button
                type="button"
                onClick={() => setShowResolveModal(false)}
                className="text-text-muted hover:text-text-primary p-1 rounded-lg"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <p className="text-sm text-text-secondary mb-4">
              {t("resolveModalDesc", {
                name: selectedElder?.preferred_name || selectedElder?.full_name || "",
              })}
            </p>

            {resolveError && (
              <div className="p-3 bg-red-50 text-emergency text-sm rounded-xl mb-4 border border-red-200">
                {resolveError}
              </div>
            )}

            <form onSubmit={handleResolve} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-text-secondary mb-1">
                  {t("resolveNoteLabel")}
                </label>
                <textarea
                  rows={3}
                  value={resolveNote}
                  onChange={(e) => setResolveNote(e.target.value)}
                  placeholder={t("resolveNotePlaceholder")}
                  className="w-full px-3 py-2 rounded-xl border border-border bg-surface text-text-primary text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                />
              </div>

              <div className="flex justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setShowResolveModal(false)}
                  disabled={isResolving}
                  className="px-4 py-2 rounded-xl text-sm font-medium text-text-secondary hover:bg-surface-muted transition-colors"
                >
                  {tCommon("cancel")}
                </button>
                <button
                  type="submit"
                  disabled={isResolving}
                  className="px-5 py-2 rounded-xl text-sm font-semibold bg-emerald-600 hover:bg-emerald-700 text-white shadow-xs transition-colors disabled:opacity-50"
                >
                  {isResolving ? tCommon("loading") : t("confirmHandledButton")}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </>
  );
}
