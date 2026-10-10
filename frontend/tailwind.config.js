/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#111827",
        muted: "#4B5563",
        line: "#D1D5DB",
        surface: "#FFFFFF",
        canvas: "#F3F4F6",
        brand: "#1F2937",
        "sev-critical": "#991B1B",
        "sev-high": "#C2410C",
        "sev-medium": "#92400E",
        "sev-medium-bg": "#FEF3C7",
        "sev-low": "#1E40AF",
        "sev-low-bg": "#DBEAFE",
      },
      fontFamily: {
        sans: [
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Roboto",
          "Helvetica Neue",
          "Arial",
          "sans-serif",
        ],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "Consolas", "monospace"],
      },
    },
  },
  plugins: [],
};
