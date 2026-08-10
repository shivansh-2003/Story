import type { ReactNode } from "react";
import { Link, NavLink } from "react-router-dom";
import { useAuth } from "@/lib/auth";
import styles from "./AppShell.module.css";

export function AppShell({ children }: { children: ReactNode }) {
  const { logout, user } = useAuth();

  return (
    <div className={styles.shell}>
      <nav className={styles.nav}>
        <Link className={styles.wordmark} to="/">
          story<span>assistant</span>
        </Link>
        <div className={styles.navLinks}>
          <NavLink to="/" end className={({ isActive }) => (isActive ? styles.active : undefined)}>
            stories
          </NavLink>
          <NavLink to="/characters" className={({ isActive }) => (isActive ? styles.active : undefined)}>
            characters
          </NavLink>
          <span>{user?.email}</span>
          <button className={styles.signOut} onClick={logout}>
            sign out
          </button>
        </div>
      </nav>
      <main className={styles.main}>{children}</main>
    </div>
  );
}
