"""Long-running weekly email scheduler (runs as its own container).

Checks once a minute; fires once per day when the configured weekday and time have passed.
Settings are read from the database each tick, so changes made in the app apply without a restart.

Usage: python -m reviewlens.scheduler            # loop forever
       python -m reviewlens.scheduler --once     # run the job now (testing)
"""

import logging
import os
import sys
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from reviewlens.emailer import run_scheduled
from reviewlens.storage import Store

log = logging.getLogger("reviewlens.scheduler")

DAYS = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
ENABLED_KEY, DAY_KEY, TIME_KEY, LAST_RUN_KEY = "schedule_enabled", "schedule_day", "schedule_time", "schedule_last_run"


def schedule_config(store: Store) -> dict:
    return {
        "enabled": store.get_setting(ENABLED_KEY, os.getenv("REPORT_SCHEDULE_ENABLED", "1")) == "1",
        "day": store.get_setting(DAY_KEY, os.getenv("REPORT_DAY", "MON")).upper(),
        "time": store.get_setting(TIME_KEY, os.getenv("REPORT_TIME", "09:00")),
        "tz": os.getenv("REPORT_TZ", "Asia/Kolkata"),
        "last_run": store.get_setting(LAST_RUN_KEY, ""),
    }


def is_due(cfg: dict, now: datetime) -> bool:
    """True once per day on the configured weekday after the configured time."""
    if not cfg["enabled"] or DAYS[now.weekday()] != cfg["day"]:
        return False
    hh, mm = (int(x) for x in cfg["time"].split(":"))
    return (now.hour, now.minute) >= (hh, mm) and cfg["last_run"] != now.date().isoformat()


def tick(store: Store, now: datetime | None = None) -> str | None:
    cfg = schedule_config(store)
    now = now or datetime.now(ZoneInfo(cfg["tz"]))
    if not is_due(cfg, now):
        return None
    store.set_setting(LAST_RUN_KEY, now.date().isoformat())  # mark first: never double-send
    try:
        result = run_scheduled(store)
    except Exception as exc:  # logged in email_log too
        result = f"failed: {exc}"
    log.info("scheduled run %s: %s", now.isoformat(timespec="minutes"), result)
    return result


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    store = Store()
    if "--once" in sys.argv:
        print(run_scheduled(store))
        return
    cfg = schedule_config(store)
    log.info("scheduler started: %s %s %s (enabled=%s)", cfg["day"], cfg["time"], cfg["tz"], cfg["enabled"])
    while True:
        try:
            tick(store)
        except Exception:
            log.exception("scheduler tick failed")
        time.sleep(60)


if __name__ == "__main__":
    main()
