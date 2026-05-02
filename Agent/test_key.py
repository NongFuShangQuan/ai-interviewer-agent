from dotenv import load_dotenv
import os
from langchain_community.chat_models import ChatTongyi

load_dotenv()

llm = ChatTongyi(
    model="qwen-plus",
    dashscope_api_key=os.getenv("DASHSCOPE_API_KEY")
)

print("✅ Key 测试中...")
response = llm.invoke("你好，请回复'测试成功'")
print(response.content)