---
name: mobile-developer
description: Mobile development specialist for React Native cross-platform apps. Use for iOS and Android native apps, offline-first architecture, WatermelonDB local database, push notifications, NFC integration, biometric authentication, deep linking, app store deployment, and building native mobile experiences for coupon exchange platforms.
---

# Mobile Developer

Build production-ready native mobile apps for iOS and Android using React Native.

## Tech Stack

- **Framework**: React Native 0.73+
- **Language**: TypeScript
- **UI Components**: NativeUI (nativeui.io)
- **State**: Zustand + React Query
- **Local DB**: WatermelonDB (offline-first)
- **Navigation**: React Navigation 6
- **NFC**: react-native-nfc-manager
- **Notifications**: @notifee/react-native
- **Biometrics**: react-native-biometrics
- **Payments**: @stripe/stripe-react-native

## NativeUI Integration

Always use NativeUI components for all UI elements:

```bash
# Install NativeUI
npm install nativeui
```

```typescript
// Import NativeUI components
import { Card, Button, Text, View, Icon } from 'nativeui';

// Example: Coupon card using NativeUI
export const CouponCard: React.FC<{ coupon: Coupon }> = ({ coupon }) => (
  <Card style={{ marginBottom: 12 }}>
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
      <Icon name="ticket" size={24} color="#f97316" />
      <View style={{ flex: 1 }}>
        <Text variant="heading" size="md">{coupon.title}</Text>
        <Text variant="body" color="secondary">
          Expires {formatDate(coupon.expiresAt)}
        </Text>
      </View>
    </View>
    <Text variant="heading" size="lg" color="#f97316" style={{ marginTop: 8 }}>
      {coupon.discount}% OFF
    </Text>
    <Button
      variant="primary"
      color="#f97316"
      onPress={() => redeemCoupon(coupon.id)}
      style={{ marginTop: 12 }}
    >
      Redeem Coupon
    </Button>
  </Card>
);
```

### Mezzofy Brand Theme

```typescript
// core/theme.ts
import { createTheme } from 'nativeui';

export const mezzofyTheme = createTheme({
  colors: {
    primary: '#f97316',      // Orange
    secondary: '#000000',    // Black
    background: '#ffffff',   // White
    text: '#000000',
    textSecondary: '#6b7280',
  },
  spacing: {
    xs: 4,
    sm: 8,
    md: 12,
    lg: 16,
    xl: 24,
  },
  borderRadius: {
    sm: 6,
    md: 10,
    lg: 16,
  },
});
```

```typescript
// App.tsx — wrap with NativeUI ThemeProvider
import { ThemeProvider } from 'nativeui';
import { mezzofyTheme } from './core/theme';

export default function App() {
  return (
    <ThemeProvider theme={mezzofyTheme}>
      {/* App content */}
    </ThemeProvider>
  );
}
```

## Project Structure

```
mobile/
├── src/
│   ├── navigation/         # App navigation
│   │   ├── AppNavigator.tsx
│   │   ├── AuthNavigator.tsx
│   │   └── TabNavigator.tsx
│   ├── screens/           # Screen components
│   │   ├── Home/
│   │   ├── Browse/
│   │   ├── Redeem/
│   │   └── Profile/
│   ├── components/        # Reusable components (built with NativeUI)
│   │   ├── CouponCard/
│   │   ├── Scanner/
│   │   └── common/
│   ├── hooks/            # Custom hooks
│   │   ├── useNFC.ts
│   │   ├── useOfflineSync.ts
│   │   └── useBiometric.ts
│   ├── services/         # API and business logic
│   │   ├── api/
│   │   ├── storage/
│   │   └── sync/
│   ├── models/           # WatermelonDB models
│   │   ├── Coupon.ts
│   │   └── schema.ts
│   ├── store/            # Zustand stores
│   │   ├── authStore.ts
│   │   └── couponStore.ts
│   └── utils/            # Utilities
│       ├── permissions.ts
│       └── constants.ts
├── ios/                  # iOS native code
├── android/              # Android native code
└── app.json             # App configuration
```

## Core Features Implementation

### 1. NFC Coupon Scanning

