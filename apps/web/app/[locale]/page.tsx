"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { AiraLogo } from "@/components/aira-logo";

export default function SplashScreenPage() {
  const router = useRouter();
  const locale = useLocale();
  const tCommon = useTranslations("common");

  const [isTransitioning, setIsTransitioning] = React.useState(false);
  const [countdown, setCountdown] = React.useState(5);

  React.useEffect(() => {
    // 1-second countdown tick for accessible status
    const interval = setInterval(() => {
      setCountdown((prev) => Math.max(0, prev - 1));
    }, 1000);

    // 5-second timer to transition to the login screen
    const timer = setTimeout(() => {
      handleTransition();
    }, 5000);

    return () => {
      clearInterval(interval);
      clearTimeout(timer);
    };
  }, []);

  const handleTransition = () => {
    setIsTransitioning(true);
    setTimeout(() => {
      router.push(`/${locale}/login`);
    }, 450); // 450ms smooth fade transition
  };

  return (
    <main
      className={`min-h-screen w-full flex flex-col items-center justify-center p-6 bg-background relative overflow-hidden select-none transition-all duration-500 ease-in-out ${
        isTransitioning ? "opacity-0 scale-95" : "opacity-100 scale-100"
      }`}
      aria-label="AIRA Launch Screen"
    >
      {/* Background Soft Radiating Glow */}
      <div className="absolute w-[340px] h-[340px] sm:w-[480px] sm:h-[480px] rounded-full bg-primary-soft/45 blur-3xl pointer-events-none" />

      {/* Main Centered Content */}
      <div className="relative z-10 flex flex-col items-center text-center max-w-sm mx-auto px-4 animate-in fade-in zoom-in-95 duration-700">
        {/* Animated Brand Emblem ('A' + Heart + Listening Pulse) */}
        <div className="relative mb-6">
          {/* Subtle warm halo */}
          <div className="absolute inset-0 rounded-[36px] bg-primary/25 blur-xl animate-pulse" />

          {/* Central Logo Box */}
          <AiraLogo size="xl" animateHeartbeat={true} className="relative z-10 shadow-glow" />
        </div>

        {/* Brand Name */}
        <h1 className="text-4xl sm:text-5xl font-black tracking-tight text-primary">
          AIRA
        </h1>

        {/* Tagline */}
        <p className="text-sm sm:text-base text-text-secondary font-medium mt-2 max-w-xs leading-relaxed">
          {tCommon("tagline")}
        </p>

        {/* 5-Second Linear Progress Bar */}
        <div className="w-48 sm:w-56 h-1.5 bg-surface-muted border border-border rounded-full overflow-hidden mt-8 shadow-2xs">
          <div className="h-full bg-primary rounded-full animate-splash-progress" />
        </div>

        {/* Skip / Continue button */}
        <button
          type="button"
          onClick={handleTransition}
          className="mt-6 text-xs font-semibold text-text-muted hover:text-primary transition-colors py-1.5 px-4 rounded-full hover:bg-surface-muted/80 active:scale-95"
        >
          {locale === "hi" ? "आगे बढ़ें →" : "Continue →"}
        </button>
      </div>

      {/* Subtle bottom companion brand credit */}
      <div className="absolute bottom-6 sm:bottom-8 text-center text-[10px] sm:text-xs text-text-muted tracking-wider uppercase font-semibold">
        AIRA Care Companion
      </div>
    </main>
  );
}
