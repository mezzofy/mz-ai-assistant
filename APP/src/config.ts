// DEV: for local dev against LAN server, replace with your machine's LAN IP:
// e.g. 'http://192.168.1.42:8000'
// For dev against EC2, use the HTTPS domain (same as prod).
const DEV_BASE_URL = 'https://assistant.mezzofy.com';
const PROD_BASE_URL = 'https://assistant.mezzofy.com';

export const SERVER_BASE_URL = __DEV__ ? DEV_BASE_URL : PROD_BASE_URL;
export const WS_BASE_URL = SERVER_BASE_URL.replace('http://', 'ws://').replace('https://', 'wss://');
