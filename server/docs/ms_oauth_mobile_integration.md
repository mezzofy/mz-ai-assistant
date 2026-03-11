# MS OAuth Mobile Integration Guide
**Feature:** Personal Microsoft Account (Delegated OAuth)
**Version:** 1.0
**Date:** 2026-03-11

This guide explains how the mobile app integrates with the MS delegated OAuth flow to allow users to connect their personal Microsoft accounts (Outlook, Calendar, OneNote, Teams).

---

## 1. Overview

The AI assistant uses **per-user delegated OAuth 2.0** (not app-level credentials) so that:
- Emails, calendar events, notes, and chats come from **the user's own account**
- The AI sends messages **as the user**, not as a service bot
- Users have explicit control (connect / disconnect in Settings)

---

## 2. OAuth Flow Sequence

```
Mobile App                Backend API              Microsoft
    |                          |                        |
    |-- GET /ms/auth/url ------>|                        |
    |<-- {auth_url, state} -----|                        |
    |                          |                        |
    |-- open auth_url in ------>|                        |
    |   in-app browser          |                        |
    |                          |<-- User authenticates ->|
    |                          |                        |
    |<-- msalauth://callback?   |                        |
    |    code=AUTH_CODE         |                        |
    |    &state=STATE_JWT       |                        |
    |                          |                        |
    |-- POST /ms/auth/callback  |                        |
    |   {code, state} --------->|                        |
    |                          |-- acquire_token_by_code->|
    |                          |<-- {access, refresh} ---|
    |                          |-- encrypt & store in DB |
    |<-- {connected, ms_email} -|                        |
```

---

## 3. Step-by-Step Implementation

### Step 1 — Get the Auth URL

```javascript
// Call from Settings screen when user taps "Connect Microsoft Account"
const response = await api.get('/ms/auth/url', {
  headers: { Authorization: `Bearer ${userAccessToken}` }
});
const { auth_url, state } = response.data;

// Store state for verification
await SecureStore.setItemAsync('ms_oauth_state', state);
```

### Step 2 — Open the In-App Browser

```javascript
import * as WebBrowser from 'expo-web-browser';
import * as Linking from 'expo-linking';

// Open Microsoft login page
const result = await WebBrowser.openAuthSessionAsync(
  auth_url,
  'msalauth://callback'  // redirect URI (deep link scheme)
);

if (result.type === 'success') {
  const url = result.url;
  // Parse code and state from the redirect URL
  const params = new URLSearchParams(url.split('?')[1] || url.split('#')[1]);
  const code = params.get('code');
  const returnedState = params.get('state');
  await handleCallback(code, returnedState);
}
```

### Step 3 — Handle the Callback Deep Link

Register the `msalauth://` scheme in your app (see Section 5 below).

```javascript
// When the deep link fires
Linking.addEventListener('url', ({ url }) => {
  const parsed = Linking.parse(url);
  const { code, state } = parsed.queryParams;
  if (code && state) {
    handleMsCallback(code, state);
  }
});

async function handleMsCallback(code, state) {
  // Verify state matches what we stored
  const savedState = await SecureStore.getItemAsync('ms_oauth_state');
  if (state !== savedState) {
    showError('OAuth state mismatch. Please try again.');
    return;
  }

  // Exchange code for tokens
  const response = await api.post('/ms/auth/callback', { code, state }, {
    headers: { Authorization: `Bearer ${userAccessToken}` }
  });

  if (response.data.connected) {
    showSuccess(`Connected as ${response.data.ms_email}`);
    updateSettingsUI(response.data);
  }
}
```

### Step 4 — Check Connection Status

```javascript
// On Settings screen mount
const status = await api.get('/ms/auth/status', {
  headers: { Authorization: `Bearer ${userAccessToken}` }
});
// { connected: bool, ms_email: "...", scopes: [...], expires_at: "..." }
```

### Step 5 — Disconnect

```javascript
await api.delete('/ms/auth/disconnect', {
  headers: { Authorization: `Bearer ${userAccessToken}` }
});
// { disconnected: true }
```

---

## 4. Deep Link Registration (React Native)

### Android — `android/app/src/main/AndroidManifest.xml`

```xml
<activity android:name=".MainActivity" ...>
  <intent-filter>
    <action android:name="android.intent.action.VIEW" />
    <category android:name="android.intent.category.DEFAULT" />
    <category android:name="android.intent.category.BROWSABLE" />
    <data android:scheme="msalauth" android:host="callback" />
  </intent-filter>
</activity>
```

### iOS — `ios/[AppName]/Info.plist`

```xml
<key>CFBundleURLTypes</key>
<array>
  <dict>
    <key>CFBundleURLSchemes</key>
    <array>
      <string>msalauth</string>
    </array>
  </dict>
</array>
```

### Expo — `app.json` / `app.config.js`

