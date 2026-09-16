"""Separate snapshot settings; all database-supported time units remain available."""
import sys

sys.path.insert(0, '/repro')
from superset_config import *  # noqa: F403

SESSION_COOKIE_NAME = 'csim_preview_session'
TIME_GRAIN_DENYLIST = []
# Native import migrates the two comparison tables to this upstream renderer.
FEATURE_FLAGS = {**FEATURE_FLAGS, 'AG_GRID_TABLE_ENABLED': True}  # noqa: F405
