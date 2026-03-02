import urllib.request, json, sys

# Login
login_data = json.dumps({'email': 'admin@mezzofy.com', 'password': 'MezzofyAI2024!'}).encode()
req = urllib.request.Request('http://3.1.255.48:8000/auth/login', data=login_data, headers={'Content-Type': 'application/json'})
try:
    with urllib.request.urlopen(req, timeout=15) as r:
        login_resp = json.load(r)
except urllib.error.HTTPError as e:
    print('Login failed:', e.code, e.read().decode())
    sys.exit(1)

token = login_resp.get('access_token', '')
if not token:
    print('No token:', login_resp)
    sys.exit(1)
print('Login OK')

# Send chat
chat_data = json.dumps({'message': 'Hello, say hi in one sentence.', 'session_id': 'test-fix-001'}).encode()
req2 = urllib.request.Request('http://3.1.255.48:8000/chat/send', data=chat_data, headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token})
try:
    with urllib.request.urlopen(req2, timeout=45) as r:
        chat_resp = json.load(r)
        print('Chat response:')
        print(json.dumps(chat_resp, indent=2)[:1000])
except urllib.error.HTTPError as e:
    body = e.read().decode()
    print('Chat failed:', e.code, body[:500])
except Exception as e:
    print('Chat error:', e)
