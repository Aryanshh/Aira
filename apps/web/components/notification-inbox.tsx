"use client";

import * as React from "react";
import { useLocale, useTranslations } from "next-intl";
import { AlertCircle, Bell, Check, CheckCheck, Clock, ExternalLink, X } from "lucide-react";

interface NotificationItem {
  id: string;
  user_id: string;
  elder_id: string | null;
  category: "sos" | "missed" | "refill" | "system";
  template_key: string;
  rendered_text: string;
  params: Record<string, unknown>;
  read_at: string | null;
  created_at: string;
}

export function NotificationInbox() {
  const t = useTranslations("notifications");
  const tCommon = useTranslations("common");
  const locale = useLocale();

  const [isOpen, setIsOpen] = React.useState(false);
  const [notifications, setNotifications] = React.useState<NotificationItem[]>([]);
  const [unreadCount, setUnreadCount] = React.useState(0);
  const [loading, setLoading] = React.useState(false);
  const dropdownRef = React.useRef<HTMLDivElement>(null);

  const fetchNotifications = React.useCallback(async () => {
    try {
      const res = await fetch("/api/v1/notifications?limit=25");
      if (res.ok) {
        const data = await res.json();
        setNotifications(data.notifications || []);
        setUnreadCount(data.unread_count || 0);
      }
    } catch {
      // Ignore background network transient
    }
  }, []);

  React.useEffect(() => {
    fetchNotifications();
    const interval = setInterval(fetchNotifications, 15000);
    return () => clearInterval(interval);
  }, [fetchNotifications]);

  // Close dropdown on outside click
  React.useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    if (isOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [isOpen]);

  const handleMarkAsRead = async (id: string, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    try {
      const res = await fetch(`/api/v1/notifications/${id}/read`, { method: "POST" });
      if (res.ok) {
        setNotifications((prev) =>
          prev.map((n) => (n.id === id ? { ...n, read_at: new Date().toISOString() } : n))
        );
        setUnreadCount((prev) => Math.max(0, prev - 1));
      }
    } catch {
      // Ignore
    }
  };

  const handleMarkAllRead = async () => {
    try {
      const res = await fetch("/api/v1/notifications/read-all", { method: "POST" });
      if (res.ok) {
        setNotifications((prev) =>
          prev.map((n) => ({ ...n, read_at: new Date().toISOString() }))
        );
        setUnreadCount(0);
      }
    } catch {
      // Ignore
    }
  };

  const getCategoryBadgeClass = (category: string) => {
    switch (category) {
      case "sos":
        return "bg-red-100 text-emergency border border-red-200";
      case "missed":
        return "bg-amber-100 text-amber-800 border border-amber-200";
      case "refill":
        return "bg-blue-100 text-blue-800 border border-blue-200";
      default:
        return "bg-surface-muted text-text-secondary border border-border";
    }
  };

  return (
    <div className="relative" ref={dropdownRef}>
      {/* Bell Button */}
      <button
        type="button"
        onClick={() => {
          setIsOpen(!isOpen);
          if (!isOpen) fetchNotifications();
        }}
        aria-label={t("inboxTitle")}
        title={t("inboxTitle")}
        className="relative p-2 rounded-lg text-text-secondary hover:text-text-primary hover:bg-surface-muted transition-colors"
      >
        <Bell className="w-5 h-5" />
        {unreadCount > 0 && (
          <span className="absolute top-1.5 right-1.5 flex h-4 w-4 items-center justify-center rounded-full bg-emergency text-[10px] font-bold text-white shadow-xs">
            {unreadCount > 9 ? "9+" : unreadCount}
          </span>
        )}
      </button>

      {/* Dropdown Menu with Responsive Sizing */}
      {isOpen && (
        <div className="absolute -right-8 sm:right-0 mt-2 w-[calc(100vw-2rem)] max-w-sm sm:w-96 rounded-2xl bg-surface border border-border shadow-2xl z-50 overflow-hidden animate-in fade-in slide-in-from-top-2">
          {/* Header */}
          <div className="flex items-center justify-between p-4 border-b border-border bg-bg-app">
            <div className="flex items-center gap-2">
              <h3 className="font-bold text-sm text-text-primary">{t("inboxTitle")}</h3>
              {unreadCount > 0 && (
                <span className="bg-primary-soft text-primary font-bold text-xs px-2 py-0.5 rounded-full">
                  {unreadCount} {t("new")}
                </span>
              )}
            </div>

            {unreadCount > 0 && (
              <button
                type="button"
                onClick={handleMarkAllRead}
                className="text-xs font-semibold text-primary hover:underline flex items-center gap-1"
              >
                <CheckCheck className="w-3.5 h-3.5" />
                <span>{t("markAllRead")}</span>
              </button>
            )}
          </div>

          {/* List */}
          <div className="max-h-[380px] overflow-y-auto divide-y divide-border">
            {notifications.length === 0 ? (
              <div className="p-8 text-center text-xs text-text-secondary">
                {t("emptyInbox")}
              </div>
            ) : (
              notifications.map((n) => {
                const isUnread = !n.read_at;
                const timeStr = new Date(n.created_at).toLocaleTimeString(
                  locale === "hi" ? "hi-IN" : "en-US",
                  { hour: "2-digit", minute: "2-digit" }
                );

                return (
                  <div
                    key={n.id}
                    onClick={() => handleMarkAsRead(n.id)}
                    className={`p-3.5 text-xs transition-colors cursor-pointer flex items-start gap-3 hover:bg-surface-muted/50 ${
                      isUnread ? "bg-primary-soft/20 font-medium" : "text-text-secondary"
                    }`}
                  >
                    <div className="pt-0.5">
                      <span
                        className={`text-[10px] font-bold px-2 py-0.5 rounded-md uppercase tracking-wider ${getCategoryBadgeClass(
                          n.category
                        )}`}
                      >
                        {t(`category_${n.category}`)}
                      </span>
                    </div>

                    <div className="flex-1 space-y-1">
                      <p className={`text-xs ${isUnread ? "text-text-primary font-semibold" : "text-text-secondary"}`}>
                        {n.rendered_text}
                      </p>
                      <span className="text-[10px] text-text-muted flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        {timeStr}
                      </span>
                    </div>

                    {isUnread && (
                      <span className="w-2 h-2 rounded-full bg-primary mt-1.5 shrink-0" />
                    )}
                  </div>
                );
              })
            )}
          </div>
        </div>
      )}
    </div>
  );
}
