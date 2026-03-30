import React, {useEffect} from 'react';
import {StatusBar} from 'react-native';
import {NavigationContainer, createNavigationContainerRef} from '@react-navigation/native';
import {createNativeStackNavigator} from '@react-navigation/native-stack';
import {createBottomTabNavigator} from '@react-navigation/bottom-tabs';
import Icon from 'react-native-vector-icons/Ionicons';
import {SafeAreaProvider, useSafeAreaInsets} from 'react-native-safe-area-context';
import messaging from '@react-native-firebase/messaging';

import {BRAND, LIGHT_THEME} from './src/utils/theme';
import {useAuthStore} from './src/stores/authStore';
import {useSettingsStore} from './src/stores/settingsStore';
import {useChatStore} from './src/stores/chatStore';
import {LoginScreen} from './src/screens/LoginScreen';
import {ChatScreen} from './src/screens/ChatScreen';
import {HistoryScreen} from './src/screens/HistoryScreen';
import {FilesScreen} from './src/screens/FilesScreen';
import {SettingsScreen} from './src/screens/SettingsScreen';
import {CameraScreen} from './src/screens/CameraScreen';
import {ProfileScreen} from './src/screens/ProfileScreen';
import {AIUsageStatsScreen} from './src/screens/AIUsageStatsScreen';
import {FileViewerScreen} from './src/screens/FileViewerScreen';
import {FolderContentsScreen} from './src/screens/FolderContentsScreen';
import {ConnectedAccountsScreen} from './src/screens/ConnectedAccountsScreen';
import {OTPVerificationScreen} from './src/screens/OTPVerificationScreen';
import {ForgotPasswordScreen} from './src/screens/ForgotPasswordScreen';
import {NewPasswordScreen} from './src/screens/NewPasswordScreen';
import {AccountActivationScreen} from './src/screens/AccountActivationScreen';
import {LeaveApplicationScreen} from './src/screens/LeaveApplicationScreen';
import {LeaveApprovalScreen} from './src/screens/LeaveApprovalScreen';
import {PrivacySecurityScreen} from './src/screens/PrivacySecurityScreen';
import {ChangePasswordScreen} from './src/screens/ChangePasswordScreen';
import {ScheduleStatsScreen} from './src/screens/ScheduleStatsScreen';
import {NotificationHistoryScreen} from './src/screens/NotificationHistoryScreen';
import {initPushNotifications} from './src/notifications/pushHandler';

const Stack = createNativeStackNavigator();
const Tab = createBottomTabNavigator();
export const navigationRef = createNavigationContainerRef<any>();

const TAB_ICONS: Record<string, {active: string; inactive: string}> = {
  Chat: {active: 'chatbubble', inactive: 'chatbubble-outline'},
  History: {active: 'time', inactive: 'time-outline'},
  Files: {active: 'folder', inactive: 'folder-outline'},
  Settings: {active: 'settings', inactive: 'settings-outline'},
};

function MainTabs() {
  const insets = useSafeAreaInsets();
  const bottomPad = insets.bottom > 0 ? insets.bottom : 8;
  const appearance = useSettingsStore(s => s.appearance);
  const colors = appearance === 'Light' ? LIGHT_THEME : BRAND;

  return (
    <Tab.Navigator
      screenOptions={({route}) => ({
        headerShown: false,
        tabBarStyle: {
          backgroundColor: colors.surface,
          borderTopColor: colors.border,
          borderTopWidth: 1,
          paddingBottom: bottomPad,
          paddingTop: 8,
          height: 58 + bottomPad,
        },
        tabBarActiveTintColor: colors.accent,
        tabBarInactiveTintColor: colors.textDim,
        tabBarIconStyle: {marginBottom: 4},
        tabBarLabelStyle: {fontSize: 10, fontWeight: '600', letterSpacing: 0.3},
        tabBarIcon: ({focused, color, size}) => {
          const icons = TAB_ICONS[route.name];
          return (
            <Icon
              name={focused ? icons.active : icons.inactive}
              size={22}
              color={color}
            />
          );
        },
      })}>
      <Tab.Screen name="Chat" component={ChatScreen} />
      <Tab.Screen name="History" component={HistoryScreen} />
      <Tab.Screen name="Files" component={FilesScreen} />
      <Tab.Screen name="Settings" component={SettingsScreen} />
    </Tab.Navigator>
  );
}

