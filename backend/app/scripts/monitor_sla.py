"""Reviewer Queue SLA Heartbeat & Alert Dispatcher CLI.

Monitors applications in unassigned review state against the SLA wait threshold (>30m).
Can be run via cron / scheduled background task or health monitoring system.

Usage:
    python -m app.scripts.monitor_sla [--trigger-alert] [--strict] [--json]
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys

# Ensure default fallback settings for standalone invocation
os.environ.setdefault("SECRET_KEY", "cutover-verification-ephemeral-key-min-32-chars")
os.environ.setdefault("DATABASE_URL", "sqlite:///./policynest_local.db")

from app.core.config import get_settings
from app.core.db import get_sessionmaker
from app.services.review import check_review_sla_status

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("monitor_sla")


def run_sla_check(*, trigger_alert: bool = False) -> dict:
    settings = get_settings()
    SessionLocal = get_sessionmaker()
    with SessionLocal() as db:
        from sqlalchemy import inspect

        engine = db.get_bind()
        if "applications" not in inspect(engine).get_table_names():
            return {
                "status": "UNINITIALIZED",
                "message": "Database tables have not been created yet. Run postgres_cutover or migrations first.",
                "sla_threshold_minutes": settings.sla_review_unassigned_threshold_minutes,
                "total_pending_queue": 0,
                "total_unassigned": 0,
                "breach_count": 0,
                "max_wait_minutes": 0.0,
                "breached_applications": [],
                "alert_webhook_configured": bool(settings.sla_alert_webhook_url),
                "alert_dispatched": False,
                "environment": settings.app_env,
            }

        res = check_review_sla_status(db, trigger_alert=trigger_alert)
        out = res.model_dump(mode="json")
        out["environment"] = settings.app_env
        out["alert_webhook_configured"] = bool(settings.sla_alert_webhook_url)
        return out


def main() -> int:
    parser = argparse.ArgumentParser(description="PolicyNest Reviewer Queue SLA Heartbeat Monitor")
    parser.add_argument("--trigger-alert", action="store_true", help="Dispatch webhook if SLA breached")
    parser.add_argument("--strict", action="store_true", help="Exit with code 2 if queue is breached")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")

    args = parser.parse_args()
    try:
        data = run_sla_check(trigger_alert=args.trigger_alert)
        if args.json:
            print(json.dumps(data, indent=2))
        else:
            print("\n=== PolicyNest Reviewer Queue SLA Report ===")
            print(f"Status:                 {data['status']}")
            print(f"SLA Threshold:          {data['sla_threshold_minutes']} minutes")
            print(f"Pending Queue Total:    {data['total_pending_queue']}")
            print(f"Unassigned Count:       {data['total_unassigned']}")
            print(f"Breached Count (>30m):  {data['breach_count']}")
            print(f"Longest Wait Time:      {data['max_wait_minutes']} minutes")
            print(f"Oldest Unassigned ID:   {data.get('oldest_unassigned_application_id') or 'None'}")
            print(f"Webhook Configured:     {data['alert_webhook_configured']}")
            print(f"Alert Dispatched:       {data['alert_dispatched']}")
            if data["breached_applications"]:
                print("\nTop Breached Applications:")
                for b in data["breached_applications"][:5]:
                    print(
                        f" - [{b['reference_code']}] Applicant: {b.get('applicant_name') or 'N/A'}, "
                        f"Wait: {b['wait_time_minutes']}m, Region: {b.get('region') or 'N/A'}"
                    )
            print("============================================\n")

        if args.strict and data["status"] == "BREACHED":
            return 2
        return 0
    except Exception as exc:
        logger.exception("SLA monitor encountered error: %s", exc)
        if args.json:
            print(json.dumps({"status": "ERROR", "error": str(exc)}, indent=2))
        return 1


if __name__ == "__main__":
    sys.exit(main())
