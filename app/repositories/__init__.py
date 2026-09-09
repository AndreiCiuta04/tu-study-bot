"""Persistence operations belong here; only repositories use ORM models/sessions.

Database setup lives in app.db. Add concrete repositories when domain persistence
is introduced; M0 liveness does not require database access.
"""
