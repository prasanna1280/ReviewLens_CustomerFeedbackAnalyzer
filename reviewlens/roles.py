"""Role definitions and permission matrix (pure Python, testable without Streamlit).

Roles are a workspace mode, not user accounts. Optional per-role PINs (ROLE_PIN_OWNER, ROLE_PIN_MANAGER,
ROLE_PIN_SUPPORT, falling back to APP_PASSWORD) stop casual switching into a more powerful role.
"""

import hmac
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Role:
    key: str
    title: str
    icon: str
    blurb: str
    tabs: tuple[str, ...]
    perms: frozenset[str]


# permissions
VIEW = "view"
UPLOAD = "upload"  # upload + analyse a new week
ADD_REVIEW = "add_review"
EDIT_ANALYSIS = "edit_analysis"  # sentiment / category / urgency / language / summary
EDIT_REPLY = "edit_reply"
MARK_HANDLED = "mark_handled"
MANAGE_WEEKS = "manage_weeks"  # regenerate report, delete week
SEND_EMAIL = "send_email"
EMAIL_SETTINGS = "email_settings"  # recipients + schedule

# tabs
OVERVIEW, TRENDS, URGENT, REVIEWS, REPORT, DATA, EMAIL = (
    "overview",
    "trends",
    "urgent",
    "reviews",
    "report",
    "data",
    "email",
)

ROLES: dict[str, Role] = {
    "owner": Role(
        "owner",
        "Business Owner",
        ":material/business_center:",
        "Weekly report, trends and the Monday email.",
        (REPORT, TRENDS, OVERVIEW, URGENT, REVIEWS, EMAIL),
        frozenset({VIEW, SEND_EMAIL, EMAIL_SETTINGS}),
    ),
    "manager": Role(
        "manager",
        "Operations Manager",
        ":material/insights:",
        "Upload reviews, correct tags, spot trends.",
        (OVERVIEW, TRENDS, URGENT, REVIEWS, REPORT, DATA, EMAIL),
        frozenset({VIEW, UPLOAD, ADD_REVIEW, EDIT_ANALYSIS, EDIT_REPLY, MARK_HANDLED, MANAGE_WEEKS, SEND_EMAIL}),
    ),
    "support": Role(
        "support",
        "Customer Support",
        ":material/support_agent:",
        "Work the urgent queue and post replies.",
        (URGENT, REVIEWS, REPORT),
        frozenset({VIEW, EDIT_REPLY, MARK_HANDLED}),
    ),
}

TAB_TITLES = {
    OVERVIEW: ":material/dashboard: Overview",
    TRENDS: ":material/trending_up: Trends",
    URGENT: ":material/priority_high: Urgent queue",
    REVIEWS: ":material/table_view: Reviews",
    REPORT: ":material/summarize: Weekly report",
    DATA: ":material/upload_file: Manage data",
    EMAIL: ":material/mail: Email",
}


def can(role_key: str | None, perm: str) -> bool:
    role = ROLES.get(role_key or "")
    return bool(role and perm in role.perms)


def pin_for(role_key: str) -> str:
    """Configured PIN for a role ('' = no PIN required)."""
    return os.getenv(f"ROLE_PIN_{role_key.upper()}", "") or os.getenv("APP_PASSWORD", "")


def check_pin(role_key: str, entered: str) -> bool:
    expected = pin_for(role_key)
    return not expected or hmac.compare_digest(entered.encode(), expected.encode())


# What each workspace can do, in display order (drives the role picker cards).
CAPABILITIES: tuple[tuple[str, str], ...] = (
    ("Weekly report", "tab:" + REPORT),
    ("Trends & dashboards", "tab:" + TRENDS),
    ("Reply to urgent reviews", EDIT_REPLY),
    ("Upload weekly reviews", UPLOAD),
    ("Correct tags, add reviews", EDIT_ANALYSIS),
    ("Manage weeks & reports", MANAGE_WEEKS),
    ("Send report email", SEND_EMAIL),
    ("Set email schedule", EMAIL_SETTINGS),
)


def capabilities(role_key: str) -> list[tuple[str, bool]]:
    """(label, allowed) for every capability, so all role cards list the same rows."""
    role = ROLES[role_key]
    return [
        (label, need.removeprefix("tab:") in role.tabs if need.startswith("tab:") else need in role.perms)
        for label, need in CAPABILITIES
    ]
