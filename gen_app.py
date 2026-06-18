import os, json, base64
BASE = r'E:\PythonProject\AIInterviewDesktop'

def w(p, c):
    fp = os.path.join(BASE, p)
    os.makedirs(os.path.dirname(fp), exist_ok=True)
    with open(fp, 'w', encoding='utf-8') as f:
        f.write(c)
    print(f'  wrote: {p}')

def decode(s):
    return base64.b64decode(s).decode('utf-8')

print('Generating all desktop app files...')

# === INIT FILES ===
for f in ['agents/__init__.py', 'ui/__init__.py', 'ui/widgets/__init__.py', 'ui/pages/__init__.py']:
    w(f, '"""\n"""\n')

# === AGENTS: interviewer.py ===
w('agents/interviewer.py', decode('IiIiSW50ZXJ2aWV3ZXIgQWdlbnQgLSBHZW5lcmF0ZXMgaW50ZXJ2aWV3IHF1ZXN0aW9ucwoiIiIKaW1wb3J0IGFzeW5jCiBpbXBvcnQgbG9nZ2luZwpmcm9tIGNvcmUuY29uZmlnIGltcG9ydCBnZXRfc2V0dGluZ3MKbG9nZ2VyID0gbG9nZ2luZy5nZXRsb2dnZXIoImFnZW50LmludGVydmlld2VyIikKc2V0dGluZ3MgPSBnZXRfc2V0dGluZ3MoKQo='))

print('Agent files done!')