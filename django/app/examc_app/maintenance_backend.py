import logging
from datetime import datetime

from constance import config
from django.utils import timezone
from maintenance_mode.backends import CacheBackend

logger = logging.getLogger(__name__)


class ScheduledCacheBackend(CacheBackend):
    """Maintenance ON if manually enabled OR within the Constance MAINT_START/MAINT_END window."""

    def get_value(self):
        if super().get_value():
            return True
        try:
            start, end = config.MAINT_START, config.MAINT_END
        except Exception as error:
            logger.warning("Cannot read maintenance window from Constance: %s", error)
            return False
        if isinstance(start, datetime) and isinstance(end, datetime):
            return start <= timezone.now() < end
        return False