"use client";

import * as React from "react";
import { useLocale, useTranslations } from "next-intl";
import {
  Check,
  Copy,
  Mail,
  Pill,
  Plus,
  Shield,
  Trash2,
  UserCheck,
  UserPlus,
  Users,
} from "lucide-react";

import { useElder } from "@/components/elder-context";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

interface TeamMember {
  user_id: string;
  full_name: string;
  email: string;
  role: "caregiver" | "family";
  is_owner: boolean;
  can_manage_medicines: boolean;
  joined_at: string;
}

export default function CareTeamPage() {
  const t = useTranslations("team");
  const tCommon = useTranslations("common");
  const locale = useLocale();
  const { selectedElder, isLoading: elderLoading } = useElder();

  const [members, setMembers] = React.useState<TeamMember[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState("");

  // Invite modal/form state
  const [showInviteForm, setShowInviteForm] = React.useState(false);
  const [inviteEmail, setInviteEmail] = React.useState("");
  const [inviteRole, setInviteRole] = React.useState<"caregiver" | "family">("family");
  const [canManageMeds, setCanManageMeds] = React.useState(false);
  const [inviteLoading, setInviteLoading] = React.useState(false);
  const [inviteSuccessUrl, setInviteSuccessUrl] = React.useState("");
  const [copiedInvite, setCopiedInvite] = React.useState(false);

  const fetchTeam = React.useCallback(async () => {
    if (!selectedElder) return;
    setLoading(true);
    setError("");

    try {
      const res = await fetch(`/api/v1/elders/${selectedElder.id}/team`);
      if (res.ok) {
        const data: TeamMember[] = await res.json();
        setMembers(data);
      } else {
        setError(t("fetchFailed"));
      }
    } catch {
      setError(t("fetchFailed"));
    } finally {
      setLoading(false);
    }
  }, [selectedElder, t]);

  React.useEffect(() => {
    fetchTeam();
  }, [fetchTeam]);

  const handleSendInvite = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedElder) return;
    setInviteLoading(true);
    setError("");

    try {
      const res = await fetch(`/api/v1/elders/${selectedElder.id}/invites`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: inviteEmail.trim().toLowerCase(),
          role: inviteRole,
          can_manage_medicines: inviteRole === "caregiver" ? true : canManageMeds,
        }),
      });

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        setError(errorData.detail || t("inviteFailed"));
        setInviteLoading(false);
        return;
      }

      const data = await res.json();
      setInviteSuccessUrl(data.invite_url);
      setInviteEmail("");
      fetchTeam();
    } catch {
      setError(t("inviteFailed"));
    } finally {
      setInviteLoading(false);
    }
  };

  const handleRemoveMember = async (userId: string, isOwner: boolean) => {
    if (!selectedElder) return;
    if (isOwner && members.filter((m) => m.is_owner).length <= 1) {
      alert(t("cannotRemoveLastOwner"));
      return;
    }

    if (!confirm(t("confirmRemoveMember"))) {
      return;
    }

    try {
      const res = await fetch(`/api/v1/elders/${selectedElder.id}/team/${userId}`, {
        method: "DELETE",
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        alert(err.detail || t("removeFailed"));
        return;
      }

      fetchTeam();
    } catch {
      alert(t("removeFailed"));
    }
  };

  const copyInviteUrl = () => {
    if (!inviteSuccessUrl) return;
    navigator.clipboard.writeText(inviteSuccessUrl);
    setCopiedInvite(true);
    setTimeout(() => setCopiedInvite(false), 2000);
  };

  if (elderLoading || (!selectedElder && loading)) {
    return (
      <div className="flex items-center justify-center min-h-[300px]">
        <div className="w-8 h-8 rounded-full border-2 border-primary border-t-transparent animate-spin" />
      </div>
    );
  }

  if (!selectedElder) {
    return (
      <div className="text-center py-12">
        <h2 className="text-xl font-bold text-text-primary">{t("noElderSelected")}</h2>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-text-primary tracking-tight flex items-center gap-2">
            <Users className="w-6 h-6 text-primary" />
            <span>{t("title", { name: selectedElder.preferred_name || selectedElder.full_name })}</span>
          </h1>
          <p className="text-sm text-text-secondary mt-1">{t("subtitle")}</p>
        </div>

        {selectedElder.is_owner && (
          <Button
            type="button"
            onClick={() => {
              setShowInviteForm(true);
              setInviteSuccessUrl("");
            }}
            className="flex items-center gap-2"
          >
            <UserPlus className="w-4 h-4" />
            <span>{t("inviteButton")}</span>
          </Button>
        )}
      </div>

      {error && (
        <div className="p-3.5 rounded-xl bg-accent-crimson/10 border border-accent-crimson/20 text-accent-crimson text-sm font-medium">
          {error}
        </div>
      )}

      {/* Invite Member Card (if open) */}
      {showInviteForm && (
        <Card className="p-6 bg-surface border border-primary/30 shadow-md">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-bold text-text-primary flex items-center gap-2">
              <Mail className="w-5 h-5 text-primary" />
              <span>{t("inviteFormTitle")}</span>
            </h2>
            <button
              type="button"
              onClick={() => {
                setShowInviteForm(false);
                setInviteSuccessUrl("");
              }}
              className="text-text-secondary hover:text-text-primary text-sm font-medium"
            >
              {tCommon("cancel")}
            </button>
          </div>

          {inviteSuccessUrl ? (
            <div className="space-y-4 p-4 rounded-xl bg-accent-green/10 border border-accent-green/30">
              <div className="flex items-center gap-2 text-accent-green font-semibold text-sm">
                <Check className="w-5 h-5" />
                <span>{t("inviteCreatedSuccess")}</span>
              </div>
              <p className="text-xs text-text-secondary">{t("inviteLinkInstruction")}</p>
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  readOnly
                  value={inviteSuccessUrl}
                  className="flex-1 px-3 py-2 rounded-lg border border-border bg-surface text-xs font-mono select-all"
                />
                <Button type="button" size="sm" variant="outline" onClick={copyInviteUrl}>
                  {copiedInvite ? <Check className="w-4 h-4 text-accent-green" /> : <Copy className="w-4 h-4" />}
                  <span className="ml-1">{copiedInvite ? tCommon("copied") : tCommon("copy")}</span>
                </Button>
              </div>
              <div className="pt-2">
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    setInviteSuccessUrl("");
                    setShowInviteForm(false);
                  }}
                >
                  {tCommon("done")}
                </Button>
              </div>
            </div>
          ) : (
            <form onSubmit={handleSendInvite} className="space-y-4">
              <Input
                label={t("inviteEmailLabel")}
                type="email"
                placeholder="colleague@example.com"
                value={inviteEmail}
                onChange={(e) => setInviteEmail(e.target.value)}
                required
              />

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <label className="text-sm font-medium text-text-primary">{t("roleLabel")}</label>
                  <select
                    value={inviteRole}
                    onChange={(e) => setInviteRole(e.target.value as "caregiver" | "family")}
                    className="w-full px-4 py-2.5 rounded-xl border border-border bg-surface text-text-primary text-sm font-medium"
                  >
                    <option value="family">{t("roleFamily")}</option>
                    <option value="caregiver">{t("roleCaregiver")}</option>
                  </select>
                </div>

                <div className="flex items-center gap-3 pt-6">
                  <label className="flex items-center gap-2 text-sm text-text-primary cursor-pointer select-none">
                    <input
                      type="checkbox"
                      checked={inviteRole === "caregiver" || canManageMeds}
                      disabled={inviteRole === "caregiver"}
                      onChange={(e) => setCanManageMeds(e.target.checked)}
                      className="w-4 h-4 text-primary rounded border-border focus:ring-primary/20"
                    />
                    <span>{t("canManageMedicinesCheckbox")}</span>
                  </label>
                </div>
              </div>

              <div className="pt-2 flex justify-end gap-2">
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() => setShowInviteForm(false)}
                >
                  {tCommon("cancel")}
                </Button>
                <Button type="submit" isLoading={inviteLoading}>
                  {t("sendInviteButton")}
                </Button>
              </div>
            </form>
          )}
        </Card>
      )}

      {/* Team Members List */}
      <div className="space-y-3">
        {members.map((member) => (
          <Card
            key={member.user_id}
            className="p-4 sm:p-5 flex items-center justify-between gap-4 bg-surface border border-border shadow-2xs hover:border-border/80 transition-all"
          >
            <div className="flex items-center gap-3.5">
              <div className="w-10 h-10 rounded-full bg-primary-soft text-primary font-bold flex items-center justify-center shrink-0">
                {member.full_name.charAt(0).toUpperCase()}
              </div>

              <div>
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-semibold text-text-primary">{member.full_name}</span>
                  {member.is_owner && (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-accent-amber/15 text-accent-amber border border-accent-amber/30">
                      <Shield className="w-3 h-3" />
                      <span>{t("badgeOwner")}</span>
                    </span>
                  )}
                  <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-surface-muted text-text-secondary border border-border capitalize">
                    {member.role === "caregiver" ? t("roleCaregiver") : t("roleFamily")}
                  </span>
                  {member.can_manage_medicines && (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-accent-green/15 text-accent-green border border-accent-green/30">
                      <Pill className="w-3 h-3" />
                      <span>{t("canManageMedsBadge")}</span>
                    </span>
                  )}
                </div>
                <p className="text-xs text-text-secondary mt-0.5">{member.email}</p>
              </div>
            </div>

            {/* Actions */}
            {selectedElder.is_owner && (!member.is_owner || members.filter((m) => m.is_owner).length > 1) && (
              <button
                type="button"
                onClick={() => handleRemoveMember(member.user_id, member.is_owner)}
                className="p-2 rounded-lg text-text-secondary hover:text-accent-crimson hover:bg-accent-crimson/10 transition-colors"
                title={t("removeMemberTooltip")}
              >
                <Trash2 className="w-4 h-4" />
              </button>
            )}
          </Card>
        ))}
      </div>
    </div>
  );
}
