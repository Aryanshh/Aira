"use client";

import * as React from "react";
import { useLocale, useTranslations } from "next-intl";
import {
  AlertCircle,
  AlertTriangle,
  ArrowDown,
  ArrowUp,
  CheckCircle2,
  Clock,
  Edit2,
  Phone,
  Plus,
  ShieldAlert,
  Trash2,
  UserCheck,
  Users,
  X,
} from "lucide-react";

import { useElder } from "@/components/elder-context";

interface Contact {
  id: string;
  elder_id: string;
  full_name: string;
  role: "family" | "doctor" | "neighbour";
  phone_e164: string;
  whatsapp_e164: string | null;
  email: string | null;
  whatsapp_opt_in: boolean;
  preferred_channels: string[];
  escalation_order: number;
  active: boolean;
  created_at: string;
}

interface SosAttempt {
  id: string;
  contact_name: string;
  channel: string;
  round: number;
  status: string;
  sent_at: string | null;
}

interface SosHistoryEvent {
  id: string;
  elder_id: string;
  source: "device" | "web";
  client_event_id: string;
  status: "active" | "handled" | "failed";
  escalation_state: "in_progress" | "exhausted" | "acknowledged";
  press_count: number;
  triggered_at: string;
  handled_at: string | null;
  handled_by: string | null;
  attempts: SosAttempt[];
}

