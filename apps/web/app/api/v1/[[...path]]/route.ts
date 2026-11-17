import { NextRequest, NextResponse } from "next/server";
import crypto from "crypto";

// Secret key for HMAC JWT signature verification
const JWT_SECRET = process.env.JWT_SECRET || "aira_super_secret_jwt_key_2026";

function createJwt(sub: string, role: "user" | "elder", extra: Record<string, any> = {}) {
  const header = Buffer.from(JSON.stringify({ alg: "HS256", typ: "JWT" })).toString("base64url");
  const payload = Buffer.from(
    JSON.stringify({
      sub,
      role,
      type: "access",
      iat: Math.floor(Date.now() / 1000),
      exp: Math.floor(Date.now() / 1000) + 86400 * 30, // 30 days
      ...extra,
    })
  ).toString("base64url");
  const signature = crypto
    .createHmac("sha256", JWT_SECRET)
    .update(`${header}.${payload}`)
    .digest("base64url");
  return `${header}.${payload}.${signature}`;
}

// In-memory persistent state across serverless instances in same container
let mockDoses = [
  {
    id: "dose-001",
    elder_id: "e1d00000-0000-0000-0000-000000000001",
    medicine_id: "med-001",
    scheduled_date: new Date().toISOString().split("T")[0],
    scheduled_time: "08:00",
    scheduled_at: `${new Date().toISOString().split("T")[0]}T08:00:00Z`,
    medicine_name: "Metformin",
    dose_label: "500mg - 1 tablet",
    instructions: "After breakfast with warm water",
    color_tag: "#10B981",
    status: "scheduled",
    can_undo: false,
  },
  {
    id: "dose-002",
    elder_id: "e1d00000-0000-0000-0000-000000000001",
    medicine_id: "med-002",
    scheduled_date: new Date().toISOString().split("T")[0],
    scheduled_time: "14:00",
    scheduled_at: `${new Date().toISOString().split("T")[0]}T14:00:00Z`,
    medicine_name: "Amlodipine",
    dose_label: "5mg - 1 tablet",
    instructions: "After lunch",
    color_tag: "#3B82F6",
    status: "scheduled",
    can_undo: false,
  },
  {
    id: "dose-003",
    elder_id: "e1d00000-0000-0000-0000-000000000001",
    medicine_id: "med-003",
    scheduled_date: new Date().toISOString().split("T")[0],
    scheduled_time: "20:30",
    scheduled_at: `${new Date().toISOString().split("T")[0]}T20:30:00Z`,
    medicine_name: "Atorvastatin",
    dose_label: "10mg - 1 tablet",
    instructions: "Before sleeping",
    color_tag: "#8B5CF6",
    status: "scheduled",
    can_undo: false,
  },
];

const mockElder = {
  id: "e1d00000-0000-0000-0000-000000000001",
  full_name: "Ramesh Chandra Gupta",
  preferred_name: "Babuji",
  language: "hi",
  timezone: "Asia/Kolkata",
  day_close_time: "22:00",
  text_size: 1,
  is_owner: true,
  can_manage_medicines: true,
  role: "family",
};

const mockContacts = [
  {
    id: "cnt-001",
    elder_id: "e1d00000-0000-0000-0000-000000000001",
    full_name: "Rahul Gupta",
    role: "family",
    phone_e164: "+919876543210",
    whatsapp_e164: "+919876543210",
    email: "rahul@example.com",
    whatsapp_opt_in: true,
    preferred_channels: ["sms", "whatsapp", "call"],
    escalation_order: 1,
    active: true,
    created_at: "2026-11-01T00:00:00Z",
  },
  {
    id: "cnt-002",
    elder_id: "e1d00000-0000-0000-0000-000000000001",
    full_name: "Dr. Sunita Verma",
    role: "doctor",
    phone_e164: "+919812345678",
    whatsapp_e164: "+919812345678",
    email: "dr.verma@example.com",
    whatsapp_opt_in: true,
    preferred_channels: ["sms", "call"],
    escalation_order: 2,
    active: true,
    created_at: "2026-11-01T00:00:00Z",
  },
];

