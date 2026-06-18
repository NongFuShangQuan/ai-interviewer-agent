@echo off
cd /d E:\PythonProject\AIInterview
set PYTHONPATH=E:\PythonProject\AIInterview\venv\Lib\site-packages
"C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m uvicorn main:app --host 0.0.0.0 --port 9000 >> server.log 2>&1