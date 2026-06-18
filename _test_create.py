import os, json
for k in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy']:
    os.environ.pop(k, None)
import urllib.request

payload = json.dumps({
    "candidate_name": "测试",
    "candidate_email": "test@test.com",
    "job_title": "Python开发",
    "job_description": "后端开发",
    "total_rounds": 5,
    "interview_type": "text"
}).encode('utf-8')

try:
    req = urllib.request.Request(
        'http://127.0.0.1:9000/api/admin/interviews',
        data=payload,
        headers={'Content-Type': 'application/json'}
    )
    r = urllib.request.urlopen(req, timeout=10)
    print('Status:', r.status)
    print('Response:', r.read().decode('utf-8'))
except urllib.error.HTTPError as e:
    print(f'HTTP Error: {e.code}')
    print(f'Body: {e.read().decode("utf-8")}')
except Exception as e:
    print(f'Error: {type(e).__name__}: {e}')
