"use client";

import * as React from "react";
import Link from "next/link";
import { useLocale, useTranslations } from "next-intl";
import {
  Activity,
  AlertCircle,
  AlertTriangle,
  Calendar,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Clock,
  Heart,
  Pill,
  Sparkles,
} from "lucide-react";

import { useElder } from "@/components/elder-context";
import { AiraLogo } from "@/components/aira-logo";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

interface DaySummary {
  elder_id: string;
  date: string;
  total_scheduled: number;
  taken_count: number;
  missed_count: number;
  skipped_count: number;
  adherence_pct: number;
  state: "all_taken" | "in_progress" | "has_missed" | "no_doses";
  missed_medicine_names: string[];
}

interface WeekSummary {
  elder_id: string;
  week_start: string;
  week_end: string;
  overall_adherence_pct: number;
  total_scheduled: number;
  total_taken: number;
  total_missed: number;
  days: DaySummary[];
  missed_highlights: string[];
}

interface MonthSummary {
  elder_id: string;
  year: number;
  month: number;
  overall_adherence_pct: number;
  total_scheduled: number;
  total_taken: number;
  total_missed: number;
  days: DaySummary[];
}

export default function StatusDashboardPage() {
  const t = useTranslations("status");
  const tCommon = useTranslations("common");
  const locale = useLocale();
  const { selectedElder, isLoading: elderLoading } = useElder();

  const [viewMode, setViewMode] = React.useState<"day" | "week" | "month">("day");

  // Day state
  const [daySummary, setDaySummary] = React.useState<DaySummary | null>(null);

  // Week state
  const [weekSummary, setWeekSummary] = React.useState<WeekSummary | null>(null);

  // Month state
  const [currentYear, setCurrentYear] = React.useState(new Date().getFullYear());
  const [currentMonth, setCurrentMonth] = React.useState(new Date().getMonth() + 1);
  const [monthSummary, setMonthSummary] = React.useState<MonthSummary | null>(null);

  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState("");

  const fetchDayData = React.useCallback(async () => {
    if (!selectedElder) return;
    try {
      const res = await fetch(`/api/v1/elders/${selectedElder.id}/status/day`);
      if (res.ok) {
        setDaySummary(await res.json());
      }
    } catch {
      // Ignored
    }
  }, [selectedElder]);

  const fetchWeekData = React.useCallback(async () => {
    if (!selectedElder) return;
    try {
      const res = await fetch(`/api/v1/elders/${selectedElder.id}/status/week`);
      if (res.ok) {
        setWeekSummary(await res.json());
      }
    } catch {
      // Ignored
    }
  }, [selectedElder]);

  const fetchMonthData = React.useCallback(async () => {
    if (!selectedElder) return;
    try {
      const res = await fetch(
        `/api/v1/elders/${selectedElder.id}/status/month?year=${currentYear}&month=${currentMonth}`
      );
      if (res.ok) {
        setMonthSummary(await res.json());
      }
    } catch {
      // Ignored
    }
  }, [selectedElder, currentYear, currentMonth]);

  React.useEffect(() => {
    if (!selectedElder) return;
    setLoading(true);
    Promise.all([fetchDayData(), fetchWeekData(), fetchMonthData()]).finally(() => {
      setLoading(false);
    });
  }, [selectedElder, fetchDayData, fetchWeekData, fetchMonthData]);

  const changeMonth = (delta: number) => {
    let nextMonth = currentMonth + delta;
    let nextYear = currentYear;
    if (nextMonth < 1) {
      nextMonth = 12;
      nextYear -= 1;
    } else if (nextMonth > 12) {
      nextMonth = 1;
      nextYear += 1;
    }
    setCurrentMonth(nextMonth);
    setCurrentYear(nextYear);
  };

  if (elderLoading || (!selectedElder && loading)) {
    return (
      <div className="flex items-center justify-center min-h-[300px]">
        <div className="w-8 h-8 rounded-full border-2 border-primary border-t-transparent animate-spin" />
      </div>
    );
  }

  if (!selectedElder) {
    return (
      <div className="max-w-xl mx-auto py-12 px-4 text-center">
        <AiraLogo size="lg" className="mx-auto mb-4" />
        <h2 className="text-2xl font-bold text-text-primary mb-2">
          {locale === "hi" ? "AIRA Care में आपका स्वागत है" : "Welcome to AIRA Care"}
        </h2>
        <p className="text-text-secondary text-sm mb-6 max-w-md mx-auto">
          {locale === "hi"
            ? "शुरू करने के लिए, अपने प्रियजन या बुजुर्ग का प्रोफाइल बनाएं।"
            : "To get started, set up a profile for your loved one or older adult."}
        </p>
        <Link href={`/${locale}/elders/new`}>
          <Button size="lg" className="inline-flex items-center gap-2 font-bold">
            <span>+</span>
            <span>{locale === "hi" ? "पहला बुजुर्ग प्रोफाइल जोड़ें" : "Add First Elder Profile"}</span>
          </Button>
        </Link>
      </div>
    );
  }

  const elderName = selectedElder.preferred_name || selectedElder.full_name;

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Header & View Mode Switcher */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-text-primary tracking-tight flex items-center gap-2">
            <Activity className="w-6 h-6 text-primary" />
            <span>{t("title", { name: elderName })}</span>
          </h1>
          <p className="text-sm text-text-secondary mt-0.5">{t("subtitle")}</p>
        </div>

        {/* Day / Week / Month Pill Tabs */}
        <div className="inline-flex w-full sm:w-auto p-1 bg-surface-muted rounded-xl border border-border">
          {[
            { id: "day", label: t("tabDay") },
            { id: "week", label: t("tabWeek") },
            { id: "month", label: t("tabMonth") },
          ].map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setViewMode(tab.id as any)}
              className={`flex-1 sm:flex-none px-4 py-2 sm:py-1.5 rounded-lg text-sm font-semibold transition-all ${
                viewMode === tab.id
                  ? "bg-surface text-primary shadow-xs font-bold"
                  : "text-text-secondary hover:text-text-primary"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Missed Medicine Highlights Callout (STA-4) */}
      {weekSummary && weekSummary.missed_highlights.length > 0 && (
        <div className="p-4 rounded-xl bg-accent-amber/15 border border-accent-amber/30 flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-accent-amber shrink-0 mt-0.5" />
          <div className="text-sm">
            <h3 className="font-bold text-text-primary">{t("missedHighlightsTitle")}</h3>
            <p className="text-text-secondary mt-0.5">
              {t("missedHighlightsDesc", {
                highlights: weekSummary.missed_highlights.join(", "),
              })}
            </p>
          </div>
        </div>
      )}

      {/* VIEW: DAY SUMMARY (STA-1) */}
      {viewMode === "day" && daySummary && (() => {
        const totalScheduled = daySummary.total_scheduled ?? 0;
        const takenCount = daySummary.taken_count ?? 0;
        const adherencePct = daySummary.adherence_pct ?? 100;
        const state = daySummary.state || (totalScheduled > 0 && takenCount >= totalScheduled ? "all_taken" : "in_progress");

        return (
          <div className="space-y-6">
            <Card className="p-4 sm:p-8 bg-surface border border-border shadow-md">
              <div className="flex flex-col md:flex-row items-center justify-between gap-5 sm:gap-6">
                {/* Left: Progress Circle & Adherence */}
                <div className="flex flex-col sm:flex-row items-center gap-4 sm:gap-6 text-center sm:text-left w-full md:w-auto">
                  <div className="relative w-36 h-36 sm:w-40 sm:h-40 shrink-0 flex items-center justify-center">
                    <svg className="w-full h-full transform -rotate-90" viewBox="0 0 120 120">
                      <circle
                        cx="60"
                        cy="60"
                        r="48"
                        className="stroke-surface-muted fill-none stroke-[8]"
                      />
                      <circle
                        cx="60"
                        cy="60"
                        r="48"
                        strokeDasharray={301.6}
                        strokeDashoffset={301.6 - (301.6 * (adherencePct || 0)) / 100}
                        className={`fill-none stroke-[8] transition-all duration-700 ease-out ${
                          state === "all_taken"
                            ? "stroke-accent-green"
                            : state === "has_missed"
                            ? "stroke-accent-amber"
                            : "stroke-primary"
                        }`}
                        strokeLinecap="round"
                      />
                    </svg>
                    <div className="absolute inset-0 flex flex-col items-center justify-center p-2 text-center pointer-events-none select-none overflow-hidden">
                      <span className="text-3xl sm:text-4xl font-extrabold text-text-primary tracking-tight leading-none">
                        {adherencePct}%
                      </span>
                      <span
                        className="text-[10px] sm:text-xs font-semibold text-text-secondary tracking-normal mt-1.5 px-2 truncate max-w-[100px] leading-tight block"
                        title={t("adherenceLabel")}
                      >
                        {t("adherenceLabel")}
                      </span>
                    </div>
                  </div>

                  <div className="min-w-0 flex-1">
                    <h2 className="text-xl sm:text-2xl font-bold text-text-primary">
                      {state === "all_taken" && t("allDoneTitle")}
                      {state === "in_progress" && t("inProgressTitle")}
                      {state === "has_missed" && t("hasMissedTitle")}
                      {state === "no_doses" && t("noDosesScheduledToday")}
                    </h2>
                    <p className="text-sm text-text-secondary mt-1">
                      {t("takenDosesCount", {
                        taken: takenCount,
                        total: totalScheduled,
                      })}
                    </p>
                  </div>
                </div>

                {/* Right: State Pill / Celebration */}
                <div className="text-center md:text-right shrink-0">
                  {state === "all_taken" && (
                    <div className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-accent-green/15 text-accent-green font-bold text-sm border border-accent-green/30">
                      <Sparkles className="w-4 h-4" />
                      <span>{t("allDoneBadge")}</span>
                    </div>
                  )}
                  {state === "has_missed" && (
                    <div className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-accent-crimson/15 text-accent-crimson font-bold text-sm border border-accent-crimson/30">
                      <AlertTriangle className="w-4 h-4" />
                      <span>{t("missedDosesCount", { count: daySummary.missed_count || 0 })}</span>
                    </div>
                  )}
                  {state === "in_progress" && (
                    <div className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-primary-soft text-primary font-bold text-sm">
                      <Clock className="w-4 h-4" />
                      <span>
                        {t("remainingDosesCount", {
                          count: Math.max(0, totalScheduled - takenCount),
                        })}
                      </span>
                    </div>
                  )}
                </div>
              </div>

              {/* Privacy notice banner (Section 1.2) */}
              <div className="mt-6 pt-4 border-t border-border flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs text-text-secondary">
                <span>{t("privacyHonestStatusNotice")}</span>
                <Link href={`/${locale}/medicines`} className="text-primary font-semibold hover:underline">
                  {t("manageMedicinesLink")} &rarr;
                </Link>
              </div>
            </Card>
          </div>
        );
      })()}

      {/* VIEW: WEEK SUMMARY (STA-2) */}
      {viewMode === "week" && weekSummary && (
        <div className="space-y-6">
          <Card className="p-4 sm:p-6 bg-surface border border-border shadow-sm">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-6">
              <div>
                <span className="text-xs font-bold uppercase tracking-wider text-text-secondary">
                  {t("weekOverviewTitle")}
                </span>
                <h2 className="text-xl font-bold text-text-primary mt-0.5">
                  {t("weekOverallAdherence", { pct: weekSummary.overall_adherence_pct ?? 100 })}
                </h2>
              </div>
              <div className="text-left sm:text-right text-xs text-text-secondary">
                <span>
                  {weekSummary.total_taken ?? 0} / {weekSummary.total_scheduled ?? 0} {t("dosesTakenTotal")}
                </span>
              </div>
            </div>

            {/* 7 Daily Chips */}
            <div className="grid grid-cols-7 gap-1 sm:gap-2">
              {(weekSummary.days || []).map((day) => {
                const dayDate = new Date(day.date + "T00:00:00");
                const dayName = dayDate.toLocaleDateString(locale, { weekday: "short" });
                const dayNum = dayDate.getDate();

                let chipColor = "bg-surface-muted text-text-secondary border-border";
                let dotColor = "bg-text-secondary/40";

                if (day.total_scheduled > 0) {
                  if (day.state === "all_taken") {
                    chipColor = "bg-accent-green/10 border-accent-green/30 text-accent-green";
                    dotColor = "bg-accent-green";
                  } else if (day.state === "has_missed") {
                    chipColor = "bg-accent-crimson/10 border-accent-crimson/30 text-accent-crimson";
                    dotColor = "bg-accent-crimson";
                  } else {
                    chipColor = "bg-primary-soft border-primary/20 text-primary";
                    dotColor = "bg-primary";
                  }
                }

                return (
                  <div
                    key={day.date}
                    className={`p-1 sm:p-2.5 rounded-xl border flex flex-col items-center justify-center text-center transition-all min-w-0 overflow-hidden ${chipColor}`}
                  >
                    <span className="text-[10px] sm:text-xs font-semibold truncate w-full">{dayName}</span>
                    <span className="text-sm sm:text-lg font-bold my-0.5 sm:my-1">{dayNum}</span>
                    <div className="flex items-center justify-center gap-0.5 sm:gap-1 w-full">
                      <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${dotColor}`} />
                      <span className="text-[9px] sm:text-xs font-bold truncate leading-none">
                        {day.total_scheduled > 0 ? `${day.adherence_pct}%` : "—"}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          </Card>
        </div>
      )}

      {/* VIEW: MONTH CALENDAR (STA-3) */}
      {viewMode === "month" && monthSummary && (
        <div className="space-y-6">
          <Card className="p-4 sm:p-6 bg-surface border border-border shadow-sm">
            {/* Month Header & Controls */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-6">
              <div>
                <span className="text-xs font-bold uppercase tracking-wider text-text-secondary">
                  {t("monthOverviewTitle")}
                </span>
                <h2 className="text-xl font-bold text-text-primary mt-0.5">
                  {new Date(currentYear, currentMonth - 1).toLocaleDateString(locale, {
                    month: "long",
                    year: "numeric",
                  })}
                </h2>
              </div>

              <div className="flex items-center justify-between sm:justify-end gap-2">
                <button
                  type="button"
                  onClick={() => changeMonth(-1)}
                  className="p-2 rounded-lg border border-border hover:bg-surface-muted transition-colors"
                  aria-label="Previous month"
                >
                  <ChevronLeft className="w-4 h-4 text-text-secondary" />
                </button>
                <span className="text-sm font-bold text-primary px-2">
                  {monthSummary.overall_adherence_pct}%
                </span>
                <button
                  type="button"
                  onClick={() => changeMonth(1)}
                  className="p-2 rounded-lg border border-border hover:bg-surface-muted transition-colors"
                  aria-label="Next month"
                >
                  <ChevronRight className="w-4 h-4 text-text-secondary" />
                </button>
              </div>
            </div>

            {/* Calendar Grid */}
            <div className="grid grid-cols-7 gap-1 sm:gap-2">
              {(monthSummary.days || []).map((day) => {
                const dayNum = parseInt(day.date.split("-")[2], 10);
                const hasDoses = day.total_scheduled > 0;

                return (
                  <div
                    key={day.date}
                    className={`h-12 sm:h-16 p-1 sm:p-2 rounded-xl border flex flex-col justify-between transition-all min-w-0 overflow-hidden ${
                      hasDoses
                        ? day.state === "all_taken"
                          ? "bg-accent-green/10 border-accent-green/30"
                          : day.state === "has_missed"
                          ? "bg-accent-crimson/10 border-accent-crimson/30"
                          : "bg-surface-muted border-border"
                        : "bg-surface border-border/50 opacity-50"
                    }`}
                  >
                    <span className="text-[11px] sm:text-xs font-bold text-text-primary">{dayNum}</span>
                    {hasDoses && (
                      <div className="text-right overflow-hidden">
                        <span
                          className={`text-[9px] sm:text-2xs font-bold truncate block ${
                            day.state === "all_taken"
                              ? "text-accent-green"
                              : day.state === "has_missed"
                              ? "text-accent-crimson"
                              : "text-text-secondary"
                          }`}
                        >
                          {day.adherence_pct}%
                        </span>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}
