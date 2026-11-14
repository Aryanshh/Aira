import createMiddleware from "next-intl/middleware";
import { locales } from "./i18n/request";

export default createMiddleware({
  locales,
  defaultLocale: "en",
  localePrefix: "always",
});

export const config = {
  // Match all request paths except for internal /api, _next, static assets
  matcher: ["/((?!api|_next|_vercel|.*\\..*).*)"],
};
