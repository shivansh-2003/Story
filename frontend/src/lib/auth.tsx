import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { apiFetch, clearToken, getToken, setToken } from "./apiFetch";
import type { User } from "./types";

type TokenResponse = { access_token: string; token_type: string };

type AuthContextValue = {
  user: User | null;
  status: "loading" | "signed-in" | "signed-out";
  login: (email: string, password: string) => Promise<void>;
  signup: (email: string, password: string) => Promise<void>;
  logout: () => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [status, setStatus] = useState<AuthContextValue["status"]>("loading");

  async function loadUser() {
    if (!getToken()) {
      setStatus("signed-out");
      return;
    }
    try {
      const me = await apiFetch<User>("/auth/me");
      setUser(me);
      setStatus("signed-in");
    } catch {
      setStatus("signed-out");
    }
  }

  useEffect(() => {
    loadUser();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function login(email: string, password: string) {
    const { access_token } = await apiFetch<TokenResponse>("/auth/login", {
      method: "POST",
      body: { email, password },
      skipAuth: true,
    });
    setToken(access_token);
    await loadUser();
  }

  async function signup(email: string, password: string) {
    const { access_token } = await apiFetch<TokenResponse>("/auth/signup", {
      method: "POST",
      body: { email, password },
      skipAuth: true,
    });
    setToken(access_token);
    await loadUser();
  }

  function logout() {
    clearToken();
    setUser(null);
    setStatus("signed-out");
  }

  return <AuthContext.Provider value={{ user, status, login, signup, logout }}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
