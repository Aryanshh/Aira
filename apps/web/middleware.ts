import createMiddleware from "next-intl/middleware";
import { NextRequest, NextResponse } from "next/server";
import { locales } from "./i18n/request";

const intlMiddleware = createMiddleware({
  locales,
  defaultLocale: "en",
  localePrefix: "always",
});

const protectedFamilyPaths = [
  "/status",
  "/medicines",
  "/sos",
  "/team",
  "/settings",
  "/elders",
  "/home",
];

const authPaths = ["/login", "/register", "/forgot-password", "/qr-login"];

function parseTokenPayload(token?: string): { role?: string; sub?: string } | null {
  if (!token) return null;
  try {
    const parts = token.split(".");
    if (parts.length !== 3) return null;
    const base64 = parts[1].replace(/-/g, "+").replace(/_/g, "/");
    const jsonStr = atob(base64);
    return JSON.parse(jsonStr);
  } catch {
    return null;
  }
}

export default async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Run next-intl middleware first
  const response = intlMiddleware(request);

  // Extract path without locale prefix
  const pathnameWithoutLocale = pathname.replace(/^\/(en|hi)/, "") || "/";
  const locale = pathname.match(/^\/(en|hi)/)?.[1] || "en";

  const token = request.cookies.get("access_token")?.value;
  const payload = parseTokenPayload(token);
  const isAuthenticated = Boolean(payload && payload.sub);
  const role = payload?.role;

  const isProtectedFamily = protectedFamilyPaths.some((p) => pathnameWithoutLocale.startsWith(p));
  const isElderView = pathnameWithoutLocale === "/elder" || pathnameWithoutLocale.startsWith("/elder/");
  const isAuthRoute = authPaths.some((p) => pathnameWithoutLocale.startsWith(p));

  // 1. Unauthenticated user trying to access protected family routes -> redirect to login
  if (isProtectedFamily && !isAuthenticated) {
    const loginUrl = new URL(`/${locale}/login`, request.url);
    loginUrl.searchParams.set("from", pathname);
    return NextResponse.redirect(loginUrl);
  }

  // 2. Unauthenticated user trying to access elder view -> redirect to login (elder tab)
  if (isElderView && !isAuthenticated) {
    const loginUrl = new URL(`/${locale}/login`, request.url);
    loginUrl.searchParams.set("tab", "elder");
    return NextResponse.redirect(loginUrl);
  }

  // 3. Authenticated user trying to access login/register
  // Allow accessing /register freely so users can always create a separate fresh account
  if (isAuthRoute && isAuthenticated && pathnameWithoutLocale !== "/register") {
    if (role === "elder") {
      return NextResponse.redirect(new URL(`/${locale}/elder`, request.url));
    }
    return NextResponse.redirect(new URL(`/${locale}/status`, request.url));
  }

  // 4. Elder trying to access family dashboard -> redirect to elder view
  if (isProtectedFamily && isAuthenticated && role === "elder") {
    return NextResponse.redirect(new URL(`/${locale}/elder`, request.url));
  }

  return response;
}

export const config = {
  // Match all request paths except for internal /api, /health, /ready, _next, static assets
  matcher: ["/((?!api|health|ready|_next|_vercel|.*\\..*).*)"],
};