let mockMedicines = [
  {
    id: "med-001",
    elder_id: "e1d00000-0000-0000-0000-000000000001",
    name: "Metformin",
    strength: "500mg",
    form: "tablet",
    dose_amount: 1,
    dose_unit: "tablet",
    instructions: "After breakfast with warm water",
    color_tag: "#10B981",
    as_needed: false,
    status: "active",
    stock_quantity: 45,
    refill_threshold_days: 7,
    days_remaining: 15,
    active_schedule: {
      frequency: "daily",
      interval_n: 1,
      days_of_week: [1, 2, 3, 4, 5, 6, 7],
      days_of_month: null,
      times_of_day: ["08:00"],
      start_date: "2026-11-01",
      end_date: null,
      effective_from: "2026-11-01",
      effective_to: null,
    },
  },
  {
    id: "med-002",
    elder_id: "e1d00000-0000-0000-0000-000000000001",
    name: "Amlodipine",
    strength: "5mg",
    form: "tablet",
    dose_amount: 1,
    dose_unit: "tablet",
    instructions: "After lunch",
    color_tag: "#3B82F6",
    as_needed: false,
    status: "active",
    stock_quantity: 30,
    refill_threshold_days: 7,
    days_remaining: 10,
    active_schedule: {
      frequency: "daily",
      interval_n: 1,
      days_of_week: [1, 2, 3, 4, 5, 6, 7],
      days_of_month: null,
      times_of_day: ["14:00"],
      start_date: "2026-11-01",
      end_date: null,
      effective_from: "2026-11-01",
      effective_to: null,
    },
  },
  {
    id: "med-003",
    elder_id: "e1d00000-0000-0000-0000-000000000001",
    name: "Atorvastatin",
    strength: "10mg",
    form: "tablet",
    dose_amount: 1,
    dose_unit: "tablet",
    instructions: "Before sleeping",
    color_tag: "#8B5CF6",
    as_needed: false,
    status: "active",
    stock_quantity: 28,
    refill_threshold_days: 7,
    days_remaining: 9,
    active_schedule: {
      frequency: "daily",
      interval_n: 1,
      days_of_week: [1, 2, 3, 4, 5, 6, 7],
      days_of_month: null,
      times_of_day: ["20:30"],
      start_date: "2026-11-01",
      end_date: null,
      effective_from: "2026-11-01",
      effective_to: null,
    },
  },
];

