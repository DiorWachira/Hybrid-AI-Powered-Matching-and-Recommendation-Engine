/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        obsidian: { DEFAULT: "#070A0F", surface: "#0D131F", card: "#141E30", border: "#233148", hover: "#1C293E" },
        spectral: { emerald: "#00F5D4", mint: "#10B981", amber: "#F59E0B", coral: "#FF6B6B", violet: "#8B5CF6", indigo: "#6366F1" },
      },
      backgroundImage: {
        "grid-pattern": "radial-gradient(circle at 1px 1px, rgba(255,255,255,0.05) 1px, transparent 0)",
        "wave-primary": "linear-gradient(135deg, rgba(0, 245, 212, 0.15) 0%, rgba(16, 185, 129, 0.05) 100%)",
        "wave-amber": "linear-gradient(135deg, rgba(245, 158, 11, 0.15) 0%, rgba(255, 107, 107, 0.05) 100%)",
        "wave-violet": "linear-gradient(135deg, rgba(139, 92, 246, 0.15) 0%, rgba(99, 102, 241, 0.05) 100%)",
        "card-gradient": "linear-gradient(180deg, rgba(20, 30, 48, 0.7) 0%, rgba(13, 19, 31, 0.9) 100%)",
      },
      backgroundSize: { "grid-sm": "24px 24px" },
      boxShadow: { "glow-emerald": "0 0 20px -5px rgba(0, 245, 212, 0.3)", "glow-amber": "0 0 20px -5px rgba(245, 158, 11, 0.3)", "glow-violet": "0 0 20px -5px rgba(139, 92, 246, 0.3)" },
      animation: { "pulse-slow": "pulse 4s cubic-bezier(0.4, 0, 0.6, 1) infinite", "wave-flow": "waveFlow 8s ease infinite" },
      keyframes: { waveFlow: { "0%, 100%": { backgroundPosition: "0% 50%" }, "50%": { backgroundPosition: "100% 50%" } } },
    },
  },
  plugins: [],
};