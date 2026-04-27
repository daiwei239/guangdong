/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        navy: "#063B7A",
        tech: "#0F73D9",
        cyanTech: "#0FA3B1",
        glowBlue: "#2F8CFF",
        textDeep: "#172033",
        textSoft: "#5D6B82"
      },
      boxShadow: {
        glass: "0 20px 50px rgba(15, 75, 150, 0.08)",
        glassHover: "0 28px 70px rgba(15, 75, 150, 0.14)"
      }
    }
  },
  plugins: []
};