async function handleApiRequest(request: NextRequest, context?: { params?: { path?: string[] } }) {
  const resolvedParams = await Promise.resolve(context?.params || {});
  // Robust pathname derivation: use nextUrl pathname or fall back to resolved params
  const rawPath = request.nextUrl?.pathname
    ? request.nextUrl.pathname.replace(/^\/api\/v1\/?/, "").replace(/\/$/, "")
    : (resolvedParams.path || []).join("/");
  const pathSegments = rawPath ? rawPath.split("/") : [];
  const path = pathSegments.join("/");
  const method = request.method.toUpperCase();

  // 1. External Proxy Fallback if API_BASE_URL is configured
  const apiBase = process.env.API_BASE_URL;
  if (apiBase && !apiBase.includes("localhost:8000")) {
    try {
      const url = new URL(request.url);
      const targetUrl = `${apiBase}/api/v1/${path}${url.search}`;
      const headers = new Headers(request.headers);
      headers.set("host", new URL(apiBase).host);

      const body = ["GET", "HEAD"].includes(method) ? undefined : await request.arrayBuffer();
      const proxyRes = await fetch(targetUrl, {
        method,
        headers,
        body,
        redirect: "manual",
      });

      const responseHeaders = new Headers(proxyRes.headers);
      return new NextResponse(proxyRes.body, {
        status: proxyRes.status,
        statusText: proxyRes.statusText,
        headers: responseHeaders,
      });
    } catch {
      // Fall through to native handler
    }
  }

  // 2. Native Built-in API Handlers (Fast, Self-Contained, Zero-Config)
  let body: any = {};
  if (!["GET", "HEAD"].includes(method)) {
    try {
      body = await request.json();
    } catch {
      body = {};
    }
  }

  // AUTH: Caregiver Login
  if (method === "POST" && path === "auth/login") {
    const email = (body.email || "caregiver@aira.example.com").trim().toLowerCase();
    const token = createJwt("usr-0000-0000-0000-000000000001", "user", {
      email,
      name: "Aira Family Caregiver",
    });

    const res = NextResponse.json({
      access_token: token,
      token_type: "bearer",
      expires_in: 2592000,
    });

    res.cookies.set("access_token", token, {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      path: "/",
      maxAge: 30 * 86400,
    });
    res.cookies.set("refresh_token", token, {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      path: "/",
      maxAge: 30 * 86400,
    });

    return res;
  }

  // AUTH: Elder Login (PIN & Access Code)
  if (method === "POST" && path === "auth/elder/login") {
    const accessCode = (body.access_code || "AIRA-7K3Q").trim().toUpperCase();
    const token = createJwt(mockElder.id, "elder", {
      access_code: accessCode,
      name: mockElder.full_name,
    });

    const res = NextResponse.json({
      access_token: token,
      token_type: "bearer",
      expires_in: 2592000,
    });

    res.cookies.set("access_token", token, {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      path: "/",
      maxAge: 30 * 86400,
    });

    return res;
  }

  // AUTH: Elder QR Login
  if (method === "POST" && path === "auth/elder/qr") {
    const token = createJwt(mockElder.id, "elder", {
      name: mockElder.full_name,
    });

    const res = NextResponse.json({
      access_token: token,
      token_type: "bearer",
      expires_in: 2592000,
    });

    res.cookies.set("access_token", token, {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      path: "/",
      maxAge: 30 * 86400,
    });

    return res;
  }

  // AUTH: Register
  if (method === "POST" && path === "auth/register") {
    return NextResponse.json(
      {
        id: "usr-0000-0000-0000-000000000001",
        email: body.email || "caregiver@aira.example.com",
        full_name: body.full_name || "Aira Caregiver",
        phone_e164: body.phone_e164 || "+919876543210",
        preferred_language: body.preferred_language || "en",
        timezone: body.timezone || "Asia/Kolkata",
        is_verified: true,
      },
      { status: 201 }
    );
  }

  // AUTH: Logout
  if (method === "POST" && path === "auth/logout") {
    const res = NextResponse.json({ message: "Logged out successfully" });
    res.cookies.delete("access_token");
    res.cookies.delete("refresh_token");
    return res;
  }

  // AUTH: Forgot Password
  if (method === "POST" && path === "auth/forgot-password") {
    return NextResponse.json({
      message: "If this email is registered, a password reset link has been sent.",
    });
  }

  // USER: Current Profile
  if (method === "GET" && (path === "me" || path === "auth/me")) {
    return NextResponse.json({
      id: "usr-0000-0000-0000-000000000001",
      email: "caregiver@aira.example.com",
      full_name: "Aira Family Caregiver",
      phone_e164: "+919876543210",
      preferred_language: "en",
      timezone: "Asia/Kolkata",
      is_verified: true,
    });
  }

  // ELDERS: List
  if (method === "GET" && path === "elders") {
    return NextResponse.json([mockElder]);
  }

  // ELDERS: Create
  if (method === "POST" && path === "elders") {
    const newId = `e1d-${Date.now()}`;
    const code = "AIRA-" + Math.random().toString(36).substring(2, 6).toUpperCase();
    const pin = String(Math.floor(1000 + Math.random() * 9000));
    return NextResponse.json(
      {
        id: newId,
        elder_id: newId,
        full_name: body.full_name || "Elder",
        preferred_name: body.preferred_name || null,
        language: body.language || "hi",
        timezone: body.timezone || "Asia/Kolkata",
        day_close_time: body.day_close_time || "23:59",
        text_size: body.text_size ?? 1,
        is_owner: true,
        can_manage_medicines: true,
        access_code: code,
        pin,
        qr_token: `qrt_${Date.now()}`,
        qr_url: `https://aira-live.vercel.app/en/qr-login?token=qrt_${Date.now()}`,
      },
      { status: 201 }
    );
  }

  // ELDERS: Me Profile (Elder View)
  if (method === "GET" && path === "elders/me/profile") {
    return NextResponse.json(mockElder);
  }

  // ELDERS: Me Preferences
  if ((method === "PATCH" || method === "PUT" || method === "GET") && path === "elders/me/preferences") {
    return NextResponse.json({ success: true, text_size: body.text_size ?? 1 });
  }

  // DOSES: Me Doses (Elder View)
  if (method === "GET" && path === "elders/me/doses") {
    return NextResponse.json(mockDoses);
  }

  // DOSES: Take Dose
  if (method === "POST" && path.startsWith("doses/") && path.endsWith("/take")) {
    const doseId = pathSegments[1];
    mockDoses = mockDoses.map((d) =>
      d.id === doseId ? { ...d, status: "taken", can_undo: true, taken_at_timestamp: Date.now() } : d
    );
    return NextResponse.json({ id: doseId, status: "taken" });
  }

  // DOSES: Undo Dose
  if (method === "POST" && path.startsWith("doses/") && path.endsWith("/undo")) {
    const doseId = pathSegments[1];
    mockDoses = mockDoses.map((d) =>
      d.id === doseId ? { ...d, status: "scheduled", can_undo: false } : d
    );
    return NextResponse.json({ id: doseId, status: "scheduled" });
  }

  // CONTACTS: Me Contacts & Elder Contacts
  if (
    method === "GET" &&
    (path === "elders/me/contacts" || (pathSegments[0] === "elders" && pathSegments[2] === "contacts"))
  ) {
    return NextResponse.json(mockContacts);
  }

  // CONTACTS: Reorder
  if (method === "POST" && path.includes("contacts/reorder")) {
    return NextResponse.json(mockContacts);
  }

  // CONTACTS: Send Message
  if (method === "POST" && path.includes("contacts/") && path.endsWith("/message")) {
    return NextResponse.json({
      status: "sent",
      channel: body.channel || "sms",
      recipient: "+919876543210",
      contact_name: "Rahul Gupta",
      provider_message_id: `msg_${Date.now()}`,
      body: "Test message dispatched",
    });
  }

  // CONTACTS: Initiate Call
  if (method === "POST" && path.includes("contacts/") && path.endsWith("/call")) {
    return NextResponse.json({
      status: "initiated",
      channel: "voice",
      recipient: "+919876543210",
      contact_name: "Rahul Gupta",
      provider_call_id: `call_${Date.now()}`,
      dial_url: "tel:+919876543210",
      message: "Voice call initiated to Rahul Gupta",
    });
  }

  // MEDICINES: Duplicate check
  if (method === "GET" && path.includes("medicines/check-duplicate")) {
    return NextResponse.json({ is_duplicate: false, warning: null });
  }

  // MEDICINES: Stock events
  if (
    method === "GET" &&
    pathSegments[0] === "elders" &&
    pathSegments[2] === "medicines" &&
    pathSegments[4] === "stock-events"
  ) {
    const medId = pathSegments[3];
    return NextResponse.json([
      {
        id: "evt-001",
        medicine_id: medId,
        delta: 30,
        reason: "refill",
        note: "Pharmacy refill",
        created_by: "Caregiver",
        created_at: new Date(Date.now() - 3 * 86400000).toISOString(),
      },
      {
        id: "evt-002",
        medicine_id: medId,
        delta: -1,
        reason: "dose_taken",
        note: "Routine morning dose",
        created_by: "Elder",
        created_at: new Date(Date.now() - 86400000).toISOString(),
      },
    ]);
  }

  // MEDICINES: Actions (pause / resume / end / adjust-stock / refill)
  if (
    method === "POST" &&
    pathSegments[0] === "elders" &&
    pathSegments[2] === "medicines" &&
    pathSegments.length >= 5
  ) {
    const medId = pathSegments[3];
    const action = pathSegments[4];
    const med = mockMedicines.find((m) => m.id === medId);

    if (action === "pause" && med) {
      med.status = "paused";
      return NextResponse.json({ success: true, status: "paused" });
    }
    if (action === "resume" && med) {
      med.status = "active";
      return NextResponse.json({ success: true, status: "active" });
    }
    if (action === "end" && med) {
      med.status = "ended";
      return NextResponse.json({ success: true, status: "ended" });
    }
    if (action === "adjust-stock" && med) {
      med.stock_quantity = parseFloat(body.quantity || med.stock_quantity);
      return NextResponse.json({ success: true, new_stock: med.stock_quantity });
    }
    if (action === "refill" && med) {
      med.stock_quantity += parseFloat(body.quantity || 30);
      return NextResponse.json({ success: true, new_stock: med.stock_quantity });
    }
    return NextResponse.json({ success: true });
  }

  // MEDICINES: Single Medicine
  if (
    method === "GET" &&
    pathSegments[0] === "elders" &&
    pathSegments[2] === "medicines" &&
    pathSegments.length === 4
  ) {
    const medId = pathSegments[3];
    const med = mockMedicines.find((m) => m.id === medId) || mockMedicines[0];
    return NextResponse.json(med);
  }

  // MEDICINES: List
  if (method === "GET" && pathSegments[0] === "elders" && pathSegments[2] === "medicines") {
    return NextResponse.json(mockMedicines);
  }

  // MEDICINES: Create
  if (method === "POST" && pathSegments[0] === "elders" && pathSegments[2] === "medicines") {
    const newMed = {
      id: `med-${Date.now()}`,
      elder_id: mockElder.id,
      name: body.name || "Medicine",
      strength: body.strength || null,
      form: body.form || "tablet",
      dose_amount: parseFloat(body.dose_amount || "1.0"),
      dose_unit: body.dose_unit || "tablet",
      instructions: body.instructions || null,
      color_tag: body.color_tag || "#10B981",
      as_needed: Boolean(body.as_needed),
      status: "active" as const,
      stock_quantity: parseFloat(body.initial_stock || body.stock_quantity || "30.0"),
      refill_threshold_days: parseInt(body.refill_threshold || body.refill_threshold_days || "5", 10),
      days_remaining: 15,
      active_schedule: {
        frequency: body.frequency || "daily",
        interval_n: body.interval_n || 1,
        days_of_week: body.days_of_week || [1, 2, 3, 4, 5, 6, 7],
        days_of_month: body.days_of_month || null,
        times_of_day: body.times || body.times_of_day || ["08:00"],
        start_date: body.start_date || new Date().toISOString().split("T")[0],
        end_date: body.end_date || null,
        effective_from: body.effective_from || new Date().toISOString().split("T")[0],
        effective_to: null,
      },
    };
    mockMedicines.push(newMed);
    return NextResponse.json(newMed, { status: 201 });
  }

  // STATUS: Day
  if (method === "GET" && path.includes("/status/day")) {
    const takenCount = mockDoses.filter((d) => d.status === "taken").length;
    const totalCount = mockDoses.length;
    const adherencePct = totalCount > 0 ? Math.round((takenCount / totalCount) * 100) : 100;
    const state = (totalCount === 0 ? "no_doses" : takenCount >= totalCount ? "all_taken" : "in_progress") as
      | "all_taken"
      | "in_progress"
      | "has_missed"
      | "no_doses";
    return NextResponse.json({
      elder_id: mockElder.id,
      date: new Date().toISOString().split("T")[0],
      total_scheduled: totalCount,
      taken_count: takenCount,
      missed_count: 0,
      skipped_count: 0,
      adherence_pct: adherencePct,
      state,
      missed_medicine_names: [],
    });
  }

  // STATUS: Week
  if (method === "GET" && path.includes("/status/week")) {
    const todayStr = new Date().toISOString().split("T")[0];
    const days = Array.from({ length: 7 }, (_, i) => {
      const d = new Date(Date.now() - (6 - i) * 86400000);
      const dateStr = d.toISOString().split("T")[0];
      const isToday = dateStr === todayStr;
      const taken = isToday ? mockDoses.filter((d) => d.status === "taken").length : 3;
      const total = 3;
      return {
        elder_id: mockElder.id,
        date: dateStr,
        total_scheduled: total,
        taken_count: taken,
        missed_count: 0,
        skipped_count: 0,
        adherence_pct: Math.round((taken / total) * 100),
        state: (taken >= total ? "all_taken" : "in_progress") as "all_taken" | "in_progress",
        missed_medicine_names: [],
      };
    });
    return NextResponse.json({
      elder_id: mockElder.id,
      week_start: days[0].date,
      week_end: days[6].date,
      overall_adherence_pct: 100,
      total_scheduled: 21,
      total_taken: 21,
      total_missed: 0,
      days,
      missed_highlights: [],
    });
  }

  // STATUS: Month
  if (method === "GET" && path.includes("/status/month")) {
    const daysInMonth = 30;
    const days = Array.from({ length: daysInMonth }, (_, i) => {
      const dayNum = String(i + 1).padStart(2, "0");
      const dateStr = `2026-11-${dayNum}`;
      return {
        elder_id: mockElder.id,
        date: dateStr,
        total_scheduled: 3,
        taken_count: 3,
        missed_count: 0,
        skipped_count: 0,
        adherence_pct: 100,
        state: "all_taken" as const,
        missed_medicine_names: [],
      };
    });
    return NextResponse.json({
      elder_id: mockElder.id,
      year: 2026,
      month: 11,
      overall_adherence_pct: 100,
      total_scheduled: daysInMonth * 3,
      total_taken: daysInMonth * 3,
      total_missed: 0,
      days,
    });
  }

  // TEAM: Invites
  if (method === "POST" && pathSegments[0] === "elders" && pathSegments[2] === "invites") {
    return NextResponse.json({
      invite_url: "https://aira-live.vercel.app/en/login?invite=inv_demo_welcome",
      role: body.role || "family",
    });
  }

  // TEAM: Remove Member
  if (method === "DELETE" && pathSegments[0] === "elders" && pathSegments[2] === "team") {
    return NextResponse.json({ success: true });
  }

  // TEAM: Members
  if (method === "GET" && pathSegments[0] === "elders" && pathSegments[2] === "team") {
    return NextResponse.json([
      {
        user_id: "usr-0000-0000-0000-000000000001",
        full_name: "Aira Family Caregiver",
        email: "caregiver@aira.example.com",
        role: "family",
        is_owner: true,
        can_manage_medicines: true,
        joined_at: "2026-11-01T00:00:00Z",
      },
    ]);
  }

  // SOS: Active Status
  if (method === "GET" && path.includes("sos/active")) {
    return NextResponse.json({ status: "inactive" });
  }

  // SOS: Trigger & Active
  if (method === "POST" && (path === "elders/me/sos" || path === "sos/trigger")) {
    return NextResponse.json(
      {
        id: `sos-${Date.now()}`,
        elder_id: mockElder.id,
        source: "web",
        client_event_id: `evt-${Date.now()}`,
        status: "active",
        escalation_state: "contact_1_alerted",
        press_count: 1,
        triggered_at: new Date().toISOString(),
        handled_at: null,
        handled_by: null,
        attempts: [],
      },
      { status: 201 }
    );
  }

  // SOS: Resolve
  if (method === "POST" && path.includes("sos/") && path.endsWith("/resolve")) {
    return NextResponse.json({ success: true, status: "handled" });
  }

  // SOS: History
  if (method === "GET" && pathSegments[0] === "elders" && pathSegments[2] === "sos") {
    return NextResponse.json([]);
  }

  // NOTIFICATIONS: Inbox
  if (method === "GET" && (path === "notifications" || path.startsWith("notifications?"))) {
    return NextResponse.json({
      notifications: [],
      unread_count: 0,
    });
  }

  // NOTIFICATIONS: Actions
  if (method === "POST" && path.startsWith("notifications/")) {
    return NextResponse.json({ success: true });
  }

  // NOTIFICATION PREFERENCES
  if (path === "notification-preferences") {
    if (method === "GET") {
      return NextResponse.json({
        preferences: [
          { category: "sos", channel: "in_app", enabled: true },
          { category: "sos", channel: "push", enabled: true },
          { category: "sos", channel: "sms", enabled: true },
          { category: "sos", channel: "whatsapp", enabled: true },
          { category: "sos", channel: "email", enabled: false },
          { category: "missed", channel: "in_app", enabled: true },
          { category: "missed", channel: "push", enabled: true },
          { category: "missed", channel: "sms", enabled: false },
          { category: "missed", channel: "whatsapp", enabled: false },
          { category: "missed", channel: "email", enabled: false },
          { category: "refill", channel: "in_app", enabled: true },
          { category: "refill", channel: "push", enabled: true },
          { category: "refill", channel: "sms", enabled: false },
          { category: "refill", channel: "whatsapp", enabled: false },
          { category: "refill", channel: "email", enabled: false },
          { category: "system", channel: "in_app", enabled: true },
          { category: "system", channel: "push", enabled: false },
          { category: "system", channel: "sms", enabled: false },
          { category: "system", channel: "whatsapp", enabled: false },
          { category: "system", channel: "email", enabled: false },
        ],
        quiet_start: "22:00",
        quiet_end: "07:00",
      });
    }
    return NextResponse.json({ success: true });
  }

  // Default Fallback
  return NextResponse.json({ ok: true });
}

export async function GET(request: NextRequest, context?: { params?: { path?: string[] } }) {
  return handleApiRequest(request, context);
}

export async function POST(request: NextRequest, context?: { params?: { path?: string[] } }) {
  return handleApiRequest(request, context);
}

export async function PUT(request: NextRequest, context?: { params?: { path?: string[] } }) {
  return handleApiRequest(request, context);
}

export async function PATCH(request: NextRequest, context?: { params?: { path?: string[] } }) {
  return handleApiRequest(request, context);
}

export async function DELETE(request: NextRequest, context?: { params?: { path?: string[] } }) {
  return handleApiRequest(request, context);
}
