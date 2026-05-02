# 简单但真实感强的眼球算法
import math


def calculate_eye_gaze(state: str, thinking_time: float):
    if state == "thinking":
        # 思考时眼球缓慢随机漂移
        angle = math.sin(thinking_time) * 15
    elif state == "speaking":
        # 说话时注视“候选人”（屏幕右侧）
        angle = 12
    else:
        # 正常对话时轻微注视
        angle = math.sin(thinking_time * 2) * 8
    return angle  # 返回眼球X轴偏移角度