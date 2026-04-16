"""Scheduler task definitions for the admin Carbon Agent.

These tasks are registered via the Carbon Agent scheduler system.
They keep the admin agent in the loop for platform management.
"""

HEALTH_CHECK_TASK = {
    "name": "Platform Health Check",
    "system_prompt": (
        "You are the admin agent for the Carbon Agent multi-user platform. "
        "You have access to the orchestrator admin API. "
        "Always use the X-Admin-Key header for authentication. "
        "Report findings concisely and take action on issues."
    ),
    "prompt": (
        "Check platform health via the orchestrator API. "
        "GET /admin/health with header X-Admin-Key. "
        "If any sessions are in ERROR state, attempt to stop and restart them. "
        "If any sessions have been SPINNING_UP for >2 minutes, force stop them. "
        "Report your findings and actions taken."
    ),
    "schedule": {
        "minute": "*/5",
        "hour": "*",
        "day": "*",
        "month": "*",
        "weekday": "*",
    },
}

IDLE_CLEANUP_TASK = {
    "name": "Idle Session Cleanup",
    "system_prompt": (
        "You are the admin agent for the Carbon Agent multi-user platform. "
        "You have access to the orchestrator admin API. "
        "Always use the X-Admin-Key header for authentication. "
        "Spin down idle sessions to save costs."
    ),
    "prompt": (
        "Find all active sessions that have been idle for more than 15 minutes. "
        "GET /admin/health to get current state. "
        "For each idle session, POST /admin/users/{user_id}/session with {action: stop}. "
        "Only stop sessions that are truly idle - do NOT stop sessions with recent activity. "
        "Report how many sessions were spun down."
    ),
    "schedule": {
        "minute": "*/5",
        "hour": "*",
        "day": "*",
        "month": "*",
        "weekday": "*",
    },
}

DAILY_REPORT_TASK = {
    "name": "Daily Platform Report",
    "system_prompt": (
        "You are the admin agent for the Carbon Agent multi-user platform. "
        "You have access to the orchestrator admin API. "
        "Always use the X-Admin-Key header for authentication. "
        "Generate clear, actionable reports."
    ),
    "prompt": (
        "Generate a daily platform status report. "
        "GET /admin/health for metrics. "
        "GET /admin/users for user details. "
        "Report: total users, active/idle/stopped sessions, estimated cost, errors, volumes. "
        "Flag any cost overages or anomalies. "
        "Save the report to memory for future reference."
    ),
    "schedule": {
        "minute": "0",
        "hour": "9",
        "day": "*",
        "month": "*",
        "weekday": "*",
    },
}

WEEKLY_VOLUME_AUDIT_TASK = {
    "name": "Weekly Volume Audit",
    "system_prompt": (
        "You are the admin agent for the Carbon Agent multi-user platform. "
        "You have access to the orchestrator admin API. "
        "Always use the X-Admin-Key header for authentication. "
        "Perform thorough audits and recommend cleanup actions."
    ),
    "prompt": (
        "Perform a weekly audit of all persistent volumes. "
        "GET /admin/users to list all users with volumes. "
        "Identify orphaned volumes and inactive users (>7 days). "
        "Recommend cleanup actions for unused volumes. "
        "Save findings to memory."
    ),
    "schedule": {
        "minute": "0",
        "hour": "2",
        "day": "*",
        "month": "*",
        "weekday": "1",
    },
}

ALL_TASKS = [
    HEALTH_CHECK_TASK,
    IDLE_CLEANUP_TASK,
    DAILY_REPORT_TASK,
    WEEKLY_VOLUME_AUDIT_TASK,
]