```typescript
// hooks/useNFC.ts
import { useState, useEffect } from 'react';
import NfcManager, { NfcTech, Ndef } from 'react-native-nfc-manager';
import { Platform } from 'react-native';

interface NFCCouponData {
  couponId: string;
  merchantId: string;
  discount: string;
  expiresAt: string;
  signature: string;
}

export const useNFC = () => {
  const [isSupported, setIsSupported] = useState(false);
  const [isScanning, setIsScanning] = useState(false);
  
  useEffect(() => {
    checkNFCSupport();
    return () => {
      NfcManager.cancelTechnologyRequest();
    };
  }, []);
  
  const checkNFCSupport = async () => {
    const supported = await NfcManager.isSupported();
    setIsSupported(supported);
  };
  
  const scanCoupon = async (): Promise<NFCCouponData> => {
    setIsScanning(true);
    
    try {
      // Request NFC technology
      await NfcManager.requestTechnology(NfcTech.Ndef);
      
      // Read NDEF message
      const tag = await NfcManager.getTag();
      
      if (!tag?.ndefMessage?.[0]) {
        throw new Error('No NDEF message found');
      }
      
      // Parse coupon data
      const payload = Ndef.text.decodePayload(
        tag.ndefMessage[0].payload
      );
      
      const couponData: NFCCouponData = JSON.parse(payload);
      
      // Verify signature
      await verifyCouponSignature(couponData);
      
      return couponData;
      
    } catch (error) {
      console.error('NFC scan error:', error);
      throw error;
    } finally {
      setIsScanning(false);
      NfcManager.cancelTechnologyRequest();
    }
  };
  
  const writeCoupon = async (couponData: NFCCouponData) => {
    try {
      await NfcManager.requestTechnology(NfcTech.Ndef);
      
      // Create NDEF message
      const bytes = Ndef.encodeMessage([
        Ndef.textRecord(JSON.stringify(couponData))
      ]);
      
      // Write to tag
      await NfcManager.ndefHandler.writeNdefMessage(bytes);
      
      alert('Coupon written to NFC tag successfully!');
      
    } catch (error) {
      console.error('NFC write error:', error);
      throw error;
    } finally {
      NfcManager.cancelTechnologyRequest();
    }
  };
  
  return {
    isSupported,
    isScanning,
    scanCoupon,
    writeCoupon,
  };
};
```

### 2. Offline-First with WatermelonDB

```typescript
// models/schema.ts
import { appSchema, tableSchema } from '@nozbe/watermelondb';

export const schema = appSchema({
  version: 1,
  tables: [
    tableSchema({
      name: 'coupons',
      columns: [
        { name: 'coupon_id', type: 'string', isIndexed: true },
        { name: 'title', type: 'string' },
        { name: 'description', type: 'string' },
        { name: 'discount', type: 'number' },
        { name: 'discount_type', type: 'string' },
        { name: 'merchant_name', type: 'string' },
        { name: 'expires_at', type: 'number' },
        { name: 'status', type: 'string' },
        { name: 'is_synced', type: 'boolean' },
        { name: 'created_at', type: 'number' },
        { name: 'updated_at', type: 'number' },
      ]
    }),
    tableSchema({
      name: 'redemptions',
      columns: [
        { name: 'coupon_id', type: 'string', isIndexed: true },
        { name: 'user_id', type: 'string' },
        { name: 'redeemed_at', type: 'number' },
        { name: 'location', type: 'string', isOptional: true },
        { name: 'is_synced', type: 'boolean' },
      ]
    }),
  ]
});

// models/Coupon.ts
import { Model } from '@nozbe/watermelondb';
import { field, date, readonly } from '@nozbe/watermelondb/decorators';

export class Coupon extends Model {
  static table = 'coupons';
  
  @field('coupon_id') couponId!: string;
  @field('title') title!: string;
  @field('description') description!: string;
  @field('discount') discount!: number;
  @field('discount_type') discountType!: string;
  @field('merchant_name') merchantName!: string;
  @date('expires_at') expiresAt!: Date;
  @field('status') status!: string;
  @field('is_synced') isSynced!: boolean;
  
  @readonly @date('created_at') createdAt!: Date;
  @readonly @date('updated_at') updatedAt!: Date;
  
  // Business logic
  get isExpired(): boolean {
    return new Date() > this.expiresAt;
  }
  
  get canRedeem(): boolean {
    return this.status === 'active' && !this.isExpired;
  }
}
```

### 3. Background Sync

