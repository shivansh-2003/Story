import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "@/lib/auth";
import { AppShell } from "./AppShell";

export function ProtectedRoute({ children }: { children: ReactNode }) {
  const { status } = useAuth();

  if (status === "loading") return null;
  if (status === "signed-out") return <Navigate to="/login" replace />;

  return <AppShell>{children}</AppShell>;
}
