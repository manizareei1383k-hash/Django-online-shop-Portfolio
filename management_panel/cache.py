from django.core.cache import cache
from django.db import transaction


DASHBOARD_STATS_CACHE_KEY = 'management_panel:dashboard:stats'
DASHBOARD_STATS_CACHE_TIMEOUT = 30


def invalidate_dashboard_stats_cache():
    transaction.on_commit(
        lambda: cache.delete(DASHBOARD_STATS_CACHE_KEY),
        robust=True,
    )
