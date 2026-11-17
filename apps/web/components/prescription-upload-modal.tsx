"use client";

import * as React from "react";
import { useLocale, useTranslations } from "next-intl";
import {
  AlertCircle,
  Camera,
  Check,
  CheckCircle2,
  Clock,
  FileText,
  Loader2,
  Pill,
  Plus,
  RefreshCw,
  Sparkles,
  Trash2,
  UploadCloud,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";

export interface DetectedMedicine {
  id: string;
  name: string;
  strength: string;
  form: string;
  dose_amount: number;
  dose_unit: string;
  times_of_day: string[];
  instructions: string;
  color_tag: string;
  stock_quantity: number;
  refill_threshold_days: number;
  confidence?: number;
  notes?: string;
}

interface PrescriptionUploadModalProps {
  isOpen: boolean;
  onClose: () => void;
  elderId: string;
  elderName: string;
  onSuccess: () => void;
}

const COMMON_TIME_PRESETS = [
  { label: "Morning", time: "08:00", icon: "☀️" },
  { label: "Afternoon", time: "14:00", icon: "🌤️" },
  { label: "Night", time: "20:30", icon: "🌙" },
];

export function PrescriptionUploadModal({
  isOpen,
  onClose,
  elderId,
  elderName,
  onSuccess,
}: PrescriptionUploadModalProps) {
  const t = useTranslations("medicines");
  const locale = useLocale();

  const [step, setStep] = React.useState<"upload" | "scanning" | "verify">("upload");
  const [selectedImage, setSelectedImage] = React.useState<string | null>(null);
  const [fileName, setFileName] = React.useState<string>("");
  const [detectedMedicines, setDetectedMedicines] = React.useState<DetectedMedicine[]>([]);
  const [scanError, setScanError] = React.useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = React.useState(false);
  const [successBanner, setSuccessBanner] = React.useState<string | null>(null);

  const fileInputRef = React.useRef<HTMLInputElement>(null);

  // Reset state on open
  React.useEffect(() => {
    if (isOpen) {
      setStep("upload");
      setSelectedImage(null);
      setFileName("");
      setDetectedMedicines([]);
      setScanError(null);
      setIsSubmitting(false);
      setSuccessBanner(null);
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setFileName(file.name);
    setScanError(null);

    const reader = new FileReader();
    reader.onload = () => {
      setSelectedImage(reader.result as string);
    };
    reader.readAsDataURL(file);
  };

  const handleScanPrescription = async (sampleId?: string) => {
    setStep("scanning");
    setScanError(null);

    try {
      const payload: Record<string, any> = {
        elder_id: elderId,
      };

      if (sampleId) {
        payload.sample_id = sampleId;
      } else if (selectedImage) {
        payload.image = selectedImage;
      } else {
        payload.sample_id = "diabetes";
      }

      const res = await fetch("/api/v1/prescriptions/scan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        throw new Error(locale === "hi" ? "पर्ची स्कैन करने में त्रुटि हुई।" : "Failed to scan prescription.");
      }

      const data = await res.json();
      const rawMeds = data.medicines || [];

      const mapped: DetectedMedicine[] = rawMeds.map((m: any, idx: number) => ({
        id: `detected-${Date.now()}-${idx}`,
        name: m.name || "Medicine",
        strength: m.strength || "500mg",
        form: m.form || "tablet",
        dose_amount: Number(m.dose_amount) || 1,
        dose_unit: m.dose_unit || "tablet",
        times_of_day: Array.isArray(m.times_of_day) && m.times_of_day.length > 0 ? m.times_of_day : ["08:00"],
        instructions: m.instructions || (locale === "hi" ? "पानी के साथ भोजन के बाद" : "After meals with water"),
        color_tag: m.color_tag || "#10B981",
        stock_quantity: Number(m.stock_quantity) || 30,
        refill_threshold_days: Number(m.refill_threshold_days) || 7,
        confidence: m.confidence || 0.95,
        notes: m.notes || "",
      }));

      setDetectedMedicines(mapped);
      setStep("verify");
    } catch (err: any) {
      setScanError(err.message || (locale === "hi" ? "पर्ची स्कैन करने में समस्या आई।" : "Unable to scan prescription."));
      setStep("upload");
    }
  };

  // Medicine Field Updates
  const updateMedicine = (id: string, updates: Partial<DetectedMedicine>) => {
    setDetectedMedicines((prev) =>
      prev.map((m) => (m.id === id ? { ...m, ...updates } : m))
    );
  };

  // Toggle Timing
  const toggleTime = (medId: string, timeStr: string) => {
    setDetectedMedicines((prev) =>
      prev.map((m) => {
        if (m.id !== medId) return m;
        const exists = m.times_of_day.includes(timeStr);
        const newTimes = exists
          ? m.times_of_day.filter((t) => t !== timeStr)
          : [...m.times_of_day, timeStr].sort();
        return { ...m, times_of_day: newTimes.length > 0 ? newTimes : [timeStr] };
      })
    );
  };

  // Remove Detected Medicine
  const removeMedicine = (id: string) => {
    setDetectedMedicines((prev) => prev.filter((m) => m.id !== id));
  };

  // Add Custom Medicine Row
  const addExtraMedicine = () => {
    const newMed: DetectedMedicine = {
      id: `detected-${Date.now()}-${Math.random().toString(36).substring(2, 6)}`,
      name: "",
      strength: "",
      form: "tablet",
      dose_amount: 1,
      dose_unit: "tablet",
      times_of_day: ["08:00"],
      instructions: locale === "hi" ? "भोजन के बाद" : "After meal",
      color_tag: "#3B82F6",
      stock_quantity: 30,
      refill_threshold_days: 7,
      confidence: 1.0,
    };
    setDetectedMedicines((prev) => [...prev, newMed]);
  };

  // Final Confirmation: Save into Elder's Schedule and Doses
  const handleConfirmAndSave = async () => {
    if (detectedMedicines.length === 0) return;
    setIsSubmitting(true);
    setScanError(null);

    try {
      // Create each confirmed medicine
      for (const med of detectedMedicines) {
        if (!med.name.trim()) continue;

        const payload = {
          name: med.name.trim(),
          strength: med.strength?.trim() || null,
          form: med.form || "tablet",
          dose_amount: med.dose_amount || 1,
          dose_unit: med.dose_unit || "tablet",
          instructions: med.instructions?.trim() || null,
          color_tag: med.color_tag || "#10B981",
          as_needed: false,
          frequency: "daily",
          interval_n: 1,
          times_of_day: med.times_of_day,
          start_date: new Date().toISOString().split("T")[0],
          initial_stock: med.stock_quantity || 30,
          refill_threshold: med.refill_threshold_days || 7,
        };

        const res = await fetch(`/api/v1/elders/${elderId}/medicines`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });

        if (!res.ok) {
          throw new Error(locale === "hi" ? "दवाइयों को शेड्यूल में जोड़ने में समस्या आई।" : "Failed to add medicine to schedule.");
        }
      }

      setSuccessBanner(
        locale === "hi"
          ? `${detectedMedicines.length} दवाइयाँ शेड्यूल और अलार्म में सफलतापूर्वक जोड़ दी गईं!`
          : `Successfully added ${detectedMedicines.length} medicines to ${elderName}'s schedule and alarms!`
      );

      // Trigger parent refresh
      onSuccess();

      setTimeout(() => {
        onClose();
      }, 1500);
    } catch (err: any) {
      setScanError(err.message || (locale === "hi" ? "शेड्यूल सहेजने में विफल।" : "Failed to save schedule."));
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4 bg-black/60 backdrop-blur-xs animate-in fade-in overflow-y-auto">
      <div className="bg-surface border border-border rounded-2xl shadow-2xl max-w-2xl w-full my-auto overflow-hidden flex flex-col max-h-[92vh]">
        {/* Header */}
        <div className="flex items-center justify-between p-4 sm:p-5 border-b border-border bg-surface shrink-0">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl bg-primary-soft text-primary flex items-center justify-center shadow-2xs">
              <Sparkles className="w-5 h-5 text-primary" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-text-primary tracking-tight">
                {t("uploadPrescriptionModalTitle")}
              </h2>
              <p className="text-xs text-text-secondary">
                {elderName ? `${elderName}` : "AI Prescription Recognition"}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg text-text-secondary hover:text-text-primary hover:bg-surface-muted transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content Body */}
        <div className="p-4 sm:p-6 overflow-y-auto flex-1 space-y-4">
          {scanError && (
            <div className="p-3 rounded-xl bg-accent-crimson/10 border border-accent-crimson/20 text-accent-crimson text-sm font-medium flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{scanError}</span>
            </div>
          )}

          {successBanner && (
            <div className="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-700 dark:text-emerald-300 font-bold text-center flex items-center justify-center gap-2 animate-in zoom-in-95">
              <CheckCircle2 className="w-5 h-5 text-emerald-600" />
              <span>{successBanner}</span>
            </div>
          )}

          {/* STEP 1: Upload & Scan Options */}
          {step === "upload" && (
            <div className="space-y-4">
              <p className="text-xs sm:text-sm text-text-secondary leading-relaxed">
                {t("uploadPrescriptionModalSubtitle")}
              </p>

              {/* Upload Dropzone */}
              <div
                onClick={() => fileInputRef.current?.click()}
                className={`border-2 border-dashed rounded-2xl p-6 sm:p-8 text-center cursor-pointer transition-all ${
                  selectedImage
                    ? "border-primary bg-primary-soft/10"
                    : "border-border hover:border-primary/50 bg-surface-muted/50"
                }`}
              >
                <input
                  type="file"
                  ref={fileInputRef}
                  onChange={handleFileChange}
                  accept="image/*,.pdf"
                  className="hidden"
                />

                {selectedImage ? (
                  <div className="space-y-3">
                    <img
                      src={selectedImage}
                      alt="Prescription preview"
                      className="max-h-48 mx-auto rounded-xl object-contain border border-border shadow-xs"
                    />
                    <div className="flex items-center justify-center gap-2 text-xs font-semibold text-primary">
                      <FileText className="w-4 h-4" />
                      <span>{fileName || "prescription.jpg"}</span>
                    </div>
                    <p className="text-2xs text-text-muted">
                      {locale === "hi" ? "दूसरी फोटो चुनने के लिए क्लिक करें" : "Click to choose a different photo"}
                    </p>
                  </div>
                ) : (
                  <div className="space-y-2">
                    <div className="w-12 h-12 rounded-2xl bg-primary-soft text-primary flex items-center justify-center mx-auto mb-2">
                      <UploadCloud className="w-6 h-6" />
                    </div>
                    <p className="font-bold text-sm text-text-primary">
                      {t("dragOrClickToUpload")}
                    </p>
                    <p className="text-2xs text-text-secondary">
                      {t("supportedFormats")}
                    </p>
                  </div>
                )}
              </div>

              {/* Scan Action Button */}
              {selectedImage && (
                <Button
                  onClick={() => handleScanPrescription()}
                  className="w-full flex items-center justify-center gap-2 font-bold py-3 shadow-md text-base"
                >
                  <Sparkles className="w-5 h-5" />
                  <span>{t("scanWithAiButton")}</span>
                </Button>
              )}

              {/* Presets & Samples */}
              <div className="pt-2 border-t border-border/60">
                <p className="text-xs font-semibold text-text-secondary mb-2.5">
                  {t("trySamplePrescription")}
                </p>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                  <button
                    type="button"
                    onClick={() => handleScanPrescription("diabetes")}
                    className="p-3 rounded-xl bg-surface border border-border hover:border-primary/50 text-left transition-all hover:bg-surface-muted group"
                  >
                    <span className="text-xs font-bold text-text-primary block group-hover:text-primary">
                      🩺 {t("sampleDiabetes")}
                    </span>
                    <span className="text-[11px] text-text-muted mt-0.5 block truncate">
                      Metformin, Telmisartan, Glimepiride
                    </span>
                  </button>

                  <button
                    type="button"
                    onClick={() => handleScanPrescription("cardiac")}
                    className="p-3 rounded-xl bg-surface border border-border hover:border-primary/50 text-left transition-all hover:bg-surface-muted group"
                  >
                    <span className="text-xs font-bold text-text-primary block group-hover:text-primary">
                      ❤️ {t("sampleCardiac")}
                    </span>
                    <span className="text-[11px] text-text-muted mt-0.5 block truncate">
                      Atorvastatin, Aspirin, Pantoprazole
                    </span>
                  </button>

                  <button
                    type="button"
                    onClick={() => handleScanPrescription("infection")}
                    className="p-3 rounded-xl bg-surface border border-border hover:border-primary/50 text-left transition-all hover:bg-surface-muted group"
                  >
                    <span className="text-xs font-bold text-text-primary block group-hover:text-primary">
                      💊 {t("sampleAntibiotics")}
                    </span>
                    <span className="text-[11px] text-text-muted mt-0.5 block truncate">
                      Amoxicillin, Paracetamol, Cetirizine
                    </span>
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* STEP 2: Scanning in Progress */}
          {step === "scanning" && (
            <div className="py-12 px-4 text-center space-y-4">
              <div className="relative w-16 h-16 mx-auto flex items-center justify-center">
                <div className="absolute inset-0 rounded-full border-4 border-primary/20 animate-ping" />
                <div className="w-14 h-14 rounded-full bg-primary-soft text-primary flex items-center justify-center shadow-md">
                  <Sparkles className="w-7 h-7 animate-spin" />
                </div>
              </div>
              <h3 className="text-lg font-bold text-text-primary">
                {t("scanningPrescription")}
              </h3>
              <p className="text-xs text-text-secondary max-w-sm mx-auto">
                {locale === "hi"
                  ? "AI डॉक्टर के हस्तलेख, दवाइयों के नाम, ताकत और 1-0-1 खुराक के समय को पहचान रहा है..."
                  : "AI is parsing drug names, strength, dosages, and doctor's schedule timings..."}
              </p>
            </div>
          )}

          {/* STEP 3: User Verification & Schedule Confirmation */}
          {step === "verify" && (
            <div className="space-y-4">
              {/* Review Guidance Banner */}
              <div className="p-3.5 rounded-xl bg-primary-soft/40 border border-primary/20 flex items-start gap-2.5">
                <Sparkles className="w-4 h-4 text-primary shrink-0 mt-0.5" />
                <div>
                  <h4 className="text-xs font-bold text-text-primary">
                    {t("reviewPrescriptionTitle")}
                  </h4>
                  <p className="text-2xs sm:text-xs text-text-secondary mt-0.5">
                    {t("reviewPrescriptionDesc", { count: detectedMedicines.length })}
                  </p>
                </div>
              </div>

              {/* List of Detected Medicines to Verify */}
              <div className="space-y-3">
                {detectedMedicines.map((med, idx) => (
                  <div
                    key={med.id}
                    className="p-3.5 sm:p-4 rounded-xl bg-surface border border-border shadow-xs space-y-3 transition-all hover:border-primary/30"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-2 flex-1 min-w-0">
                        <span
                          className="w-3 h-3 rounded-full shrink-0"
                          style={{ backgroundColor: med.color_tag }}
                        />
                        <span className="text-xs font-bold text-text-secondary uppercase tracking-wider">
                          {locale === "hi" ? `दवा #${idx + 1}` : `Medicine #${idx + 1}`}
                        </span>
                        {med.confidence && (
                          <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
                            ✓ {Math.round(med.confidence * 100)}% {locale === "hi" ? "सटीकता" : "match"}
                          </span>
                        )}
                      </div>

                      <button
                        type="button"
                        onClick={() => removeMedicine(med.id)}
                        className="p-1.5 rounded-lg text-text-muted hover:text-accent-crimson hover:bg-accent-crimson/10 transition-colors"
                        title="Remove medicine"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>

                    {/* Inputs: Name, Strength, Form */}
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 sm:gap-3">
                      <div className="sm:col-span-2">
                        <label className="text-[11px] font-semibold text-text-secondary block mb-1">
                          {t("medicineNameLabel")} *
                        </label>
                        <input
                          type="text"
                          value={med.name}
                          onChange={(e) => updateMedicine(med.id, { name: e.target.value })}
                          className="w-full px-3 py-1.5 text-sm rounded-lg bg-surface border border-border focus:ring-2 focus:ring-primary/20 focus:border-primary font-semibold"
                          placeholder="e.g. Metformin"
                          required
                        />
                      </div>

                      <div>
                        <label className="text-[11px] font-semibold text-text-secondary block mb-1">
                          {t("strengthLabel")}
                        </label>
                        <input
                          type="text"
                          value={med.strength}
                          onChange={(e) => updateMedicine(med.id, { strength: e.target.value })}
                          className="w-full px-3 py-1.5 text-sm rounded-lg bg-surface border border-border focus:ring-2 focus:ring-primary/20 focus:border-primary"
                          placeholder="e.g. 500mg"
                        />
                      </div>
                    </div>

                    {/* Schedule & Timing Pills */}
                    <div>
                      <label className="text-[11px] font-semibold text-text-secondary block mb-1.5 flex items-center gap-1.5">
                        <Clock className="w-3.5 h-3.5 text-primary" />
                        <span>{t("timesOfDayLabel")}</span>
                      </label>
                      <div className="flex flex-wrap items-center gap-2">
                        {COMMON_TIME_PRESETS.map((preset) => {
                          const isSelected = med.times_of_day.includes(preset.time);
                          return (
                            <button
                              key={preset.time}
                              type="button"
                              onClick={() => toggleTime(med.id, preset.time)}
                              className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold transition-all border ${
                                isSelected
                                  ? "bg-primary text-white border-primary shadow-xs"
                                  : "bg-surface-muted text-text-secondary border-border hover:text-text-primary"
                              }`}
                            >
                              <span>{preset.icon}</span>
                              <span>
                                {preset.label === "Morning"
                                  ? t("timingMorning")
                                  : preset.label === "Afternoon"
                                  ? t("timingAfternoon")
                                  : t("timingNight")}
                              </span>
                              {isSelected && <Check className="w-3.5 h-3.5" />}
                            </button>
                          );
                        })}
                      </div>
                    </div>

                    {/* Instructions & Stock */}
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 sm:gap-3">
                      <div className="sm:col-span-2">
                        <label className="text-[11px] font-semibold text-text-secondary block mb-1">
                          {t("instructionsLabel")}
                        </label>
                        <input
                          type="text"
                          value={med.instructions}
                          onChange={(e) => updateMedicine(med.id, { instructions: e.target.value })}
                          className="w-full px-3 py-1.5 text-xs rounded-lg bg-surface border border-border focus:ring-2 focus:ring-primary/20 focus:border-primary text-text-secondary"
                          placeholder="e.g. After breakfast with water"
                        />
                      </div>

                      <div>
                        <label className="text-[11px] font-semibold text-text-secondary block mb-1">
                          {t("initialStockLabel")}
                        </label>
                        <input
                          type="number"
                          min="1"
                          value={med.stock_quantity}
                          onChange={(e) => updateMedicine(med.id, { stock_quantity: Number(e.target.value) || 30 })}
                          className="w-full px-3 py-1.5 text-xs rounded-lg bg-surface border border-border focus:ring-2 focus:ring-primary/20 focus:border-primary"
                        />
                      </div>
                    </div>
                  </div>
                ))}

                <button
                  type="button"
                  onClick={addExtraMedicine}
                  className="w-full py-2.5 rounded-xl border border-dashed border-border hover:border-primary/60 text-primary text-xs font-bold flex items-center justify-center gap-1.5 hover:bg-primary-soft/10 transition-colors"
                >
                  <Plus className="w-4 h-4" />
                  <span>{t("addAnotherDetectedMed")}</span>
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Modal Footer Actions */}
        <div className="p-4 sm:p-5 border-t border-border bg-surface shrink-0 flex items-center justify-between gap-3">
          {step === "verify" ? (
            <>
              <button
                type="button"
                onClick={() => setStep("upload")}
                disabled={isSubmitting}
                className="px-4 py-2 rounded-xl text-xs sm:text-sm font-semibold text-text-secondary hover:text-text-primary hover:bg-surface-muted transition-colors"
              >
                ← {t("reuploadButton")}
              </button>

              <Button
                onClick={handleConfirmAndSave}
                disabled={isSubmitting || detectedMedicines.length === 0}
                className="flex items-center gap-2 font-bold px-5 py-2.5 shadow-md"
              >
                {isSubmitting ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>{t("addingMedicines")}</span>
                  </>
                ) : (
                  <>
                    <CheckCircle2 className="w-4 h-4" />
                    <span>{t("confirmAddAllToSchedule", { count: detectedMedicines.length })}</span>
                  </>
                )}
              </Button>
            </>
          ) : (
            <>
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 rounded-xl text-xs sm:text-sm font-semibold text-text-secondary hover:text-text-primary hover:bg-surface-muted transition-colors"
              >
                {locale === "hi" ? "रद्द करें" : "Cancel"}
              </button>

              {selectedImage && step === "upload" && (
                <Button
                  onClick={() => handleScanPrescription()}
                  className="flex items-center gap-2 font-bold"
                >
                  <Sparkles className="w-4 h-4" />
                  <span>{t("scanWithAiButton")}</span>
                </Button>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
