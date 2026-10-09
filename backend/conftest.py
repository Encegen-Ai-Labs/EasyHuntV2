# backend/conftest.py
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
# Tests must not depend on a developer's local .env. Environment variables take
# precedence over the env file, so pin the settings that change code paths.
# (Tests that need the extraction cache enable it explicitly.)
os.environ["EXTRACTION_CACHE_ENABLED"] = "false"
os.environ["CELERY_ENABLED"] = "false"
