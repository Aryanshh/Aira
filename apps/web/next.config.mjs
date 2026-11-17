import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin("./i18n/request.ts");

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async redirects() {
    return [
      {
        source: "/:path*",
        has: [
          {
            type: "host",
            value: "airacare.vercel.app",
          },
        ],
        destination: "https://aira-live.vercel.app/:path*",
        permanent: true,
      },
      {
        source: "/:path*",
        has: [
          {
            type: "host",
            value: "aira-elder.vercel.app",
          },
        ],
        destination: "https://aira-live.vercel.app/:path*",
        permanent: true,
      },
      {
        source: "/:path*",
        has: [
          {
            type: "host",
            value: "aira-liart.vercel.app",
          },
        ],
        destination: "https://aira-live.vercel.app/:path*",
        permanent: true,
      },
    ];
  },
  async rewrites() {
    const apiBase = process.env.API_BASE_URL;
    // When running serverless on Vercel without external API_BASE_URL,
    // do NOT rewrite to localhost:8000 so the internal App Router Route Handler runs.
    if (!apiBase) {
      return [];
    }
    return [
      {
        source: "/api/v1/:path*",
        destination: `${apiBase}/api/v1/:path*`,
      },
      {
        source: "/health",
        destination: `${apiBase}/health`,
      },
      {
        source: "/ready",
        destination: `${apiBase}/ready`,
      },
    ];
  },
};

export default withNextIntl(nextConfig);
