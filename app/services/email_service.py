"""Email Service - Send interview invitations"""
import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from jinja2 import Template
from app.core.config import get_settings

settings = get_settings()

INVITATION_TEMPLATE = """
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: 'Segoe UI', Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; border-radius: 12px 12px 0 0;">
        <h1 style="color: white; margin: 0; font-size: 24px;">🤖 AI 智能面试系统</h1>
        <p style="color: rgba(255,255,255,0.9); margin: 8px 0 0 0;">AI Interview Agent</p>
    </div>
    <div style="background: #f8f9fa; padding: 30px; border-radius: 0 0 12px 12px; border: 1px solid #e9ecef;">
        <p style="font-size: 16px; color: #333;">亲爱的 <strong>{{ candidate_name }}</strong>，您好！</p>
        <p style="color: #555;">感谢您投递简历。我们诚挚地邀请您参加 <strong>{{ job_title }}</strong> 职位的AI智能面试。</p>

        <div style="background: white; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #667eea;">
            <p style="margin: 0 0 8px 0;"><strong>📋 职位：</strong>{{ job_title }}</p>
            <p style="margin: 0 0 8px 0;"><strong>🔄 面试轮次：</strong>{{ total_rounds }} 轮问答</p>
            <p style="margin: 0;"><strong>⏱️ 预计时长：</strong>15-30 分钟</p>
        </div>

        <div style="text-align: center; margin: 30px 0;">
            <a href="{{ interview_url }}"
               style="display: inline-block; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 14px 40px; text-decoration: none; border-radius: 8px; font-size: 16px; font-weight: bold;">
                开始面试
            </a>
        </div>

        <p style="color: #888; font-size: 13px;">
            💡 提示：请在网络稳定的环境下进行面试，面试过程中请如实回答问题。面试完成后，系统将自动为您生成评估报告。
        </p>
        <hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;">
        <p style="color: #aaa; font-size: 12px; text-align: center;">
            此邮件由 AI 智能面试系统自动发送，请勿直接回复。
        </p>
    </div>
</body>
</html>
"""


def render_invitation_email(
    candidate_name: str,
    job_title: str,
    interview_url: str,
    total_rounds: int = 10,
) -> str:
    """Render the invitation email HTML"""
    template = Template(INVITATION_TEMPLATE)
    return template.render(
        candidate_name=candidate_name,
        job_title=job_title,
        interview_url=interview_url,
        total_rounds=total_rounds,
    )


async def send_invitation_email(
    to_email: str,
    candidate_name: str,
    job_title: str,
    interview_url: str,
    total_rounds: int = 10,
) -> bool:
    """Send interview invitation email via SMTP"""
    if not settings.smtp_user or not settings.smtp_password:
        print(f"[EMAIL MOCK] Would send invitation to {to_email}")
        print(f"[EMAIL MOCK] Interview URL: {interview_url}")
        return True

    html_content = render_invitation_email(
        candidate_name=candidate_name,
        job_title=job_title,
        interview_url=interview_url,
        total_rounds=total_rounds,
    )

    msg = MIMEMultipart("alternative")
    msg["From"] = settings.email_from
    msg["To"] = to_email
    msg["Subject"] = f"🤖 面试邀请 - {job_title} 职位"

    msg.attach(MIMEText(html_content, "html", "utf-8"))

    try:
        await aiosmtplib.send(
            msg,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_user,
            password=settings.smtp_password,
            use_tls=False,
            start_tls=True,
        )
        return True
    except Exception as e:
        print(f"[EMAIL ERROR] Failed to send to {to_email}: {e}")
        return False