export default function SosManagementPage() {
  const { selectedElder } = useElder();
  const locale = useLocale();
  const t = useTranslations("sos");
  const tCommon = useTranslations("common");

  // Contacts State
  const [contacts, setContacts] = React.useState<Contact[]>([]);
  const [loadingContacts, setLoadingContacts] = React.useState(true);
  const [contactError, setContactError] = React.useState<string | null>(null);

  // Contact Modal State
  const [showContactModal, setShowContactModal] = React.useState(false);
  const [editingContact, setEditingContact] = React.useState<Contact | null>(null);
  const [contactFormName, setContactFormName] = React.useState("");
  const [contactFormRole, setContactFormRole] = React.useState<"family" | "doctor" | "neighbour">("family");
  const [contactFormPhone, setContactFormPhone] = React.useState("");
  const [contactFormWhatsapp, setContactFormWhatsapp] = React.useState("");
  const [contactFormEmail, setContactFormEmail] = React.useState("");
  const [contactFormWhatsappOptIn, setContactFormWhatsappOptIn] = React.useState(true);
  const [contactFormChannels, setContactFormChannels] = React.useState<string[]>(["sms", "whatsapp"]);
  const [submittingContact, setSubmittingContact] = React.useState(false);

  // History State
  const [history, setHistory] = React.useState<SosHistoryEvent[]>([]);
  const [loadingHistory, setLoadingHistory] = React.useState(true);

  // Trigger Test SOS Modal
  const [showTriggerModal, setShowTriggerModal] = React.useState(false);
  const [triggeringSos, setTriggeringSos] = React.useState(false);
  const [triggerError, setTriggerError] = React.useState<string | null>(null);

  const fetchContacts = React.useCallback(async () => {
    if (!selectedElder) return;
    setLoadingContacts(true);
    setContactError(null);
    try {
      const res = await fetch(`/api/v1/elders/${selectedElder.id}/contacts`);
      if (!res.ok) throw new Error(t("fetchContactsFailed"));
      const data = await res.json();
      setContacts(data);
    } catch (err) {
      setContactError(err instanceof Error ? err.message : t("fetchContactsFailed"));
    } finally {
      setLoadingContacts(false);
    }
  }, [selectedElder, t]);

  const fetchHistory = React.useCallback(async () => {
    if (!selectedElder) return;
    setLoadingHistory(true);
    try {
      const res = await fetch(`/api/v1/elders/${selectedElder.id}/sos`);
      if (res.ok) {
        const data = await res.json();
        setHistory(data);
      }
    } catch {
      // Ignore background network error
    } finally {
      setLoadingHistory(false);
    }
  }, [selectedElder]);

  React.useEffect(() => {
    fetchContacts();
    fetchHistory();
  }, [fetchContacts, fetchHistory]);

  // Open modal for Add
  const handleOpenAddModal = () => {
    setEditingContact(null);
    setContactFormName("");
    setContactFormRole("family");
    setContactFormPhone("+91");
    setContactFormWhatsapp("");
    setContactFormEmail("");
    setContactFormWhatsappOptIn(true);
    setContactFormChannels(["sms", "whatsapp"]);
    setContactError(null);
    setShowContactModal(true);
  };

  // Open modal for Edit
  const handleOpenEditModal = (c: Contact) => {
    setEditingContact(c);
    setContactFormName(c.full_name);
    setContactFormRole(c.role);
    setContactFormPhone(c.phone_e164);
    setContactFormWhatsapp(c.whatsapp_e164 || "");
    setContactFormEmail(c.email || "");
    setContactFormWhatsappOptIn(c.whatsapp_opt_in);
    setContactFormChannels(c.preferred_channels || ["sms", "whatsapp"]);
    setContactError(null);
    setShowContactModal(true);
  };

  // Save Contact (Create or Update)
  const handleSaveContact = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedElder) return;

    setSubmittingContact(true);
    setContactError(null);

    const payload = {
      full_name: contactFormName.trim(),
      role: contactFormRole,
      phone_e164: contactFormPhone.trim(),
      whatsapp_e164: contactFormWhatsapp.trim() || undefined,
      email: contactFormEmail.trim() || undefined,
      whatsapp_opt_in: contactFormWhatsappOptIn,
      preferred_channels: contactFormChannels,
    };

    try {
      const url = editingContact
        ? `/api/v1/elders/${selectedElder.id}/contacts/${editingContact.id}`
        : `/api/v1/elders/${selectedElder.id}/contacts`;
      const method = editingContact ? "PUT" : "POST";

      const res = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(errorData.detail || t("saveContactFailed"));
      }

      setShowContactModal(false);
      await fetchContacts();
    } catch (err) {
      setContactError(err instanceof Error ? err.message : t("saveContactFailed"));
    } finally {
      setSubmittingContact(false);
    }
  };

  // Delete Contact
  const handleDeleteContact = async (c: Contact) => {
    if (!selectedElder) return;
    if (!window.confirm(t("confirmDeleteContact", { name: c.full_name }))) return;

    try {
      const res = await fetch(`/api/v1/elders/${selectedElder.id}/contacts/${c.id}`, {
        method: "DELETE",
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        if (data.code === "LAST_CONTACT_CANNOT_BE_DELETED") {
          alert(t("lastContactCannotBeDeleted"));
          return;
        }
        throw new Error(data.detail || t("deleteContactFailed"));
      }

      await fetchContacts();
    } catch (err) {
      alert(err instanceof Error ? err.message : t("deleteContactFailed"));
    }
  };

  // Reorder contacts up or down
  const handleMoveOrder = async (index: number, direction: "up" | "down") => {
    if (!selectedElder) return;
    const targetIndex = direction === "up" ? index - 1 : index + 1;
    if (targetIndex < 0 || targetIndex >= contacts.length) return;

    const newOrder = [...contacts];
    const temp = newOrder[index];
    newOrder[index] = newOrder[targetIndex];
    newOrder[targetIndex] = temp;

    // Optimistic update
    setContacts(newOrder);

    try {
      const res = await fetch(`/api/v1/elders/${selectedElder.id}/contacts/reorder`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          contact_ids: newOrder.map((c) => c.id),
        }),
      });

      if (!res.ok) throw new Error(t("reorderFailed"));
      const updated = await res.json();
      setContacts(updated);
    } catch {
      await fetchContacts();
    }
  };

  // Trigger Test SOS
  const handleTriggerSos = async () => {
    if (!selectedElder) return;
    setTriggeringSos(true);
    setTriggerError(null);
    try {
      const res = await fetch("/api/v1/sos/trigger", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          elder_id: selectedElder.id,
          source: "web",
        }),
      });

      if (!res.ok) {
        throw new Error(t("triggerFailed"));
      }

      setShowTriggerModal(false);
      await fetchHistory();
      // Reload page state or let live banner handle active alert
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (err) {
      setTriggerError(err instanceof Error ? err.message : t("triggerFailed"));
    } finally {
      setTriggeringSos(false);
    }
  };

  if (!selectedElder) {
    return (
      <div className="bg-surface rounded-2xl p-8 text-center border border-border">
        <p className="text-text-secondary">{t("noElderSelected")}</p>
      </div>
    );
  }

  return (
    <div className="space-y-8 animate-in fade-in">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-text-primary tracking-tight">
            {t("pageTitle", { name: selectedElder.preferred_name || selectedElder.full_name })}
          </h1>
          <p className="text-sm text-text-secondary mt-1">
            {t("pageSubtitle")}
          </p>
        </div>

        {/* Trigger Test SOS button */}
        <button
          type="button"
          onClick={() => setShowTriggerModal(true)}
          className="inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-emergency text-white font-bold text-sm shadow-xs hover:bg-red-700 transition-colors self-start sm:self-auto"
        >
          <ShieldAlert className="w-4 h-4" />
          <span>{t("triggerTestSosButton")}</span>
        </button>
      </div>

      {/* SECTION 1: Emergency Contacts & Escalation Order */}
      <div className="bg-surface rounded-2xl p-6 sm:p-8 border border-border shadow-2xs space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-border pb-4">
          <div>
            <div className="flex items-center gap-2">
              <Users className="w-5 h-5 text-primary" />
              <h2 className="text-lg font-bold text-text-primary">
                {t("contactsSectionTitle")}
              </h2>
            </div>
            <p className="text-xs sm:text-sm text-text-secondary mt-1">
              {t("contactsSectionSubtitle")}
            </p>
          </div>

          <button
            type="button"
            onClick={handleOpenAddModal}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-primary text-white font-medium text-sm hover:bg-primary/90 transition-colors self-start sm:self-auto shadow-xs"
          >
            <Plus className="w-4 h-4" />
            <span>{t("addContactButton")}</span>
          </button>
        </div>

        {contactError && (
          <div className="p-3 bg-red-50 text-emergency text-sm rounded-xl border border-red-200">
            {contactError}
          </div>
        )}

        {loadingContacts ? (
          <div className="py-8 text-center text-text-secondary text-sm">
            {tCommon("loading")}
          </div>
        ) : contacts.length === 0 ? (
          <div className="py-8 text-center space-y-3">
            <p className="text-text-secondary text-sm">
              {t("noContactsYet")}
            </p>
            <button
              type="button"
              onClick={handleOpenAddModal}
              className="text-primary hover:underline text-sm font-semibold"
            >
              + {t("addFirstContactButton")}
            </button>
          </div>
        ) : (
          <div className="space-y-3">
            {contacts.map((contact, index) => {
              const isFirst = index === 0;
              const isLast = index === contacts.length - 1;

              return (
                <div
                  key={contact.id}
                  className="flex flex-col sm:flex-row sm:items-center justify-between p-4 rounded-xl border border-border bg-bg-app hover:bg-surface-muted/50 transition-colors gap-4"
                >
                  <div className="flex items-center gap-3">
                    {/* Escalation badge */}
                    <div
                      className={`w-9 h-9 rounded-full flex items-center justify-center font-bold text-sm shrink-0 ${
                        isFirst
                          ? "bg-red-100 text-emergency border border-red-200"
                          : "bg-surface text-text-secondary border border-border"
                      }`}
                    >
                      {contact.escalation_order}
                    </div>

                    <div>
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-bold text-text-primary text-base">
                          {contact.full_name}
                        </span>
                        {isFirst && (
                          <span className="bg-red-50 text-emergency text-xs font-bold px-2 py-0.5 rounded-full border border-red-200">
                            {t("primaryBadge")}
                          </span>
                        )}
                        <span className="bg-primary-soft text-primary text-xs font-medium px-2 py-0.5 rounded-full capitalize">
                          {t(`role_${contact.role}`)}
                        </span>
                      </div>

                      <div className="flex items-center gap-4 text-xs text-text-secondary mt-1 flex-wrap">
                        <span className="flex items-center gap-1 font-mono">
                          <Phone className="w-3.5 h-3.5 text-text-muted" />
                          {contact.phone_e164}
                        </span>
                        {contact.whatsapp_opt_in && (
                          <span className="text-emerald-700 font-medium">
                            ✓ {t("whatsappOptedIn")}
                          </span>
                        )}
                        <span className="text-text-muted">
                          Channels: {contact.preferred_channels.join(", ")}
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Actions & Ordering */}
                  <div className="flex items-center gap-1.5 self-end sm:self-center">
                    <button
                      type="button"
                      disabled={isFirst}
                      onClick={() => handleMoveOrder(index, "up")}
                      title={t("moveUpTooltip")}
                      aria-label={t("moveUpTooltip")}
                      className="p-1.5 rounded-lg border border-border hover:bg-surface disabled:opacity-30 disabled:pointer-events-none transition-colors"
                    >
                      <ArrowUp className="w-4 h-4 text-text-secondary" />
                    </button>
                    <button
                      type="button"
                      disabled={isLast}
                      onClick={() => handleMoveOrder(index, "down")}
                      title={t("moveDownTooltip")}
                      aria-label={t("moveDownTooltip")}
                      className="p-1.5 rounded-lg border border-border hover:bg-surface disabled:opacity-30 disabled:pointer-events-none transition-colors"
                    >
                      <ArrowDown className="w-4 h-4 text-text-secondary" />
                    </button>

                    <div className="w-px h-5 bg-border mx-1" />

                    <button
                      type="button"
                      onClick={() => handleOpenEditModal(contact)}
                      title={t("editTooltip")}
                      aria-label={t("editTooltip")}
                      className="p-1.5 rounded-lg border border-border hover:bg-surface text-text-secondary hover:text-text-primary transition-colors"
                    >
                      <Edit2 className="w-4 h-4" />
                    </button>
                    <button
                      type="button"
                      onClick={() => handleDeleteContact(contact)}
                      title={t("deleteTooltip")}
                      aria-label={t("deleteTooltip")}
                      className="p-1.5 rounded-lg border border-border hover:bg-red-50 text-text-secondary hover:text-emergency transition-colors"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* SECTION 2: SOS History (SOS-6) */}
      <div className="bg-surface rounded-2xl p-6 sm:p-8 border border-border shadow-2xs space-y-6">
        <div className="border-b border-border pb-4">
          <div className="flex items-center gap-2">
            <Clock className="w-5 h-5 text-text-secondary" />
            <h2 className="text-lg font-bold text-text-primary">
              {t("historySectionTitle")}
            </h2>
          </div>
          <p className="text-xs sm:text-sm text-text-secondary mt-1">
            {t("historySectionSubtitle")}
          </p>
        </div>

        {loadingHistory ? (
          <div className="py-8 text-center text-text-secondary text-sm">
            {tCommon("loading")}
          </div>
        ) : history.length === 0 ? (
          <div className="py-8 text-center text-text-secondary text-sm">
            {t("noSosHistory")}
          </div>
        ) : (
          <div className="space-y-4">
            {history.map((item) => {
              const triggeredTime = new Date(item.triggered_at).toLocaleString(
                locale === "hi" ? "hi-IN" : "en-US",
                {
                  dateStyle: "medium",
                  timeStyle: "short",
                }
              );

              return (
                <div
                  key={item.id}
                  className="p-5 rounded-xl border border-border bg-bg-app space-y-3"
                >
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                    <div className="flex items-center gap-2.5">
                      <span
                        className={`text-xs font-bold px-2.5 py-1 rounded-full uppercase tracking-wider ${
                          item.status === "active"
                            ? "bg-red-100 text-emergency border border-red-200 animate-pulse"
                            : item.status === "handled"
                            ? "bg-emerald-100 text-emerald-800 border border-emerald-200"
                            : "bg-amber-100 text-amber-800 border border-amber-200"
                        }`}
                      >
                        {item.status}
                      </span>
                      <span className="font-semibold text-text-primary text-sm">
                        {triggeredTime}
                      </span>
                      <span className="text-xs text-text-muted">
                        • {item.source === "device" ? t("sourceDevice") : t("sourceWeb")}
                      </span>
                    </div>

                    <div className="text-xs font-mono text-text-secondary">
                      {t("pressCountBadge", { count: item.press_count })}
                    </div>
                  </div>

                  {item.handled_at && (
                    <p className="text-xs text-text-secondary bg-surface p-2.5 rounded-lg border border-border">
                      <span className="font-semibold text-emerald-700">✓ {t("handledStatus")}: </span>
                      {new Date(item.handled_at).toLocaleString(locale === "hi" ? "hi-IN" : "en-US", {
                        dateStyle: "short",
                        timeStyle: "short",
                      })}
                    </p>
                  )}

                  {/* Attempts breakdown */}
                  {item.attempts && item.attempts.length > 0 && (
                    <div className="text-xs border-t border-border pt-2 space-y-1">
                      <p className="font-semibold text-text-secondary">
                        {t("escalationAttemptsLabel")}:
                      </p>
                      <div className="flex flex-wrap gap-2">
                        {item.attempts.map((att) => (
                          <span
                            key={att.id}
                            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-surface border border-border text-text-secondary text-xs"
                          >
                            <span className="font-medium text-text-primary">
                              {att.contact_name}
                            </span>
                            <span className="uppercase text-[10px] text-text-muted">
                              ({att.channel})
                            </span>
                            <span
                              className={`text-[10px] font-bold uppercase ${
                                att.status === "delivered"
                                  ? "text-emerald-700"
                                  : att.status === "failed"
                                  ? "text-emergency"
                                  : "text-amber-700"
                              }`}
                            >
                              {att.status}
                            </span>
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* MODAL: Add/Edit Emergency Contact */}
      {showContactModal && (
        <div
          role="dialog"
          aria-modal="true"
          className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4 animate-in fade-in"
        >
          <div className="bg-surface rounded-2xl max-w-lg w-full p-6 sm:p-8 shadow-2xl border border-border max-h-[90vh] overflow-y-auto">
            <div className="flex items-start justify-between gap-4 mb-4">
              <div>
                <h2 className="text-lg font-bold text-text-primary">
                  {editingContact ? t("editContactModalTitle") : t("addContactModalTitle")}
                </h2>
                <p className="text-xs text-text-secondary mt-0.5">
                  {t("contactModalSubtitle")}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setShowContactModal(false)}
                className="text-text-muted hover:text-text-primary p-1 rounded-lg"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {contactError && (
              <div className="p-3 bg-red-50 text-emergency text-sm rounded-xl mb-4 border border-red-200">
                {contactError}
              </div>
            )}

            <form onSubmit={handleSaveContact} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-text-secondary mb-1">
                  {t("contactFullNameLabel")} *
                </label>
                <input
                  type="text"
                  required
                  value={contactFormName}
                  onChange={(e) => setContactFormName(e.target.value)}
                  placeholder="e.g. Dr. Verma, Priya Sharma"
                  className="w-full px-3 py-2 rounded-xl border border-border bg-surface text-text-primary text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-text-secondary mb-1">
                  {t("contactRoleLabel")} *
                </label>
                <select
                  value={contactFormRole}
                  onChange={(e) =>
                    setContactFormRole(e.target.value as "family" | "doctor" | "neighbour")
                  }
                  className="w-full px-3 py-2 rounded-xl border border-border bg-surface text-text-primary text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                >
                  <option value="family">{t("role_family")}</option>
                  <option value="doctor">{t("role_doctor")}</option>
                  <option value="neighbour">{t("role_neighbour")}</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-text-secondary mb-1">
                  {t("contactPhoneLabel")} * (E.164 with country code)
                </label>
                <input
                  type="tel"
                  required
                  value={contactFormPhone}
                  onChange={(e) => setContactFormPhone(e.target.value)}
                  placeholder="+919876543210"
                  className="w-full px-3 py-2 rounded-xl border border-border bg-surface text-text-primary text-sm font-mono focus:outline-none focus:ring-2 focus:ring-primary"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-text-secondary mb-1">
                  {t("contactWhatsappLabel")} (optional, if different from phone)
                </label>
                <input
                  type="tel"
                  value={contactFormWhatsapp}
                  onChange={(e) => setContactFormWhatsapp(e.target.value)}
                  placeholder="+919876543210"
                  className="w-full px-3 py-2 rounded-xl border border-border bg-surface text-text-primary text-sm font-mono focus:outline-none focus:ring-2 focus:ring-primary"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-text-secondary mb-1">
                  {t("contactEmailLabel")} (optional)
                </label>
                <input
                  type="email"
                  value={contactFormEmail}
                  onChange={(e) => setContactFormEmail(e.target.value)}
                  placeholder="contact@example.com"
                  className="w-full px-3 py-2 rounded-xl border border-border bg-surface text-text-primary text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                />
              </div>

              <div className="pt-2">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={contactFormWhatsappOptIn}
                    onChange={(e) => setContactFormWhatsappOptIn(e.target.checked)}
                    className="w-4 h-4 text-primary rounded border-border focus:ring-primary"
                  />
                  <span className="text-xs text-text-secondary font-medium">
                    {t("whatsappOptInCheckbox")}
                  </span>
                </label>
              </div>

              <div className="flex justify-end gap-3 pt-4 border-t border-border">
                <button
                  type="button"
                  onClick={() => setShowContactModal(false)}
                  disabled={submittingContact}
                  className="px-4 py-2 rounded-xl text-sm font-medium text-text-secondary hover:bg-surface-muted transition-colors"
                >
                  {tCommon("cancel")}
                </button>
                <button
                  type="submit"
                  disabled={submittingContact}
                  className="px-5 py-2 rounded-xl text-sm font-semibold bg-primary hover:bg-primary/90 text-white shadow-xs transition-colors disabled:opacity-50"
                >
                  {submittingContact ? tCommon("loading") : tCommon("save")}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL: Trigger Test SOS Confirmation */}
      {showTriggerModal && (
        <div
          role="dialog"
          aria-modal="true"
          className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4 animate-in fade-in"
        >
          <div className="bg-surface rounded-2xl max-w-md w-full p-6 shadow-2xl border border-border">
            <div className="flex items-start justify-between gap-4 mb-4">
              <div className="flex items-center gap-2 text-emergency">
                <ShieldAlert className="w-6 h-6" />
                <h2 className="text-lg font-bold text-text-primary">
                  {t("triggerModalTitle")}
                </h2>
              </div>
              <button
                type="button"
                onClick={() => setShowTriggerModal(false)}
                className="text-text-muted hover:text-text-primary p-1 rounded-lg"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <p className="text-sm text-text-secondary mb-4 leading-relaxed">
              {t("triggerModalDesc", {
                name: selectedElder.preferred_name || selectedElder.full_name,
              })}
            </p>

            {triggerError && (
              <div className="p-3 bg-red-50 text-emergency text-sm rounded-xl mb-4 border border-red-200">
                {triggerError}
              </div>
            )}

            <div className="flex justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={() => setShowTriggerModal(false)}
                disabled={triggeringSos}
                className="px-4 py-2 rounded-xl text-sm font-medium text-text-secondary hover:bg-surface-muted transition-colors"
              >
                {tCommon("cancel")}
              </button>
              <button
                type="button"
                onClick={handleTriggerSos}
                disabled={triggeringSos}
                className="px-5 py-2 rounded-xl text-sm font-bold bg-emergency hover:bg-red-700 text-white shadow-xs transition-colors disabled:opacity-50 flex items-center gap-1.5"
              >
                <AlertTriangle className="w-4 h-4" />
                <span>{triggeringSos ? tCommon("loading") : t("confirmTriggerButton")}</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
