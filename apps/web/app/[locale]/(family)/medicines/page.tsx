"use client";

import * as React from "react";
import Link from "next/link";
import { useLocale, useTranslations } from "next-intl";
import {
  AlertCircle,
  Bell,
  Calendar,
  Clock,
  Edit2,
  Package,
  Pause,
  Pill,
  Play,
  Plus,
  Square,
  StopCircle,
  Volume2,
} from "lucide-react";

import { useElder } from "@/components/elder-context";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

interface Schedule {
  frequency: string;
  interval_n: number;
  days_of_week?: number[] | null;
  days_of_month?: number[] | null;
  times_of_day: string[];
  start_date: string;
  end_date?: string | null;
  effective_from: string;
  effective_to?: string | null;
}

interface Medicine {
  id: string;
  elder_id: string;
  name: string;
  strength?: string | null;
  form?: string | null;
  dose_amount: number;
  dose_unit: string;
  instructions?: string | null;
  color_tag?: string | null;
  as_needed: boolean;
  status: "active" | "paused" | "ended";
  stock_quantity: number;
  refill_threshold_days: number;
  days_remaining?: number | null;
  active_schedule?: Schedule | null;
}

export default function MedicinesListPage() {
  const t = useTranslations("medicines");
  const tCommon = useTranslations("common");
  const locale = useLocale();
  const { selectedElder, isLoading: elderLoading } = useElder();

  const [medicines, setMedicines] = React.useState<Medicine[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState("");

  const fetchMedicines = React.useCallback(async () => {
    if (!selectedElder) return;
    setLoading(true);
    setError("");

    try {
      const res = await fetch(`/api/v1/elders/${selectedElder.id}/medicines`);
      if (res.ok) {
        const data: Medicine[] = await res.json();
        setMedicines(data);
      } else {
        setError(t("fetchFailed"));
      }
    } catch {
      setError(t("fetchFailed"));
    } finally {
      setLoading(false);
    }
  }, [selectedElder, t]);

  React.useEffect(() => {
    fetchMedicines();
  }, [fetchMedicines]);

  const handlePauseResume = async (med: Medicine) => {
    if (!selectedElder) return;
    const action = med.status === "active" ? "pause" : "resume";
    try {
      const res = await fetch(
        `/api/v1/elders/${selectedElder.id}/medicines/${med.id}/${action}`,
        { method: "POST" }
      );
      if (res.ok) {
        fetchMedicines();
      }
    } catch {
      // Ignored
    }
  };

  const handleTestAlarm = (med: Medicine) => {
    const scheduledTime = med.active_schedule?.times_of_day?.[0] || "08:00";
    window.dispatchEvent(
      new CustomEvent("aira:trigger-medicine-alarm", {
        detail: {
          id: med.id,
          medicine_name: med.name,
          dose_label: `${med.dose_amount} ${med.dose_unit}`,
          instructions: med.instructions,
          scheduled_time: scheduledTime,
          isTest: true,
        },
      })
    );
  };

  const handleEndMedicine = async (medId: string) => {
    if (!selectedElder) return;
    if (!confirm(t("confirmEndMedicine"))) return;

    try {
      const res = await fetch(
        `/api/v1/elders/${selectedElder.id}/medicines/${medId}/end`,
        { method: "POST" }
      );
      if (res.ok) {
        fetchMedicines();
      }
    } catch {
      // Ignored
    }
  };

  const formatScheduleText = (med: Medicine): string => {
    if (med.as_needed) return t("asNeededLabel");
    if (!med.active_schedule) return t("noSchedule");

    const times = (med.active_schedule.times_of_day || []).join(", ") || "08:00";
    if (med.active_schedule.frequency === "daily") {
      return t("scheduleDaily", { times });
    }
    if (med.active_schedule.frequency === "weekly") {
      const daysMap: Record<number, string> = {
        1: t("mon"),
        2: t("tue"),
        3: t("wed"),
        4: t("thu"),
        5: t("fri"),
        6: t("sat"),
        7: t("sun"),
      };
      const days = (med.active_schedule.days_of_week || [])
        .map((d) => daysMap[d])
        .join(", ");
      return t("scheduleWeekly", { days, times });
    }
    if (med.active_schedule.frequency === "every_n_days") {
      return t("scheduleEveryNDays", { n: med.active_schedule.interval_n, times });
    }
    if (med.active_schedule.frequency === "monthly") {
      const dom = (med.active_schedule.days_of_month || []).join(", ");
      return t("scheduleMonthly", { days: dom, times });
    }
    return times;
  };

  if (elderLoading || (selectedElder && loading)) {
    return (
      <div className="flex items-center justify-center min-h-[300px]">
        <div className="w-8 h-8 rounded-full border-2 border-primary border-t-transparent animate-spin" />
      </div>
    );
  }

  if (!selectedElder) {
    return (
      <div className="max-w-xl mx-auto py-12 px-4 text-center">
        <h2 className="text-xl font-bold text-text-primary mb-2">
          {locale === "hi" ? "कोई बुजुर्ग चुना नहीं गया" : "No Elder Profile Selected"}
        </h2>
        <p className="text-text-secondary text-sm mb-6">
          {locale === "hi"
            ? "दवाएं प्रबंधित करने के लिए पहले एक बुजुर्ग का प्रोफाइल बनाएं।"
            : "Please create an elder profile to manage medicines."}
        </p>
        <Link href={`/${locale}/elders/new`}>
          <Button className="font-bold">
            {locale === "hi" ? "+ बुजुर्ग प्रोफाइल जोड़ें" : "+ Add Elder Profile"}
          </Button>
        </Link>
      </div>
    );
  }

  const canManage = selectedElder.is_owner || selectedElder.can_manage_medicines;

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Disclaimer Notice (MED-9) */}
      <div className="p-3.5 rounded-xl bg-surface-muted border border-border text-xs text-text-secondary flex items-start gap-2.5">
        <AlertCircle className="w-4 h-4 text-text-secondary shrink-0 mt-0.5" />
        <span>{tCommon("disclaimer")}</span>
      </div>

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-text-primary tracking-tight flex items-center gap-2">
            <Pill className="w-6 h-6 text-primary" />
            <span>{t("title", { name: selectedElder.preferred_name || selectedElder.full_name })}</span>
          </h1>
          <p className="text-sm text-text-secondary mt-1">{t("subtitle")}</p>
        </div>

        {canManage && (
          <Link href={`/${locale}/medicines/new`}>
            <Button className="flex items-center gap-2">
              <Plus className="w-4 h-4" />
              <span>{t("addMedicineButton")}</span>
            </Button>
          </Link>
        )}
      </div>

      {error && (
        <div className="p-3.5 rounded-xl bg-accent-crimson/10 border border-accent-crimson/20 text-accent-crimson text-sm font-medium">
          {error}
        </div>
      )}

      {/* Empty State */}
      {!loading && medicines.length === 0 && (
        <Card className="p-12 text-center bg-surface border border-dashed border-border rounded-2xl">
          <div className="w-12 h-12 rounded-full bg-primary-soft text-primary flex items-center justify-center mx-auto mb-3">
            <Pill className="w-6 h-6" />
          </div>
          <h3 className="text-lg font-bold text-text-primary">{t("noMedicinesTitle")}</h3>
          <p className="text-sm text-text-secondary mt-1 max-w-sm mx-auto">
            {t("noMedicinesSubtitle")}
          </p>
          {canManage && (
            <div className="mt-5">
              <Link href={`/${locale}/medicines/new`}>
                <Button>{t("addFirstMedicineButton")}</Button>
              </Link>
            </div>
          )}
        </Card>
      )}

      {/* Medicines Cards List */}
      <div className="space-y-4">
        {medicines.map((med) => {
          const isLowStock =
            med.days_remaining !== null &&
            med.days_remaining !== undefined &&
            med.days_remaining <= med.refill_threshold_days;

          return (
            <Card
              key={med.id}
              className={`p-5 bg-surface border transition-all ${
                med.status === "ended"
                  ? "opacity-60 border-border"
                  : med.status === "paused"
                  ? "border-accent-amber/40 bg-accent-amber/5"
                  : "border-border shadow-2xs hover:border-border/80"
              }`}
            >
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                {/* Medicine info */}
                <div className="space-y-1.5 flex-1">
                  <div className="flex items-center gap-2.5 flex-wrap">
                    <span className="text-lg font-bold text-text-primary">{med.name}</span>
                    {med.strength && (
                      <span className="px-2 py-0.5 rounded-md text-xs font-semibold bg-surface-muted text-text-secondary border border-border">
                        {med.strength}
                      </span>
                    )}

                    {/* Status Badge */}
                    {med.status === "paused" && (
                      <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-accent-amber/20 text-accent-amber border border-accent-amber/40">
                        {t("statusPaused")}
                      </span>
                    )}
                    {med.status === "ended" && (
                      <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-surface-muted text-text-secondary border border-border">
                        {t("statusEnded")}
                      </span>
                    )}

                    {/* Low Stock Badge (STK-4) */}
                    {isLowStock && med.status === "active" && (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-accent-crimson/15 text-accent-crimson border border-accent-crimson/30">
                        <AlertCircle className="w-3 h-3" />
                        <span>{t("lowStockBadge", { days: med.days_remaining })}</span>
                      </span>
                    )}
                  </div>

                  <p className="text-sm text-text-secondary flex items-center gap-2">
                    <Clock className="w-4 h-4 text-primary shrink-0" />
                    <span>{formatScheduleText(med)}</span>
                  </p>

                  {/* Scheduled Alarms Pill Badges */}
                  {med.status === "active" && !med.as_needed && med.active_schedule?.times_of_day?.length ? (
                    <div className="flex items-center gap-1.5 flex-wrap pt-1">
                      <span className="text-[11px] font-bold text-text-secondary flex items-center gap-1">
                        <Bell className="w-3.5 h-3.5 text-primary" />
                        <span>{t("remindersLabel")}:</span>
                      </span>
                      {med.active_schedule.times_of_day.map((time) => (
                        <span
                          key={time}
                          className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-bold bg-primary-soft text-primary border border-primary/20"
                        >
                          <Clock className="w-2.5 h-2.5" />
                          <span>{time}</span>
                          <span className="text-[9px] uppercase tracking-wider text-primary/80 font-black">• {t("alarmActiveBadge")}</span>
                        </span>
                      ))}
                    </div>
                  ) : null}

                  {med.instructions && (
                    <p className="text-xs text-text-secondary italic">
                      "{med.instructions}"
                    </p>
                  )}
                </div>

                {/* Stock Details & Actions */}
                <div className="flex items-center justify-between sm:justify-end gap-4 text-left sm:text-right pt-3 border-t border-border/70 sm:border-t-0 sm:pt-0 sm:border-l sm:border-border sm:pl-5">
                  <Link
                    href={`/${locale}/medicines/${med.id}/stock`}
                    className="text-left sm:text-right group hover:opacity-80 transition-opacity"
                    title={t("viewStockHistoryTooltip")}
                  >
                    <span className="text-xs text-text-secondary block font-medium group-hover:text-primary">
                      {t("stockRemaining")}
                    </span>
                    <span className="text-sm font-bold text-text-primary group-hover:text-primary">
                      {med.stock_quantity} {med.dose_unit}
                    </span>
                    {!med.as_needed && med.days_remaining !== null && (
                      <span className="text-xs text-text-secondary block">
                        (~{med.days_remaining} {t("days")})
                      </span>
                    )}
                  </Link>

                  {/* Actions for Authorized Users */}
                  {canManage && med.status !== "ended" && (
                    <div className="flex items-center gap-1">
                      <Link
                        href={`/${locale}/medicines/${med.id}/edit`}
                        className="p-2 rounded-lg text-text-secondary hover:text-text-primary hover:bg-surface-muted transition-colors"
                        title={t("editTooltip")}
                      >
                        <Edit2 className="w-4 h-4" />
                      </Link>

                      <button
                        type="button"
                        onClick={() => handlePauseResume(med)}
                        className="p-2 rounded-lg text-text-secondary hover:text-text-primary hover:bg-surface-muted transition-colors"
                        title={med.status === "active" ? t("pauseTooltip") : t("resumeTooltip")}
                      >
                        {med.status === "active" ? (
                          <Pause className="w-4 h-4" />
                        ) : (
                          <Play className="w-4 h-4 text-accent-green" />
                        )}
                      </button>

                      <button
                        type="button"
                        onClick={() => handleEndMedicine(med.id)}
                        className="p-2 rounded-lg text-text-secondary hover:text-accent-crimson hover:bg-accent-crimson/10 transition-colors"
                        title={t("endTooltip")}
                      >
                        <StopCircle className="w-4 h-4" />
                      </button>

                      {/* Test Alarm Button */}
                      <button
                        type="button"
                        onClick={() => handleTestAlarm(med)}
                        className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-bold bg-primary-soft text-primary hover:bg-primary/20 transition-all active:scale-95 border border-primary/25 ml-1"
                        title={t("testAlarmButton")}
                      >
                        <Volume2 className="w-3.5 h-3.5 animate-pulse text-primary shrink-0" />
                        <span className="hidden sm:inline">{t("testAlarmButton")}</span>
                      </button>
                    </div>
                  )}
                </div>
              </div>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
