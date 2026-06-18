"""Speech-to-Text API - MediaRecorder audio to server-side Google STT recognition"""
import io
import os
import tempfile
import socket

from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import JSONResponse

router = APIRouter()

def _detect_proxy():
    """Auto-detect local proxy (Clash/v2ray) for Google STT access in China"""
    for port in [7890, 7891, 10808, 10809, 1080, 8080]:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.3)
            s.connect(('127.0.0.1', port))
            s.close()
            proxy_url = f'http://127.0.0.1:{port}'
            os.environ.setdefault('HTTP_PROXY', proxy_url)
            os.environ.setdefault('HTTPS_PROXY', proxy_url)
            os.environ.setdefault('http_proxy', proxy_url)
            os.environ.setdefault('https_proxy', proxy_url)
            print(f"[STT] Proxy detected on port {port}")
            return proxy_url
        except (ConnectionRefusedError, socket.timeout, OSError):
            continue
    print("[STT] No proxy detected, Google STT may not work in China")
    return None

_proxy = _detect_proxy()


@router.post("/api/stt")
async def speech_to_text(
    audio: UploadFile = File(...),
    lang: str = Form("zh-CN"),
):
    """Accept WAV audio from browser MediaRecorder and transcribe via Google STT."""
    try:
        audio_bytes = await audio.read()
        if len(audio_bytes) < 500:
            return JSONResponse({"text": "", "error": "Audio too short"})

        # Determine suffix
        suffix = ".wav"
        if audio.content_type and "webm" in audio.content_type:
            suffix = ".webm"
        elif audio.content_type and "ogg" in audio.content_type:
            suffix = ".ogg"

        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        try:
            import speech_recognition as sr
            recognizer = sr.Recognizer()
            recognizer.energy_threshold = 300
            recognizer.dynamic_energy_threshold = True

            # Read audio file
            try:
                with sr.AudioFile(tmp_path) as source:
                    audio_data = recognizer.record(source)
            except Exception as read_err:
                # If WAV fails and we have webm, try ffmpeg conversion
                if suffix != ".wav":
                    wav_path = tmp_path + ".wav"
                    try:
                        import subprocess, shutil
                        ffmpeg = shutil.which("ffmpeg")
                        if ffmpeg:
                            subprocess.run([
                                ffmpeg, "-y", "-i", tmp_path,
                                "-ar", "16000", "-ac", "1", "-f", "wav", wav_path
                            ], capture_output=True, timeout=10)
                            with sr.AudioFile(wav_path) as source:
                                audio_data = recognizer.record(source)
                        else:
                            return JSONResponse({"text": "", "error": f"Cannot process {suffix} format. Browser should send WAV."})
                    except Exception as conv_err:
                        return JSONResponse({"text": "", "error": f"Conversion failed: {str(conv_err)}"})
                    finally:
                        if os.path.exists(wav_path):
                            os.unlink(wav_path)
                else:
                    return JSONResponse({"text": "", "error": f"Audio read failed: {str(read_err)}"})

            # Google STT
            try:
                text = recognizer.recognize_google(audio_data, language=lang)
                return JSONResponse({"text": text, "engine": "google"})
            except sr.UnknownValueError:
                return JSONResponse({"text": "", "error": "Could not understand audio"})
            except sr.RequestError as e:
                return JSONResponse({"text": "", "error": f"STT service unavailable: {str(e)}. Check VPN/proxy."})

        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    except Exception as e:
        print(f"[STT] Error: {e}")
        return JSONResponse({"text": "", "error": str(e)})