```typescript
// services/sync/offlineSync.ts
import { database } from '../database';
import { Q } from '@nozbe/watermelondb';
import NetInfo from '@react-native-community/netinfo';
import { apiClient } from '../api/client';

export class OfflineSync {
  private isSyncing = false;
  
  async syncPendingData() {
    if (this.isSyncing) return;
    
    const netInfo = await NetInfo.fetch();
    if (!netInfo.isConnected) {
      console.log('No internet connection, skipping sync');
      return;
    }
    
    this.isSyncing = true;
    
    try {
      // Sync redemptions first (critical data)
      await this.syncRedemptions();
      
      // Then sync coupons
      await this.syncCoupons();
      
      console.log('Sync completed successfully');
    } catch (error) {
      console.error('Sync failed:', error);
    } finally {
      this.isSyncing = false;
    }
  }
  
  private async syncRedemptions() {
    const redemptionsCollection = database.collections.get('redemptions');
    
    const unsyncedRedemptions = await redemptionsCollection
      .query(Q.where('is_synced', false))
      .fetch();
    
    for (const redemption of unsyncedRedemptions) {
      try {
        await apiClient.post('/redemptions', {
          couponId: redemption.couponId,
          userId: redemption.userId,
          redeemedAt: redemption.redeemedAt,
        });
        
        // Mark as synced
        await database.write(async () => {
          await redemption.update(r => {
            r.isSynced = true;
          });
        });
        
      } catch (error) {
        console.error(`Failed to sync redemption ${redemption.id}:`, error);
      }
    }
  }
  
  private async syncCoupons() {
    // Fetch latest coupons from server
    const response = await apiClient.get('/coupons');
    const serverCoupons = response.data;
    
    const couponsCollection = database.collections.get('coupons');
    
    await database.write(async () => {
      for (const serverCoupon of serverCoupons) {
        const existingCoupon = await couponsCollection
          .query(Q.where('coupon_id', serverCoupon.id))
          .fetch();
        
        if (existingCoupon.length > 0) {
          // Update existing
          await existingCoupon[0].update(c => {
            Object.assign(c, serverCoupon);
            c.isSynced = true;
          });
        } else {
          // Create new
          await couponsCollection.create(c => {
            Object.assign(c, serverCoupon);
            c.isSynced = true;
          });
        }
      }
    });
  }
}

// Auto-sync on network reconnection
NetInfo.addEventListener(state => {
  if (state.isConnected) {
    const sync = new OfflineSync();
    sync.syncPendingData();
  }
});
```

### 4. Push Notifications

```typescript
// services/notifications/pushNotifications.ts
import notifee, { AndroidImportance } from '@notifee/react-native';
import messaging from '@react-native-firebase/messaging';

export class PushNotificationService {
  async initialize() {
    // Request permission
    await this.requestPermission();
    
    // Create notification channel (Android)
    await this.createChannel();
    
    // Handle foreground notifications
    messaging().onMessage(this.handleForegroundMessage);
    
    // Handle background/quit notifications
    messaging().setBackgroundMessageHandler(this.handleBackgroundMessage);
    
    // Get FCM token
    const token = await messaging().getToken();
    console.log('FCM Token:', token);
    
    return token;
  }
  
  private async requestPermission() {
    const authStatus = await messaging().requestPermission();
    const enabled =
      authStatus === messaging.AuthorizationStatus.AUTHORIZED ||
      authStatus === messaging.AuthorizationStatus.PROVISIONAL;
    
    if (!enabled) {
      console.warn('Push notification permission denied');
    }
  }
  
  private async createChannel() {
    await notifee.createChannel({
      id: 'coupons',
      name: 'Coupon Updates',
      importance: AndroidImportance.HIGH,
    });
  }
  
  private handleForegroundMessage = async (message: any) => {
    await notifee.displayNotification({
      title: message.notification?.title,
      body: message.notification?.body,
      android: {
        channelId: 'coupons',
        smallIcon: 'ic_notification',
        pressAction: {
          id: 'default',
        },
      },
      ios: {
        sound: 'default',
      },
      data: message.data,
    });
  };
  
  private handleBackgroundMessage = async (message: any) => {
    console.log('Background message:', message);
    
    // Handle notification tap
    if (message.data?.type === 'coupon_expiring') {
      // Navigate to coupon detail
      // This will be handled by notification tap handler
    }
  };
  
  async sendLocalNotification(
    title: string,
    body: string,
    data?: any
  ) {
    await notifee.displayNotification({
      title,
      body,
      android: {
        channelId: 'coupons',
      },
      data,
    });
  }
  
  async scheduleCouponExpiry(coupon: any) {
    const expiryDate = new Date(coupon.expiresAt);
    const oneDayBefore = new Date(expiryDate.getTime() - 24 * 60 * 60 * 1000);
    
    await notifee.createTriggerNotification(
      {
        title: 'Coupon Expiring Soon!',
        body: `Your ${coupon.title} expires tomorrow`,
        android: {
          channelId: 'coupons',
        },
        data: {
          couponId: coupon.id,
        },
      },
      {
        type: notifee.TriggerType.TIMESTAMP,
        timestamp: oneDayBefore.getTime(),
      }
    );
  }
}
```

