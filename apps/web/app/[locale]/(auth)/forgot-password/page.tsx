"use client";

import * as React from "react";
import Link from "next/link";
import { useLocale, useTranslations } from "next-intl";
import { ArrowLeft, Heart } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { LanguageToggle } from "@/components/language-toggle";

export default function ForgotPasswordPage() {
  const t = useTranslations("auth");
  const tCommon = useTranslations("common");
  const locale = useLocale();

  const [email, setEmail] = React.useState("");
  const [loading, setLoading] = React.useState(false);
  const [submitted, setSubmitted] = React.useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);

    try {
      await fetch("/api/v1/auth/forgot-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });
      setSubmitted(true);
    } catch {
      setSubmitted(true);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex-1 flex flex-col items-center justify-center p-4 sm:p-6 md:p-8">
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

      <Card className="w-full max-w-md">
        <div className="mb-4">
          <Link
            href={`/${locale}/login`}
            className="inline-flex items-center gap-1.5 text-sm font-semibold text-text-muted hover:text-text-main"
          >
            <ArrowLeft className="w-4 h-4" />
            <span>{t("backToLogin")}</span>
          </Link>
        </div>

        <h2 className="text-2xl font-bold mb-3">{t("resetPasswordTitle")}</h2>
        <p className="text-sm text-text-muted mb-6">
          Enter your email address and we'll send you a secure link to reset your password.
        </p>

        {submitted ? (
          <div className="p-4 bg-secondary-soft text-secondary rounded-card font-medium text-sm">
            If an account exists for this email, you will receive a reset link shortly.
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <Input
              label={t("emailLabel")}
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
            />

            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? tCommon("loading") : t("sendResetLink")}
            </Button>
          </form>
        )}
      </Card>
    </div>
  );
}
