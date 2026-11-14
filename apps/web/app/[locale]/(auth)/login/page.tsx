"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { Heart, QrCode, Shield, Users } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { LanguageToggle } from "@/components/language-toggle";

export default function LoginPage() {
  const t = useTranslations("auth");
  const tCommon = useTranslations("common");
  const locale = useLocale();
  const router = useRouter();

  const [activeTab, setActiveTab] = React.useState<"team" | "elder">("team");

  // Family / Caregiver state
  const [email, setEmail] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [teamLoading, setTeamLoading] = React.useState(false);
  const [teamError, setTeamError] = React.useState("");

  // Elder state
  const [accessCode, setAccessCode] = React.useState("");
  const [pin, setPin] = React.useState("");
  const [elderLoading, setElderLoading] = React.useState(false);
  const [elderError, setElderError] = React.useState("");

  const handleTeamLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setTeamLoading(true);
    setTeamError("");

    try {
      const res = await fetch("/api/v1/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        if (errorData.code === "EMAIL_NOT_VERIFIED") {
          setTeamError(t("emailNotVerified"));
        } else {
          setTeamError(t("loginFailed"));
        }
        setTeamLoading(false);
        return;
      }

      router.push(`/${locale}/home`);
    } catch {
      setTeamError(t("loginFailed"));
      setTeamLoading(false);
    }
  };

  const handleElderLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setElderLoading(true);
    setElderError("");

    try {
      const res = await fetch("/api/v1/auth/elder/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ access_code: accessCode.trim().toUpperCase(), pin }),
      });

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        if (errorData.code === "ELDER_LOCKED") {
          setElderError(t("elderLocked"));
        } else {
          setElderError(t("loginFailed"));
        }
        setElderLoading(false);
        return;
      }

      router.push(`/${locale}/elder`);
    } catch {
      setElderError(t("loginFailed"));
      setElderLoading(false);
    }
  };

  return (
    <div className="flex-1 flex flex-col items-center justify-center p-4 sm:p-6 md:p-8">
      {/* Top Bar with Language Toggle */}
      <header className="w-full max-w-md flex justify-between items-center mb-6">
        <div className="flex items-center gap-2">
          <div className="w-10 h-10 rounded-full bg-primary-soft flex items-center justify-center text-primary">
            <Heart className="w-6 h-6 fill-current" />
          </div>
          <div>
            <h1 className="font-extrabold text-xl text-primary leading-tight">AIRA</h1>
            <p className="text-xs text-text-muted">{tCommon("tagline")}</p>
          </div>
        </div>
        <LanguageToggle />
      </header>

      {/* Main Login Card */}
      <Card className="w-full max-w-md">
        <h2 className="text-2xl font-bold text-center mb-6">{t("loginTitle")}</h2>

        {/* Segmented Control for Sign-in Paths */}
        <div className="grid grid-cols-2 p-1 bg-surface-soft rounded-btn mb-6" role="tablist">
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === "team"}
            onClick={() => setActiveTab("team")}
            className={`flex items-center justify-center gap-2 py-2.5 px-3 rounded-btn text-sm font-bold transition-all ${
              activeTab === "team"
                ? "bg-surface text-primary shadow-sm"
                : "text-text-muted hover:text-text-main"
            }`}
          >
            <Users className="w-4 h-4" />
            <span>{t("familyCaregiverTab")}</span>
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === "elder"}
            onClick={() => setActiveTab("elder")}
            className={`flex items-center justify-center gap-2 py-2.5 px-3 rounded-btn text-sm font-bold transition-all ${
              activeTab === "elder"
                ? "bg-surface text-primary shadow-sm"
                : "text-text-muted hover:text-text-main"
            }`}
          >
            <Shield className="w-4 h-4" />
            <span>{t("elderTab")}</span>
          </button>
        </div>

        {/* Family & Caregiver Login Form */}
        {activeTab === "team" ? (
          <form onSubmit={handleTeamLogin} className="space-y-4">
            {teamError && (
              <div className="p-3.5 bg-warning-bg text-warning rounded-input text-sm font-semibold border border-warning">
                {teamError}
              </div>
            )}

            <Input
              label={t("emailLabel")}
              type="email"
              required
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
            />

            <Input
              label={t("passwordLabel")}
              type="password"
              required
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••••"
            />

            <div className="flex justify-end">
              <Link
                href={`/${locale}/forgot-password`}
                className="text-sm font-semibold text-primary hover:underline"
              >
                {t("forgotPassword")}
              </Link>
            </div>

            <Button type="submit" className="w-full" disabled={teamLoading}>
              {teamLoading ? tCommon("loading") : t("signInButton")}
            </Button>

            <div className="pt-4 text-center text-sm text-text-muted">
              {t("noAccount")}{" "}
              <Link href={`/${locale}/register`} className="font-bold text-primary hover:underline">
                {t("registerButton")}
              </Link>
            </div>
          </form>
        ) : (
          /* Elder Sign-in Form */
          <form onSubmit={handleElderLogin} className="space-y-4">
            {elderError && (
              <div className="p-3.5 bg-warning-bg text-warning rounded-input text-sm font-semibold border border-warning">
                {elderError}
              </div>
            )}

            <Input
              label={t("accessCodeLabel")}
              type="text"
              required
              value={accessCode}
              onChange={(e) => setAccessCode(e.target.value)}
              placeholder={t("accessCodePlaceholder")}
              className="uppercase tracking-wider text-center text-lg font-bold"
            />

            <Input
              label={t("pinLabel")}
              type="password"
              inputMode="numeric"
              maxLength={4}
              required
              value={pin}
              onChange={(e) => setPin(e.target.value)}
              placeholder="••••"
              className="text-center text-2xl tracking-[0.5em] font-bold"
            />

            <Button type="submit" size="elder" className="w-full mt-2" disabled={elderLoading}>
              {elderLoading ? tCommon("loading") : t("signInButton")}
            </Button>

            <div className="pt-4 border-t border-border text-center space-y-2">
              <div className="flex items-center justify-center gap-2 text-text-muted text-sm">
                <QrCode className="w-5 h-5 text-primary" />
                <span>{t("scanQrPrompt")}</span>
              </div>
            </div>
          </form>
        )}
      </Card>

      {/* Medical Disclaimer Note (MED-9) */}
      <footer className="w-full max-w-md mt-6 text-center text-xs text-text-muted">
        <p>{tCommon("disclaimer")}</p>
      </footer>
    </div>
  );
}