### 5. Biometric Authentication

```typescript
// hooks/useBiometric.ts
import { useState, useEffect } from 'react';
import ReactNativeBiometrics from 'react-native-biometrics';

export const useBiometric = () => {
  const [isAvailable, setIsAvailable] = useState(false);
  const [biometryType, setBiometryType] = useState<string | null>(null);
  
  useEffect(() => {
    checkBiometricAvailability();
  }, []);
  
  const checkBiometricAvailability = async () => {
    const rnBiometrics = new ReactNativeBiometrics();
    
    const { available, biometryType: type } = 
      await rnBiometrics.isSensorAvailable();
    
    setIsAvailable(available);
    setBiometryType(type);
  };
  
  const authenticate = async (): Promise<boolean> => {
    const rnBiometrics = new ReactNativeBiometrics();
    
    try {
      const { success } = await rnBiometrics.simplePrompt({
        promptMessage: 'Authenticate to redeem coupon',
      });
      
      return success;
      
    } catch (error) {
      console.error('Biometric authentication failed:', error);
      return false;
    }
  };
  
  const createSignature = async (
    payload: string
  ): Promise<string | null> => {
    const rnBiometrics = new ReactNativeBiometrics();
    
    try {
      // Create keys if not exists
      const { publicKey } = await rnBiometrics.createKeys();
      
      // Create signature
      const { success, signature } = await rnBiometrics.createSignature({
        promptMessage: 'Sign this transaction',
        payload,
      });
      
      if (success && signature) {
        return signature;
      }
      
      return null;
      
    } catch (error) {
      console.error('Signature creation failed:', error);
      return null;
    }
  };
  
  return {
    isAvailable,
    biometryType,
    authenticate,
    createSignature,
  };
};
```

## Navigation Setup

```typescript
// navigation/AppNavigator.tsx
import React from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { Icon } from 'nativeui';

import HomeScreen from '../screens/Home/HomeScreen';
import BrowseScreen from '../screens/Browse/BrowseScreen';
import RedeemScreen from '../screens/Redeem/RedeemScreen';
import ProfileScreen from '../screens/Profile/ProfileScreen';

const Tab = createBottomTabNavigator();
const Stack = createNativeStackNavigator();

const TabNavigator = () => {
  return (
    <Tab.Navigator
      screenOptions={({ route }) => ({
        tabBarIcon: ({ focused, color, size }) => {
          let iconName = 'home';

          if (route.name === 'Home') iconName = 'home';
          else if (route.name === 'Browse') iconName = 'search';
          else if (route.name === 'Redeem') iconName = 'qr-code';
          else if (route.name === 'Profile') iconName = 'person';

          return <Icon name={iconName} size={size} color={color} />;
        },
        tabBarActiveTintColor: '#f97316',   // Mezzofy orange
        tabBarInactiveTintColor: '#6b7280', // gray
      })}
    >
      <Tab.Screen name="Home" component={HomeScreen} />
      <Tab.Screen name="Browse" component={BrowseScreen} />
      <Tab.Screen name="Redeem" component={RedeemScreen} />
      <Tab.Screen name="Profile" component={ProfileScreen} />
    </Tab.Navigator>
  );
};

export const AppNavigator = () => {
  return (
    <NavigationContainer>
      <Stack.Navigator>
        <Stack.Screen
          name="Main"
          component={TabNavigator}
          options={{ headerShown: false }}
        />
      </Stack.Navigator>
    </NavigationContainer>
  );
};
```

