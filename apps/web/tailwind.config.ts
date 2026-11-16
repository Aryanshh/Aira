import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      fontSize: {
        "3xs": ["0.625rem", { lineHeight: "0.75rem" }], // 10px
        "2xs": ["0.6875rem", { lineHeight: "0.875rem" }], // 11px
      },
      colors: {
        background: "var(--bg)",
        "bg-app": "var(--bg)",
        surface: {
          DEFAULT: "var(--surface)",
          soft: "var(--surface-soft)",
          muted: "var(--surface-muted)",
        },
        "surface-muted": "var(--surface-muted)",
        text: {
          DEFAULT: "var(--text)",
          main: "var(--text)",
          primary: "var(--text-primary)",
          secondary: "var(--text-secondary)",
          muted: "var(--text-muted)",
        },
        "text-primary": "var(--text-primary)",
        "text-secondary": "var(--text-secondary)",
        "text-muted": "var(--text-muted)",
        primary: {
          DEFAULT: "var(--primary)",
          soft: "var(--primary-soft)",
          hover: "var(--primary-hover)",
        },
        secondary: {
          DEFAULT: "var(--secondary)",
          soft: "var(--secondary-soft)",
        },
        warning: {
          DEFAULT: "var(--warning)",
          bg: "var(--warning-bg)",
        },
        accent: {
          amber: "var(--accent-amber)",
          "amber-soft": "var(--accent-amber-soft)",
          emerald: "var(--accent-emerald)",
          "emerald-soft": "var(--accent-emerald-soft)",
          green: "#15803D",
          crimson: "#C62828",
          blue: "var(--accent-blue)",
          "blue-soft": "var(--accent-blue-soft)",
        },
        "accent-amber": "var(--accent-amber)",
        "accent-emerald": "var(--accent-emerald)",
        "accent-green": "#15803D",
        "accent-crimson": "#C62828",
        "accent-blue": "var(--accent-blue)",
        sos: {
          DEFAULT: "var(--sos)",
          soft: "var(--sos-soft)",
        },
        emergency: "var(--sos)",
        border: "var(--border)",
      },
      borderRadius: {
        card: "20px",
        btn: "16px",
        input: "14px",
      },
      fontFamily: {
        sans: ["var(--font-nunito)", "var(--font-noto-sans-devanagari)", "sans-serif"],
      },
      boxShadow: {
        soft: "0 4px 16px rgba(120, 80, 60, 0.08)",
        card: "0 6px 20px -2px rgba(90, 50, 30, 0.07), 0 2px 6px -1px rgba(90, 50, 30, 0.04)",
        glow: "0 0 24px rgba(181, 71, 47, 0.25)",
        "glow-sos": "0 0 30px rgba(198, 40, 40, 0.35)",
        xs: "0 1px 2px rgba(0, 0, 0, 0.05)",
        "2xs": "0 1px 1px rgba(0, 0, 0, 0.03)",
      },
    },
  },
  plugins: [require("@tailwindcss/forms")],
};

export default config;
