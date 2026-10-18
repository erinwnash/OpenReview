"""
Per-media annotation bookkeeping.

OpenReview keeps one AnnotationStore for the whole window. Without this, notes
drawn on one piece of media stay in the store when the reviewer opens another,
and show up on that media's matching frame numbers. PerMediaAnnotations keeps
each media's notes apart: on a switch it stashes the store's contents under the
media being left and restores whatever was stashed for the media being opened.
"""
from __future__ import annotations

from typing import Any, Dict, Optional


class PerMediaAnnotations:
    def __init__(self, store: Any):
        self._store = store
        self._by_media: Dict[str, Dict[str, Any]] = {}
        self._current: Optional[str] = None

    @property
    def current(self) -> Optional[str]:
        return self._current

    def switch_to(self, media_key: str) -> None:
        """Make `media_key` the media the store describes.

        The first switch only adopts the store as it is (anything drawn before
        the first media was opened belongs to it). Later switches stash the
        store under the old media and load the new media's notes (empty if it
        has none yet).
        """
        if media_key == self._current:
            return
        if self._current is None:
            self._current = media_key
            return
        self._by_media[self._current] = self._store.to_dict()
        self._store.from_dict(self._by_media.get(media_key, {}))
        self._current = media_key

    def reset(self) -> None:
        """Forget everything (a new session)."""
        self._by_media.clear()
        self._current = None
