import Cookies from 'js-cookie';

export interface UserPayload {
  id: string;
  email: string;
  name: string;
  avatar?: string;
  provider?: 'credentials' | 'google';
  role?: string;
}

const TOKEN_KEY = 'semantic_auth_token';
const REFRESH_TOKEN_KEY = 'semantic_refresh_token';

// Create a client-side JWT token (Base64 signature for client state)
export function createJWTToken(user: UserPayload): string {
  const header = { alg: 'HS256', typ: 'JWT' };
  const payload = {
    ...user,
    iat: Math.floor(Date.now() / 1000),
    exp: Math.floor(Date.now() / 1000) + 7 * 24 * 60 * 60, // 7 days
  };

  const encodedHeader = btoa(JSON.stringify(header));
  const encodedPayload = btoa(
    unescape(encodeURIComponent(JSON.stringify(payload)))
  );
  const mockSignature = btoa(`sig_${Date.now()}`);

  return `${encodedHeader}.${encodedPayload}.${mockSignature}`;
}

export function parseJWTToken(token: string): UserPayload | null {
  try {
    const parts = token.split('.');
    if (parts.length !== 3) return null;

    // Convert Base64URL to standard Base64
    let base64 = parts[1].replace(/-/g, '+').replace(/_/g, '/');
    while (base64.length % 4 !== 0) {
      base64 += '=';
    }

    const payloadStr = decodeURIComponent(
      atob(base64)
        .split('')
        .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
        .join('')
    );
    const payload = JSON.parse(payloadStr);

    if (payload.exp && payload.exp * 1000 < Date.now()) {
      return null; // Expired
    }

    return {
      id: String(payload.sub || payload.id || `usr_${Date.now()}`),
      email: payload.email || '',
      name:
        payload.name ||
        payload.full_name ||
        payload.username ||
        payload.email ||
        'User',
      avatar: payload.avatar,
      provider: payload.provider || 'credentials',
      role: payload.role || 'analyst',
    };
  } catch (err) {
    console.error('Error parsing JWT:', err);
    return null;
  }
}

// ---- Access Token ----

export function getStoredToken(): string | null {
  if (typeof window === 'undefined') return null;
  return Cookies.get(TOKEN_KEY) || localStorage.getItem(TOKEN_KEY);
}

export function setStoredToken(token: string): void {
  if (typeof window === 'undefined') return;
  Cookies.set(TOKEN_KEY, token, { expires: 7, path: '/' });
  localStorage.setItem(TOKEN_KEY, token);
}

export function removeStoredToken(): void {
  if (typeof window === 'undefined') return;
  Cookies.remove(TOKEN_KEY, { path: '/' });
  localStorage.removeItem(TOKEN_KEY);
}

// ---- Refresh Token ----

export function getStoredRefreshToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem(REFRESH_TOKEN_KEY);
}

export function setStoredRefreshToken(token: string): void {
  if (typeof window === 'undefined') return;
  localStorage.setItem(REFRESH_TOKEN_KEY, token);
}

export function removeStoredRefreshToken(): void {
  if (typeof window === 'undefined') return;
  localStorage.removeItem(REFRESH_TOKEN_KEY);
}

export function removeStoredTokens(): void {
  removeStoredToken();
  removeStoredRefreshToken();
}
