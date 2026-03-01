// DEV: replace YOUR_LAN_IP with your machine's LAN IP (run `ipconfig`, look for Wi-Fi IPv4)
// e.g. 'http://192.168.1.42:8000'
// Phone and dev machine must be on the same Wi-Fi network.
// Start server with: uvicorn app.main:app --host 0.0.0.0 --port 8000
const DEV_BASE_URL = 'http://3.1.255.48:8000';
const PROD_BASE_URL = 'https://assistant.mezzofy.com';

export const SERVER_BASE_URL = __DEV__ ? DEV_BASE_URL : PROD_BASE_URL;
export const WS_BASE_URL = SERVER_BASE_URL.replace('http://', 'ws://').replace('https://', 'wss://');
