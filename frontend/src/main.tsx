import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { QueryClientProvider } from "@tanstack/react-query";
import { MotionConfig } from "motion/react";
import App from "./App.tsx";
import { AuthProvider } from "./lib/auth.tsx";
import { queryClient } from "./lib/queryClient.ts";
import { applyTheme, getTheme } from "./lib/theme.ts";
import "./styles/global.css";

applyTheme(getTheme());

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    {/* reducedMotion="user" is the one global escape hatch — every Motion
        animation in the app respects the OS setting without being audited
        and gated one by one. */}
    <MotionConfig reducedMotion="user">
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <AuthProvider>
            <App />
          </AuthProvider>
        </BrowserRouter>
      </QueryClientProvider>
    </MotionConfig>
  </StrictMode>,
);
