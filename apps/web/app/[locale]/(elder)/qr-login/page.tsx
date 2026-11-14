"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { AlertCircle, Heart, RefreshCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

export default function ElderQrLoginPage() {
  const t = useTranslations("auth");
  const tCommon = useTranslations("common");
  const locale = useLocale();
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams.get("token");

  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState("");

  React.useEffect(() => {
    if (!token) {
      setError(t("loginFailed"));
      setLoading(false);
      return;
    }

    const performQrLogin = async () => {
      try {
        const res = await fetch("/api/v1/auth/elder/qr", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ token }),
        });

        if (res.ok) {
          router.push(`/${locale}/elder`);
        } else {
          setError(t("loginFailed"));
          setLoading(false);
        }
      } catch {
        setError(t("loginFailed"));
        setLoading(false);
      }
    };

    performQrLogin();
  }, [token, router, locale, t]);

  if (loading) {
    return (
      <div className="min-h-screen bg-bg-app flex flex-col items-center justify-center p-6 text-center">
        <div className="w-16 h-16 rounded-full bg-primary-soft text-primary flex items-center justify-center animate-pulse mb-4">
          <Heart className="w-8 h-8 fill-current" />
        </div>
        <h1 className="text-xl font-bold text-text-primary">{tCommon("loading")}</h1>
        <p className="text-sm text-text-secondary mt-1">{t("welcome")}</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-bg-app flex flex-col items-center justify-center p-6">
      <Card className="max-w-md w-full p-8 text-center bg-surface border border-border shadow-md">
        <div className="w-12 h-12 rounded-full bg-accent-crimson/15 text-accent-crimson flex items-center justify-center mx-auto mb-4">
          <AlertCircle className="w-6 h-6" />
        </div>
        <h1 className="text-xl font-bold text-text-primary mb-2">
          {error || t("loginFailed")}
        </h1>
        <p className="text-sm text-text-secondary mb-6 leading-relaxed">
          {t("scanQrPrompt")}
        </p>
        <Link href={`/${locale}/login`}>
          <Button className="w-full">
            {t("backToLogin")}
          </Button>
        </Link>
      </Card>
    </div>
  );
}
