/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#edf7f1",
          100: "#d4efe0",
          200: "#a9dfc1",
          300: "#72c89a",
          400: "#40a976",
          500: "#1e6b4e",
          600: "#195a41",
          700: "#154835",
          800: "#11382a",
          900: "#0d2b20",
        },
        accent: {
          50: "#fff6ed",
          100: "#ffead4",
          200: "#ffd1a8",
          300: "#ffb070",
          400: "#ff8537",
          500: "#e8590c",
          600: "#d14505",
          700: "#ad3609",
          800: "#8c2d0f",
          900: "#732810",
        },
        warm: {
          50: "#faf8f5",
          100: "#f5f3f0",
          200: "#ebe7e2",
          300: "#d9d3cc",
          400: "#b8b0a5",
          500: "#9b9184",
          600: "#7d7367",
          700: "#655c52",
          800: "#544c44",
          900: "#48403a",
        },
      },
      fontFamily: {
        display: ['"Noto Serif SC"', "Georgia", "serif"],
        body: ['"Inter"', '"PingFang SC"', '"Microsoft YaHei"', "sans-serif"],
      },
      borderRadius: {
        "2xl": "1rem",
        "3xl": "1.5rem",
      },
      boxShadow: {
        card: "0 1px 3px rgba(0,0,0,0.04), 0 1px 2px rgba(0,0,0,0.06)",
        elevated: "0 4px 16px rgba(0,0,0,0.06), 0 1px 4px rgba(0,0,0,0.04)",
        nav: "1px 0 4px rgba(0,0,0,0.04)",
      },
    },
  },
  plugins: [],
};
