"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { ArrowLeft, Clock, Globe, Heart, Type, User } from "lucide-react";

import { useElder } from "@/components/elder-context";
import { PrintableCredentials } from "@/components/printable-credentials";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

interface CreatedCredentials {
  elder_id: string;
  access_code: string;
  pin: string;
  qr_token: string;
  qr_url: string;
}

export default function NewElderPage() {
  const t = useTranslations("elderCreate");
  const tCommon = useTranslations("common");
  const locale = useLocale();
  const router = useRouter();
  const { refreshElders, selectElder } = useElder();

  // Form states
  const [fullName, setFullName] = React.useState("");
  const [preferredName, setPreferredName] = React.useState("");
  const [dateOfBirth, setDateOfBirth] = React.useState("");
  const [language, setLanguage] = React.useState<"en" | "hi">("hi");
  const [timezone, setTimezone] = React.useState("Asia/Kolkata");
  const [dayCloseTime, setDayCloseTime] = React.useState("23:59");
  const [textSize, setTextSize] = React.useState<number>(1); // 0=normal, 1=large, 2=xlarge

  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState("");
  const [timeError, setTimeError] = React.useState("");

  // Resulting credentials
  const [credentials, setCredentials] = React.useState<CreatedCredentials | null>(null);

  const validateDayCloseTime = (val: string): boolean => {
    if (!val) return false;
    const [hours, minutes] = val.split(":").map(Number);
    if (isNaN(hours) || isNaN(minutes)) return false;
    if (hours < 20) {
      setTimeError(t("dayCloseTimeMinError"));
      return false;
    }
    setTimeError("");
    return true;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (!fullName.trim()) {
      setError(t("fullNameRequired"));
      return;
    }

    if (!validateDayCloseTime(dayCloseTime)) {
      return;
    }

    setLoading(true);

    try {
      const payload = {
        full_name: fullName.trim(),
        preferred_name: preferredName.trim() || null,
        date_of_birth: dateOfBirth || null,
        language,
        timezone,
        day_close_time: dayCloseTime,
        text_size: Number(textSize),
      };

      const res = await fetch("/api/v1/elders", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        setError(errorData.detail || t("createFailed"));
        setLoading(false);
        return;
      }

      const creds: CreatedCredentials = await res.json();
      setCredentials(creds);
      await refreshElders();
      selectElder(creds.elder_id);
    } catch {
      setError(t("createFailed"));
    } finally {
      setLoading(false);
    }
  };

  if (credentials) {
    return (
      <div className="py-6">
        <PrintableCredentials
          elderName={preferredName || fullName}
          accessCode={credentials.access_code}
          pin={credentials.pin}
          qrUrl={credentials.qr_url}
          onDone={() => router.push(`/${locale}/status`)}
        />
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto py-4 sm:py-6">
      {/* Header */}
      <div className="mb-6 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link
            href={`/${locale}/status`}
            className="p-2 rounded-lg text-text-secondary hover:text-text-primary hover:bg-surface-muted transition-colors"
          >
            <ArrowLeft className="w-5 h-5" />
          </Link>
          <div>
            <h1 className="text-2xl font-bold text-text-primary tracking-tight">
              {t("title")}
            </h1>
            <p className="text-sm text-text-secondary mt-0.5">{t("subtitle")}</p>
          </div>
        </div>
      </div>

      <Card className="p-6 sm:p-8 bg-surface border border-border shadow-sm">
        <form onSubmit={handleSubmit} className="space-y-6">
          {error && (
            <div className="p-3.5 rounded-xl bg-accent-crimson/10 border border-accent-crimson/20 text-accent-crimson text-sm font-medium">
              {error}
            </div>
          )}

          {/* Full Name & Preferred Name */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Input
              label={t("fullNameLabel")}
              placeholder={t("fullNamePlaceholder")}
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              required
            />
            <Input
              label={t("preferredNameLabel")}
              placeholder={t("preferredNamePlaceholder")}
              value={preferredName}
              onChange={(e) => setPreferredName(e.target.value)}
            />
          </div>

          {/* Date of Birth */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Input
              label={t("dobLabel")}
              type="date"
              value={dateOfBirth}
              onChange={(e) => setDateOfBirth(e.target.value)}
            />

            {/* Language Selection */}
            <div className="space-y-1.5">
              <label className="text-sm font-medium text-text-primary flex items-center gap-1.5">
                <Globe className="w-4 h-4 text-text-secondary" />
                <span>{t("languageLabel")}</span>
              </label>
              <select
                value={language}
                onChange={(e) => setLanguage(e.target.value as "en" | "hi")}
                className="w-full px-4 py-2.5 rounded-xl border border-border bg-surface text-text-primary focus:outline-hidden focus:ring-2 focus:ring-primary/20 focus:border-primary transition-all text-sm font-medium"
              >
                <option value="hi">हिन्दी (Hindi)</option>
                <option value="en">English</option>
              </select>
            </div>
          </div>

          {/* Time Zone & Day-Close Time */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <label className="text-sm font-medium text-text-primary flex items-center gap-1.5">
                <Clock className="w-4 h-4 text-text-secondary" />
                <span>{t("timezoneLabel")}</span>
              </label>
              <select
                value={timezone}
                onChange={(e) => setTimezone(e.target.value)}
                className="w-full px-4 py-2.5 rounded-xl border border-border bg-surface text-text-primary focus:outline-hidden focus:ring-2 focus:ring-primary/20 focus:border-primary transition-all text-sm font-medium"
              >
                <option value="Asia/Kolkata">India Standard Time (IST - Asia/Kolkata)</option>
                <option value="UTC">Coordinated Universal Time (UTC)</option>
                <option value="America/New_York">US Eastern (America/New_York)</option>
                <option value="America/Los_Angeles">US Pacific (America/Los_Angeles)</option>
                <option value="Europe/London">UK (Europe/London)</option>
              </select>
            </div>

            <div className="space-y-1.5">
              <Input
                label={t("dayCloseTimeLabel")}
                type="time"
                value={dayCloseTime}
                onChange={(e) => {
                  setDayCloseTime(e.target.value);
                  validateDayCloseTime(e.target.value);
                }}
                error={timeError}
                required
              />
              <p className="text-xs text-text-secondary">
                {t("dayCloseTimeHelp")}
              </p>
            </div>
          </div>

          {/* Text Size Preference for Elder Interface */}
          <div className="space-y-2 pt-2 border-t border-border">
            <label className="text-sm font-medium text-text-primary flex items-center gap-1.5">
              <Type className="w-4 h-4 text-text-secondary" />
              <span>{t("textSizeLabel")}</span>
            </label>
            <div className="grid grid-cols-3 gap-3">
              {[
                { val: 0, label: t("textSizeNormal"), sample: "Aa" },
                { val: 1, label: t("textSizeLarge"), sample: "Aa" },
                { val: 2, label: t("textSizeXLarge"), sample: "Aa" },
              ].map((opt) => (
                <button
                  key={opt.val}
                  type="button"
                  onClick={() => setTextSize(opt.val)}
                  className={`p-3 rounded-xl border text-center transition-all ${
                    textSize === opt.val
                      ? "border-primary bg-primary-soft text-primary font-semibold ring-2 ring-primary/20"
                      : "border-border bg-surface text-text-secondary hover:border-primary/40 hover:text-text-primary"
                  }`}
                >
                  <span
                    className={`block font-bold mb-1 ${
                      opt.val === 0 ? "text-sm" : opt.val === 1 ? "text-lg" : "text-xl"
                    }`}
                  >
                    {opt.sample}
                  </span>
                  <span className="text-xs">{opt.label}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Form Actions */}
          <div className="pt-4 flex items-center justify-end gap-3">
            <Link href={`/${locale}/status`}>
              <Button type="button" variant="ghost">
                {tCommon("cancel")}
              </Button>
            </Link>
            <Button type="submit" isLoading={loading}>
              {t("createButton")}
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
}
