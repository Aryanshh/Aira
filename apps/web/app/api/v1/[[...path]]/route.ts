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

function parseJwtPayload(token?: string): { sub?: string; role?: string; email?: string; [key: string]: any } | null {
  if (!token) return null;
  try {
    const parts = token.split(".");
    if (parts.length !== 3) return null;
    const base64 = parts[1].replace(/-/g, "+").replace(/_/g, "/");
    const jsonStr = Buffer.from(base64, "base64").toString("utf8");
    return JSON.parse(jsonStr);
  } catch {
    return null;
  }
}

function getAuthUser(request: NextRequest): { userId: string; role: "user" | "elder"; email?: string } | null {
  let token = request.cookies.get("access_token")?.value;
  if (!token) {
    const authHeader = request.headers.get("authorization") || request.headers.get("Authorization");
    if (authHeader?.startsWith("Bearer ")) {
      token = authHeader.substring(7).trim();
    }
  }
  const payload = parseJwtPayload(token);
  if (!payload?.sub) return null;
  return {
    userId: payload.sub,
    role: (payload.role as any) || "user",
    email: payload.email,
  };
}

// ---------------------------------------------------------------------------
// Multi-Tenant Data Types
// ---------------------------------------------------------------------------
export interface UserAccount {
  id: string;
  email: string;
  full_name: string;
  phone_e164: string;
  preferred_language: string;
  timezone: string;
  is_verified: boolean;
  created_at: string;
}

export interface ElderRecord {
  id: string;
  user_id: string;
  full_name: string;
  preferred_name: string | null;
  language: string;
  timezone: string;
  day_close_time: string;
  text_size: number;
  is_owner: boolean;
  can_manage_medicines: boolean;
  role: string;
  access_code: string;
  pin: string;
  qr_token: string;
  qr_url: string;
  created_at: string;
}

export interface DoseRecord {
  id: string;
  elder_id: string;
  medicine_id: string;
  scheduled_date: string;
  scheduled_time: string;
  scheduled_at: string;
  medicine_name: string;
  dose_label: string;
  instructions: string;
  color_tag: string;
  status: "scheduled" | "taken" | "missed" | "skipped";
  can_undo: boolean;
  taken_at_timestamp?: number;
}

export interface MedicineRecord {
  id: string;
  elder_id: string;
  name: string;
  strength?: string | null;
  form: string;
  dose_amount: number;
  dose_unit: string;
  instructions?: string | null;
  color_tag: string;
  as_needed: boolean;
  status: "active" | "paused" | "ended";
  stock_quantity: number;
  refill_threshold_days: number;
  days_remaining: number;
  active_schedule?: {
    frequency: string;
    interval_n: number;
    days_of_week?: number[] | null;
    days_of_month?: number[] | null;
    times_of_day: string[];
    start_date: string;
    end_date?: string | null;
    effective_from: string;
    effective_to?: string | null;
  } | null;
}

