"""
Interview Result Export Service
Supports: JSON, CSV, HTML report formats
"""
import json
import csv
import io
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger("export_service")


def export_json(interview_data: dict) -> str:
    """Export interview result as JSON string"""
    return json.dumps(interview_data, ensure_ascii=False, indent=2, default=str)


def export_csv(interview_data: dict) -> str:
    """Export interview result as CSV string"""
    output = io.StringIO()
    writer = csv.writer(output)

    # Header section
    writer.writerow(["AI Interview Report"])
    writer.writerow([])

    # Basic info
    writer.writerow(["Basic Info"])
    writer.writerow(["Candidate", interview_data.get("candidate_name", "")])
    writer.writerow(["Job Title", interview_data.get("job_title", "")])
    writer.writerow(["Status", interview_data.get("status", "")])
    writer.writerow(["Date", interview_data.get("created_at", "")])
    writer.writerow([])

    # Scores
    evaluation = interview_data.get("evaluation", {})
    if evaluation:
        writer.writerow(["Scores"])
        score_labels = {
            "overall_score": "Overall",
            "technical_score": "Technical",
            "communication_score": "Communication",
            "problem_solving_score": "Problem Solving",
            "cultural_fit_score": "Cultural Fit",
            "experience_score": "Experience",
        }
        for key, label in score_labels.items():
            writer.writerow([label, evaluation.get(key, "-")])
        writer.writerow([])
        writer.writerow(["Recommendation", evaluation.get("recommendation", "-")])
        writer.writerow(["Summary", evaluation.get("summary", "")])
        writer.writerow([])

    # Dialogue
    messages = interview_data.get("messages", [])
    if messages:
        writer.writerow(["Interview Dialogue"])
        writer.writerow(["Round", "Role", "Content"])
        for msg in messages:
            role = "AI" if msg.get("role") == "ai" else "Candidate"
            writer.writerow([msg.get("round_num", ""), role, msg.get("content", "")])

    return output.getvalue()


def export_html(interview_data: dict) -> str:
    """Export interview result as HTML report"""
    candidate = interview_data.get("candidate_name", "")
    job_title = interview_data.get("job_title", "")
    status = interview_data.get("status", "")
    created = interview_data.get("created_at", "")
    evaluation = interview_data.get("evaluation", {})
    messages = interview_data.get("messages", [])

    score_html = ""
    if evaluation:
        score_labels = {
            "overall_score": ("Overall", "#4f46e5"),
            "technical_score": ("Technical", "#059669"),
            "communication_score": ("Communication", "#0891b2"),
            "problem_solving_score": ("Problem Solving", "#7c3aed"),
            "cultural_fit_score": ("Cultural Fit", "#d97706"),
            "experience_score": ("Experience", "#dc2626"),
        }
        for key, (label, color) in score_labels.items():
            val = evaluation.get(key, 0)
            pct = min(100, max(0, float(val) * 10)) if val else 0
            score_html += f'''
            <div style="margin-bottom:12px">
                <div style="display:flex;justify-content:space-between;margin-bottom:4px">
                    <span style="font-size:13px;font-weight:600">{label}</span>
                    <span style="font-size:13px;font-weight:700;color:{color}">{val}/10</span>
                </div>
                <div style="background:#e5e7eb;border-radius:4px;height:8px">
                    <div style="background:{color};width:{pct}%;height:8px;border-radius:4px"></div>
                </div>
            </div>'''

    dialogue_html = ""
    for msg in messages:
        role = "AI" if msg.get("role") == "ai" else "Candidate"
        bg = "#f0f4ff" if role == "AI" else "#f0fdf4"
        border = "#4f46e5" if role == "AI" else "#059669"
        content = msg.get("content", "").replace("\n", "<br>")
        dialogue_html += f'''
        <div style="margin-bottom:12px;padding:12px;background:{bg};border-left:3px solid {border};border-radius:0 8px 8px 0">
            <div style="font-size:11px;font-weight:600;color:{border};margin-bottom:4px">
                {role} - Round {msg.get("round_num", "")}
            </div>
            <div style="font-size:13px;color:#374151">{content}</div>
        </div>'''

    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>Interview Report - {candidate}</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 800px; margin: 0 auto; padding: 40px 20px; color: #1f2937; background: #f9fafb; }}
h1 {{ font-size: 24px; color: #111827; }}
.section {{ background: white; border: 1px solid #e5e7eb; border-radius: 12px; padding: 24px; margin-bottom: 20px; }}
.section h2 {{ font-size: 16px; color: #4f46e5; margin-bottom: 16px; }}
.info-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }}
.info-item label {{ font-size: 11px; color: #6b7280; text-transform: uppercase; display: block; }}
.info-item span {{ font-size: 14px; font-weight: 600; }}
</style>
</head>
<body>
<h1>AI Interview Report</h1>
<div class="section">
    <h2>Basic Info</h2>
    <div class="info-grid">
        <div class="info-item"><label>Candidate</label><span>{candidate}</span></div>
        <div class="info-item"><label>Job Title</label><span>{job_title}</span></div>
        <div class="info-item"><label>Status</label><span>{status}</span></div>
        <div class="info-item"><label>Date</label><span>{created}</span></div>
    </div>
</div>
<div class="section">
    <h2>Scores</h2>
    {score_html if score_html else "<p>No evaluation data</p>"}
    {f'<div style="margin-top:16px;padding:12px;background:#f0fdf4;border-radius:8px"><strong>Recommendation:</strong> {evaluation.get("recommendation", "-")}</div>' if evaluation else ""}
</div>
<div class="section">
    <h2>Summary</h2>
    <p style="font-size:14px;line-height:1.7;color:#374151">{evaluation.get("summary", "N/A")}</p>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:16px">
        <div style="padding:12px;background:#f0fdf4;border-radius:8px">
            <div style="font-weight:600;color:#059669;margin-bottom:4px">Strengths</div>
            <div style="font-size:13px;color:#374151">{evaluation.get("strengths", "N/A").replace(chr(10), "<br>")}</div>
        </div>
        <div style="padding:12px;background:#fef2f2;border-radius:8px">
            <div style="font-weight:600;color:#dc2626;margin-bottom:4px">Areas to Improve</div>
            <div style="font-size:13px;color:#374151">{evaluation.get("weaknesses", "N/A").replace(chr(10), "<br>")}</div>
        </div>
    </div>
</div>
<div class="section">
    <h2>Interview Dialogue</h2>
    {dialogue_html if dialogue_html else "<p>No dialogue data</p>"}
</div>
<div style="text-align:center;color:#9ca3af;font-size:12px;margin-top:32px">
    Generated by AI Interview System | {datetime.now().strftime("%Y-%m-%d %H:%M")}
</div>
</body>
</html>'''
    return html