import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useMemo, type ReactNode } from "react";

import { api, ApiError } from "../api/client";
import type { User } from "../api/types";

interface AuthState {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<User>;
  register: (body: {
    full_name: string;
    email: string;
    password: string;
    store_code_default: boolean;
  }) => Promise<User>;
  logout: () => Promise<void>;
  setUser: (user: User) => void;
}

const AuthContext = createContext<AuthState | null>(null);

async function fetchMe(): Promise<User | null> {
  try {
    return await api.me();
  } catch (e) {
    if (e instanceof ApiError && e.status === 401) return null;
    throw e;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["me"],
    queryFn: fetchMe,
    staleTime: 60_000,
    retry: false,
  });

  const setUser = useCallback((user: User | null) => queryClient.setQueryData(["me"], user), [queryClient]);

  const login = useCallback(
    async (email: string, password: string) => {
      const user = await api.login(email, password);
      setUser(user);
      return user;
    },
    [setUser],
  );

  const register = useCallback(
    async (body: { full_name: string; email: string; password: string; store_code_default: boolean }) => {
      const user = await api.register(body);
      setUser(user);
      return user;
    },
    [setUser],
  );

  const logout = useCallback(async () => {
    try {
      await api.logout();
    } finally {
      setUser(null);
      queryClient.removeQueries({ queryKey: ["history"] });
    }
  }, [setUser, queryClient]);

  const value = useMemo<AuthState>(
    () => ({ user: data ?? null, loading: isLoading, login, register, logout, setUser }),
    [data, isLoading, login, register, logout, setUser],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
