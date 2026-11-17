"use client";

import * as React from "react";

export interface ElderSummary {
  id: string;
  full_name: string;
  preferred_name?: string | null;
  language: string;
  timezone: string;
  day_close_time: string;
  text_size: number;
  is_owner: boolean;
  can_manage_medicines: boolean;
  role?: string | null;
}

interface ElderContextType {
  elders: ElderSummary[];
  selectedElder: ElderSummary | null;
  selectedElderId: string | null;
  selectElder: (id: string) => void;
  refreshElders: () => Promise<void>;
  isLoading: boolean;
}

export const ElderContext = React.createContext<ElderContextType | undefined>(undefined);

const STORAGE_KEY = "aira_selected_elder_id";

export function ElderProvider({ children }: { children: React.ReactNode }) {
  const [elders, setElders] = React.useState<ElderSummary[]>([]);
  const [selectedElderId, setSelectedElderId] = React.useState<string | null>(null);
  const [isLoading, setIsLoading] = React.useState(true);

  const refreshElders = React.useCallback(async () => {
    try {
      setIsLoading(true);
      const res = await fetch("/api/v1/elders");
      if (res.ok) {
        const data: ElderSummary[] = await res.json();
        setElders(data);

        // Retain previous selection if valid, or default to first elder
        const stored = localStorage.getItem(STORAGE_KEY);
        if (stored && data.some((e) => e.id === stored)) {
          setSelectedElderId(stored);
        } else if (data.length > 0) {
          setSelectedElderId(data[0].id);
          localStorage.setItem(STORAGE_KEY, data[0].id);
        } else {
          setSelectedElderId(null);
          localStorage.removeItem(STORAGE_KEY);
        }
      }
    } catch {
      // Error handled silently, empty state presented
    } finally {
      setIsLoading(false);
    }
  }, []);

  React.useEffect(() => {
    refreshElders();
  }, [refreshElders]);

  const selectElder = (id: string) => {
    setSelectedElderId(id);
    localStorage.setItem(STORAGE_KEY, id);
  };

  const selectedElder = React.useMemo(() => {
    return elders.find((e) => e.id === selectedElderId) || elders[0] || null;
  }, [elders, selectedElderId]);

  return (
    <ElderContext.Provider
      value={{
        elders,
        selectedElder,
        selectedElderId: selectedElder?.id || null,
        selectElder,
        refreshElders,
        isLoading,
      }}
    >
      {children}
    </ElderContext.Provider>
  );
}

export function useElder() {
  const context = React.useContext(ElderContext);
  if (!context) {
    throw new Error("useElder must be used within an ElderProvider");
  }
  return context;
}
