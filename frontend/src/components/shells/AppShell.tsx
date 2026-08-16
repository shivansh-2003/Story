import { useState, type ReactNode } from "react";
import { Link, NavLink, useNavigate } from "react-router-dom";
import { LogOut, Moon, Sun } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";
import { getTheme, setTheme } from "@/lib/theme";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Monogram } from "@/components/Monogram";

const navLinkClass = ({ isActive }: { isActive: boolean }) =>
  cn(
    "text-sm font-medium transition-colors",
    isActive ? "text-primary" : "text-muted-foreground hover:text-foreground",
  );

export function AppShell({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [theme, setThemeState] = useState(getTheme());

  function toggleTheme() {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    setThemeState(next);
  }

  // Signing out otherwise falls through to ProtectedRoute's signed-out
  // redirect, which lands on /login — a dead end with no way back to the
  // public landing page. Send them there directly instead.
  function handleLogout() {
    logout();
    navigate("/");
  }

  return (
    <div className="flex min-h-full flex-col bg-background">
      <header className="sticky top-0 z-10 border-b border-border bg-background/80 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-[1200px] items-center justify-between px-6">
          <Link to="/" className="font-display text-lg font-medium tracking-tight">
            story<span className="text-primary">assistant</span>
          </Link>
          <nav className="flex items-center gap-6">
            <NavLink to="/library" className={navLinkClass}>
              Library
            </NavLink>
            <NavLink to="/cast" className={navLinkClass}>
              Cast
            </NavLink>
            <DropdownMenu>
              <DropdownMenuTrigger className="-m-1.5 flex size-11 items-center justify-center rounded-full outline-none focus-visible:ring-2 focus-visible:ring-primary/60 focus-visible:ring-offset-2 focus-visible:ring-offset-background">
                <Monogram seed={user?.id ?? ""} label={user?.email ?? "?"} size="sm" />
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuLabel className="font-mono text-xs font-normal text-muted-foreground">
                  {user?.email}
                </DropdownMenuLabel>
                <DropdownMenuItem onSelect={toggleTheme}>
                  {theme === "dark" ? <Sun /> : <Moon />} {theme === "dark" ? "Light mode" : "Dark mode"}
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem onSelect={handleLogout} variant="destructive">
                  <LogOut /> Sign out
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </nav>
        </div>
      </header>
      <main className="mx-auto w-full max-w-[1200px] flex-1 px-6 py-8">{children}</main>
    </div>
  );
}
