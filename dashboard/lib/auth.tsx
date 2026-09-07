'use client';

/**
 * lib/auth.tsx — session context backed by the httpOnly cookie.
 *
 * The Discord OAuth access token lives ONLY in an httpOnly cookie set
 * by app/api/auth/* route handlers (same-origin), so no client-side
 * JS can read it. The browser authenticates to the Flask API through
 * the /api/proxy/* route which attaches the bearer server-side.
 */

import { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { endpoints, ApiRequestError } from './api';
import type { DashboardUser, ManageableGuild } from './types';

interface AuthState {
  user: DashboardUser | null;
  guilds: ManageableGuild[] | null;
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthState>({
  user: null,
  guilds: null,
  loading: true,
  error: null,
  refresh: async () => {},
  logout: async () => {},
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<DashboardUser | null>(null);
  const [guilds, setGuilds] = useState<ManageableGuild[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await endpoints.user();
      setUser(res.user);
      setGuilds(res.guilds);
    } catch (e) {
      setUser(null);
      setGuilds(null);
      if (e instanceof ApiRequestError && e.status === 401) {
        setError('not logged in');
      } else {
        setError(e instanceof Error ? e.message : 'could not reach the api');
      }
    } finally {
      setLoading(false);
    }
  }, []);

  const logout = useCallback(async () => {
    try {
      await fetch('/api/auth/logout', { method: 'POST' });
    } catch {
      // ignore network errors on logout
    }
    setUser(null);
    setGuilds(null);
    window.location.href = '/';
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return (
    <AuthContext.Provider value={{ user, guilds, loading, error, refresh, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
