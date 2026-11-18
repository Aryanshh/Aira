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
import { MedicineAlarmBanner } from "@/components/medicine-alarm-banner";
import { AiraLogo } from "@/components/aira-logo";

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
      await fetch("/api/v1/auth/logout", { method: "POST" });
    } catch {
      // Ignored
    }
    window.location.href = `/${locale}/login`;
  };

  return (
    <ElderProvider>
      <div className="min-h-screen min-h-[100dvh] bg-bg-app flex flex-col font-sans">
        {/* Top Header with Safe Area Insets */}
        <header className="sticky top-0 z-40 bg-surface/98 backdrop-blur-md border-b border-border shadow-xs pt-[env(safe-area-inset-top,0px)]">
          <div className="max-w-6xl mx-auto px-3 sm:px-6 h-16 flex items-center justify-between gap-2 sm:gap-4">
            {/* Left: Brand + Elder Switcher */}
            <div className="flex items-center gap-2 sm:gap-6 min-w-0">
              <Link href={`/${locale}/status`} className="flex items-center gap-2 text-primary group shrink-0">
                <AiraLogo size="sm" className="group-hover:scale-105 transition-transform shadow-xs" />
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

          {/* Sub-Navigation: High-contrast mobile pill dock + classic desktop tab bar */}
          <nav className="max-w-6xl mx-auto px-3 sm:px-6 flex items-center gap-1.5 sm:gap-6 border-t border-border/70 overflow-x-auto no-scrollbar py-2 sm:py-0 bg-surface/95 sm:bg-transparent">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = pathname.startsWith(item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`inline-flex items-center gap-1.5 sm:gap-2 px-3 py-1.5 sm:px-0 sm:py-3 text-xs sm:text-sm font-semibold transition-all whitespace-nowrap shrink-0 rounded-xl sm:rounded-none sm:border-b-2 ${
                    isActive
                      ? "bg-primary text-white sm:bg-transparent sm:text-primary sm:border-primary font-bold shadow-xs sm:shadow-none"
                      : "bg-surface text-text-primary hover:bg-surface-muted hover:text-text-primary sm:bg-transparent sm:text-text-secondary sm:hover:text-text-primary sm:hover:border-border sm:border-transparent border border-border/80 sm:border-0 shadow-2xs sm:shadow-none"
                  }`}
                >
                  <Icon className={`w-3.5 h-3.5 sm:w-4 sm:h-4 shrink-0 ${isActive ? "text-white sm:text-primary" : "text-text-secondary"}`} />
                  <span>{item.label}</span>
                </Link>
              );
            })}
          </nav>
        </header>

        {/* Live SOS Alert Banner (SOS-3) */}
        <SosLiveBanner />

        {/* Medicine Alarm Banner */}
        <MedicineAlarmBanner />

        {/* Main Content Area: with safe area bottom clearance */}
        <main className="flex-1 max-w-6xl w-full mx-auto p-3.5 sm:p-6 md:p-8 pb-[calc(6.5rem+env(safe-area-inset-bottom,0px))] sm:pb-8">
          {children}
        </main>

        {/* Mobile Bottom Navigation with Safe Area Support */}
        <nav className="sm:hidden fixed bottom-0 left-0 right-0 z-40 bg-surface/98 backdrop-blur-xl border-t border-border/90 shadow-[0_-4px_20px_rgba(43,38,35,0.08)] h-[calc(4rem+env(safe-area-inset-bottom,0px))] pb-[env(safe-area-inset-bottom,0px)]">
          <div className="flex justify-around items-center h-16 px-1">
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
                  <div className={`p-1 rounded-xl transition-colors ${isActive ? "bg-primary-soft text-primary border border-primary/25 shadow-xs" : ""}`}>
                    <Icon className="w-5 h-5" />
                  </div>
                  <span className="mt-0.5 leading-tight tracking-tight truncate w-full text-center px-0.5 text-[10px] sm:text-[11px]">{item.label}</span>
                </Link>
              );
            })}
          </div>
        </nav>
      </div>
    </ElderProvider>
  );
}
