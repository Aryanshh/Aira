"use client";

import * as React from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import {
  AlertCircle,
  ArrowLeft,
  Calendar,
  Clock,
  Info,
  Pill,
  Plus,
  Trash2,
} from "lucide-react";

import { useElder } from "@/components/elder-context";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

export default function EditMedicinePage() {
  const t = useTranslations("medicines");
  const tCommon = useTranslations("common");
  const locale = useLocale();
  const router = useRouter();
  const params = useParams();
  const medicineId = params.id as string;
  const { selectedElder } = useElder();

  const [loading, setLoading] = React.useState(true);
  const [submitting, setSubmitting] = React.useState(false);
  const [error, setError] = React.useState("");

  // Form states
  const [name, setName] = React.useState("");
  const [strength, setStrength] = React.useState("");
  const [doseAmount, setDoseAmount] = React.useState("1.0");
  const [doseUnit, setDoseUnit] = React.useState("tablet");
  const [instructions, setInstructions] = React.useState("");
  const [timesOfDay, setTimesOfDay] = React.useState<string[]>(["08:00"]);
  const [refillThreshold, setRefillThreshold] = React.useState("5");

  // Effective from (MED-6: default tomorrow)
  const tomorrowStr = React.useMemo(() => {
    const d = new Date();
    d.setDate(d.getDate() + 1);
    return d.toISOString().split("T")[0];
  }, []);
  const [effectiveFrom, setEffectiveFrom] = React.useState(tomorrowStr);

  React.useEffect(() => {
    if (!selectedElder || !medicineId) return;

    const fetchMed = async () => {
      setLoading(true);
      try {
        const res = await fetch(`/api/v1/elders/${selectedElder.id}/medicines/${medicineId}`);
        if (res.ok) {
          const data = await res.json();
          setName(data.name || "");
          setStrength(data.strength || "");
          setDoseAmount(String(data.dose_amount || "1.0"));
          setDoseUnit(data.dose_unit || "tablet");
          setInstructions(data.instructions || "");
          setRefillThreshold(String(data.refill_threshold_days || "5"));
          if (data.active_schedule?.times_of_day) {
            setTimesOfDay(data.active_schedule.times_of_day);
          }
        } else {
          setError(t("fetchFailed"));
        }
      } catch {
        setError(t("fetchFailed"));
      } finally {
        setLoading(false);
      }
    };

    fetchMed();
  }, [selectedElder, medicineId, t]);

  const addTimeSlot = () => {
    setTimesOfDay([...timesOfDay, "20:00"]);
  };

  const updateTimeSlot = (index: number, val: string) => {
    const updated = [...timesOfDay];
    updated[index] = val;
    setTimesOfDay(updated);
  };

  const removeTimeSlot = (index: number) => {
    if (timesOfDay.length <= 1) return;
    setTimesOfDay(timesOfDay.filter((_, i) => i !== index));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedElder) return;
    setSubmitting(true);
    setError("");

    try {
      const payload = {
        name: name.trim(),
        strength: strength.trim() || null,
        dose_amount: parseFloat(doseAmount) || 1.0,
        dose_unit: doseUnit.trim() || "tablet",
        instructions: instructions.trim() || null,
        times_of_day: timesOfDay,
        refill_threshold_days: parseInt(refillThreshold, 10) || 5,
        effective_from: effectiveFrom,
      };

      const res = await fetch(
        `/api/v1/elders/${selectedElder.id}/medicines/${medicineId}`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        }
      );

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        setError(err.detail || t("updateFailed"));
        setSubmitting(false);
        return;
      }

      router.push(`/${locale}/medicines`);
    } catch {
      setError(t("updateFailed"));
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[300px]">
        <div className="w-8 h-8 rounded-full border-2 border-primary border-t-transparent animate-spin" />
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto py-4 sm:py-6 space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Link
          href={`/${locale}/medicines`}
          className="p-2 rounded-lg text-text-secondary hover:text-text-primary hover:bg-surface-muted transition-colors"
        >
          <ArrowLeft className="w-5 h-5" />
        </Link>
        <div>
          <h1 className="text-2xl font-bold text-text-primary tracking-tight">
            {t("editMedicineTitle", { name })}
          </h1>
          <p className="text-sm text-text-secondary mt-0.5">{t("editMedicineSubtitle")}</p>
        </div>
      </div>

      {/* MED-6 Notice on Schedule Versioning */}
      <div className="p-4 rounded-xl bg-primary-soft/40 border border-primary/20 text-xs text-text-primary flex items-start gap-3">
        <Info className="w-4 h-4 text-primary shrink-0 mt-0.5" />
        <div>
          <p className="font-semibold">{t("scheduleVersioningNoteTitle")}</p>
          <p className="text-text-secondary mt-0.5">{t("scheduleVersioningNoteDesc")}</p>
        </div>
      </div>

      {error && (
        <div className="p-3.5 rounded-xl bg-accent-crimson/10 border border-accent-crimson/20 text-accent-crimson text-sm font-medium">
          {error}
        </div>
      )}

      <Card className="p-6 sm:p-8 bg-surface border border-border shadow-sm">
        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Effective From Date (MED-6) */}
          <div className="p-4 rounded-xl bg-surface-muted border border-border space-y-2">
            <Input
              label={t("effectiveFromLabel")}
              type="date"
              value={effectiveFrom}
              onChange={(e) => setEffectiveFrom(e.target.value)}
              required
            />
            <p className="text-xs text-text-secondary">
              {t("effectiveFromHelp")}
            </p>
          </div>

          {/* Name & Strength */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Input
              label={t("medicineNameLabel")}
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
            />
            <Input
              label={t("strengthLabel")}
              value={strength}
              onChange={(e) => setStrength(e.target.value)}
            />
          </div>

          {/* Dose Amount & Unit */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 sm:gap-4">
            <Input
              label={t("doseAmountLabel")}
              type="number"
              step="0.1"
              min="0.1"
              value={doseAmount}
              onChange={(e) => setDoseAmount(e.target.value)}
              required
            />
            <Input
              label={t("doseUnitLabel")}
              value={doseUnit}
              onChange={(e) => setDoseUnit(e.target.value)}
              required
            />
          </div>

          {/* Instructions */}
          <Input
            label={t("instructionsLabel")}
            value={instructions}
            onChange={(e) => setInstructions(e.target.value)}
          />

          {/* Times of Day */}
          <div className="space-y-2.5 pt-2 border-t border-border">
            <label className="text-xs font-semibold text-text-secondary block">
              {t("timesOfDayLabel")}
            </label>
            <div className="flex flex-wrap items-center gap-2">
              {timesOfDay.map((tm, idx) => (
                <div key={idx} className="flex items-center gap-1 bg-surface-muted p-1.5 rounded-xl border border-border">
                  <input
                    type="time"
                    value={tm}
                    onChange={(e) => updateTimeSlot(idx, e.target.value)}
                    className="bg-transparent border-none text-sm font-bold text-text-primary focus:outline-hidden"
                  />
                  {timesOfDay.length > 1 && (
                    <button
                      type="button"
                      onClick={() => removeTimeSlot(idx)}
                      className="p-1 text-text-secondary hover:text-accent-crimson rounded-md transition-colors"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  )}
                </div>
              ))}
              <button
                type="button"
                onClick={addTimeSlot}
                className="inline-flex items-center gap-1 px-3 py-2 text-xs font-semibold rounded-xl bg-primary-soft text-primary hover:bg-primary/20 transition-colors"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>{t("addTimeButton")}</span>
              </button>
            </div>
          </div>

          {/* Refill Threshold */}
          <div className="pt-2 border-t border-border w-48">
            <Input
              label={t("refillThresholdDaysLabel")}
              type="number"
              min="1"
              max="60"
              value={refillThreshold}
              onChange={(e) => setRefillThreshold(e.target.value)}
              required
            />
          </div>

          {/* Actions */}
          <div className="pt-4 flex items-center justify-end gap-3 border-t border-border">
            <Link href={`/${locale}/medicines`}>
              <Button type="button" variant="ghost">
                {tCommon("cancel")}
              </Button>
            </Link>
            <Button type="submit" isLoading={submitting}>
              {tCommon("save")}
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
}