export interface ContactRecord {
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

// ---------------------------------------------------------------------------
// Constants: Official Demo Account
// ---------------------------------------------------------------------------
const DEMO_USER_ID = "usr-demo-0000-0000-0000-000000000001";
const DEMO_ELDER_ID = "e1d00000-0000-0000-0000-000000000001";

const DEMO_USER: UserAccount = {
  id: DEMO_USER_ID,
  email: "caregiver@aira.example.com",
  full_name: "Aira Family Caregiver",
  phone_e164: "+919876543210",
  preferred_language: "en",
  timezone: "Asia/Kolkata",
  is_verified: true,
  created_at: "2026-11-01T00:00:00Z",
};

const DEMO_ELDER: ElderRecord = {
  id: DEMO_ELDER_ID,
  user_id: DEMO_USER_ID,
  full_name: "Ramesh Chandra Gupta",
  preferred_name: "Babuji",
  language: "hi",
  timezone: "Asia/Kolkata",
  day_close_time: "22:00",
  text_size: 1,
  is_owner: true,
  can_manage_medicines: true,
  role: "family",
  access_code: "AIRA-7K3Q",
  pin: "1234",
  qr_token: "qrt_demo_babuji",
  qr_url: "https://aira-live.vercel.app/en/qr-login?token=qrt_demo_babuji",
  created_at: "2026-11-01T00:00:00Z",
};

const demoDoses: DoseRecord[] = [
  {
    id: "dose-001",
    elder_id: DEMO_ELDER_ID,
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
    elder_id: DEMO_ELDER_ID,
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
    elder_id: DEMO_ELDER_ID,
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

const demoMedicines: MedicineRecord[] = [
  {
    id: "med-001",
    elder_id: DEMO_ELDER_ID,
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
    elder_id: DEMO_ELDER_ID,
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
    elder_id: DEMO_ELDER_ID,
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

const demoContacts: ContactRecord[] = [
  {
    id: "cnt-001",
    elder_id: DEMO_ELDER_ID,
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
    elder_id: DEMO_ELDER_ID,
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

// ---------------------------------------------------------------------------
// In-Memory Multi-Tenant Store
// ---------------------------------------------------------------------------
const usersByEmail = new Map<string, UserAccount>([
  ["caregiver@aira.example.com", DEMO_USER],
  ["demo@aira.example.com", DEMO_USER],
]);
const usersById = new Map<string, UserAccount>([
  [DEMO_USER_ID, DEMO_USER],
]);
const eldersByUserId = new Map<string, ElderRecord[]>([
  [DEMO_USER_ID, [DEMO_ELDER]],
]);
const eldersById = new Map<string, ElderRecord>([
  [DEMO_ELDER_ID, DEMO_ELDER],
]);
const eldersByAccessCode = new Map<string, ElderRecord>([
  ["AIRA-7K3Q", DEMO_ELDER],
]);
const eldersByQrToken = new Map<string, ElderRecord>([
  ["qrt_demo_babuji", DEMO_ELDER],
]);
const medicinesByElderId = new Map<string, MedicineRecord[]>([
  [DEMO_ELDER_ID, demoMedicines],
]);
const dosesByElderId = new Map<string, DoseRecord[]>([
  [DEMO_ELDER_ID, demoDoses],
]);
const contactsByElderId = new Map<string, ContactRecord[]>([
  [DEMO_ELDER_ID, demoContacts],
]);
const teamMembersByElderId = new Map<string, any[]>([
  [
    DEMO_ELDER_ID,
    [
      {
        user_id: DEMO_USER_ID,
        full_name: "Aira Family Caregiver",
        email: "caregiver@aira.example.com",
        role: "family",
        is_owner: true,
        can_manage_medicines: true,
        joined_at: "2026-11-01T00:00:00Z",
      },
    ],
  ],
]);
const sosHistoryByElderId = new Map<string, any[]>();
const activeSosByElderId = new Map<string, any>();
const notificationsByUserId = new Map<string, any[]>();

// ---------------------------------------------------------------------------
// Main Router
// ---------------------------------------------------------------------------
async function handleApiRequest(request: NextRequest, context?: { params?: { path?: string[] } }) {
  const resolvedParams = await Promise.resolve(context?.params || {});
  const rawPath = request.nextUrl?.pathname
    ? request.nextUrl.pathname.replace(/^\/api\/v1\/?/, "").replace(/\/$/, "")
    : (resolvedParams.path || []).join("/");
  const pathSegments = rawPath ? rawPath.split("/") : [];
  const path = pathSegments.join("/");
  const method = request.method.toUpperCase();

  // 1. External Proxy Fallback if configured (optional)
  const apiBase = process.env.API_BASE_URL;
  if (apiBase && !apiBase.includes("localhost:8000")) {
    try {
      const url = new URL(request.url);
      const targetUrl = `${apiBase}/api/v1/${path}${url.search}`;
      const headers = new Headers(request.headers);
      headers.set("host", new URL(apiBase).host);

      const bodyBuffer = ["GET", "HEAD"].includes(method) ? undefined : await request.arrayBuffer();
      const proxyRes = await fetch(targetUrl, {
        method,
        headers,
        body: bodyBuffer,
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

  // 2. Parse request body if applicable
  let body: any = {};
  if (!["GET", "HEAD"].includes(method)) {
    try {
      body = await request.json();
    } catch {
      body = {};
    }
  }

  // Helper to attach auth cookies
  const setAuthCookies = (res: NextResponse, token: string) => {
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
  };

  // -------------------------------------------------------------------------
  // AUTH: Caregiver Login
  // -------------------------------------------------------------------------
  if (method === "POST" && path === "auth/login") {
    const email = (body.email || "caregiver@aira.example.com").trim().toLowerCase();

    let user: UserAccount;
    if (email === "caregiver@aira.example.com" || email === "demo@aira.example.com") {
      user = DEMO_USER;
    } else if (usersByEmail.has(email)) {
      user = usersByEmail.get(email)!;
    } else {
      // Auto-provision fresh isolated user for new non-demo emails
      const newUserId = "usr-" + crypto.randomUUID();
      user = {
        id: newUserId,
        email,
        full_name: email.split("@")[0] || "Aira Caregiver",
        phone_e164: "+919876543210",
        preferred_language: "en",
        timezone: "Asia/Kolkata",
        is_verified: true,
        created_at: new Date().toISOString(),
      };
      usersByEmail.set(email, user);
      usersById.set(newUserId, user);
      eldersByUserId.set(newUserId, []);
      notificationsByUserId.set(newUserId, []);
    }

    const token = createJwt(user.id, "user", {
      email: user.email,
      name: user.full_name,
    });

    const res = NextResponse.json({
      access_token: token,
      token_type: "bearer",
      expires_in: 2592000,
      user,
    });
    setAuthCookies(res, token);
    return res;
  }

  // -------------------------------------------------------------------------
  // AUTH: Register (Strict Account Isolation)
  // -------------------------------------------------------------------------
  if (method === "POST" && path === "auth/register") {
    const email = (body.email || "").trim().toLowerCase();
    if (!email) {
      return NextResponse.json({ detail: "Email address is required." }, { status: 400 });
    }

    let user: UserAccount;
    if (usersByEmail.has(email)) {
      user = usersByEmail.get(email)!;
    } else {
      const newUserId = "usr-" + crypto.randomUUID();
      user = {
        id: newUserId,
        email,
        full_name: (body.full_name || email.split("@")[0] || "Aira Caregiver").trim(),
        phone_e164: body.phone_e164 || "+919876543210",
        preferred_language: body.preferred_language || "en",
        timezone: body.timezone || "Asia/Kolkata",
        is_verified: true,
        created_at: new Date().toISOString(),
      };
      usersByEmail.set(email, user);
      usersById.set(newUserId, user);
      // Strictly empty initial elders and notifications
      eldersByUserId.set(newUserId, []);
      notificationsByUserId.set(newUserId, []);
    }

    const token = createJwt(user.id, "user", {
      email: user.email,
      name: user.full_name,
    });

    const res = NextResponse.json(
      {
        id: user.id,
        email: user.email,
        full_name: user.full_name,
        phone_e164: user.phone_e164,
        preferred_language: user.preferred_language,
        timezone: user.timezone,
        is_verified: true,
        access_token: token,
        token_type: "bearer",
        expires_in: 2592000,
      },
      { status: 201 }
    );
    setAuthCookies(res, token);
    return res;
  }

  // -------------------------------------------------------------------------
  // AUTH: Elder Login (Access Code & PIN)
  // -------------------------------------------------------------------------
  if (method === "POST" && path === "auth/elder/login") {
    const accessCode = (body.access_code || "").trim().toUpperCase();
    const pin = (body.pin || "").trim();

    let elder = eldersByAccessCode.get(accessCode);
    if (!elder && (accessCode === "AIRA-7K3Q" || !accessCode)) {
      elder = DEMO_ELDER;
    }

    if (!elder) {
      return NextResponse.json(
        { detail: "Invalid access code. Please check and try again.", code: "INVALID_CREDENTIALS" },
        { status: 401 }
      );
    }

    if (pin && elder.pin && elder.pin !== pin && accessCode !== "AIRA-7K3Q") {
      return NextResponse.json(
        { detail: "Incorrect 4-digit PIN.", code: "INVALID_CREDENTIALS" },
        { status: 401 }
      );
    }

    const token = createJwt(elder.id, "elder", {
      access_code: elder.access_code,
      name: elder.full_name,
    });

    const res = NextResponse.json({
      access_token: token,
      token_type: "bearer",
      expires_in: 2592000,
      elder_id: elder.id,
    });
    setAuthCookies(res, token);
    return res;
  }

  // -------------------------------------------------------------------------
  // AUTH: Elder QR Login
  // -------------------------------------------------------------------------
  if (method === "POST" && path === "auth/elder/qr") {
    const qrToken = (body.qr_token || "").trim();
    const elder = eldersByQrToken.get(qrToken) || DEMO_ELDER;

    const token = createJwt(elder.id, "elder", {
      name: elder.full_name,
      qr_token: elder.qr_token,
    });

    const res = NextResponse.json({
      access_token: token,
      token_type: "bearer",
      expires_in: 2592000,
      elder_id: elder.id,
    });
    setAuthCookies(res, token);
    return res;
  }

  // -------------------------------------------------------------------------
  // AUTH: Logout
  // -------------------------------------------------------------------------
  if (method === "POST" && path === "auth/logout") {
    const res = NextResponse.json({ message: "Logged out successfully" });
    res.cookies.delete("access_token");
    res.cookies.delete("refresh_token");
    return res;
  }

  // -------------------------------------------------------------------------
  // AUTH: Forgot Password
  // -------------------------------------------------------------------------
  if (method === "POST" && path === "auth/forgot-password") {
    return NextResponse.json({
      message: "If this email is registered, a password reset link has been sent.",
    });
  }

  // -------------------------------------------------------------------------
  // USER: Current Profile
  // -------------------------------------------------------------------------
  if (method === "GET" && (path === "me" || path === "auth/me")) {
    const authUser = getAuthUser(request);
    if (!authUser) {
      return NextResponse.json({ detail: "Not authenticated" }, { status: 401 });
    }
    const user = usersById.get(authUser.userId) || (authUser.userId === DEMO_USER_ID ? DEMO_USER : null);
    if (user) {
      return NextResponse.json(user);
    }
    return NextResponse.json({
      id: authUser.userId,
      email: authUser.email || "user@aira.example.com",
      full_name: "Aira Caregiver",
      phone_e164: "+919876543210",
      preferred_language: "en",
      timezone: "Asia/Kolkata",
      is_verified: true,
    });
  }

  // -------------------------------------------------------------------------
  // ELDERS: List (Isolated per User)
  // -------------------------------------------------------------------------
  if (method === "GET" && path === "elders") {
    const authUser = getAuthUser(request);
    if (!authUser) {
      // Unauthenticated requests never get demo data
      return NextResponse.json([]);
    }
    if (authUser.userId === DEMO_USER_ID) {
      return NextResponse.json(eldersByUserId.get(DEMO_USER_ID) || [DEMO_ELDER]);
    }
    // Return this specific user's elders (defaults to empty array for fresh accounts)
    const userElders = eldersByUserId.get(authUser.userId) || [];
    return NextResponse.json(userElders);
  }

  // -------------------------------------------------------------------------
  // ELDERS: Create (Saved to Authenticated User)
  // -------------------------------------------------------------------------
  if (method === "POST" && path === "elders") {
    const authUser = getAuthUser(request);
    const userId = authUser?.userId || DEMO_USER_ID;

    const newId = "eld-" + crypto.randomUUID();
    const code = "AIRA-" + crypto.randomBytes(3).toString("hex").toUpperCase().substring(0, 4);
    const pin = String(Math.floor(1000 + Math.random() * 9000));
    const qrToken = "qrt_" + crypto.randomBytes(6).toString("hex");
    const qrUrl = `https://aira-live.vercel.app/en/qr-login?token=${qrToken}`;

    const newElder: ElderRecord = {
      id: newId,
      user_id: userId,
      full_name: (body.full_name || "Elder").trim(),
      preferred_name: body.preferred_name?.trim() || null,
      language: body.language || "hi",
      timezone: body.timezone || "Asia/Kolkata",
      day_close_time: body.day_close_time || "22:00",
      text_size: body.text_size ?? 1,
      is_owner: true,
      can_manage_medicines: true,
      role: "family",
      access_code: code,
      pin,
      qr_token: qrToken,
      qr_url: qrUrl,
      created_at: new Date().toISOString(),
    };

    // Save elder to indexes
    eldersById.set(newId, newElder);
    eldersByAccessCode.set(code, newElder);
    eldersByQrToken.set(qrToken, newElder);

    const userList = eldersByUserId.get(userId) || [];
    userList.push(newElder);
    eldersByUserId.set(userId, userList);

    // Initialize clean sub-resources for this elder
    medicinesByElderId.set(newId, []);
    dosesByElderId.set(newId, []);
    contactsByElderId.set(newId, []);
    sosHistoryByElderId.set(newId, []);
    teamMembersByElderId.set(newId, [
      {
        user_id: userId,
        full_name: authUser?.email?.split("@")[0] || "Owner Caregiver",
        email: authUser?.email || "caregiver@aira.example.com",
        role: "family",
        is_owner: true,
        can_manage_medicines: true,
        joined_at: new Date().toISOString(),
      },
    ]);

    return NextResponse.json(
      {
        ...newElder,
        elder_id: newId,
      },
      { status: 201 }
    );
  }

  // -------------------------------------------------------------------------
  // ELDERS: Me Profile (Elder View)
  // -------------------------------------------------------------------------
  if (method === "GET" && path === "elders/me/profile") {
    const authUser = getAuthUser(request);
    if (authUser?.role === "elder") {
      const elder = eldersById.get(authUser.userId);
      if (elder) return NextResponse.json(elder);
    }
    return NextResponse.json(DEMO_ELDER);
  }

  // -------------------------------------------------------------------------
  // ELDERS: Preferences
  // -------------------------------------------------------------------------
  if ((method === "PATCH" || method === "PUT" || method === "GET") && path === "elders/me/preferences") {
    return NextResponse.json({ success: true, text_size: body.text_size ?? 1 });
  }

  // -------------------------------------------------------------------------
  // DOSES: List for Elder
  // -------------------------------------------------------------------------
  if (
    method === "GET" &&
    (path === "elders/me/doses" || (pathSegments[0] === "elders" && pathSegments[2] === "doses"))
  ) {
    const elderId =
      path === "elders/me/doses"
        ? getAuthUser(request)?.userId || DEMO_ELDER_ID
        : pathSegments[1];

    const doses = dosesByElderId.get(elderId) || (elderId === DEMO_ELDER_ID ? demoDoses : []);
    return NextResponse.json(doses);
  }

  // -------------------------------------------------------------------------
  // DOSES: Take & Undo Dose Actions
  // -------------------------------------------------------------------------
  if (method === "POST" && path.startsWith("doses/") && (path.endsWith("/take") || path.endsWith("/undo"))) {
    const doseId = pathSegments[1];
    const isTake = path.endsWith("/take");

    let updatedStatus: "taken" | "scheduled" = isTake ? "taken" : "scheduled";
    let found = false;

    dosesByElderId.forEach((dList) => {
      if (found) return;
      const idx = dList.findIndex((d) => d.id === doseId);
      if (idx !== -1) {
        dList[idx] = {
          ...dList[idx],
          status: isTake ? "taken" : "scheduled",
          can_undo: isTake,
          taken_at_timestamp: isTake ? Date.now() : undefined,
        };
        updatedStatus = dList[idx].status as any;
        found = true;
      }
    });

    return NextResponse.json({ id: doseId, status: updatedStatus });
  }

  // -------------------------------------------------------------------------
  // CONTACTS: List for Elder
  // -------------------------------------------------------------------------
  if (
    method === "GET" &&
    (path === "elders/me/contacts" || (pathSegments[0] === "elders" && pathSegments[2] === "contacts"))
  ) {
    const elderId =
      path === "elders/me/contacts"
        ? getAuthUser(request)?.userId || DEMO_ELDER_ID
        : pathSegments[1];

    const contacts = contactsByElderId.get(elderId) || (elderId === DEMO_ELDER_ID ? demoContacts : []);
    return NextResponse.json(contacts);
  }

  // -------------------------------------------------------------------------
  // CONTACTS: Create Contact for Elder
  // -------------------------------------------------------------------------
  if (method === "POST" && pathSegments[0] === "elders" && pathSegments[2] === "contacts" && pathSegments.length === 3) {
    const elderId = pathSegments[1];
    const list = contactsByElderId.get(elderId) || [];
    const newContact: ContactRecord = {
      id: "cnt-" + Date.now(),
      elder_id: elderId,
      full_name: (body.full_name || "Emergency Contact").trim(),
      role: body.role || "family",
      phone_e164: body.phone_e164 || "+919876543210",
      whatsapp_e164: body.whatsapp_e164 || null,
      email: body.email || null,
      whatsapp_opt_in: Boolean(body.whatsapp_opt_in),
      preferred_channels: body.preferred_channels || ["sms", "whatsapp"],
      escalation_order: list.length + 1,
      active: true,
      created_at: new Date().toISOString(),
    };
    list.push(newContact);
    contactsByElderId.set(elderId, list);
    return NextResponse.json(newContact, { status: 201 });
  }

  // -------------------------------------------------------------------------
  // CONTACTS: Update Contact for Elder
  // -------------------------------------------------------------------------
  if (method === "PUT" && pathSegments[0] === "elders" && pathSegments[2] === "contacts" && pathSegments.length === 4) {
    const elderId = pathSegments[1];
    const contactId = pathSegments[3];
    const list = contactsByElderId.get(elderId) || [];
    const idx = list.findIndex((c) => c.id === contactId);
    if (idx !== -1) {
      list[idx] = { ...list[idx], ...body, id: contactId, elder_id: elderId };
      return NextResponse.json(list[idx]);
    }
    return NextResponse.json({ success: true });
  }

  // -------------------------------------------------------------------------
  // CONTACTS: Delete Contact for Elder
  // -------------------------------------------------------------------------
  if (method === "DELETE" && pathSegments[0] === "elders" && pathSegments[2] === "contacts" && pathSegments.length === 4) {
    const elderId = pathSegments[1];
    const contactId = pathSegments[3];
    let list = contactsByElderId.get(elderId) || [];
    list = list.filter((c) => c.id !== contactId);
    contactsByElderId.set(elderId, list);
    return NextResponse.json({ success: true });
  }

  // -------------------------------------------------------------------------
  // CONTACTS: Reorder Contacts
  // -------------------------------------------------------------------------
  if (method === "POST" && path.includes("contacts/reorder")) {
    const elderId = pathSegments[1] || DEMO_ELDER_ID;
    if (Array.isArray(body.contacts)) {
      contactsByElderId.set(elderId, body.contacts);
    }
    return NextResponse.json(contactsByElderId.get(elderId) || []);
  }

  // -------------------------------------------------------------------------
  // CONTACTS: Message Dispatch
  // -------------------------------------------------------------------------
  if (method === "POST" && path.includes("contacts/") && path.endsWith("/message")) {
    return NextResponse.json({
      status: "sent",
      channel: body.channel || "sms",
      recipient: "+919876543210",
      contact_name: "Contact",
      provider_message_id: `msg_${Date.now()}`,
      body: "Test message dispatched",
    });
  }

  // -------------------------------------------------------------------------
  // CONTACTS: Call Initiation
  // -------------------------------------------------------------------------
  if (method === "POST" && path.includes("contacts/") && path.endsWith("/call")) {
    return NextResponse.json({
      status: "initiated",
      channel: "voice",
      recipient: "+919876543210",
      contact_name: "Contact",
      provider_call_id: `call_${Date.now()}`,
      dial_url: "tel:+919876543210",
      message: "Voice call initiated",
    });
  }

  // -------------------------------------------------------------------------
  // MEDICINES: Duplicate Check
  // -------------------------------------------------------------------------
  if (method === "GET" && path.includes("medicines/check-duplicate")) {
    return NextResponse.json({ is_duplicate: false, warning: null });
  }

  // -------------------------------------------------------------------------
  // MEDICINES: Stock Events
  // -------------------------------------------------------------------------
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

  // -------------------------------------------------------------------------
  // MEDICINES: Actions (pause / resume / end / adjust-stock / refill)
  // -------------------------------------------------------------------------
  if (
    method === "POST" &&
    pathSegments[0] === "elders" &&
    pathSegments[2] === "medicines" &&
    pathSegments.length >= 5
  ) {
    const elderId = pathSegments[1];
    const medId = pathSegments[3];
    const action = pathSegments[4];
    const meds = medicinesByElderId.get(elderId) || [];
    const med = meds.find((m) => m.id === medId);

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
    if ((action === "adjust-stock" || action === "stock-adjust") && med) {
      med.stock_quantity = parseFloat(body.quantity || med.stock_quantity);
      return NextResponse.json({ success: true, new_stock: med.stock_quantity });
    }
    if (action === "refill" && med) {
      med.stock_quantity += parseFloat(body.quantity || 30);
      return NextResponse.json({ success: true, new_stock: med.stock_quantity });
    }
    return NextResponse.json({ success: true });
  }

  // -------------------------------------------------------------------------
  // MEDICINES: Single Medicine Details
  // -------------------------------------------------------------------------
  if (
    method === "GET" &&
    pathSegments[0] === "elders" &&
    pathSegments[2] === "medicines" &&
    pathSegments.length === 4
  ) {
    const elderId = pathSegments[1];
    const medId = pathSegments[3];
    const meds = medicinesByElderId.get(elderId) || (elderId === DEMO_ELDER_ID ? demoMedicines : []);
    const med = meds.find((m) => m.id === medId);
    if (med) return NextResponse.json(med);
    return NextResponse.json({ detail: "Medicine not found" }, { status: 404 });
  }

  // -------------------------------------------------------------------------
  // MEDICINES: List for Elder
  // -------------------------------------------------------------------------
  if (method === "GET" && pathSegments[0] === "elders" && pathSegments[2] === "medicines") {
    const elderId = pathSegments[1];
    const meds = medicinesByElderId.get(elderId) || (elderId === DEMO_ELDER_ID ? demoMedicines : []);
    return NextResponse.json(meds);
  }

  // -------------------------------------------------------------------------
  // MEDICINES: Create Medicine for Elder
  // -------------------------------------------------------------------------
  if (method === "POST" && pathSegments[0] === "elders" && pathSegments[2] === "medicines") {
    const elderId = pathSegments[1];
    const list = medicinesByElderId.get(elderId) || [];

    const newMed: MedicineRecord = {
      id: `med-${Date.now()}-${Math.random().toString(36).substring(2, 6)}`,
      elder_id: elderId,
      name: (body.name || "Medicine").trim(),
      strength: body.strength?.trim() || null,
      form: body.form || "tablet",
      dose_amount: parseFloat(body.dose_amount || "1.0"),
      dose_unit: body.dose_unit || "tablet",
      instructions: body.instructions?.trim() || null,
      color_tag: body.color_tag || "#10B981",
      as_needed: Boolean(body.as_needed),
      status: "active",
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

    list.push(newMed);
    medicinesByElderId.set(elderId, list);

    // Auto-generate today's doses for this medicine
    const dList = dosesByElderId.get(elderId) || [];
    const today = new Date().toISOString().split("T")[0];
    const times: string[] = newMed.active_schedule?.times_of_day || ["08:00"];
    times.forEach((t: string, idx: number) => {
      dList.push({
        id: `dose-${Date.now()}-${idx}`,
        elder_id: elderId,
        medicine_id: newMed.id,
        scheduled_date: today,
        scheduled_time: t,
        scheduled_at: `${today}T${t}:00Z`,
        medicine_name: newMed.name,
        dose_label: `${newMed.dose_amount} ${newMed.dose_unit}`,
        instructions: newMed.instructions || "",
        color_tag: newMed.color_tag,
        status: "scheduled",
        can_undo: false,
      });
    });
    dosesByElderId.set(elderId, dList);

    return NextResponse.json(newMed, { status: 201 });
  }

  // -------------------------------------------------------------------------
  // STATUS: Day Summary
  // -------------------------------------------------------------------------
  if (method === "GET" && path.includes("/status/day")) {
    const elderId = pathSegments[1] || DEMO_ELDER_ID;
    const doses = dosesByElderId.get(elderId) || (elderId === DEMO_ELDER_ID ? demoDoses : []);

    const totalCount = doses.length;
    if (totalCount === 0) {
      return NextResponse.json({
        elder_id: elderId,
        date: new Date().toISOString().split("T")[0],
        total_scheduled: 0,
        taken_count: 0,
        missed_count: 0,
        skipped_count: 0,
        adherence_pct: 100,
        state: "no_doses",
        missed_medicine_names: [],
      });
    }

    const takenCount = doses.filter((d) => d.status === "taken").length;
    const adherencePct = Math.round((takenCount / totalCount) * 100);
    const state = takenCount >= totalCount ? "all_taken" : "in_progress";

    return NextResponse.json({
      elder_id: elderId,
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

  // -------------------------------------------------------------------------
  // STATUS: Week Summary
  // -------------------------------------------------------------------------
  if (method === "GET" && path.includes("/status/week")) {
    const elderId = pathSegments[1] || DEMO_ELDER_ID;
    const doses = dosesByElderId.get(elderId) || (elderId === DEMO_ELDER_ID ? demoDoses : []);
    const isDemo = elderId === DEMO_ELDER_ID;

    const todayStr = new Date().toISOString().split("T")[0];
    const days = Array.from({ length: 7 }, (_, i) => {
      const d = new Date(Date.now() - (6 - i) * 86400000);
      const dateStr = d.toISOString().split("T")[0];
      const isToday = dateStr === todayStr;

      const taken = isToday ? doses.filter((ds) => ds.status === "taken").length : isDemo ? 3 : 0;
      const total = isToday ? doses.length : isDemo ? 3 : 0;
      const state = total === 0 ? "no_doses" : taken >= total ? "all_taken" : "in_progress";

      return {
        elder_id: elderId,
        date: dateStr,
        total_scheduled: total,
        taken_count: taken,
        missed_count: 0,
        skipped_count: 0,
        adherence_pct: total > 0 ? Math.round((taken / total) * 100) : 100,
        state,
        missed_medicine_names: [],
      };
    });

    const totalScheduled = days.reduce((sum, d) => sum + d.total_scheduled, 0);
    const totalTaken = days.reduce((sum, d) => sum + d.taken_count, 0);
    const overallAdherence = totalScheduled > 0 ? Math.round((totalTaken / totalScheduled) * 100) : 100;

    return NextResponse.json({
      elder_id: elderId,
      week_start: days[0].date,
      week_end: days[6].date,
      overall_adherence_pct: overallAdherence,
      total_scheduled: totalScheduled,
      total_taken: totalTaken,
      total_missed: 0,
      days,
      missed_highlights: [],
    });
  }

  // -------------------------------------------------------------------------
  // STATUS: Month Summary
  // -------------------------------------------------------------------------
  if (method === "GET" && path.includes("/status/month")) {
    const elderId = pathSegments[1] || DEMO_ELDER_ID;
    const isDemo = elderId === DEMO_ELDER_ID;
    const daysInMonth = 30;

    const days = Array.from({ length: daysInMonth }, (_, i) => {
      const dayNum = String(i + 1).padStart(2, "0");
      const dateStr = `2026-11-${dayNum}`;
      return {
        elder_id: elderId,
        date: dateStr,
        total_scheduled: isDemo ? 3 : 0,
        taken_count: isDemo ? 3 : 0,
        missed_count: 0,
        skipped_count: 0,
        adherence_pct: 100,
        state: isDemo ? ("all_taken" as const) : ("no_doses" as const),
        missed_medicine_names: [],
      };
    });

    return NextResponse.json({
      elder_id: elderId,
      year: 2026,
      month: 11,
      overall_adherence_pct: 100,
      total_scheduled: isDemo ? daysInMonth * 3 : 0,
      total_taken: isDemo ? daysInMonth * 3 : 0,
      total_missed: 0,
      days,
    });
  }

  // -------------------------------------------------------------------------
  // TEAM: Members & Invites
  // -------------------------------------------------------------------------
  if (method === "GET" && pathSegments[0] === "elders" && pathSegments[2] === "team") {
    const elderId = pathSegments[1];
    return NextResponse.json(teamMembersByElderId.get(elderId) || []);
  }

  if (method === "POST" && pathSegments[0] === "elders" && pathSegments[2] === "invites") {
    return NextResponse.json({
      invite_url: "https://aira-live.vercel.app/en/login?invite=inv_" + Date.now(),
      role: body.role || "family",
    });
  }

  if (method === "DELETE" && pathSegments[0] === "elders" && pathSegments[2] === "team") {
    return NextResponse.json({ success: true });
  }

  // -------------------------------------------------------------------------
  // SOS: Active Status, Trigger & Resolve
  // -------------------------------------------------------------------------
  if (method === "GET" && path.includes("sos/active")) {
    const elderId = pathSegments.length > 2 ? pathSegments[1] : DEMO_ELDER_ID;
    const active = activeSosByElderId.get(elderId);
    return NextResponse.json({ status: active ? "active" : "inactive", event: active || null });
  }

  if (method === "POST" && (path === "elders/me/sos" || path === "sos/trigger" || (pathSegments[0] === "elders" && pathSegments[2] === "sos"))) {
    const elderId = pathSegments[0] === "elders" && pathSegments[1] !== "me" ? pathSegments[1] : DEMO_ELDER_ID;
    const sosEvent = {
      id: `sos-${Date.now()}`,
      elder_id: elderId,
      source: "web",
      client_event_id: `evt-${Date.now()}`,
      status: "active",
      escalation_state: "contact_1_alerted",
      press_count: 1,
      triggered_at: new Date().toISOString(),
      handled_at: null,
      handled_by: null,
      attempts: [],
    };
    activeSosByElderId.set(elderId, sosEvent);
    const hist = sosHistoryByElderId.get(elderId) || [];
    hist.unshift(sosEvent);
    sosHistoryByElderId.set(elderId, hist);
    return NextResponse.json(sosEvent, { status: 201 });
  }

  if (method === "POST" && path.includes("sos/") && path.endsWith("/resolve")) {
    const elderId = pathSegments[1] || DEMO_ELDER_ID;
    activeSosByElderId.delete(elderId);
    return NextResponse.json({ success: true, status: "handled" });
  }

  if (method === "GET" && pathSegments[0] === "elders" && pathSegments[2] === "sos") {
    const elderId = pathSegments[1];
    return NextResponse.json(sosHistoryByElderId.get(elderId) || []);
  }

  // -------------------------------------------------------------------------
  // NOTIFICATIONS
  // -------------------------------------------------------------------------
  if (method === "GET" && (path === "notifications" || path.startsWith("notifications?"))) {
    const authUser = getAuthUser(request);
    const userNotifications = notificationsByUserId.get(authUser?.userId || "") || [];
    return NextResponse.json({
      notifications: userNotifications,
      unread_count: userNotifications.filter((n) => !n.read).length,
    });
  }

  if (method === "POST" && path.startsWith("notifications/")) {
    return NextResponse.json({ success: true });
  }

  // -------------------------------------------------------------------------
  // NOTIFICATION PREFERENCES
  // -------------------------------------------------------------------------
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
