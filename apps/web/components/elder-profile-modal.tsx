"use client";

import * as React from "react";
import { useTranslations } from "next-intl";
import { Check, Loader2, Sparkles, User, X } from "lucide-react";
import { ElderSummary, useElder } from "@/components/elder-context";

interface ElderProfileModalProps {
  elder: ElderSummary | null;
  isOpen: boolean;
  onClose: () => void;
}

export function ElderProfileModal({ elder, isOpen, onClose }: ElderProfileModalProps) {
  const t = useTranslations("switcher");
  const { updateElder } = useElder();

  const [preferredName, setPreferredName] = React.useState("");
  const [fullName, setFullName] = React.useState("");
  const [language, setLanguage] = React.useState("hi");
  const [textSize, setTextSize] = React.useState<number>(1);
  const [saving, setSaving] = React.useState(false);
  const [success, setSuccess] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  // Sync state when elder prop changes or modal opens
  React.useEffect(() => {
    if (elder) {
      setPreferredName(elder.preferred_name || "");
      setFullName(elder.full_name || "");
      setLanguage(elder.language || "hi");
      setTextSize(elder.text_size ?? 1);
      setError(null);
      setSuccess(false);
    }
  }, [elder, isOpen]);

  if (!isOpen || !elder) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!fullName.trim()) {
      setError("Full name is required.");
      return;
    }

    try {
      setSaving(true);
      setError(null);
      const ok = await updateElder(elder.id, {
        preferred_name: preferredName.trim() || null,
        full_name: fullName.trim(),
        language,
        text_size: textSize,
      });

      if (ok) {
        setSuccess(true);
        setTimeout(() => {
          setSuccess(false);
          onClose();
        }, 800);
      } else {
        setError("Failed to update profile. Please try again.");
      }
    } catch {
      setError("An unexpected network error occurred.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-xs animate-in fade-in duration-150">
      <div
        className="w-full max-w-md bg-surface rounded-2xl border border-border shadow-2xl overflow-hidden animate-in zoom-in-95 duration-150"
        role="dialog"
        aria-modal="true"
        aria-labelledby="modal-title"
      >
        {/* Header */}
        <div className="px-6 py-4 border-b border-border flex items-center justify-between bg-surface-muted/40">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-full bg-primary-soft text-primary flex items-center justify-center font-bold text-sm">
              <User className="w-4 h-4" />
            </div>
            <div>
              <h2 id="modal-title" className="text-base font-bold text-text-primary">
                {t("editElderTitle")}
              </h2>
              <p className="text-xs text-text-secondary">
                {elder.preferred_name || elder.full_name}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="p-1.5 rounded-lg text-text-secondary hover:text-text-primary hover:bg-surface transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Live sync banner */}
        <div className="px-6 py-2.5 bg-primary-soft/40 border-b border-primary/10 flex items-center gap-2 text-xs text-primary font-medium">
          <Sparkles className="w-4 h-4 shrink-0 animate-pulse text-primary" />
          <span>{t("editElderDesc")}</span>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {error && (
            <div className="p-3 text-xs rounded-xl bg-danger/10 border border-danger/20 text-danger font-medium">
              {error}
            </div>
          )}

          {success && (
            <div className="p-3 text-xs rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-700 flex items-center gap-2 font-medium">
              <Check className="w-4 h-4 text-emerald-600" />
              <span>{t("saveSuccess")}</span>
            </div>
          )}

          {/* Preferred Name */}
          <div>
            <label className="block text-xs font-semibold text-text-primary mb-1">
              {t("preferredNameLabel")}
            </label>
            <input
              type="text"
              value={preferredName}
              onChange={(e) => setPreferredName(e.target.value)}
              placeholder="e.g. Dadaji, Ramesh ji, नानाजी"
              className="w-full px-3.5 py-2 text-sm rounded-xl bg-surface border border-border focus:outline-hidden focus:ring-2 focus:ring-primary/20 focus:border-primary transition-all text-text-primary"
            />
            <p className="text-[11px] text-text-secondary mt-1">
              Used in voice companion greeting and elder screen heading.
            </p>
          </div>

          {/* Full Name */}
          <div>
            <label className="block text-xs font-semibold text-text-primary mb-1">
              {t("fullNameLabel")} *
            </label>
            <input
              type="text"
              required
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              placeholder="e.g. Ramesh Chandra Sharma"
              className="w-full px-3.5 py-2 text-sm rounded-xl bg-surface border border-border focus:outline-hidden focus:ring-2 focus:ring-primary/20 focus:border-primary transition-all text-text-primary"
            />
          </div>

          {/* Language Selection */}
          <div>
            <label className="block text-xs font-semibold text-text-primary mb-1.5">
              {t("languageLabel")}
            </label>
            <div className="grid grid-cols-2 gap-2.5">
              <button
                type="button"
                onClick={() => setLanguage("hi")}
                className={`py-2 px-3 text-xs font-semibold rounded-xl border flex items-center justify-center gap-2 transition-all ${
                  language === "hi"
                    ? "border-primary bg-primary text-white shadow-xs"
                    : "border-border bg-surface text-text-secondary hover:text-text-primary"
                }`}
              >
                <span>हिन्दी (Hindi)</span>
                {language === "hi" && <Check className="w-3.5 h-3.5" />}
              </button>
              <button
                type="button"
                onClick={() => setLanguage("en")}
                className={`py-2 px-3 text-xs font-semibold rounded-xl border flex items-center justify-center gap-2 transition-all ${
                  language === "en"
                    ? "border-primary bg-primary text-white shadow-xs"
                    : "border-border bg-surface text-text-secondary hover:text-text-primary"
                }`}
              >
                <span>English</span>
                {language === "en" && <Check className="w-3.5 h-3.5" />}
              </button>
            </div>
          </div>

          {/* Text Size Selection */}
          <div>
            <label className="block text-xs font-semibold text-text-primary mb-1.5">
              {t("textSizeLabel")}
            </label>
            <div className="grid grid-cols-3 gap-2">
              {[
                { val: 0, label: "Normal (A)" },
                { val: 1, label: "Large (A+)" },
                { val: 2, label: "Extra (A++)" },
              ].map((opt) => (
                <button
                  key={opt.val}
                  type="button"
                  onClick={() => setTextSize(opt.val)}
                  className={`py-2 px-2 text-xs font-semibold rounded-xl border text-center transition-all ${
                    textSize === opt.val
                      ? "border-primary bg-primary-soft text-primary font-bold shadow-2xs"
                      : "border-border bg-surface text-text-secondary hover:text-text-primary"
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>

          {/* Action buttons */}
          <div className="pt-2 flex items-center justify-end gap-2.5">
            <button
              type="button"
              onClick={onClose}
              disabled={saving}
              className="px-4 py-2 text-sm font-medium rounded-xl text-text-secondary hover:text-text-primary hover:bg-surface-muted transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving}
              className="inline-flex items-center gap-1.5 px-4 py-2 text-sm font-semibold rounded-xl bg-primary text-white hover:bg-primary-hover active:scale-98 transition-all shadow-xs disabled:opacity-50"
            >
              {saving ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>{t("saving")}</span>
                </>
              ) : (
                <span>{t("saveChanges")}</span>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
