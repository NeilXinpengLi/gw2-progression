"""Delivery service — generate and send weekly reports."""

import logging
import os
import smtplib
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from gw2_progression.services.report_service import generate_report
from gw2_progression.services.subscription_service import get_active_subscriptions, mark_delivered

logger = logging.getLogger("gw2.delivery")

SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASS = os.environ.get("SMTP_PASS", "")
SMTP_FROM = os.environ.get("SMTP_FROM", "gw2-progression@localhost")


async def deliver_weekly_reports():
    """Generate and send weekly reports for all active subscriptions due for delivery."""
    subs = await get_active_subscriptions()
    if not subs:
        logger.info("No subscriptions due for delivery")
        return

    for sub in subs:
        try:
            await deliver_single_report(sub)
        except Exception as e:
            logger.error("Failed to deliver report for %s: %s", sub["account_name"], e)


async def deliver_single_report(sub: dict):
    """Generate a report for a single subscription and send it."""
    account_name = sub["account_name"]
    email = sub["email"]

    report = await generate_report(
        account_name=account_name,
        report_type="weekly",
        title=f"Weekly Report — {account_name}",
        summary=f"Weekly progression report for {account_name} generated on {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')[:10]}",
        snapshot_time=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
    )

    if email and SMTP_HOST:
        _send_email(email, report)
        logger.info("Delivered weekly report to %s", email)

    await mark_delivered(sub["id"])
    logger.info("Marked subscription %d as delivered", sub["id"])


def _send_email(to_addr: str, report) -> None:
    """Send report via SMTP. Falls back to logging if SMTP not configured."""
    body = f"""Your Weekly GW2 Progression Report

Account: {report.account_name}
Value: {report.total_value_buy // 10000}g
Summary: {report.summary}

Recommendations:
{chr(10).join(f"- {r}" for r in (report.recommendations or [])[:5]) or "No recommendations."}

Generated: {report.created_at}
"""

    if not SMTP_HOST:
        logger.info("SMTP not configured. Report for %s would be sent to %s:\n%s", report.account_name, to_addr, body)
        return

    try:
        msg = MIMEMultipart()
        msg["From"] = SMTP_FROM
        msg["To"] = to_addr
        msg["Subject"] = report.title or f"Weekly Report — {report.account_name}"

        msg.attach(MIMEText(body, "plain", "utf-8"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            if SMTP_USER and SMTP_PASS:
                server.starttls()
                server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)

        logger.info("Email sent to %s", to_addr)
    except Exception as e:
        logger.warning("Failed to send email to %s: %s", to_addr, e)
