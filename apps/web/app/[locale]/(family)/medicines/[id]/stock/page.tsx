"use client";

import * as React from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import {
  AlertCircle,
  ArrowDownRight,
  ArrowLeft,
  ArrowUpRight,
  Clock,
  History,
  Package,
  Plus,
  SlidersHorizontal,
} from "lucide-react";

import { useElder } from "@/components/elder-context";
import { RefillModal } from "@/components/refill-modal";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

interface StockEvent {
  id: string;
  medicine_id: string;
  delta: number;
  reason: string;
  note?: string | null;
  created_by?: string | null;
  created_at: string;
}

interface MedicineDetails {
  id: string;
  name: string;
  strength?: string | null;
  dose_unit: string;
  stock_quantity: number;
  refill_threshold_days: number;
  days_remaining?: number | null;
  as_needed: boolean;
}

export default function MedicineStockPage() {
  const t = useTranslations("stock");
  const tCommon = useTranslations("common");
  const locale = useLocale();
  const params = useParams();
  const medicineId = params.id as string;
  const { selectedElder } = useElder();

  const [med, setMed] = React.useState<MedicineDetails | null>(null);
  const [events, setEvents] = React.useState<StockEvent[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState("");

  // Refill Modal state
  const [showRefillModal, setShowRefillModal] = React.useState(false);

  // Manual Adjust form state
  const [showAdjustForm, setShowAdjustForm] = React.useState(false);
  const [adjustQuantity, setAdjustQuantity] = React.useState("");
  const [adjustNote, setAdjustNote] = React.useState("");
  const [adjusting, setAdjusting] = React.useState(false);

  const fetchData = React.useCallback(async () => {
    if (!selectedElder || !medicineId) return;
    setLoading(true);
    setError("");

    try {
      const [medRes, eventsRes] = await Promise.all([
        fetch(`/api/v1/elders/${selectedElder.id}/medicines/${medicineId}`),
        fetch(`/api/v1/elders/${selectedElder.id}/medicines/${medicineId}/stock-events`),
      ]);

      if (medRes.ok && eventsRes.ok) {
        const medData = await medRes.json();
        const eventsData = await eventsRes.json();
        setMed(medData);
        setEvents(eventsData);
        setAdjustQuantity(String(medData.stock_quantity));
      } else {
        setError(t("fetchFailed"));
      }
    } catch {
      setError(t("fetchFailed"));
    } finally {
      setLoading(false);
    }
  }, [selectedElder, medicineId, t]);

  React.useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleAdjustSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedElder || !medicineId) return;
    setAdjusting(true);

    try {
      const res = await fetch(
        `/api/v1/elders/${selectedElder.id}/medicines/${medicineId}/stock-adjust`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            new_quantity: parseFloat(adjustQuantity),
            note: adjustNote.trim() || null,
          }),
        }
      );

      if (res.ok) {
        setShowAdjustForm(false);
        setAdjustNote("");
        fetchData();
      } else {
        const err = await res.json().catch(() => ({}));
        alert(err.detail || t("adjustFailed"));
      }
    } catch {
      alert(t("adjustFailed"));
    } finally {
      setAdjusting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[300px]">
        <div className="w-8 h-8 rounded-full border-2 border-primary border-t-transparent animate-spin" />
      </div>
    );
  }

  if (!med) {
    return (
      <div className="text-center py-12">
        <h2 className="text-lg font-bold text-text-primary">{t("medicineNotFound")}</h2>
      </div>
    );
  }

  const isLowStock =
    med.days_remaining !== null &&
    med.days_remaining !== undefined &&
    med.days_remaining <= med.refill_threshold_days;

  return (
    <div className="max-w-4xl mx-auto py-4 sm:py-6 space-y-6">
      {/* Back & Title */}
      <div className="flex items-center gap-3">
        <Link
          href={`/${locale}/medicines`}
          className="p-2 rounded-lg text-text-secondary hover:text-text-primary hover:bg-surface-muted transition-colors"
        >
          <ArrowLeft className="w-5 h-5" />
        </Link>
        <div>
          <h1 className="text-2xl font-bold text-text-primary tracking-tight">
            {t("stockPageTitle", { name: med.name })}
          </h1>
          <p className="text-sm text-text-secondary mt-0.5">{t("stockPageSubtitle")}</p>
        </div>
      </div>

      {error && (
        <div className="p-3.5 rounded-xl bg-accent-crimson/10 border border-accent-crimson/20 text-accent-crimson text-sm font-medium">
          {error}
        </div>
      )}

      {/* Low Stock Warning Banner */}
      {isLowStock && (
        <div className="p-4 rounded-xl bg-accent-crimson/10 border border-accent-crimson/30 flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-accent-crimson shrink-0 mt-0.5" />
          <div>
            <h3 className="font-bold text-accent-crimson">{t("lowStockAlertTitle")}</h3>
            <p className="text-sm text-text-secondary mt-0.5">
              {t("lowStockAlertDesc", {
                name: med.name,
                days: med.days_remaining,
                threshold: med.refill_threshold_days,
              })}
            </p>
          </div>
        </div>
      )}

      {/* Stock KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {/* Current Stock */}
        <Card className="p-5 bg-surface border border-border shadow-2xs">
          <div className="flex items-center justify-between text-text-secondary mb-2">
            <span className="text-xs font-bold uppercase tracking-wider">{t("currentStockLabel")}</span>
            <Package className="w-4 h-4 text-primary" />
          </div>
          <div className="text-3xl font-black text-text-primary">
            {med.stock_quantity}{" "}
            <span className="text-sm font-semibold text-text-secondary">{med.dose_unit}</span>
          </div>
        </Card>

        {/* Days Remaining */}
        <Card className="p-5 bg-surface border border-border shadow-2xs">
          <div className="flex items-center justify-between text-text-secondary mb-2">
            <span className="text-xs font-bold uppercase tracking-wider">{t("estimatedDaysLabel")}</span>
            <Clock className="w-4 h-4 text-accent-green" />
          </div>
          <div className="text-3xl font-black text-text-primary">
            {med.days_remaining !== null && med.days_remaining !== undefined ? (
              <>
                ~{med.days_remaining}{" "}
                <span className="text-sm font-semibold text-text-secondary">{t("daysUnit")}</span>
              </>
            ) : (
              <span className="text-lg font-medium text-text-secondary">N/A (as needed)</span>
            )}
          </div>
        </Card>

        {/* Refill Threshold */}
        <Card className="p-5 bg-surface border border-border shadow-2xs">
          <div className="flex items-center justify-between text-text-secondary mb-2">
            <span className="text-xs font-bold uppercase tracking-wider">{t("refillAlertThresholdLabel")}</span>
            <AlertCircle className="w-4 h-4 text-accent-amber" />
          </div>
          <div className="text-3xl font-black text-text-primary">
            {med.refill_threshold_days}{" "}
            <span className="text-sm font-semibold text-text-secondary">{t("daysUnit")}</span>
          </div>
        </Card>
      </div>

      {/* Quick Actions */}
      <div className="flex flex-wrap items-center gap-3">
        <Button
          type="button"
          onClick={() => setShowRefillModal(true)}
          className="flex items-center gap-2"
        >
          <Plus className="w-4 h-4" />
          <span>{t("recordRefillButton")}</span>
        </Button>

        <Button
          type="button"
          variant="outline"
          onClick={() => setShowAdjustForm(!showAdjustForm)}
          className="flex items-center gap-2"
        >
          <SlidersHorizontal className="w-4 h-4" />
          <span>{t("adjustStockButton")}</span>
        </Button>
      </div>

      {/* Manual Stock Adjust Form (Accordion) */}
      {showAdjustForm && (
        <Card className="p-5 bg-surface border border-primary/30 shadow-md animate-in fade-in duration-100">
          <h3 className="font-bold text-text-primary mb-3 flex items-center gap-2">
            <SlidersHorizontal className="w-4 h-4 text-primary" />
            <span>{t("adjustFormTitle")}</span>
          </h3>
          <form onSubmit={handleAdjustSubmit} className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Input
                label={t("setExactStockLabel", { unit: med.dose_unit })}
                type="number"
                step="1"
                min="0"
                value={adjustQuantity}
                onChange={(e) => setAdjustQuantity(e.target.value)}
                required
              />
              <Input
                label={t("adjustmentReasonLabel")}
                placeholder="e.g. Physical inventory count, damaged tablets"
                value={adjustNote}
                onChange={(e) => setAdjustNote(e.target.value)}
              />
            </div>
            <div className="flex justify-end gap-2">
              <Button type="button" variant="ghost" onClick={() => setShowAdjustForm(false)}>
                {tCommon("cancel")}
              </Button>
              <Button type="submit" isLoading={adjusting}>
                {tCommon("save")}
              </Button>
            </div>
          </form>
        </Card>
      )}

      {/* Stock Ledger History Table */}
      <div className="space-y-3 pt-2">
        <h2 className="text-lg font-bold text-text-primary flex items-center gap-2">
          <History className="w-5 h-5 text-primary" />
          <span>{t("ledgerHistoryTitle")}</span>
        </h2>

        {events.length === 0 ? (
          <p className="text-sm text-text-secondary">{t("noEventsYet")}</p>
        ) : (
          <div className="overflow-x-auto rounded-xl border border-border bg-surface">
            <table className="w-full text-left text-sm border-collapse">
              <thead>
                <tr className="border-b border-border bg-surface-muted/50 text-xs font-bold uppercase tracking-wider text-text-secondary">
                  <th className="py-3 px-4">{t("tableDate")}</th>
                  <th className="py-3 px-4">{t("tableEvent")}</th>
                  <th className="py-3 px-4">{t("tableDelta")}</th>
                  <th className="py-3 px-4">{t("tableNoteAndActor")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {events.map((ev) => {
                  const isPositive = Number(ev.delta) > 0;
                  const deltaNum = Number(ev.delta);

                  return (
                    <tr key={ev.id} className="hover:bg-surface-muted/30 transition-colors">
                      <td className="py-3 px-4 text-xs font-medium text-text-secondary whitespace-nowrap">
                        {new Date(ev.created_at).toLocaleString(locale, {
                          dateStyle: "medium",
                          timeStyle: "short",
                        })}
                      </td>

                      <td className="py-3 px-4">
                        <span className="capitalize font-semibold text-text-primary">
                          {ev.reason.replace("_", " ")}
                        </span>
                      </td>

                      <td className="py-3 px-4 whitespace-nowrap">
                        <span
                          className={`inline-flex items-center gap-1 font-mono font-bold text-sm px-2 py-0.5 rounded-md ${
                            isPositive
                              ? "bg-accent-green/15 text-accent-green"
                              : "bg-accent-crimson/15 text-accent-crimson"
                          }`}
                        >
                          {isPositive ? (
                            <ArrowUpRight className="w-3.5 h-3.5" />
                          ) : (
                            <ArrowDownRight className="w-3.5 h-3.5" />
                          )}
                          {isPositive ? `+${deltaNum}` : `${deltaNum}`} {med.dose_unit}
                        </span>
                      </td>

                      <td className="py-3 px-4 text-xs text-text-secondary">
                        {ev.note && <p className="italic text-text-primary">"{ev.note}"</p>}
                        {ev.created_by && (
                          <p className="text-2xs text-text-secondary mt-0.5">
                            {t("recordedBy", { actor: ev.created_by })}
                          </p>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Refill Modal */}
      {selectedElder && (
        <RefillModal
          elderId={selectedElder.id}
          medicineId={med.id}
          medicineName={med.name}
          doseUnit={med.dose_unit}
          currentStock={med.stock_quantity}
          isOpen={showRefillModal}
          onClose={() => setShowRefillModal(false)}
          onSuccess={fetchData}
        />
      )}
    </div>
  );
}
