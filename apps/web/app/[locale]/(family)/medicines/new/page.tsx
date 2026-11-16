"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import {
  AlertCircle,
  ArrowLeft,
  Calendar,
  Clock,
  Package,
  Pill,
  Plus,
  Trash2,
} from "lucide-react";

import { useElder } from "@/components/elder-context";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

export default function NewMedicinePage() {
  const t = useTranslations("medicines");
  const tCommon = useTranslations("common");
  const locale = useLocale();
  const router = useRouter();
  const { selectedElder } = useElder();

  // Basic fields
  const [name, setName] = React.useState("");
  const [strength, setStrength] = React.useState("");
  const [form, setForm] = React.useState("tablet");
  const [doseAmount, setDoseAmount] = React.useState("1.0");
  const [doseUnit, setDoseUnit] = React.useState("tablet");
  const [instructions, setInstructions] = React.useState("");
  const [asNeeded, setAsNeeded] = React.useState(false);

  // Recurrence
  const [frequency, setFrequency] = React.useState<"daily" | "weekly" | "every_n_days" | "monthly">("daily");
  const [timesOfDay, setTimesOfDay] = React.useState<string[]>(["08:00"]);
  const [daysOfWeek, setDaysOfWeek] = React.useState<number[]>([1, 2, 3, 4, 5]); // Mon-Fri
  const [intervalN, setIntervalN] = React.useState(2);
  const [daysOfMonth, setDaysOfMonth] = React.useState<number[]>([1]);
  const [startDate, setStartDate] = React.useState(new Date().toISOString().split("T")[0]);
  const [endDate, setEndDate] = React.useState("");

  // Stock
  const [stockQuantity, setStockQuantity] = React.useState("30.0");
  const [refillThreshold, setRefillThreshold] = React.useState("5");

  // Warnings & Loading
  const [dupWarning, setDupWarning] = React.useState<string | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState("");

  // Live duplicate check (MED-8)
  React.useEffect(() => {
    if (!selectedElder || !name.trim()) {
      setDupWarning(null);
      return;
    }

    const timer = setTimeout(async () => {
      try {
        const query = new URLSearchParams({
          name: name.trim(),
          ...(strength.trim() ? { strength: strength.trim() } : {}),
        });
        const res = await fetch(
          `/api/v1/elders/${selectedElder.id}/medicines/check-duplicate?${query.toString()}`
        );
        if (res.ok) {
          const data = await res.json();
          setDupWarning(data.is_duplicate ? data.warning : null);
        }
      } catch {
        // Ignored
      }
    }, 400);

    return () => clearTimeout(timer);
  }, [name, strength, selectedElder]);

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

  const toggleDayOfWeek = (day: number) => {
    if (daysOfWeek.includes(day)) {
      if (daysOfWeek.length > 1) {
        setDaysOfWeek(daysOfWeek.filter((d) => d !== day));
      }
    } else {
      setDaysOfWeek([...daysOfWeek, day].sort());
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedElder) return;
    setError("");

    if (!name.trim()) {
      setError(t("nameRequired"));
      return;
    }

    setLoading(true);

    try {
      const payload = {
        name: name.trim(),
        strength: strength.trim() || null,
        form,
        dose_amount: parseFloat(doseAmount) || 1.0,
        dose_unit: doseUnit.trim() || "tablet",
        instructions: instructions.trim() || null,
        as_needed: asNeeded,
        frequency: asNeeded ? null : frequency,
        interval_n: frequency === "every_n_days" ? Number(intervalN) : 1,
        days_of_week: frequency === "weekly" ? daysOfWeek : null,
        days_of_month: frequency === "monthly" ? daysOfMonth : null,
        times_of_day: asNeeded ? ["08:00"] : timesOfDay,
        start_date: startDate,
        end_date: endDate || null,
        stock_quantity: parseFloat(stockQuantity) || 0.0,
        refill_threshold_days: parseInt(refillThreshold, 10) || 5,
      };

      const res = await fetch(`/api/v1/elders/${selectedElder.id}/medicines`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        setError(err.detail || t("createFailed"));
        setLoading(false);
        return;
      }

      router.push(`/${locale}/medicines`);
    } catch {
      setError(t("createFailed"));
      setLoading(false);
    }
  };

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
            {t("addNewMedicineTitle")}
          </h1>
          <p className="text-sm text-text-secondary mt-0.5">
            {t("addNewMedicineSubtitle", { name: selectedElder?.preferred_name || selectedElder?.full_name })}
          </p>
        </div>
      </div>

      {/* Disclaimer (MED-9) */}
      <div className="p-3.5 rounded-xl bg-surface-muted border border-border text-xs text-text-secondary flex items-start gap-2.5">
        <AlertCircle className="w-4 h-4 text-text-secondary shrink-0 mt-0.5" />
        <span>{tCommon("disclaimer")}</span>
      </div>

      {/* Duplicate Warning (MED-8) */}
      {dupWarning && (
        <div className="p-3.5 rounded-xl bg-accent-amber/15 border border-accent-amber/30 text-accent-amber text-sm font-medium flex items-start gap-2.5">
          <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
          <span>{dupWarning}</span>
        </div>
      )}

      {error && (
        <div className="p-3.5 rounded-xl bg-accent-crimson/10 border border-accent-crimson/20 text-accent-crimson text-sm font-medium">
          {error}
        </div>
      )}

      <Card className="p-6 sm:p-8 bg-surface border border-border shadow-sm">
        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Name & Strength */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Input
              label={t("medicineNameLabel")}
              placeholder={t("medicineNamePlaceholder")}
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
            />
            <Input
              label={t("strengthLabel")}
              placeholder="e.g. 500 mg, 10 ml"
              value={strength}
              onChange={(e) => setStrength(e.target.value)}
            />
          </div>

          {/* Form & Dose Amount & Unit */}
          <div className="grid grid-cols-3 gap-4">
            <div className="space-y-1.5">
              <label className="text-sm font-medium text-text-primary">{t("formLabel")}</label>
              <select
                value={form}
                onChange={(e) => setForm(e.target.value)}
                className="w-full px-4 py-2.5 rounded-xl border border-border bg-surface text-text-primary text-sm font-medium"
              >
                <option value="tablet">{t("formTablet")}</option>
                <option value="capsule">{t("formCapsule")}</option>
                <option value="syrup">{t("formSyrup")}</option>
                <option value="drops">{t("formDrops")}</option>
                <option value="injection">{t("formInjection")}</option>
                <option value="other">{t("formOther")}</option>
              </select>
            </div>

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
              placeholder="tablet"
              value={doseUnit}
              onChange={(e) => setDoseUnit(e.target.value)}
              required
            />
          </div>

          {/* Instructions */}
          <Input
            label={t("instructionsLabel")}
            placeholder={t("instructionsPlaceholder")}
            value={instructions}
            onChange={(e) => setInstructions(e.target.value)}
          />

          {/* As-Needed Toggle */}
          <div className="pt-2 border-t border-border">
            <label className="flex items-center gap-3 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={asNeeded}
                onChange={(e) => setAsNeeded(e.target.checked)}
                className="w-4 h-4 text-primary rounded border-border focus:ring-primary/20"
              />
              <div>
                <span className="text-sm font-medium text-text-primary block">
                  {t("asNeededCheckboxLabel")}
                </span>
                <span className="text-xs text-text-secondary">
                  {t("asNeededCheckboxHelp")}
                </span>
              </div>
            </label>
          </div>

          {/* Recurrence Configuration (if NOT as-needed) */}
          {!asNeeded && (
            <div className="space-y-5 pt-4 border-t border-border">
              <h3 className="text-sm font-bold uppercase tracking-wider text-text-secondary">
                {t("scheduleSectionTitle")}
              </h3>

              {/* Frequency Selector */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
                {[
                  { id: "daily", label: t("freqDaily") },
                  { id: "weekly", label: t("freqWeekly") },
                  { id: "every_n_days", label: t("freqEveryNDays") },
                  { id: "monthly", label: t("freqMonthly") },
                ].map((f) => (
                  <button
                    key={f.id}
                    type="button"
                    onClick={() => setFrequency(f.id as any)}
                    className={`py-2 px-3 rounded-xl border text-sm font-medium transition-all ${
                      frequency === f.id
                        ? "border-primary bg-primary-soft text-primary font-bold shadow-2xs"
                        : "border-border bg-surface text-text-secondary hover:border-primary/40 hover:text-text-primary"
                    }`}
                  >
                    {f.label}
                  </button>
                ))}
              </div>

              {/* Weekly Day Picker */}
              {frequency === "weekly" && (
                <div className="space-y-2">
                  <label className="text-xs font-semibold text-text-secondary">
                    {t("selectDaysOfWeek")}
                  </label>
                  <div className="flex gap-2 flex-wrap">
                    {[
                      { num: 1, label: t("mon") },
                      { num: 2, label: t("tue") },
                      { num: 3, label: t("wed") },
                      { num: 4, label: t("thu") },
                      { num: 5, label: t("fri") },
                      { num: 6, label: t("sat") },
                      { num: 7, label: t("sun") },
                    ].map((d) => (
                      <button
                        key={d.num}
                        type="button"
                        onClick={() => toggleDayOfWeek(d.num)}
                        className={`w-10 h-10 rounded-xl text-sm font-bold flex items-center justify-center shrink-0 transition-all ${
                          daysOfWeek.includes(d.num)
                            ? "bg-primary text-white"
                            : "bg-surface-muted text-text-secondary hover:bg-surface-muted/80"
                        }`}
                      >
                        {d.label.slice(0, 2)}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* Every N Days */}
              {frequency === "every_n_days" && (
                <div className="w-48">
                  <Input
                    label={t("intervalDaysLabel")}
                    type="number"
                    min="2"
                    max="90"
                    value={intervalN}
                    onChange={(e) => setIntervalN(parseInt(e.target.value, 10) || 2)}
                    required
                  />
                </div>
              )}

              {/* Times of Day */}
              <div className="space-y-2.5">
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

              {/* Start & End Dates */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <Input
                  label={t("startDateLabel")}
                  type="date"
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                  required
                />
                <Input
                  label={t("endDateLabel")}
                  type="date"
                  value={endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                />
              </div>
            </div>
          )}

          {/* Stock Tracking */}
          <div className="space-y-4 pt-4 border-t border-border">
            <h3 className="text-sm font-bold uppercase tracking-wider text-text-secondary">
              {t("stockSectionTitle")}
            </h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Input
                label={t("initialStockLabel")}
                type="number"
                step="1"
                min="0"
                value={stockQuantity}
                onChange={(e) => setStockQuantity(e.target.value)}
                required
              />
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
          </div>

          {/* Form Actions */}
          <div className="pt-4 flex items-center justify-end gap-3 border-t border-border">
            <Link href={`/${locale}/medicines`}>
              <Button type="button" variant="ghost">
                {tCommon("cancel")}
              </Button>
            </Link>
            <Button type="submit" isLoading={loading}>
              {t("saveMedicineButton")}
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
}
