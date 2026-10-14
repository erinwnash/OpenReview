import gc
import pytest
from PySide6.QtCore import QSettings
from openreview.core.preferences import PreferencesManager


@pytest.fixture(autouse=True)
def reset_preferences(tmp_path_factory):
    """Ensure clean preferences isolated from real ~/.openreview/preferences.json."""
    temp_dir = tmp_path_factory.mktemp("openreview_test_prefs")
    test_mgr = PreferencesManager(config_dir=temp_dir)
    PreferencesManager._instance = test_mgr
    try:
        QSettings("OpenReview", "OpenReview").clear()
    except Exception:
        pass
    yield
    PreferencesManager.reset_instance()
    try:
        QSettings("OpenReview", "OpenReview").clear()
    except Exception:
        pass
    gc.collect()
