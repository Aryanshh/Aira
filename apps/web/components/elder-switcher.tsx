"use client";

import * as React from "react";
import Link from "next/link";
import { useLocale, useTranslations } from "next-intl";
import { ChevronDown, Pencil, Plus, Settings2, User } from "lucide-react";

import { ElderSummary, useElder } from "@/components/elder-context";
import { ElderProfileModal } from "@/components/elder-profile-modal";

export function ElderSwitcher() {
  const t = useTranslations("switcher");
  const locale = useLocale();
  const { elders, selectedElder, selectElder, isLoading } = useElder();
  const [isOpen, setIsOpen] = React.useState(false);
  const [isModalOpen, setIsModalOpen] = React.useState(false);
  const [editingElder, setEditingElder] = React.useState<ElderSummary | null>(null);
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

  const handleOpenEdit = (e: React.MouseEvent, targetElder: ElderSummary) => {
    e.stopPropagation();
    setEditingElder(targetElder);
    setIsOpen(false);
    setIsModalOpen(true);
  };

  return (
    <>
      <div className="relative inline-flex items-center gap-1" ref={dropdownRef}>
        <button
          type="button"
          onClick={() => setIsOpen(!isOpen)}
          className="inline-flex items-center gap-1.5 sm:gap-2 px-2.5 py-1.5 sm:px-3.5 sm:py-2 rounded-xl bg-surface border border-border shadow-xs hover:border-primary/40 focus:outline-hidden focus:ring-2 focus:ring-primary/20 transition-all text-sm font-medium text-text-primary"
          aria-haspopup="true"
          aria-expanded={isOpen}
        >
          <div className="w-6 h-6 rounded-full bg-primary-soft text-primary flex items-center justify-center text-xs font-bold shrink-0">
            {displayName.charAt(0).toUpperCase()}
          </div>
          <span className="truncate max-w-[95px] sm:max-w-[180px] text-xs sm:text-sm">{displayName}</span>
          <ChevronDown className="w-3.5 h-3.5 sm:w-4 sm:h-4 text-text-secondary shrink-0" />
        </button>

        {selectedElder && (
          <button
            type="button"
            onClick={(e) => handleOpenEdit(e, selectedElder)}
            title={t("editProfile")}
            aria-label={t("editProfile")}
            className="p-1.5 sm:p-2 rounded-xl bg-surface border border-border text-text-secondary hover:text-primary hover:border-primary/30 transition-all shadow-xs active:scale-95"
          >
            <Pencil className="w-3.5 h-3.5 sm:w-4 sm:h-4" />
          </button>
        )}

        {isOpen && (
          <div className="absolute left-0 top-full mt-2 w-72 max-w-[calc(100vw-2rem)] rounded-2xl bg-surface border border-border shadow-xl py-2 z-50 animate-in fade-in zoom-in-95 duration-100">
            <div className="px-3.5 py-1.5 text-xs font-semibold text-text-secondary uppercase tracking-wider flex items-center justify-between">
              <span>{t("elders")}</span>
              <span className="text-[10px] text-primary lowercase bg-primary-soft px-1.5 py-0.5 rounded-full font-medium">
                real-time sync
              </span>
            </div>

            <div className="max-h-60 overflow-y-auto py-1">
              {elders.map((elder) => {
                const name = elder.preferred_name || elder.full_name;
                const isSelected = elder.id === selectedElder?.id;
                return (
                  <div
                    key={elder.id}
                    className={`w-full px-3.5 py-2 text-sm flex items-center justify-between gap-2 transition-colors ${
                      isSelected
                        ? "bg-primary-soft/60 text-primary font-medium"
                        : "text-text-primary hover:bg-surface-muted"
                    }`}
                  >
                    <button
                      type="button"
                      onClick={() => {
                        selectElder(elder.id);
                        setIsOpen(false);
                      }}
                      className="flex items-center gap-2.5 flex-1 min-w-0 text-left"
                    >
                      <User className={`w-4 h-4 shrink-0 ${isSelected ? "text-primary" : "text-text-secondary"}`} />
                      <div className="truncate flex-1">
                        <div className="truncate font-semibold">{name}</div>
                        {elder.preferred_name && (
                          <div className="text-[11px] text-text-secondary truncate">{elder.full_name}</div>
                        )}
                      </div>
                      {isSelected && (
                        <span className="w-2 h-2 rounded-full bg-primary shrink-0" />
                      )}
                    </button>

                    <button
                      type="button"
                      onClick={(e) => handleOpenEdit(e, elder)}
                      title={t("editProfile")}
                      className="p-1 rounded-lg text-text-secondary hover:text-primary hover:bg-surface transition-colors shrink-0"
                    >
                      <Settings2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                );
              })}
            </div>

            <div className="border-t border-border mt-1 pt-1.5 px-1.5 space-y-0.5">
              {selectedElder && (
                <button
                  type="button"
                  onClick={(e) => handleOpenEdit(e, selectedElder)}
                  className="w-full text-left px-3 py-1.5 text-xs text-text-secondary hover:text-text-primary hover:bg-surface-muted rounded-lg flex items-center gap-2 transition-colors font-medium"
                >
                  <Pencil className="w-3.5 h-3.5 text-primary" />
                  <span>{t("editProfile")}: {displayName}</span>
                </button>
              )}

              <Link
                href={`/${locale}/elders/new`}
                onClick={() => setIsOpen(false)}
                className="w-full text-left px-3 py-1.5 text-xs text-primary hover:bg-primary-soft rounded-lg flex items-center gap-2 transition-colors font-semibold"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>{t("addNewElder")}</span>
              </Link>
            </div>
          </div>
        )}
      </div>

      <ElderProfileModal
        elder={editingElder || selectedElder}
        isOpen={isModalOpen}
        onClose={() => {
          setIsModalOpen(false);
          setEditingElder(null);
        }}
      />
    </>
  );
}
