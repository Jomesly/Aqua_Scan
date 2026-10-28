import { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { api } from './api';

const AuthCtx = createContext(null);

export function AuthProvider({ children }) {
  const [state, setState] = useState({ user: null, system: null, loading: true });

  const refresh = useCallback(async () => {
    const [user, system] = await Promise.all([
      api.get('/api/auth/me').catch(() => null),
      api.get('/api/system').catch(() => null),
    ]);
    setState({ user, system, loading: false });
    return user;
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const login = async (username, password) => {
    const user = await api.post('/api/auth/login', { username, password });
    setState((s) => ({ ...s, user }));
    return user;
  };
  const logout = async () => {
    await api.post('/api/auth/logout').catch(() => {});
    setState((s) => ({ ...s, user: null }));
  };

  return <AuthCtx.Provider value={{ ...state, refresh, login, logout }}>{children}</AuthCtx.Provider>;
}

export const useAuth = () => useContext(AuthCtx);

export const can = {
  sample: (u) => u && (u.role === 'caretaker' || u.role === 'admin'),
  review: (u) => u && (u.role === 'technician' || u.role === 'admin'),
  evaluate: (u) => u && (u.role === 'technician' || u.role === 'admin'),
  admin: (u) => u && u.role === 'admin',
};

export const ROLE_LABEL = { caretaker: 'Caretaker', technician: 'Technician', admin: 'Administrator' };
