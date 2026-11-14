"use client";

import * as React from "react";
import Link from "next/link";
import { useLocale, useTranslations } from "next-intl";
import { ChevronDown, Plus, User } from "lucide-react";

import { useElder } from "@/components/elder-context";

export function ElderSwitcher() {
  const t = useTranslations("switcher");
  const locale = useLocale();
  const { elders, selectedElder, selectElder, isLoading } = useElder();
  const [isOpen, setIsOpen] = React.useState(false);
  const dropdownRef = React.useRef<HTMLDivElement>(null);

  // Close dropdown on outside click
  React.useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  if (isLoading) {
    return (
      <div className="h-10 w-36 bg-surface-muted animate-pulse rounded-lg border border-border" />
    );
  }

  if (elders.length === 0) {
    return (
      <Link
        href={`/${locale}/elders/new`}
        className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-lg bg-primary-soft text-primary hover:bg-primary/20 transition-colors"
      >
        <Plus className="w-4 h-4" />
        <span>{t("addFirstElder")}</span>
      </Link>
    );
  }

  const displayName = selectedElder?.preferred_name || selectedElder?.full_name || t("selectElder");

  return (
    <div className="relative inline-block text-left" ref={dropdownRef}>
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="inline-flex items-center gap-2 px-3.5 py-2 rounded-xl bg-surface border border-border shadow-xs hover:border-primary/40 focus:outline-hidden focus:ring-2 focus:ring-primary/20 transition-all text-sm font-medium text-text-primary"
        aria-haspopup="true"
        aria-expanded={isOpen}
      >
        <div className="w-6 h-6 rounded-full bg-primary-soft text-primary flex items-center justify-center text-xs font-bold">
          {displayName.charAt(0).toUpperCase()}
        </div>
        <span className="truncate max-w-[130px] sm:max-w-[180px]">{displayName}</span>
        <ChevronDown className="w-4 h-4 text-text-secondary" />
      </button>

      {isOpen && (
        <div className="absolute right-0 mt-2 w-64 rounded-xl bg-surface border border-border shadow-md py-1.5 z-50 animate-in fade-in zoom-in-95 duration-100">
          <div className="px-3 py-1.5 text-xs font-semibold text-text-secondary uppercase tracking-wider">
            {t("elders")}
          </div>

          <div className="max-h-60 overflow-y-auto py-1">
            {elders.map((elder) => {
              const name = elder.preferred_name || elder.full_name;
              const isSelected = elder.id === selectedElder?.id;
              return (
                <button
                  key={elder.id}
                  type="button"
                  onClick={() => {
                    selectElder(elder.id);
                    setIsOpen(false);
                  }}
                  className={`w-full text-left px-3.5 py-2 text-sm flex items-center gap-2.5 transition-colors ${
                    isSelected
                      ? "bg-primary-soft text-primary font-medium"
                      : "text-text-primary hover:bg-surface-muted"
                  }`}
                >
                  <User className={`w-4 h-4 ${isSelected ? "text-primary" : "text-text-secondary"}`} />
                  <span className="truncate flex-1">{name}</span>
                  {isSelected && (
                    <span className="w-2 h-2 rounded-full bg-primary" />
                  )}
                </button>
              );
            })}
          </div>

          <div className="border-t border-border mt-1 pt-1">
            <Link
              href={`/${locale}/elders/new`}
              onClick={() => setIsOpen(false)}
              className="w-full text-left px-3.5 py-2 text-sm text-primary hover:bg-primary-soft flex items-center gap-2 transition-colors font-medium"
            >
              <Plus className="w-4 h-4" />
              <span>{t("addNewElder")}</span>
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}
