"use client";

import * as React from "react";
import { useTranslations } from "next-intl";
import { Package, Plus, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

interface RefillModalProps {
  elderId: string;
  medicineId: string;
  medicineName: string;
  doseUnit: string;
  currentStock: number;
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export function RefillModal({
  elderId,
  medicineId,
  medicineName,
  doseUnit,
  currentStock,
  isOpen,
  onClose,
  onSuccess,
}: RefillModalProps) {
  const t = useTranslations("stock");
  const tCommon = useTranslations("common");

  const [quantity, setQuantity] = React.useState("30");
  const [note, setNote] = React.useState("");
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState("");

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    const parsedQty = parseFloat(quantity);
    if (isNaN(parsedQty) || parsedQty <= 0) {
      setError(t("validQuantityRequired"));
      return;
    }

    setLoading(true);

    try {
      const res = await fetch(
        `/api/v1/elders/${elderId}/medicines/${medicineId}/refill`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            quantity: parsedQty,
            note: note.trim() || null,
          }),
        }
      );

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        setError(err.detail || t("refillFailed"));
        setLoading(false);
        return;
      }

      onSuccess();
      onClose();
    } catch {
      setError(t("refillFailed"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-xs animate-in fade-in duration-150">
      <Card className="w-full max-w-md p-6 bg-surface border border-border shadow-xl relative animate-in zoom-in-95 duration-150">
        <button
          type="button"
          onClick={onClose}
          className="absolute top-4 right-4 p-1.5 rounded-lg text-text-secondary hover:text-text-primary hover:bg-surface-muted transition-colors"
        >
          <X className="w-5 h-5" />
        </button>

        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-full bg-accent-green/15 text-accent-green flex items-center justify-center">
            <Package className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-text-primary">
              {t("refillModalTitle", { name: medicineName })}
            </h2>
            <p className="text-xs text-text-secondary">
              {t("currentStockLabel")}: <span className="font-bold">{currentStock} {doseUnit}</span>
            </p>
          </div>
        </div>

        {error && (
          <div className="mb-4 p-3 rounded-xl bg-accent-crimson/10 border border-accent-crimson/20 text-accent-crimson text-xs font-medium">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <Input
            label={t("quantityToAddLabel", { unit: doseUnit })}
            type="number"
            step="1"
            min="1"
            value={quantity}
            onChange={(e) => setQuantity(e.target.value)}
            required
            autoFocus
          />

          <Input
            label={t("refillNoteLabel")}
            placeholder={t("refillNotePlaceholder")}
            value={note}
            onChange={(e) => setNote(e.target.value)}
          />

          <div className="pt-2 flex justify-end gap-2">
            <Button type="button" variant="ghost" onClick={onClose}>
              {tCommon("cancel")}
            </Button>
            <Button type="submit" isLoading={loading} className="flex items-center gap-1.5">
              <Plus className="w-4 h-4" />
              <span>{t("confirmRefillButton")}</span>
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
}
