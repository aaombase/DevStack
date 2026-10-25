import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api, clearTokens, getTokens, setTokens } from "./api";

const AuthContext = createContext(null);
export const useAuth = () => useContext(AuthContext);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(Boolean(getTokens()));

  const logout = useCallback(() => {
    clearTokens();
    setUser(null);
  }, []);

  useEffect(() => {
    if (!getTokens()) return;
    api("/auth/me/")
      .then(setUser)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    window.addEventListener("devtrack:logout", logout);
    return () => window.removeEventListener("devtrack:logout", logout);
  }, [logout]);

  const login = async (username, password) => {
    const tokens = await api("/auth/token/", { method: "POST", body: { username, password }, auth: false });
    setTokens(tokens);
    setUser(await api("/auth/me/"));
  };

  const register = async (fields) => {
    await api("/auth/register/", { method: "POST", body: fields, auth: false });
    await login(fields.username, fields.password);
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}
