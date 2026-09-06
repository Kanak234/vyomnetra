"""VYOMNETRA SSA Situational Report & Executive PDF Generator.

Generates branded PDF/HTML executive briefings containing conjunction alert tables,
ISRO asset status matrices, space weather summaries, and re-entry risk assessments.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

from vyomnetra.config import settings
from vyomnetra.utils.logger import get_logger

logger = get_logger("vyomnetra.reports")


class SSASituationalReport(BaseModel):
    """Data model for executive SSA report."""
    report_title: str = "VYOMNETRA SSA DAILY EXECUTIVE BRIEFING"
    generated_at_utc: str
    security_classification: str = "RESTRICTED"
    total_active_satellites: int
    critical_conjunction_count: int
    isro_asset_conjunction_count: int
    space_weather_summary: str
    high_risk_reentries: List[Dict[str, Any]]
    conjunction_alerts: List[Dict[str, Any]]


class PDFReportGenerator:
    """Report generator producing branded HTML/PDF executive briefings."""

    def generate_report_html(self, report_data: SSASituationalReport) -> str:
        """Generates self-contained, print-styled HTML report."""
        alerts_html = ""
        for a in report_data.conjunction_alerts:
            alerts_html += f"""
            <tr>
                <td><strong>{a.get('primary_name')}</strong> (#{a.get('primary_norad')})</td>
                <td><strong>{a.get('secondary_name')}</strong> (#{a.get('secondary_norad')})</td>
                <td>{a.get('tca_utc')}</td>
                <td>{a.get('miss_distance_km')} km</td>
                <td>{a.get('calculated_pc'):.2e}</td>
                <td><span class="badge {a.get('severity').lower()}">{a.get('severity')}</span></td>
            </tr>
            """

        reentry_html = ""
        for r in report_data.high_risk_reentries:
            reentry_html += f"""
            <tr>
                <td>{r.get('sat_name')} (#{r.get('norad_id')})</td>
                <td>{r.get('decay_rate')} km/day</td>
                <td>{r.get('lifetime_days')} days</td>
                <td><span class="badge high">{r.get('risk_level')}</span></td>
            </tr>
            """

        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{report_data.report_title}</title>
    <style>
        body {{ font-family: 'Helvetica Neue', Arial, sans-serif; background: #0b0f19; color: #e2e8f0; margin: 0; padding: 40px; }}
        .header {{ border-bottom: 2px solid #3b82f6; padding-bottom: 20px; margin-bottom: 30px; display: flex; justify-content: space-between; }}
        .title {{ font-size: 24px; font-weight: bold; color: #60a5fa; letter-spacing: 1px; }}
        .classification {{ font-size: 14px; font-weight: bold; color: #ef4444; background: rgba(239,68,68,0.2); padding: 4px 12px; border-radius: 4px; }}
        .summary-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin-bottom: 30px; }}
        .card {{ background: #1e293b; padding: 15px; border-radius: 8px; border: 1px solid #334155; }}
        .card-num {{ font-size: 28px; font-weight: bold; color: #38bdf8; margin-top: 5px; }}
        .card-label {{ font-size: 12px; color: #94a3b8; text-transform: uppercase; }}
        table {{ width: 100%; border-collapse: collapse; margin-bottom: 30px; background: #1e293b; border-radius: 8px; overflow: hidden; }}
        th, td {{ padding: 12px 16px; text-align: left; border-bottom: 1px solid #334155; font-size: 14px; }}
        th {{ background: #0f172a; color: #94a3b8; font-weight: 600; text-transform: uppercase; font-size: 12px; }}
        .badge {{ padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; }}
        .badge.critical {{ background: #991b1b; color: #fca5a5; }}
        .badge.high {{ background: #9a3412; color: #fdba74; }}
        .badge.medium {{ background: #854d0e; color: #fef08a; }}
        .badge.low {{ background: #166534; color: #bbf7d0; }}
        .footer {{ border-top: 1px solid #334155; padding-top: 15px; font-size: 12px; color: #64748b; text-align: center; }}
    </style>
</head>
<body>
    <div class="header">
        <div>
            <div class="title">{report_data.report_title}</div>
            <div style="font-size: 12px; color: #94a3b8; margin-top: 5px;">Generated: {report_data.generated_at_utc} UTC | System: VYOMNETRA SSA v{settings.app_version}</div>
        </div>
        <div>
            <span class="classification">{report_data.security_classification}</span>
        </div>
    </div>

    <div class="summary-grid">
        <div class="card">
            <div class="card-label">Active Tracked Objects</div>
            <div class="card-num">{report_data.total_active_satellites:,}</div>
        </div>
        <div class="card">
            <div class="card-label">Critical Conjunctions</div>
            <div class="card-num" style="color: #ef4444;">{report_data.critical_conjunction_count}</div>
        </div>
        <div class="card">
            <div class="card-label">ISRO Priority Alerts</div>
            <div class="card-num" style="color: #f59e0b;">{report_data.isro_asset_conjunction_count}</div>
        </div>
        <div class="card">
            <div class="card-label">Space Weather State</div>
            <div class="card-num" style="font-size: 16px; margin-top: 12px; color: #10b981;">{report_data.space_weather_summary}</div>
        </div>
    </div>

    <h3 style="color: #93c5fd; margin-bottom: 15px;">Close Approach & Conjunction Warnings</h3>
    <table>
        <thead>
            <tr>
                <th>Primary Target</th>
                <th>Secondary Object</th>
                <th>TCA (UTC)</th>
                <th>Miss Distance</th>
                <th>Collision Prob (Pc)</th>
                <th>Severity</th>
            </tr>
        </thead>
        <tbody>
            {alerts_html if alerts_html else '<tr><td colspan="6" style="text-align:center; color:#64748b;">No active conjunction warnings detected in window.</td></tr>'}
        </tbody>
    </table>

    <h3 style="color: #93c5fd; margin-bottom: 15px;">High-Risk Atmospheric Re-Entry Pipeline</h3>
    <table>
        <thead>
            <tr>
                <th>Satellite Object</th>
                <th>Decay Rate</th>
                <th>Est. Remaining Lifetime</th>
                <th>Risk Classification</th>
            </tr>
        </thead>
        <tbody>
            {reentry_html if reentry_html else '<tr><td colspan="4" style="text-align:center; color:#64748b;">No objects currently below critical re-entry threshold.</td></tr>'}
        </tbody>
    </table>

    <div class="footer">
        CONFIDENTIAL & PROPRIETARY — ISRO / VYOMNETRA SPACE SITUATIONAL AWARENESS PLATFORM
    </div>
</body>
</html>
"""
        return html_content

    def export_report_to_file(self, report_data: SSASituationalReport, output_path: Path) -> Path:
        """Exports situational report to HTML file."""
        html_str = self.generate_report_html(report_data)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html_str, encoding="utf-8")
        logger.info(f"Exported SSA Situational Report to {output_path}")
        return output_path
