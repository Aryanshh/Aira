"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { Activity, AlertTriangle, Calendar, Heart, LogOut, Pill, Users } from "lucide-react";

import { ElderProvider } from "@/components/elder-context";
import { ElderSwitcher } from "@/components/elder-switcher";
import { LanguageToggle } from "@/components/language-toggle";
import { SosLiveBanner } from "@/components/sos-live-banner";

export default function FamilyLayout({ children }: { children: React.ReactNode }) {
  const t = useTranslations("nav");
  const locale = useLocale();
  const pathname = usePathname();
  const router = useRouter();

  const navItems = [
    { href: `/${locale}/status`, label: t("status"), icon: Activity },
    { href: `/${locale}/medicines`, label: t("medicines"), icon: Pill },
    { href: `/${locale}/sos`, label: t("sos"), icon: AlertTriangle },
    { href: `/${locale}/team`, label: t("team"), icon: Users },
  ];

  const handleSignOut = async () => {
    try {
      await fetch("/api/v1/auth/logout", { method: "POST" });
    } catch {
      // Ignored
    }
    router.push(`/${locale}/login`);
  };

  return (
    <ElderProvider>
      <div className="min-h-screen bg-bg-app flex flex-col font-sans">
        {/* Top Header */}
        <header className="sticky top-0 z-40 bg-surface/90 backdrop-blur-md border-b border-border shadow-2xs">
          <div className="max-w-6xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between gap-4">
            {/* Left: Brand + Elder Switcher */}
            <div className="flex items-center gap-4 sm:gap-6">
              <Link href={`/${locale}/status`} className="flex items-center gap-2 text-primary group">
                <div className="w-9 h-9 rounded-full bg-primary-soft flex items-center justify-center text-primary group-hover:scale-105 transition-transform">
                  <Heart className="w-5 h-5 fill-current" />
                </div>
                <span className="font-bold text-lg text-text-primary hidden sm:inline tracking-tight">
                  AIRA Care
                </span>
              </Link>

              {/* Elder Switcher (ELD-2) */}
              <ElderSwitcher />
            </div>

            {/* Right: Actions & Nav */}
            <div className="flex items-center gap-2 sm:gap-3">
              <LanguageToggle />
              <button
                type="button"
                onClick={handleSignOut}
                aria-label={t("signOut")}
                title={t("signOut")}
                className="p-2 rounded-lg text-text-secondary hover:text-text-primary hover:bg-surface-muted transition-colors"
              >
                <LogOut className="w-5 h-5" />
              </button>
            </div>
          </div>

          {/* Desktop & Tablet Sub-Navigation */}
          <nav className="max-w-6xl mx-auto px-4 sm:px-6 hidden sm:flex border-t border-border/50 gap-6">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = pathname.startsWith(item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`inline-flex items-center gap-2 py-3 text-sm font-medium border-b-2 transition-colors ${
                    isActive
                      ? "border-primary text-primary"
                      : "border-transparent text-text-secondary hover:text-text-primary hover:border-border"
                  }`}
                >
                  <Icon className="w-4 h-4" />
                  <span>{item.label}</span>
                </Link>
              );
            })}
          </nav>
        </header>

        {/* Live SOS Alert Banner (SOS-3) */}
        <SosLiveBanner />

        {/* Main Content Area */}
        <main className="flex-1 max-w-6xl w-full mx-auto p-4 sm:p-6 md:p-8 pb-20 sm:pb-8">
          {children}
        </main>

        {/* Mobile Bottom Navigation */}
        <nav className="sm:hidden fixed bottom-0 left-0 right-0 z-40 bg-surface border-t border-border flex justify-around items-center h-16 px-2 shadow-lg">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex flex-col items-center justify-center w-full h-full py-1 text-xs font-medium transition-colors ${
                  isActive ? "text-primary font-bold" : "text-text-secondary hover:text-text-primary"
                }`}
              >
                <Icon className={`w-5 h-5 ${isActive ? "text-primary" : "text-text-secondary"}`} />
                <span className="mt-1">{item.label}</span>
              </Link>
            );
          })}
        </nav>
      </div>
    </ElderProvider>
  );
}
