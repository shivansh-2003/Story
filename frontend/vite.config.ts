import { fileURLToPath, URL } from "node:url";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  server: {
    // fail loudly if 5173 is taken instead of silently drifting to another
    // port — a drifted port isn't in the backend's CORS allow-list, which
    // fails as an opaque "Failed to fetch" in the browser with no clear cause.
    port: 5173,
    strictPort: true,
  },
});
