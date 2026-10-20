import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api } from "../api/client";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(() => sessionStorage.getItem("campus-pilot-token"));
  const [ready, setReady] = useState(!sessionStorage.getItem("campus-pilot-token"));

  useEffect(() => {
    if (!token) {
      setReady(true);
      return;
    }
    let active = true;
    api.get("/auth/me").then(({ data }) => {
      if (active) setUser(data);
    }).catch(() => {
      if (!active) return;
      sessionStorage.removeItem("campus-pilot-token");
      setToken(null);
    }).finally(() => {
      if (active) setReady(true);
    });
    return () => { active = false; };
  }, [token]);

  const signIn = useCallback(async (credentials) => {
    const body = new URLSearchParams({ username: credentials.email, password: credentials.password });
    const { data } = await api.post("/auth/login", body);
    sessionStorage.setItem("campus-pilot-token", data.access_token);
    setToken(data.access_token);
    setUser(data.user);
    return data.user;
  }, []);

  const register = useCallback(async (form) => {
    const { data } = await api.post("/auth/register", form);
    sessionStorage.setItem("campus-pilot-token", data.access_token);
    setToken(data.access_token);
    setUser(data.user);
    return data.user;
  }, []);

  const signOut = useCallback(() => {
    sessionStorage.removeItem("campus-pilot-token");
    setToken(null);
    setUser(null);
  }, []);

  const value = useMemo(() => ({ user, token, ready, signIn, register, signOut, setUser }), [
    user, token, ready, signIn, register, signOut,
  ]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}
