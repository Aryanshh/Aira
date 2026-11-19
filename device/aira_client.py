#!/usr/bin/env python3
"""
AIRA Webapp Synchronization Client (Raspberry Pi to FastAPI Backend)
Synchronizes:
  - Elder Profile & Credentials (Access Code: AIRA-7K3Q, PIN: 1234)
  - Today's Scheduled Medicines & Timings (/api/v1/elders/me/doses)
  - Dose Confirmation / Mark Taken (/api/v1/doses/{dose_id}/take)
  - Doctor & Emergency Contacts (/api/v1/elders/me/contacts)
  - Doctor Connect & Outbound Calling (/api/v1/elders/{elder_id}/contacts/{contact_id}/call)
  - Safety-Critical Emergency SOS (/api/v1/elders/me/sos)
  - Offline Resilience: Local JSON caching if backend is temporarily unreachable.
"""

from __future__ import annotations

import datetime
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional


CACHE_FILE = "/tmp/aira_sync_cache.json" if sys.platform != "win32" else os.path.join(os.environ.get("TEMP", "."), "aira_sync_cache.json")


class AiraApiClient:
    """
    Communicates with the AIRA FastAPI backend to keep hardware & AI
    in real-time sync with the caregiver/family web application.
    """

    def __init__(
        self,
        base_url: str | None = None,
        access_code: str | None = None,
        pin: str | None = None,
        device_label: str = "AIRA Raspberry Pi Hardware",
    ) -> None:
        # Default to environment variable or localhost:8000
        self.base_url = (base_url or os.environ.get("AIRA_API_URL") or "http://localhost:8000").rstrip("/")
        self.access_code = (access_code or os.environ.get("AIRA_ACCESS_CODE") or "AIRA-7K3Q").strip().upper()
        self.pin = (pin or os.environ.get("AIRA_PIN") or "1234").strip()
        self.device_label = device_label

        self.token: Optional[str] = None
        self.elder_id: Optional[str] = None
        self.profile: Dict[str, Any] = {}
        self.doses_cache: List[Dict[str, Any]] = []
        self.contacts_cache: List[Dict[str, Any]] = []
        self.doctor_contact: Optional[Dict[str, Any]] = None
        self.is_online = False

        # Load any previous offline cache on startup
        self._load_cache()

    def _load_cache(self) -> None:
        """Loads cached data from disk if available."""
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.profile = data.get("profile", {})
                    self.elder_id = self.profile.get("id")
                    self.doses_cache = data.get("doses", [])
                    self.contacts_cache = data.get("contacts", [])
                    self._update_doctor_from_contacts()
            except Exception:
                pass

    def _save_cache(self) -> None:
        """Saves current state to disk cache for offline resilience."""
        try:
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "profile": self.profile,
                        "doses": self.doses_cache,
                        "contacts": self.contacts_cache,
                        "updated_at": datetime.datetime.now().isoformat(),
                    },
                    f,
                    ensure_ascii=False,
                    indent=2,
                )
        except Exception:
            pass

    def _make_request(
        self,
        endpoint: str,
        method: str = "GET",
        payload: Optional[Dict[str, Any]] = None,
        auth_required: bool = True,
        timeout: float = 3.5,
    ) -> Optional[Any]:
        """HTTP helper using standard library urllib."""
        url = f"{self.base_url}{endpoint}"
        headers = {"Content-Type": "application/json"}
        if auth_required and self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        data_bytes = json.dumps(payload).encode("utf-8") if payload is not None else None
        req = urllib.request.Request(url, data=data_bytes, headers=headers, method=method)

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                self.is_online = True
                content = resp.read().decode("utf-8")
                return json.loads(content) if content else {}
        except urllib.error.HTTPError as e:
            if e.code == 401 and auth_required and endpoint != "/api/v1/auth/elder/login":
                # Token may have expired, re-login once
                if self.login():
                    headers["Authorization"] = f"Bearer {self.token}"
                    req = urllib.request.Request(url, data=data_bytes, headers=headers, method=method)
                    try:
                        with urllib.request.urlopen(req, timeout=timeout) as resp2:
                            content2 = resp2.read().decode("utf-8")
                            return json.loads(content2) if content2 else {}
                    except Exception:
                        pass
            return None
        except Exception:
            self.is_online = False
            return None

    def login(self) -> bool:
        """Authenticates with the backend as the elder using Access Code & PIN."""
        payload = {
            "access_code": self.access_code,
            "pin": self.pin,
            "device_label": self.device_label,
        }
        res = self._make_request("/api/v1/auth/elder/login", method="POST", payload=payload, auth_required=False)
        if res and "access_token" in res:
            self.token = res["access_token"]
            self.is_online = True
            # Refresh profile immediately
            self.fetch_profile()
            return True
        return False

    def fetch_profile(self) -> Dict[str, Any]:
        """Fetches the authenticated elder's profile."""
        res = self._make_request("/api/v1/elders/me/profile")
        if res and isinstance(res, dict):
            self.profile = res
            self.elder_id = res.get("id")
            self._save_cache()
            return self.profile
        return self.profile

    def get_preferred_name(self) -> str:
        """Returns elder's preferred name (e.g. 'Dadaji' or 'रमेश जी')."""
        if self.profile:
            pref = self.profile.get("preferred_name")
            if pref:
                return pref
            full = self.profile.get("full_name")
            if full:
                return full
        return "दादाजी"

    def fetch_doses(self) -> List[Dict[str, Any]]:
        """Fetches today's dose schedule for this elder from the webapp."""
        res = self._make_request("/api/v1/elders/me/doses")
        if res is not None and isinstance(res, list):
            self.doses_cache = res
            self._save_cache()
            return self.doses_cache
        return self.doses_cache

    def mark_dose_taken(self, dose_id: str) -> bool:
        """
        Marks a medicine dose as taken in the webapp backend.
        Immediately updates caregiver portal and elder dashboard with green checkmark!
        """
        res = self._make_request(f"/api/v1/doses/{dose_id}/take", method="POST")
        if res and isinstance(res, dict):
            # Update local cache status
            for d in self.doses_cache:
                if d.get("id") == dose_id:
                    d["status"] = "taken"
            self._save_cache()
            return True
        return False

    def mark_dose_skipped(self, dose_id: str, reason: str = "Elder requested skip") -> bool:
        """Marks dose skipped in the webapp backend."""
        payload = {"reason": reason}
        res = self._make_request(f"/api/v1/doses/{dose_id}/skip", method="POST", payload=payload)
        if res and isinstance(res, dict):
            for d in self.doses_cache:
                if d.get("id") == dose_id:
                    d["status"] = "skipped"
            self._save_cache()
            return True
        return False

    def fetch_contacts(self) -> List[Dict[str, Any]]:
        """Fetches emergency and doctor contacts from the webapp."""
        res = self._make_request("/api/v1/elders/me/contacts")
        if res is not None and isinstance(res, list):
            self.contacts_cache = res
            self._update_doctor_from_contacts()
            self._save_cache()
            return self.contacts_cache
        return self.contacts_cache

    def _update_doctor_from_contacts(self) -> None:
        """Extracts doctor contact from contacts list."""
        self.doctor_contact = None
        for c in self.contacts_cache:
            if c.get("role") == "doctor" and c.get("active", True):
                self.doctor_contact = c
                break
        # Fallback to first contact if no doctor specified
        if not self.doctor_contact and self.contacts_cache:
            self.doctor_contact = self.contacts_cache[0]

    def get_doctor_details(self) -> Optional[Dict[str, Any]]:
        """Returns doctor name, phone, and role."""
        if not self.doctor_contact:
            self.fetch_contacts()
        return self.doctor_contact

    def connect_doctor(self, channel: str = "sms", custom_text: Optional[str] = None) -> bool:
        """
        Connects elder with their doctor by triggering outbound alert / call via webapp backend.
        """
        if not self.elder_id or not self.doctor_contact:
            self.fetch_profile()
            self.fetch_contacts()

        if not self.elder_id or not self.doctor_contact:
            return False

        contact_id = self.doctor_contact.get("id")
        if not contact_id:
            return False

        if channel == "call":
            res = self._make_request(f"/api/v1/elders/{self.elder_id}/contacts/{contact_id}/call", method="POST")
        else:
            payload = {
                "channel": channel,
                "custom_text": custom_text or f"AIRA Voice Alert: Patient {self.get_preferred_name()} requests contact with their doctor.",
            }
            res = self._make_request(
                f"/api/v1/elders/{self.elder_id}/contacts/{contact_id}/message",
                method="POST",
                payload=payload,
            )
        return res is not None

    def trigger_sos(self, source: str = "voice_hardware") -> bool:
        """
        Triggers Emergency SOS in the webapp!
        Fires real-time alert, red banner, and escalation cascade across all caregiver screens.
        """
        res = self._make_request("/api/v1/elders/me/sos", method="POST", payload={"source": source})
        if res and isinstance(res, dict):
            return True

        # Fallback: public SOS trigger endpoint
        if self.elder_id:
            payload = {
                "elder_id": self.elder_id,
                "source": source,
            }
            res2 = self._make_request("/api/v1/sos/trigger", method="POST", payload=payload, auth_required=False)
            return res2 is not None
        return False

    def sync_all(self) -> bool:
        """Performs full sync of profile, doses, and contacts."""
        if not self.token:
            if not self.login():
                return False
        self.fetch_profile()
        self.fetch_doses()
        self.fetch_contacts()
        return True

    def get_due_or_upcoming_doses(self, window_minutes: int = 45) -> List[Dict[str, Any]]:
        """
        Returns doses that are currently scheduled around current time
        or are due for reminder.
        """
        now = datetime.datetime.now()
        current_time_str = now.strftime("%H:%M")
        now_dt = datetime.datetime.strptime(current_time_str, "%H:%M")

        due_doses: List[Dict[str, Any]] = []
        for d in self.doses_cache:
            if d.get("status") != "scheduled":
                continue

            sched_time_str = d.get("scheduled_time", "")
            if not sched_time_str:
                continue

            # Parse HH:MM:SS or HH:MM
            try:
                parts = sched_time_str.split(":")
                dose_time_str = f"{int(parts[0]):02d}:{int(parts[1]):02d}"
                dose_dt = datetime.datetime.strptime(dose_time_str, "%H:%M")
                diff_sec = (dose_dt - now_dt).total_seconds()
                diff_min = diff_sec / 60.0

                # Due if within window_minutes before or up to 60 minutes after
                if -60 <= diff_min <= window_minutes:
                    due_doses.append(d)
            except Exception:
                continue

        return due_doses

    def format_medicines_summary(self) -> str:
        """
        Formats a clean, conversational summary of today's medicines
        for injection into Gemini prompt or spoken output.
        """
        if not self.doses_cache:
            return "आज के लिए कोई निर्धारित दवाइयां नहीं मिलीं।"

        lines = []
        for d in self.doses_cache:
            name = d.get("medicine_name", "दवा")
            strength = d.get("strength", "")
            time_raw = d.get("scheduled_time", "")
            time_clean = time_raw[:5] if len(time_raw) >= 5 else time_raw
            status = d.get("status", "scheduled")
            instr = d.get("instructions") or ""

            status_hi = "ले ली गई है (Taken)" if status == "taken" else ("छूट गई (Missed)" if status == "missed" else "बाकी है (Pending)")
            lines.append(f"- {name} {strength} (समय: {time_clean}, स्थिति: {status_hi}){f' [नोट: {instr}]' if instr else ''}")

        return "\n".join(lines)


# Singleton instance
_client_instance: Optional[AiraApiClient] = None


def get_api_client(base_url: str | None = None, access_code: str | None = None, pin: str | None = None) -> AiraApiClient:
    """Returns singleton API client instance."""
    global _client_instance
    if _client_instance is None or base_url or access_code or pin:
        _client_instance = AiraApiClient(base_url=base_url, access_code=access_code, pin=pin)
    return _client_instance
