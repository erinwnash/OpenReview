import json
from unittest.mock import patch, MagicMock
from openreview.packages.updater import SoftwareUpdater, parse_version_tuple, UpdateInfo


def test_parse_version():
    assert parse_version_tuple("v1.2.3") == (1, 2, 3)
    assert parse_version_tuple("0.1.0") == (0, 1, 0)
    assert parse_version_tuple("2.10.4-beta") == (2, 10, 4)
    assert parse_version_tuple("invalid") == (0, 0, 0)


def test_updater_no_update():
    updater = SoftwareUpdater(current_version="1.0.0")
    mock_response = MagicMock()
    mock_response.__enter__.return_value = mock_response
    mock_response.read.return_value = json.dumps(
        {
            "tag_name": "v1.0.0",
            "name": "Version 1.0.0",
            "body": "No changes.",
            "html_url": "https://github.com/vfx/openreview/releases/tag/v1.0.0",
            "assets": [],
        }
    ).encode("utf-8")

    with patch("urllib.request.urlopen", return_value=mock_response):
        info = updater.check_for_updates()
        assert info.is_update_available is False
        assert info.latest_version == "1.0.0"


def test_updater_has_newer_release():
    updater = SoftwareUpdater(current_version="0.1.0")
    mock_response = MagicMock()
    mock_response.__enter__.return_value = mock_response
    mock_response.read.return_value = json.dumps(
        {
            "tag_name": "v0.1.5",
            "name": "OpenReview 0.1.5",
            "body": "Performance improvements and bug fixes.",
            "html_url": "https://github.com/vfx/openreview/releases/tag/v0.1.5",
            "assets": [
                {
                    "name": "OpenReview-0.1.5-Windows-x64.zip",
                    "browser_download_url": "https://github.com/downloads/OpenReview-0.1.5.zip"
                }
            ],
        }
    ).encode("utf-8")

    with patch("urllib.request.urlopen", return_value=mock_response):
        info = updater.check_for_updates()
        assert info.is_update_available is True
        assert info.latest_version == "0.1.5"
        assert info.download_url == "https://github.com/downloads/OpenReview-0.1.5.zip"
        assert "Performance improvements" in info.release_notes

