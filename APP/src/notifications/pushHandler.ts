import {Platform, PermissionsAndroid} from 'react-native';
import messaging from '@react-native-firebase/messaging';
import {registerDevice, unregisterDevice as apiUnregisterDevice} from '../api/notificationsApi';

async function requestAndroidPermission(): Promise<boolean> {
  if (Platform.OS !== 'android' || Platform.Version < 33) {
    return true;
  }
  const result = await PermissionsAndroid.request(
    PermissionsAndroid.PERMISSIONS.POST_NOTIFICATIONS,
  );
  return result === PermissionsAndroid.RESULTS.GRANTED;
}

export async function initPushNotifications(): Promise<string | null> {
  try {
    if (!await requestAndroidPermission()) {
      return null;
    }
    const token = await messaging().getToken();
    if (!token) {
      return null;
    }
    await registerDevice(token, Platform.OS === 'ios' ? 'ios' : 'android');
    // Background/killed state — RN Firebase shows notification automatically from FCM payload
    messaging().setBackgroundMessageHandler(async _msg => {});
    // Re-register when FCM rotates the token
    messaging().onTokenRefresh(newToken => {
      registerDevice(newToken, Platform.OS === 'ios' ? 'ios' : 'android').catch(() => {});
    });
    return token;
  } catch (e) {
    console.warn('[Push] initPushNotifications failed:', e);
    return null;
  }
}

export async function unregisterPushDevice(): Promise<void> {
  try {
    const token = await messaging().getToken();
    if (token) {
      await apiUnregisterDevice(token, Platform.OS === 'ios' ? 'ios' : 'android');
    }
  } catch {
    /* non-fatal */
  }
}
