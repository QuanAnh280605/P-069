'use client';

import React, { createContext, useContext, useState, useEffect } from 'react';
import {
  UserPayload,
  parseJWTToken,
  getStoredToken,
  setStoredToken,
  getStoredRefreshToken,
  setStoredRefreshToken,
  removeStoredTokens,
} from '@/lib/jwt';

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ||
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  'http://localhost:8000';

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

/** Call POST /auth/refresh and store new tokens. Returns new access token or null. */
async function refreshAccessToken(): Promise<string | null> {
  const refreshToken = getStoredRefreshToken();
  if (!refreshToken) return null;

  try {
    const res = await fetch(`${API_BASE_URL}/api/v1/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });

    if (!res.ok) return null;

    const data = await res.json();
    setStoredToken(data.access_token);
    setStoredRefreshToken(data.refresh_token);
    return data.access_token;
  } catch {
    return null;
  }
}

/** Fetch /auth/me with auto-refresh on 401. */
async function fetchUserProfile(
  accessToken: string
): Promise<{ profile: Record<string, unknown>; token: string } | null> {
  const doFetch = async (tok: string) =>
    fetch(`${API_BASE_URL}/api/v1/auth/me`, {
      headers: { Authorization: `Bearer ${tok}` },
    });

  let res = await doFetch(accessToken);

  // Auto-refresh on 401
  if (res.status === 401) {
    const newToken = await refreshAccessToken();
    if (newToken) {
      res = await doFetch(newToken);
      if (res.ok) {
        return { profile: await res.json(), token: newToken };
      }
    }
    return null; // refresh also failed
  }

  if (res.ok) {
    return { profile: await res.json(), token: accessToken };
  }
  return null;
}

/** Store both tokens from an auth API response. */
function storeAuthTokens(data: {
  access_token: string;
  refresh_token: string;
}): void {
  setStoredToken(data.access_token);
  setStoredRefreshToken(data.refresh_token);
}

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
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

      try {
        const result = await fetchUserProfile(savedToken);

        if (result) {
          const profile = result.profile as Record<string, unknown>;
          setToken(result.token);
          setUser({
            id: String(profile.id),
            email: profile.email as string,
            name:
              (profile.full_name as string) ||
              (profile.username as string) ||
              (profile.email as string),
            provider: 'credentials',
            role: (profile.role as string) || 'analyst',
          });
        } else {
          removeStoredTokens();
          setToken(null);
          setUser(null);
        }
      } catch (err) {
        console.warn('Backend verification check offline:', err);
        const parsedUser = parseJWTToken(savedToken);
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
        storeAuthTokens(data);
        setToken(data.access_token);
        setUser({
          id: String(data.user.id),
          email: data.user.email,
          name: data.user.name || data.user.username,
          provider: 'credentials',
          role: data.user.role || 'analyst',
        });
        return true;
      }

      const errorData = await res.json().catch(() => null);
      throw new Error(errorData?.detail || 'Login failed');
    } catch (err: unknown) {
      if (err instanceof TypeError || (err as Error).message === 'Failed to fetch') {
        throw new Error('Cannot connect to auth server. Check your network.');
      }
      throw err;
    }
  };

  const register = async (
    name: string,
    email: string,
    pass: string
  ): Promise<boolean> => {
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
        storeAuthTokens(data);
        setToken(data.access_token);
        setUser({
          id: String(data.user.id),
          email: data.user.email,
          name: data.user.name || name,
          provider: 'credentials',
          role: data.user.role || 'analyst',
        });
        return true;
      }

      const errorData = await res.json().catch(() => null);
      throw new Error(errorData?.detail || 'Registration failed');
    } catch (err: unknown) {
      if (err instanceof TypeError || (err as Error).message === 'Failed to fetch') {
        throw new Error('Cannot connect to auth server. Check your network.');
      }
      throw err;
    }
  };

  const loginWithGoogle = async (
    googleCredential: string
  ): Promise<boolean> => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/auth/google`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ credential: googleCredential }),
      });

      if (res.ok) {
        const data = await res.json();
        storeAuthTokens(data);
        setToken(data.access_token);
        setUser({
          id: String(data.user.id),
          email: data.user.email,
          name: data.user.name,
          provider: 'google',
          role: data.user.role || 'analyst',
        });
        return true;
      }

      const errorData = await res.json().catch(() => null);
      throw new Error(errorData?.detail || 'Google authentication failed');
    } catch (err: unknown) {
      if (err instanceof TypeError || (err as Error).message === 'Failed to fetch') {
        throw new Error('Cannot connect to Google auth server.');
      }
      throw err;
    }
  };

  const logout = async () => {
    const refreshToken = getStoredRefreshToken();
    if (refreshToken) {
      try {
        await fetch(`${API_BASE_URL}/api/v1/auth/logout`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh_token: refreshToken }),
        });
      } catch {
        // ignore network error on logout
      }
    }
    removeStoredTokens();
    setToken(null);
    setUser(null);
  };

  return (
    <AuthContext.Provider
      value={{ user, token, isLoading, login, register, loginWithGoogle, logout }}
    >
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
