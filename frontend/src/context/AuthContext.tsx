'use client';

import React, { createContext, useContext, useState, useEffect } from 'react';
import {
  UserPayload,
  parseJWTToken,
  getStoredToken,
  setStoredToken,
  removeStoredToken,
} from '@/lib/jwt';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

interface AuthContextType {
  user: UserPayload | null;
  token: string | null;
  isLoading: boolean;
  login: (email: string, pass: string) => Promise<boolean>;
  register: (name: string, email: string, pass: string) => Promise<boolean>;
  loginWithGoogle: (googleCredential: string) => Promise<boolean>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<UserPayload | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const checkAuth = async () => {
      const savedToken = getStoredToken();
      if (!savedToken) {
        setIsLoading(false);
        return;
      }

      const parsedUser = parseJWTToken(savedToken);
      if (!parsedUser) {
        removeStoredToken();
        setToken(null);
        setUser(null);
        setIsLoading(false);
        return;
      }

      try {
        const res = await fetch(`${API_BASE_URL}/api/v1/auth/me`, {
          headers: { Authorization: `Bearer ${savedToken}` },
        });

        if (res.ok) {
          const profile = await res.json();
          setToken(savedToken);
          setUser({
            id: String(profile.id),
            email: profile.email,
            name: profile.full_name || profile.username || profile.email,
            provider: 'credentials',
            role: profile.role || 'analyst',
          });
        } else if (res.status === 401) {
          removeStoredToken();
          setToken(null);
          setUser(null);
        } else {
          setToken(savedToken);
          setUser(parsedUser);
        }
      } catch (err) {
        console.warn('Backend verification check offline:', err);
        setToken(savedToken);
        setUser(parsedUser);
      } finally {
        setIsLoading(false);
      }
    };

    checkAuth();
  }, []);

  const login = async (email: string, pass: string): Promise<boolean> => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email_or_username: email, password: pass }),
      });

      if (res.ok) {
        const data = await res.json();
        const jwtToken = data.access_token;
        const apiUser: UserPayload = {
          id: String(data.user.id),
          email: data.user.email,
          name: data.user.name || data.user.username,
          provider: 'credentials',
          role: data.user.role || 'analyst',
        };
        setStoredToken(jwtToken);
        setToken(jwtToken);
        setUser(apiUser);
        return true;
      } else {
        const errorData = await res.json().catch(() => null);
        throw new Error(errorData?.detail || 'Đăng nhập không thành công');
      }
    } catch (err: any) {
      if (err.name === 'TypeError' || err.message === 'Failed to fetch') {
        throw new Error('Không thể kết nối đến máy chủ xác thực. Vui lòng kiểm tra lại mạng.');
      }
      throw err;
    }
  };

  const register = async (name: string, email: string, pass: string): Promise<boolean> => {
    try {
      const username = email.split('@')[0].replace(/[^a-zA-Z0-9_]/g, '_');
      const res = await fetch(`${API_BASE_URL}/api/v1/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email,
          username,
          password: pass,
          full_name: name,
        }),
      });

      if (res.ok) {
        const data = await res.json();
        const jwtToken = data.access_token;
        const apiUser: UserPayload = {
          id: String(data.user.id),
          email: data.user.email,
          name: data.user.name || name,
          provider: 'credentials',
          role: data.user.role || 'analyst',
        };
        setStoredToken(jwtToken);
        setToken(jwtToken);
        setUser(apiUser);
        return true;
      } else {
        const errorData = await res.json().catch(() => null);
        throw new Error(errorData?.detail || 'Đăng ký không thành công');
      }
    } catch (err: any) {
      if (err.name === 'TypeError' || err.message === 'Failed to fetch') {
        throw new Error('Không thể kết nối đến máy chủ xác thực. Vui lòng kiểm tra lại mạng.');
      }
      throw err;
    }
  };

  const loginWithGoogle = async (googleCredential: string): Promise<boolean> => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/auth/google`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ credential: googleCredential }),
      });

      if (res.ok) {
        const data = await res.json();
        const jwtToken = data.access_token;
        const apiUser: UserPayload = {
          id: String(data.user.id),
          email: data.user.email,
          name: data.user.name,
          provider: 'google',
          role: data.user.role || 'analyst',
        };
        setStoredToken(jwtToken);
        setToken(jwtToken);
        setUser(apiUser);
        return true;
      } else {
        const errorData = await res.json().catch(() => null);
        throw new Error(errorData?.detail || 'Xác thực Google không thành công');
      }
    } catch (err: any) {
      if (err.name === 'TypeError' || err.message === 'Failed to fetch') {
        throw new Error('Không thể kết nối đến máy chủ xác thực Google.');
      }
      throw err;
    }
  };

  const logout = async () => {
    const currentToken = token || getStoredToken();
    if (currentToken) {
      try {
        await fetch(`${API_BASE_URL}/api/v1/auth/logout`, {
          method: 'POST',
          headers: { Authorization: `Bearer ${currentToken}` },
        });
      } catch {
        // ignore network error on logout
      }
    }
    removeStoredToken();
    setToken(null);
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, token, isLoading, login, register, loginWithGoogle, logout }}>
      {children}
    </AuthContext.Provider>
  );
};

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
