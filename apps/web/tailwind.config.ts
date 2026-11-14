import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "var(--bg)",
        surface: {
          DEFAULT: "var(--surface)",
          soft: "var(--surface-soft)",
        },
        text: {
          main: "var(--text)",
          muted: "var(--text-muted)",
        },
        primary: {
          DEFAULT: "var(--primary)",
          soft: "var(--primary-soft)",
        },
        secondary: {
          DEFAULT: "var(--secondary)",
          soft: "var(--secondary-soft)",
        },
        warning: {
          DEFAULT: "var(--warning)",
          bg: "var(--warning-bg)",
        },
        sos: "var(--sos)",
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
      },
    },
  },
  plugins: [require("@tailwindcss/forms")],
};

export default config;
