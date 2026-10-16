"use client";

import * as React from "react";
import { api } from "@/lib/api";
import type { User } from "@/lib/types";

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  refresh: () => Promise<void>;
  setUser: (user: User | null) => void;
}

const AuthContext = React.createContext<AuthContextValue>({
  user: null,
  loading: true,
  refresh: async () => undefined,
  setUser: () => undefined,
});

/**
 * Client-side session state.
 *
 * The session lives in an httpOnly cookie, so it is resolved after hydration
 * rather than during SSR. That keeps the first paint fast and avoids leaking
 * any token into the HTML.
 */
export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = React.useState<User | null>(null);
  const [loading, setLoading] = React.useState(true);

  const refresh = React.useCallback(async () => {
    try {
      const me = await api.me();
      setUser(me);
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    void refresh();
  }, [refresh]);

  const value = React.useMemo(
    () => ({ user, loading, refresh, setUser }),
    [user, loading, refresh],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return React.useContext(AuthContext);
}

/** Stable per-browser id used to tie click events to a session. */
export function useSessionId(): string | null {
  const [id, setId] = React.useState<string | null>(null);
  React.useEffect(() => {
    const key = "zexrdealhub-session";
    let value = window.localStorage.getItem(key);
    if (!value) {
      value = Math.random().toString(36).slice(2) + Date.now().toString(36);
      window.localStorage.setItem(key, value);
    }
    setId(value);
  }, []);
  return id;
}