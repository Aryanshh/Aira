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

export interface ElderUpdateRequestPayload {
  full_name?: string;
  preferred_name?: string | null;
  language?: string;
  text_size?: number;
  timezone?: string;
  day_close_time?: string;
}

interface ElderContextType {
  elders: ElderSummary[];
  selectedElder: ElderSummary | null;
  selectedElderId: string | null;
  selectElder: (id: string) => void;
  refreshElders: (silent?: boolean) => Promise<void>;
  updateElder: (elderId: string, payload: ElderUpdateRequestPayload) => Promise<boolean>;
  isLoading: boolean;
}

export const ElderContext = React.createContext<ElderContextType | undefined>(undefined);

const STORAGE_KEY = "aira_selected_elder_id";

export function ElderProvider({ children }: { children: React.ReactNode }) {
  const [elders, setElders] = React.useState<ElderSummary[]>([]);
  const [selectedElderId, setSelectedElderId] = React.useState<string | null>(null);
  const [isLoading, setIsLoading] = React.useState(true);

  const refreshElders = React.useCallback(async (silent = false) => {
    try {
      if (!silent) {
        setIsLoading(true);
      }
      const res = await fetch("/api/v1/elders");
      if (res.ok) {
        const data: ElderSummary[] = await res.json();
        setElders(data);

        // Retain previous selection if valid, or default to first elder
        const stored = typeof window !== "undefined" ? localStorage.getItem(STORAGE_KEY) : null;
        if (stored && data.some((e) => e.id === stored)) {
          setSelectedElderId(stored);
        } else if (data.length > 0) {
          setSelectedElderId((prev) => (prev && data.some((e) => e.id === prev) ? prev : data[0].id));
          if (typeof window !== "undefined") {
            localStorage.setItem(STORAGE_KEY, data[0].id);
          }
        } else {
          setSelectedElderId(null);
          if (typeof window !== "undefined") {
            localStorage.removeItem(STORAGE_KEY);
          }
        }
      }
    } catch {
      // Error handled silently, empty state presented
    } finally {
      if (!silent) {
        setIsLoading(false);
      }
    }
  }, []);

  const updateElder = React.useCallback(
    async (elderId: string, payload: ElderUpdateRequestPayload): Promise<boolean> => {
      try {
        const res = await fetch(`/api/v1/elders/${elderId}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        if (res.ok) {
          const updated: ElderSummary = await res.json();
          // Optimistically update list
          setElders((prev) =>
            prev.map((e) => (e.id === elderId ? { ...e, ...updated } : e))
          );
          // Broadcast to other tabs & windows
          if (typeof window !== "undefined") {
            window.dispatchEvent(new CustomEvent("aira:profile-updated", { detail: updated }));
            try {
              const bc = new BroadcastChannel("aira_sync");
              bc.postMessage({ type: "profile_updated", elderId, data: updated });
              bc.close();
            } catch {
              // BroadcastChannel might not be supported everywhere
            }
          }
          await refreshElders(true);
          return true;
        }
        return false;
      } catch {
        return false;
      }
    },
    [refreshElders]
  );

  React.useEffect(() => {
    refreshElders(false);

    // Continuous 3-second background polling for live profile sync
    const pollTimer = setInterval(() => {
      refreshElders(true);
    }, 3000);

    // Cross-tab and window event listener
    const handleProfileUpdate = () => {
      refreshElders(true);
    };
    window.addEventListener("aira:profile-updated", handleProfileUpdate);

    let bc: BroadcastChannel | null = null;
    try {
      bc = new BroadcastChannel("aira_sync");
      bc.onmessage = (event) => {
        if (event.data?.type === "profile_updated") {
          refreshElders(true);
        }
      };
    } catch {
      // Ignored
    }

    return () => {
      clearInterval(pollTimer);
      window.removeEventListener("aira:profile-updated", handleProfileUpdate);
      if (bc) bc.close();
    };
  }, [refreshElders]);

  const selectElder = (id: string) => {
    setSelectedElderId(id);
    if (typeof window !== "undefined") {
      localStorage.setItem(STORAGE_KEY, id);
    }
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
        updateElder,
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
