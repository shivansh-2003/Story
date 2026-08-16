import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { LightTablePanel } from "@/features/auth/LightTablePanel";

export function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="grid min-h-full grid-cols-1 md:grid-cols-2">
      <div className="hidden md:block">
        <LightTablePanel />
      </div>
      <div className="flex items-center justify-center px-6 py-16">
        <div className="w-full max-w-sm">
          <Link to="/" className="font-display text-lg font-medium tracking-tight">
            story<span className="text-primary">assistant</span>
          </Link>
          <div className="mt-8">{children}</div>
        </div>
      </div>
    </div>
  );
}
