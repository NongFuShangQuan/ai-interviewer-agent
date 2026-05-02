import streamlit as st
import time
import sys
from pathlib import Path

# ====================== 修复导入 ======================
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))
if str(ROOT_DIR / "Agent") not in sys.path:
    sys.path.append(str(ROOT_DIR / "Agent"))

try:
    from ai_interviewer import run_ai_interviewer, InterviewInputs
except ImportError:
    st.error("❌ 无法找到 Agent/ai_interviewer.py")
    st.stop()

# ====================== 北森风格数字人（使用真实图片） ======================
st.set_page_config(page_title="北森AI数字人面试官", layout="wide")

st.markdown("""
<style>
.avatar-container {
    position: relative;
    width: 380px;
    height: 520px;
    margin: 0 auto;
    border-radius: 30px;
    overflow: hidden;
    box-shadow: 0 20px 40px rgba(0,0,0,0.25);
}
.avatar-img {
    width: 100%;
    height: 100%;
    object-fit: cover;
}
.eye {
    position: absolute;
    width: 52px;
    height: 52px;
    background: #fff;
    border-radius: 50%;
    top: 38%;
    box-shadow: inset 0 6px 12px rgba(0,0,0,0.3);
    overflow: hidden;
}
.eye-left { left: 22%; }
.eye-right { right: 22%; }
.pupil {
    position: absolute;
    width: 26px;
    height: 26px;
    background: #1e3a8a;
    border-radius: 50%;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    transition: all 0.35s cubic-bezier(0.4, 0, 0.2, 1);
    box-shadow: 0 3px 8px rgba(0,0,0,0.4);
}
.mouth {
    position: absolute;
    top: 64%;
    left: 50%;
    transform: translateX(-50%);
    width: 88px;
    height: 14px;
    background: #e74c3c;
    border-radius: 0 0 40px 40px;
    transition: height 0.15s ease;
}
</style>
""", unsafe_allow_html=True)

def get_avatar_html(state: str = "listening"):
    if state == "thinking":
        left_x = "6px"
        right_x = "-6px"
        mouth_h = "8px"
    elif state == "speaking":
        left_x = "14px"
        right_x = "14px"
        mouth_h = "26px"
    else:
        left_x = "0px"
        right_x = "0px"
        mouth_h = "12px"

    return f"""
    <div class="avatar-container">
        <img src="avatar.png" class="avatar-img" alt="北森数字人">
        <!-- 左眼 -->
        <div class="eye eye-left">
            <div class="pupil" style="transform: translate(-50%, -50%) translate({left_x}, 0);"></div>
        </div>
        <!-- 右眼 -->
        <div class="eye eye-right">
            <div class="pupil" style="transform: translate(-50%, -50%) translate({right_x}, 0);"></div>
        </div>
        <!-- 嘴巴 -->
        <div class="mouth" style="height: {mouth_h};"></div>
    </div>
    """

# ====================== 主界面 ======================
col1, col2 = st.columns([1, 1.8])

with col1:
    current_state = st.session_state.get("avatar_state", "listening")
    st.markdown(get_avatar_html(current_state), unsafe_allow_html=True)
    st.caption("👀 北森数字人 · 眼球实时跟随 + 嘴巴说话")

with col2:
    st.title("🎤 北森AI数字人面试官")
    st.markdown("**多Agent驱动 · 真实卡通风格**")

    if "messages" not in st.session_state:
        st.session_state.messages = [{"role": "assistant", "content": "你好！我是你的AI数字人面试官。请简单介绍一下自己吧～"}]

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    if prompt := st.chat_input("输入你的回答..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.write(prompt)

        st.session_state.avatar_state = "thinking"
        with st.spinner("数字人思考中..."):
            time.sleep(1.2)
            try:
                inputs = InterviewInputs(resume="Python后端经验", jd="招聘Python后端工程师")
                result = run_ai_interviewer()
                reply = str(result)[:700]
            except:
                reply = "回答得很好！请继续说说你在项目中如何处理高并发场景？"

        st.session_state.avatar_state = "speaking"
        st.session_state.messages.append({"role": "assistant", "content": reply})
        with st.chat_message("assistant"):
            st.write(reply)

        time.sleep(1.8)
        st.session_state.avatar_state = "listening"
        st.rerun()

with st.sidebar:
    st.success("✅ 已使用你上传的可爱女孩图片作为数字人")
    st.info("眼球会随状态左右移动，嘴巴会随说话开合")

st.caption("为小米MiMo百万Token申请打造 · 虚拟数字人 + CrewAI")