# Mezzofy AI Assistant — React Native App

Enterprise AI assistant for Mezzofy team (Finance, Sales, Marketing, Support, Management).

## 📱 Screens

| Screen | Description |
|--------|-------------|
| **Login** | Email/password auth with Mezzofy branding |
| **Chat** | Main AI chat with 8 input modes (text, image, video, camera, speech, audio, file, URL) |
| **History** | Searchable conversation list with department badges |
| **Files** | Generated artifacts (PDF, CSV, PPTX, MD) with download |
| **Settings** | Profile, notifications, privacy, sign out |
| **Camera** | Live camera view with AI analysis overlay |

## 🛠 Prerequisites

- **Node.js** 18+ → https://nodejs.org
- **Java JDK 17** → `brew install openjdk@17` (Mac) or https://adoptium.net
- **Android Studio** → https://developer.android.com/studio
  - SDK 34 (Android 14)
  - Build Tools 34.0.0
  - NDK 25.1.8937393
  - Set `ANDROID_HOME` environment variable

### Environment Variables

Add to `~/.bashrc` or `~/.zshrc`:

```bash
export ANDROID_HOME=$HOME/Android/Sdk        # Linux
# export ANDROID_HOME=$HOME/Library/Android/sdk  # macOS
export PATH=$PATH:$ANDROID_HOME/emulator
export PATH=$PATH:$ANDROID_HOME/platform-tools
```

## 🚀 Quick Start

```bash
# 1. Install dependencies
npm install

# 2. Start Metro bundler
npx react-native start

# 3. Build & run on connected device/emulator (in another terminal)
npx react-native run-android
```

## 📦 Build APK

### Debug APK (for testing)

```bash
# Generates: android/app/build/outputs/apk/debug/app-debug.apk
cd android
./gradlew assembleDebug
```

### Release APK (for distribution)

```bash
# 1. Generate signing key (one time)
keytool -genkeypair -v -storetype PKCS12 \
  -keystore android/app/mezzofy-release.keystore \
  -alias mezzofy -keyalg RSA -keysize 2048 -validity 10000

# 2. Update android/app/build.gradle signingConfigs.release with your keystore

# 3. Build
cd android
./gradlew assembleRelease
# Output: android/app/build/outputs/apk/release/app-release.apk
```

### Install APK on phone

```bash
# Via USB (enable USB debugging on phone)
adb install android/app/build/outputs/apk/debug/app-debug.apk

# Or transfer the APK file to your phone and tap to install
# (enable "Install from unknown sources" in Android settings)
```

## 🏗 Project Structure

```
MezzofyAI/
├── App.tsx                          # Root: navigation + auth gate
├── index.js                         # Entry point
├── app.json                         # App name config
├── package.json                     # Dependencies
├── tsconfig.json                    # TypeScript config
├── babel.config.js                  # Babel + Reanimated plugin
├── metro.config.js                  # Metro bundler config
│
├── src/
│   ├── screens/
│   │   ├── LoginScreen.tsx          # Login with email/password
│   │   ├── ChatScreen.tsx           # AI chat + 8 input modes
│   │   ├── HistoryScreen.tsx        # Conversation history
│   │   ├── FilesScreen.tsx          # Generated files list
│   │   ├── SettingsScreen.tsx       # User settings + profile
│   │   └── CameraScreen.tsx         # Live camera AI analysis
│   │
│   ├── components/
│   │   └── shared/
│   │       └── DeptBadge.tsx        # Department color badge
│   │
│   ├── stores/
│   │   ├── authStore.ts             # Auth state (zustand)
│   │   └── chatStore.ts             # Chat state (zustand)
│   │
│   └── utils/
│       └── theme.ts                 # Brand colors, demo data, constants
│
└── android/                         # Android native project
    ├── build.gradle                 # Root gradle config
    ├── settings.gradle              # Project settings
    ├── gradle.properties            # Build properties
    └── app/
        ├── build.gradle             # App gradle config
        ├── proguard-rules.pro       # ProGuard rules
        └── src/main/
            ├── AndroidManifest.xml  # Permissions & activity
            ├── java/com/mezzofyai/
            │   ├── MainActivity.kt
            │   └── MainApplication.kt
            └── res/
                ├── values/
                │   ├── strings.xml
                │   └── styles.xml
                └── mipmap-*/        # App icons (all densities)
```

## 🎨 Design System

| Token | Value | Usage |
|-------|-------|-------|
| `primary` | `#0A1628` | Background |
| `surface` | `#0F1F35` | Tab bar, cards |
| `surfaceLight` | `#162A45` | Input fields, bubbles |
| `accent` | `#00D4AA` | CTAs, active states |
| `text` | `#E8F0F8` | Primary text |
| `textMuted` | `#7A8FA6` | Secondary text |
| `danger` | `#FF4B6E` | Recording, errors |

### Department Colors
- Finance: `#FFB84D` (amber)
- Sales: `#00D4AA` (teal)
- Marketing: `#C77DFF` (purple)
- Support: `#4DA6FF` (blue)
- Management: `#FF6B8A` (pink)

## 🔌 Connecting to Backend

Replace demo data in `src/utils/theme.ts` with API calls:

```typescript
// src/services/api.ts
const API_BASE = 'https://your-ec2-server.com/api/v1';

export const api = {
  login: (email: string, password: string) =>
    fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({email, password}),
    }).then(r => r.json()),

  sendMessage: (text: string, sessionId: string, token: string) =>
    fetch(`${API_BASE}/gateway`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
      body: JSON.stringify({source: 'chat', content: text, session_id: sessionId}),
    }).then(r => r.json()),
};
```

## 📋 Tech Stack

- **React Native** 0.73 — Cross-platform mobile
- **TypeScript** — Type safety
- **React Navigation** 6 — Stack + Bottom Tab navigation
- **Zustand** — Lightweight state management
- **Ionicons** — Icon set via react-native-vector-icons
- **React Native Reanimated** — Smooth animations

## ⚠️ Notes

- This is a **demo/mockup build** — chat responses are simulated
- Camera uses placeholder viewfinder (no real camera access in demo)
- File downloads show UI only (no actual file transfer)
- To connect to your real backend, update the API service layer
