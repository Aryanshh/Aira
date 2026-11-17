"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { Heart } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { LanguageToggle } from "@/components/language-toggle";
import { AiraLogo } from "@/components/aira-logo";

export default function RegisterPage() {
  const t = useTranslations("auth");
  const tCommon = useTranslations("common");
  const locale = useLocale();
  const router = useRouter();

  const [fullName, setFullName] = React.useState("");
  const [email, setEmail] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState("");
  const [success, setSuccess] = React.useState(false);

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (password.length < 10) {
      setError(t("passwordMinLengthError"));
      return;
    }

    setLoading(true);

    try {
      const normalizedEmail = email.trim().toLowerCase();
      const res = await fetch("/api/v1/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          full_name: fullName.trim(),
          email: normalizedEmail,
          password,
          preferred_language: locale,
          timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "Asia/Kolkata",
        }),
      });

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        setError(errorData.detail || "Registration failed. Please try again.");
        setLoading(false);
        return;
      }

      // Clear any prior cached elder data from localStorage
      if (typeof window !== "undefined") {
        try {
          localStorage.removeItem("aira_selected_elder_id");
          localStorage.removeItem("aira_elder_profile");
          localStorage.removeItem("aira_elder_doses");
          localStorage.removeItem("aira_elder_contacts");
        } catch {
          // Ignored
        }
      }

      // Direct seamless transition into fresh account onboarding
      window.location.href = `/${locale}/elders/new`;
      return;
    } catch {
      setError("An unexpected network error occurred.");
      setLoading(false);
    }
  };

  return (
    <div className="flex-1 flex flex-col items-center justify-center p-4 sm:p-6 md:p-8">
      {/* Top Bar with Language Toggle */}
      <header className="w-full max-w-md flex justify-between items-center mb-6">
        <div className="flex items-center gap-3">
          <AiraLogo size="md" className="shadow-xs" />
          <div>
            <h1 className="font-extrabold text-xl text-primary leading-tight">AIRA</h1>
            <p className="text-xs text-text-muted">{tCommon("tagline")}</p>
          </div>
        </div>
        <LanguageToggle />
      </header>

      {/* Main Register Card */}
      <Card className="w-full max-w-md shadow-md">
        <h2 className="text-2xl font-bold text-center mb-6">{t("registerTitle")}</h2>

        {success ? (
          <div className="p-4 bg-secondary-soft text-secondary rounded-card text-center font-bold">
            Account created! Redirecting...
          </div>
        ) : (
          <form onSubmit={handleRegister} className="space-y-4">
            {error && (
              <div className="p-3.5 bg-warning-bg text-warning rounded-input text-sm font-semibold border border-warning">
                {error}
              </div>
            )}

            <Input
              label={t("fullNameLabel")}
              type="text"
              required
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              placeholder="e.g. Anjali Sharma"
            />

            <Input
              label={t("emailLabel")}
              type="email"
              inputMode="email"
              autoCapitalize="none"
              autoCorrect="off"
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
              minLength={10}
              autoComplete="new-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Min. 10 characters"
            />

            <Button type="submit" className="w-full font-bold mt-2" disabled={loading}>
              {loading ? tCommon("loading") : t("registerButton")}
            </Button>

            <div className="pt-4 text-center text-sm text-text-muted">
              {t("alreadyHaveAccount")}{" "}
              <Link href={`/${locale}/login`} className="font-bold text-primary hover:underline">
                {t("signInButton")}
              </Link>
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