## Deep Linking

```typescript
// App.tsx deep linking configuration
import { Linking } from 'react-native';

const linking = {
  prefixes: ['mezzofy://', 'https://mezzofy.com'],
  config: {
    screens: {
      Home: 'home',
      CouponDetail: 'coupon/:id',
      Redeem: 'redeem/:id',
      Profile: 'profile',
    },
  },
};

// Usage in NavigationContainer
<NavigationContainer linking={linking}>
  {/* navigation structure */}
</NavigationContainer>

// Handle deep links
useEffect(() => {
  Linking.getInitialURL().then(url => {
    if (url) {
      console.log('App opened with URL:', url);
      // mezzofy://coupon/123
    }
  });
  
  Linking.addEventListener('url', ({ url }) => {
    console.log('Deep link received:', url);
  });
}, []);
```

## App Store Deployment

### iOS (App Store)

```bash
# 1. Update version in ios/MezzofyApp/Info.plist
# CFBundleShortVersionString: 1.2.0
# CFBundleVersion: 42

# 2. Build release
cd ios
pod install
xcodebuild -workspace MezzofyApp.xcworkspace \
  -scheme MezzofyApp \
  -configuration Release \
  -archivePath ./build/MezzofyApp.xcarchive \
  archive

# 3. Export IPA
xcodebuild -exportArchive \
  -archivePath ./build/MezzofyApp.xcarchive \
  -exportPath ./build \
  -exportOptionsPlist ExportOptions.plist

# 4. Upload to App Store Connect
xcrun altool --upload-app \
  -f ./build/MezzofyApp.ipa \
  -t ios \
  -u your@email.com \
  -p app-specific-password
```

### Android (Google Play)

```bash
# 1. Update version in android/app/build.gradle
# versionCode 42
# versionName "1.2.0"

# 2. Build release APK/AAB
cd android
./gradlew bundleRelease

# 3. Sign bundle
jarsigner -verbose \
  -sigalg SHA256withRSA \
  -digestalg SHA-256 \
  -keystore mezzofy.keystore \
  app/build/outputs/bundle/release/app-release.aab \
  mezzofy-key

# 4. Upload to Google Play Console (manual or via API)
```

## Performance Optimization

```typescript
import { Card, Text, Button, View } from 'nativeui';
import { FlatList } from 'react-native';

// Use React.memo for expensive NativeUI components
export const CouponCard = React.memo<CouponCardProps>(
  ({ coupon, onRedeem }) => (
    <Card style={{ marginBottom: 12 }}>
      <Text variant="heading" size="md">{coupon.title}</Text>
      <Text variant="body" color="secondary">
        {coupon.discount}% OFF
      </Text>
      <Button variant="primary" color="#f97316" onPress={() => onRedeem(coupon.id)}>
        Redeem
      </Button>
    </Card>
  ),
  (prevProps, nextProps) => {
    return prevProps.coupon.id === nextProps.coupon.id;
  }
);

// Use FlatList for long lists
<FlatList
  data={coupons}
  renderItem={({ item }) => <CouponCard coupon={item} onRedeem={handleRedeem} />}
  keyExtractor={item => item.id}
  initialNumToRender={10}
  maxToRenderPerBatch={10}
  windowSize={5}
  removeClippedSubviews={true}
  getItemLayout={(data, index) => ({
    length: 200,
    offset: 200 * index,
    index,
  })}
/>

// Image optimization with NativeUI Image
import { Image } from 'nativeui';

<Image
  source={{ uri: coupon.imageUrl }}
  style={{ width: '100%', height: 160 }}
  resizeMode="cover"
  placeholder="gray"
/>
```

## Quality Checklist

- [ ] NativeUI components used (nativeui.io)
- [ ] Mezzofy theme applied via NativeUI ThemeProvider
- [ ] Offline-first architecture implemented
- [ ] WatermelonDB for local storage
- [ ] Background sync working
- [ ] NFC reading/writing tested
- [ ] Push notifications configured
- [ ] Biometric authentication implemented
- [ ] Deep linking configured
- [ ] Navigation properly structured
- [ ] Performance optimized (FlatList, memo)
- [ ] iOS build successful
- [ ] Android build successful
- [ ] App icons and splash screens
- [ ] App store metadata prepared
- [ ] Privacy policy and terms included
- [ ] Analytics integrated (optional)
