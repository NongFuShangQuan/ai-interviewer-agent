"""Edge TTS API - Natural neural voice synthesis"""
import io
import asyncio
import edge_tts
from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

router = APIRouter()

DEFAULT_VOICE = "zh-CN-XiaoxiaoNeural"

VOICES = {
    "xiaoxiao": "zh-CN-XiaoxiaoNeural",
    "xiaoyi": "zh-CN-XiaoyiNeural",
    "xiaohan": "zh-CN-XiaohanNeural",
    "xiaomeng": "zh-CN-XiaomengNeural",
    "xiaorui": "zh-CN-XiaoruiNeural",
    "xiaoxuan": "zh-CN-XiaoxuanNeural",
    "xiaoyan": "zh-CN-XiaoyanNeural",
    "yunjian": "zh-CN-YunjianNeural",
    "yunxi": "zh-CN-YunxiNeural",
    "yunxia": "zh-CN-YunxiaNeural",
    "yunyang": "zh-CN-YunyangNeural",
}


@router.get("/api/tts")
async def text_to_speech(
    text: str = Query(..., description="Text to speak"),
    voice: str = Query(DEFAULT_VOICE, description="Voice name"),
    rate: str = Query("+0%", description="Speech rate"),
):
    if not text.strip():
        return StreamingResponse(io.BytesIO(), media_type="audio/mpeg", status_code=200)
    if voice in VOICES:
        voice = VOICES[voice]
    try:
        communicate = edge_tts.Communicate(text, voice, rate=rate)
        audio_buffer = io.BytesIO()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_buffer.write(chunk["data"])
        audio_buffer.seek(0)
        return StreamingResponse(
            audio_buffer,
            media_type="audio/mpeg",
            headers={"Cache-Control": "public, max-age=3600"},
        )
    except Exception as e:
        print(f"[TTS] Error: {e}")
        return StreamingResponse(io.BytesIO(), media_type="audio/mpeg", status_code=500)


@router.get("/api/tts/voices")
async def list_voices():
    return {"voices": VOICES, "default": DEFAULT_VOICE}
