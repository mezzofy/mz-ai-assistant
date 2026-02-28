import {SERVER_BASE_URL} from '../config';
import {getAccessToken, getRefreshToken, saveTokens, clearTokens} from '../storage/tokenStorage';

// ── Callback registration (breaks circular dep with authStore) ────────────────
let _onUnauthorized: (() => void) | null = null;

export function registerUnauthorizedHandler(handler: () => void): void {
  _onUnauthorized = handler;
}

// ── ApiError ──────────────────────────────────────────────────────────────────
export class ApiError extends Error {
  public readonly status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    Object.setPrototypeOf(this, ApiError.prototype); // Required for instanceof after TS transpile
  }
}

interface ApiFetchOptions extends RequestInit {
  skipAuth?: boolean;
}

// ── Internal helpers ──────────────────────────────────────────────────────────
async function _parseErrorMessage(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as {detail?: string; message?: string};
    return body.detail ?? body.message ?? response.statusText;
  } catch {
    return response.statusText;
  }
}

async function _rawFetch(
  path: string,
  options: ApiFetchOptions,
  accessToken: string | null,
): Promise<Response> {
  const {skipAuth, ...fetchOptions} = options;
  const headers = new Headers(fetchOptions.headers);
  if (!skipAuth && accessToken) {
    headers.set('Authorization', `Bearer ${accessToken}`);
  }
  // Do NOT set Content-Type for FormData — fetch sets it with boundary automatically
  if (!headers.has('Content-Type') && !(fetchOptions.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }
  return fetch(`${SERVER_BASE_URL}${path}`, {...fetchOptions, headers});
}

async function _attemptTokenRefresh(refreshToken: string): Promise<string> {
  // Calls /auth/refresh directly (NOT via auth.ts) to avoid circular import
  const response = await fetch(`${SERVER_BASE_URL}/auth/refresh`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({refresh_token: refreshToken}),
  });
  if (!response.ok) {
    throw new ApiError(401, 'Session expired. Please log in again.');
  }
  const data = (await response.json()) as {access_token: string};
  return data.access_token;
}

// ── Public: apiFetch ──────────────────────────────────────────────────────────
export async function apiFetch<T = unknown>(
  path: string,
  options: ApiFetchOptions = {},
): Promise<T> {
  const accessToken = options.skipAuth ? null : await getAccessToken();
  let response = await _rawFetch(path, options, accessToken);

  if (response.status === 401 && !options.skipAuth) {
    const storedRefresh = await getRefreshToken();
    if (!storedRefresh) {
      _onUnauthorized?.();
      throw new ApiError(401, 'Session expired. Please log in again.');
    }
    let newAccessToken: string;
    try {
      newAccessToken = await _attemptTokenRefresh(storedRefresh);
      await saveTokens(newAccessToken, storedRefresh); // Server does not rotate refresh tokens
    } catch {
      await clearTokens();
      _onUnauthorized?.();
      throw new ApiError(401, 'Session expired. Please log in again.');
    }
    response = await _rawFetch(path, options, newAccessToken); // Retry once
  }

  if (!response.ok) {
    const message = await _parseErrorMessage(response);
    throw new ApiError(response.status, message);
  }

  if (response.status === 204) {
    return undefined as T; // logout returns 204 No Content — no body to parse
  }

  return response.json() as Promise<T>;
}
