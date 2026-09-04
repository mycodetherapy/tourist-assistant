import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import type { UserInfo } from "../api/types";
import {
  fetchMe,
  login as apiLogin,
  logout as apiLogout,
  register as apiRegister,
} from "../api/auth";
import { clearLegacyAuthToken } from "../api/client";

interface AuthContextValue {
  user: UserInfo | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<number | undefined>;
  register: (email: string, password: string) => Promise<number | undefined>;
  logout: () => Promise<void>;
  completeLogin: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserInfo | null>(null);
  const [loading, setLoading] = useState(true);

  const refreshUser = useCallback(async () => {
    const me = await fetchMe();
    setUser(me);
    clearLegacyAuthToken();
  }, []);

  const completeLogin = useCallback(async () => {
    await refreshUser();
  }, [refreshUser]);

  const logout = useCallback(async () => {
    try {
      await apiLogout();
    } catch {
      /* cookie already gone */
    }
    clearLegacyAuthToken();
    setUser(null);
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const me = await fetchMe();
        if (!cancelled) {
          setUser(me);
          clearLegacyAuthToken();
        }
      } catch {
        if (!cancelled) {
          setUser(null);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback(
    async (email: string, password: string) => {
      const data = await apiLogin(email, password);
      await completeLogin();
      return data.claimed_trip_id;
    },
    [completeLogin],
  );

  const register = useCallback(
    async (email: string, password: string) => {
      const data = await apiRegister(email, password);
      await completeLogin();
      return data.claimed_trip_id;
    },
    [completeLogin],
  );

  const value = useMemo(
    () => ({
      user,
      loading,
      login,
      register,
      logout,
      completeLogin,
      refreshUser,
    }),
    [user, loading, login, register, logout, completeLogin, refreshUser],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth вне AuthProvider");
  }
  return ctx;
}
