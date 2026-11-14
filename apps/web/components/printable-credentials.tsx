"use client";

import * as React from "react";
import QRCode from "qrcode";
import { AlertCircle, Check, Copy, Printer, Shield } from "lucide-react";
import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

interface PrintableCredentialsProps {
  elderName: string;
  accessCode: string;
  pin: string;
  qrUrl: string;
  onDone?: () => void;
}

export function PrintableCredentials({
  elderName,
  accessCode,
  pin,
  qrUrl,
  onDone,
}: PrintableCredentialsProps) {
  const t = useTranslations("credentials");
  const canvasRef = React.useRef<HTMLCanvasElement>(null);
  const [copiedCode, setCopiedCode] = React.useState(false);
  const [copiedPin, setCopiedPin] = React.useState(false);

  React.useEffect(() => {
    if (canvasRef.current && qrUrl) {
      QRCode.toCanvas(canvasRef.current, qrUrl, {
        width: 180,
        margin: 2,
        color: {
          dark: "#2A2A2A",
          light: "#FFFFFF",
        },
      }).catch((err) => {
        console.error("QR Code render failed", err);
      });
    }
  }, [qrUrl]);

  const copyToClipboard = (text: string, type: "code" | "pin") => {
    navigator.clipboard.writeText(text);
    if (type === "code") {
      setCopiedCode(true);
      setTimeout(() => setCopiedCode(false), 2000);
    } else {
      setCopiedPin(true);
      setTimeout(() => setCopiedPin(false), 2000);
    }
  };

  const handlePrint = () => {
    window.print();
  };

  return (
    <div className="w-full max-w-lg mx-auto print:max-w-none print:w-full">
      {/* Alert Banner: Only shown once */}
      <div className="mb-4 p-4 rounded-xl bg-accent-amber/15 border border-accent-amber/30 flex items-start gap-3 print:hidden">
        <AlertCircle className="w-5 h-5 text-accent-amber shrink-0 mt-0.5" />
        <div className="text-sm">
          <p className="font-semibold text-text-primary">{t("shownOnceTitle")}</p>
          <p className="text-text-secondary mt-0.5">{t("shownOnceDesc")}</p>
        </div>
      </div>

      {/* Printable Card */}
      <Card className="p-6 md:p-8 bg-surface border-2 border-primary/20 shadow-lg print:border-black print:shadow-none">
        <div className="text-center pb-6 border-b border-border">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-primary-soft text-primary mb-2 print:border print:border-black">
            <Shield className="w-6 h-6" />
          </div>
          <h2 className="text-2xl font-bold text-text-primary tracking-tight">
            {t("cardTitle", { name: elderName })}
          </h2>
          <p className="text-sm text-text-secondary mt-1">{t("cardSubtitle")}</p>
        </div>

        <div className="py-6 space-y-6">
          {/* Method 1: QR Code Scan */}
          <div className="flex flex-col items-center justify-center p-4 rounded-xl bg-surface-muted/50 border border-border/80 print:border-black">
            <span className="text-xs font-bold uppercase tracking-wider text-text-secondary mb-2">
              {t("method1")}
            </span>
            <div className="p-2 bg-white rounded-lg shadow-xs border border-border">
              <canvas ref={canvasRef} className="block" />
            </div>
            <p className="text-xs text-text-secondary mt-3 text-center max-w-xs">
              {t("qrInstructions")}
            </p>
          </div>

          {/* Method 2: Access Code + 4-digit PIN */}
          <div className="space-y-4">
            <div className="text-center">
              <span className="text-xs font-bold uppercase tracking-wider text-text-secondary">
                {t("method2")}
              </span>
            </div>

            <div className="grid grid-cols-2 gap-3">
              {/* Access Code Box */}
              <div className="p-4 rounded-xl bg-surface-muted border border-border flex flex-col items-center justify-center text-center">
                <span className="text-xs font-medium text-text-secondary">{t("accessCodeLabel")}</span>
                <span className="text-xl font-mono font-bold tracking-wider text-primary mt-1">
                  {accessCode}
                </span>
                <button
                  type="button"
                  onClick={() => copyToClipboard(accessCode, "code")}
                  className="mt-2 text-xs text-text-secondary hover:text-text-primary flex items-center gap-1 print:hidden"
                >
                  {copiedCode ? <Check className="w-3.5 h-3.5 text-accent-green" /> : <Copy className="w-3.5 h-3.5" />}
                  <span>{copiedCode ? t("copied") : t("copy")}</span>
                </button>
              </div>

              {/* 4-digit PIN Box */}
              <div className="p-4 rounded-xl bg-surface-muted border border-border flex flex-col items-center justify-center text-center">
                <span className="text-xs font-medium text-text-secondary">{t("pinLabel")}</span>
                <span className="text-3xl font-mono font-black tracking-widest text-text-primary mt-0.5">
                  {pin}
                </span>
                <button
                  type="button"
                  onClick={() => copyToClipboard(pin, "pin")}
                  className="mt-2 text-xs text-text-secondary hover:text-text-primary flex items-center gap-1 print:hidden"
                >
                  {copiedPin ? <Check className="w-3.5 h-3.5 text-accent-green" /> : <Copy className="w-3.5 h-3.5" />}
                  <span>{copiedPin ? t("copied") : t("copy")}</span>
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Footer actions (hidden in print) */}
        <div className="pt-6 border-t border-border flex flex-col sm:flex-row gap-3 print:hidden">
          <Button
            type="button"
            variant="outline"
            className="flex-1 flex items-center justify-center gap-2"
            onClick={handlePrint}
          >
            <Printer className="w-4 h-4" />
            <span>{t("printButton")}</span>
          </Button>

          {onDone && (
            <Button
              type="button"
              className="flex-1"
              onClick={onDone}
            >
              {t("doneButton")}
            </Button>
          )}
        </div>
      </Card>
    </div>
  );
}
