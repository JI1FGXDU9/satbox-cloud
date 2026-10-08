"""Framework-independent notification planning. Push delivery is a separate module."""
from .planning import NotificationPreferences, NotificationPlan, build_plan, validate_preferences
