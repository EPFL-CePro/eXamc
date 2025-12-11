from datetime import datetime

from constance.signals import config_updated
from django.dispatch import receiver
from django.utils import timezone
from constance import config
from maintenance_mode.core import get_maintenance_mode, set_maintenance_mode
import logging

log = logging.getLogger(__name__)

def _get(key):
    try:
        return config._backend.get(key)  # safe read, no default write, no signal
    except Exception:
        return None

def recompute_now():
    log.info("********************* updating maintenance mode")
    start = _get("MAINT_START")
    end = _get("MAINT_END")
    if not (start and end):
        log.debug("maintenance: missing MAINT_START/END; skipping recompute")
        return
    now = timezone.localtime()
    should = False
    # if isinstance(start, datetime) and isinstance(end, datetime):
    #     should = start <= now < end
    cur = get_maintenance_mode()
    log.info("maintenance values : (should=%s, cur=%s, now=%s, start=%s, end=%s)",  should, cur, now, start, end)
    if should != cur:
        set_maintenance_mode(should)
        log.info("maintenance: set %s (now=%s, start=%s, end=%s)", "ON" if should else "OFF", now, start, end)

@receiver(config_updated, dispatch_uid="examc_app_constance_updated")
def constance_config_updated(sender, key, old_value, new_value, **kwargs):
    # Recompute on ANY key change – safe because recompute_now() only reads Constance
    recompute_now()
