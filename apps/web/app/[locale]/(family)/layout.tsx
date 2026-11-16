"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { Activity, AlertTriangle, Calendar, Heart, LogOut, Pill, Settings, Users } from "lucide-react";

import { ElderProvider } from "@/components/elder-context";
import { ElderSwitcher } from "@/components/elder-switcher";
import { LanguageToggle } from "@/components/language-toggle";
import { NotificationInbox } from "@/components/notification-inbox";
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
    { href: `/${locale}/settings/notifications`, label: t("settings"), icon: Settings },
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
        {/* Top Header with Safe Area Insets */}
        <header className="sticky top-0 z-40 bg-surface/95 backdrop-blur-md border-b border-border shadow-2xs pt-[env(safe-area-inset-top,0px)]">
          <div className="max-w-6xl mx-auto px-3 sm:px-6 h-16 flex items-center justify-between gap-2 sm:gap-4">
            {/* Left: Brand + Elder Switcher */}
            <div className="flex items-center gap-2 sm:gap-6 min-w-0">
              <Link href={`/${locale}/status`} className="flex items-center gap-2 text-primary group shrink-0">
                <div className="w-9 h-9 rounded-full bg-primary-soft flex items-center justify-center text-primary group-hover:scale-105 transition-transform shadow-2xs">
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
            <div className="flex items-center gap-1.5 sm:gap-3 shrink-0">
              <NotificationInbox />
              <LanguageToggle />
              <button
                type="button"
                onClick={handleSignOut}
                aria-label={t("signOut")}
                title={t("signOut")}
                className="p-2 rounded-lg text-text-secondary hover:text-text-primary hover:bg-surface-muted transition-colors active:scale-95"
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

        {/* Main Content Area: with safe area bottom clearance */}
        <main className="flex-1 max-w-6xl w-full mx-auto p-3.5 sm:p-6 md:p-8 pb-[calc(5rem+env(safe-area-inset-bottom,0px))] sm:pb-8">
          {children}
        </main>

        {/* Mobile Bottom Navigation with Safe Area Support */}
        <nav className="sm:hidden fixed bottom-0 left-0 right-0 z-40 bg-surface/95 backdrop-blur-md border-t border-border flex justify-around items-center px-1 shadow-lg h-[calc(4rem+env(safe-area-inset-bottom,0px))] pb-[env(safe-area-inset-bottom,0px)]">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex flex-col items-center justify-center flex-1 h-full py-1 text-[11px] font-semibold transition-all active:scale-95 ${
                  isActive ? "text-primary font-bold" : "text-text-secondary hover:text-text-primary"
                }`}
              >
                <div className={`p-1 rounded-xl transition-colors ${isActive ? "bg-primary-soft text-primary" : ""}`}>
                  <Icon className="w-5 h-5" />
                </div>
                <span className="mt-0.5 leading-none tracking-tight">{item.label}</span>
              </Link>
            );
          })}
        </nav>
      </div>
    </ElderProvider>
  );
}
