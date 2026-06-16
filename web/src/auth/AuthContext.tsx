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
import { fetchMe, login as apiLogin, register as apiRegister } from "../api/auth";
import { getAuthToken, setAuthToken, TOKEN_KEY } from "../api/client";

interface AuthContextValue {
  user: UserInfo | null;
  token: string | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => void;
  setTokenFromOAuth: (token: string) => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserInfo | null>(null);
  const [token, setToken] = useState<string | null>(() => localStorage.getItem(TOKEN_KEY));
  const [loading, setLoading] = useState(true);

  const applySession = useCallback(async (accessToken: string) => {
    setAuthToken(accessToken);
    setToken(accessToken);
    const me = await fetchMe();
    setUser(me);
  }, []);

  const logout = useCallback(() => {
    setAuthToken(null);
    setToken(null);
    setUser(null);
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (!token) {
        setLoading(false);
        return;
      }
      try {
        setAuthToken(getAuthToken() ?? token);
        const me = await fetchMe();
        if (!cancelled) {
          setUser(me);
        }
      } catch {
        if (!cancelled) {
          logout();
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
  }, [token, logout]);

  const login = useCallback(
    async (email: string, password: string) => {
      const data = await apiLogin(email, password);
      await applySession(data.access_token);
    },
    [applySession],
  );

  const register = useCallback(
    async (email: string, password: string) => {
      const data = await apiRegister(email, password);
      await applySession(data.access_token);
    },
    [applySession],
  );

  const setTokenFromOAuth = useCallback(
    async (accessToken: string) => {
      await applySession(accessToken);
    },
    [applySession],
  );

  const value = useMemo(
    () => ({
      user,
      token,
      loading,
      login,
      register,
      logout,
      setTokenFromOAuth,
    }),
    [user, token, loading, login, register, logout, setTokenFromOAuth],
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
