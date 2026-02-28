import {Platform} from 'react-native';

const DEV_BASE_URL =
  Platform.OS === 'android' ? 'http://10.0.2.2:8000' : 'http://localhost:8000';
const PROD_BASE_URL = 'https://api.mezzofy.com';

export const SERVER_BASE_URL = __DEV__ ? DEV_BASE_URL : PROD_BASE_URL;
export const WS_BASE_URL = __DEV__
  ? SERVER_BASE_URL.replace('http://', 'ws://')
  : PROD_BASE_URL.replace('https://', 'wss://');