```json
{
  "expo": {
    "scheme": "msalauth",
    "android": {
      "intentFilters": [
        {
          "action": "VIEW",
          "data": [{ "scheme": "msalauth", "host": "callback" }],
          "category": ["BROWSABLE", "DEFAULT"]
        }
      ]
    }
  }
}
```

---

## 5. Settings Tab UI

```
Connected Accounts
──────────────────────────────────────────
Microsoft Account
  ● Connected as john.doe@outlook.com     [Disconnect]
  Scopes: Mail, Calendar, OneNote, Teams

  — or —

  ○ Not connected                         [Connect]
──────────────────────────────────────────
```

**Key UI states:**
- `status.connected = false` → show "Connect Microsoft Account" button
- `status.connected = true` → show email + "Disconnect" button
- During OAuth flow → show loading spinner
- On error → show error message with retry

---

## 6. API Reference

### GET `/ms/auth/url`

**Auth:** Bearer token required

**Response:**
```json
{
  "auth_url": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize?...",
  "state": "eyJhbGciOiJIUzI1NiJ9..."
}
```

---

### POST `/ms/auth/callback`

**Auth:** Bearer token required

**Request body:**
```json
{
  "code": "0.AAAAAAAA...",
  "state": "eyJhbGciOiJIUzI1NiJ9..."
}
```

**Response (success):**
```json
{
  "connected": true,
  "ms_email": "john.doe@outlook.com",
  "scopes": ["Mail.Read", "Mail.Send", "Calendars.ReadWrite", "Chat.ReadWrite"]
}
```

**Response (error):**
```json
{
  "detail": "Token exchange failed: AADSTS70011 — invalid scope"
}
```

---

### GET `/ms/auth/status`

**Auth:** Bearer token required

**Response (connected):**
```json
{
  "connected": true,
  "ms_email": "john.doe@outlook.com",
  "scopes": ["offline_access", "User.Read", "Mail.Read", "Mail.Send", "Calendars.ReadWrite"],
  "expires_at": "2026-03-11T10:30:00+00:00"
}
```

**Response (not connected):**
```json
{
  "connected": false,
  "ms_email": null,
  "scopes": [],
  "expires_at": null
}
```

---

### DELETE `/ms/auth/disconnect`

**Auth:** Bearer token required

**Response:**
```json
{
  "disconnected": true
}
```

---

## 7. Error Handling

| Scenario | HTTP Code | Handling |
|----------|-----------|---------|
| User not connected | Tool returns friendly message | Show "Connect in Settings" prompt |
| Token expired (auto-refreshed) | Transparent | No action needed |
| Refresh token revoked (user changed password) | 400 from `/ms/auth/callback` | Show "Reconnect" prompt |
| MS OAuth not configured on server | 503 from `/ms/auth/url` | Show "Feature not available" |
| State mismatch (CSRF) | 403 from `/ms/auth/callback` | Show "Try again" |
| User cancels browser | `result.type === 'dismiss'` in WebBrowser | No-op |

### Token Expiry & Auto-Refresh

Access tokens expire after ~1 hour. The backend **auto-refreshes** using the refresh token stored in the database. The mobile app never needs to handle token expiry — just call any personal MS tool and the backend handles refresh transparently.

If the refresh token itself is revoked (e.g., user changed Microsoft password or revoked app access in their Microsoft account settings), the next tool call will fail with an `MSNotConnectedException`. The tool response will include the "connect in Settings" message, prompting the user to reconnect.

---

## 8. Azure AD App Registration

To support personal Microsoft accounts AND work/school accounts, configure the Azure AD app registration:

### Required Changes

1. **Supported account types:** Set to **"Accounts in any organizational directory and personal Microsoft accounts"** (common tenant)

2. **Redirect URI:** Add a Mobile and desktop application redirect URI:
   ```
   msalauth://callback
   ```

3. **API Permissions (Delegated — not Application):**
   - `User.Read`
   - `offline_access`
   - `Mail.Read`
   - `Mail.ReadWrite`
   - `Mail.Send`
   - `Calendars.ReadWrite`
   - `Notes.Read`
   - `Notes.ReadWrite`
   - `Chat.ReadWrite`

4. **Grant admin consent** for the delegated permissions (required for work/school accounts in the tenant)

### Environment Variables Required

Add these to the server's `.env` / environment:

```bash
# Already required for app-level MS Graph:
MS365_CLIENT_ID=<your-app-client-id>
MS365_CLIENT_SECRET=<your-app-client-secret>
MS365_TENANT_ID=<your-tenant-id>  # kept for app-level tools

# New for delegated OAuth:
MS365_DELEGATED_REDIRECT_URI=msalauth://callback
MS_TOKEN_FERNET_KEY=<generate-with-command-below>
```

**Generate Fernet key:**
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Keep `MS_TOKEN_FERNET_KEY` secret — it's used to encrypt/decrypt OAuth tokens stored in the database. If it changes, all stored tokens become unreadable and users will need to reconnect.