function App(): React.JSX.Element {
  const isLoggedIn = useAuthStore(s => s.isLoggedIn);
  const loadStoredUser = useAuthStore(s => s.loadStoredUser);
  const loadTitles = useChatStore(s => s.loadTitles);
  const appearance = useSettingsStore(s => s.appearance);
  const notifications = useSettingsStore(s => s.notifications);
  const isDark = appearance !== 'Light';
  const colors = isDark ? BRAND : LIGHT_THEME;

  useEffect(() => {
    loadStoredUser();
    loadTitles();
  }, [loadStoredUser, loadTitles]);

  useEffect(() => {
    if (isLoggedIn && notifications) {
      initPushNotifications().catch(() => {});
    }
  }, [isLoggedIn, notifications]);

  // Handle push notification tap — route to the appropriate screen
  useEffect(() => {
    if (!isLoggedIn) return;

    // App was backgrounded and user tapped a notification
    const unsubscribe = messaging().onNotificationOpenedApp(remoteMessage => {
      const type = remoteMessage?.data?.type;
      if (type === 'leave_approval' || type === 'leave_decision') {
        navigationRef.current?.navigate('LeaveApproval');
      }
    });

    // App was killed and user tapped a notification (cold start)
    messaging()
      .getInitialNotification()
      .then(remoteMessage => {
        if (!remoteMessage) return;
        const type = remoteMessage?.data?.type;
        if (type === 'leave_approval' || type === 'leave_decision') {
          setTimeout(() => {
            navigationRef.current?.navigate('LeaveApproval');
          }, 500);
        }
      })
      .catch(() => {});

    return unsubscribe;
  }, [isLoggedIn]);

  return (
    <SafeAreaProvider>
      <StatusBar
        barStyle={isDark ? 'light-content' : 'dark-content'}
        backgroundColor={colors.primary}
      />
      <NavigationContainer
        ref={navigationRef}
        theme={{
          dark: isDark,
          colors: {
            primary: colors.accent,
            background: colors.primary,
            card: colors.surface,
            text: colors.text,
            border: colors.border,
            notification: colors.danger,
          },
        }}>
        <Stack.Navigator screenOptions={{headerShown: false}}>
          {!isLoggedIn ? (
            <>
              <Stack.Screen name="Login" component={LoginScreen} />
              <Stack.Screen
                name="OTPVerification"
                component={OTPVerificationScreen}
                options={{animation: 'slide_from_right'}}
              />
              <Stack.Screen
                name="ForgotPassword"
                component={ForgotPasswordScreen}
                options={{animation: 'slide_from_right'}}
              />
              <Stack.Screen
                name="NewPassword"
                component={NewPasswordScreen}
                options={{animation: 'slide_from_right'}}
              />
              <Stack.Screen
                name="AccountActivation"
                component={AccountActivationScreen}
                options={{animation: 'slide_from_right'}}
              />
            </>
          ) : (
            <>
              <Stack.Screen name="Main" component={MainTabs} />
              <Stack.Screen
                name="Camera"
                component={CameraScreen}
                options={{animation: 'slide_from_bottom'}}
              />
              <Stack.Screen
                name="Profile"
                component={ProfileScreen}
                options={{animation: 'slide_from_right'}}
              />
              <Stack.Screen
                name="AIUsageStats"
                component={AIUsageStatsScreen}
                options={{animation: 'slide_from_right'}}
              />
              <Stack.Screen
                name="FileViewer"
                component={FileViewerScreen}
                options={{animation: 'slide_from_right'}}
              />
              <Stack.Screen
                name="FolderContents"
                component={FolderContentsScreen}
                options={{animation: 'slide_from_right'}}
              />
              <Stack.Screen
                name="ConnectedAccounts"
                component={ConnectedAccountsScreen}
                options={{animation: 'slide_from_right'}}
              />
              <Stack.Screen
                name="PrivacySecurity"
                component={PrivacySecurityScreen}
                options={{animation: 'slide_from_right'}}
              />
              <Stack.Screen
                name="ChangePassword"
                component={ChangePasswordScreen}
                options={{animation: 'slide_from_right'}}
              />
              <Stack.Screen
                name="ScheduleStats"
                component={ScheduleStatsScreen}
                options={{animation: 'slide_from_right'}}
              />
              <Stack.Screen
                name="NotificationHistory"
                component={NotificationHistoryScreen}
                options={{animation: 'slide_from_right'}}
              />
              <Stack.Screen
                name="LeaveApplication"
                component={LeaveApplicationScreen}
                options={{animation: 'slide_from_right'}}
              />
              <Stack.Screen
                name="LeaveApproval"
                component={LeaveApprovalScreen}
                options={{animation: 'slide_from_right'}}
              />
            </>
          )}
        </Stack.Navigator>
      </NavigationContainer>
    </SafeAreaProvider>
  );
}

export default App;
