"""
Python SDK Client for OpenReview.
Provides clean programmatic control over local or remote OpenReview instances from Python scripts,
DCC applications (Nuke, Maya, Houdini), and pipeline production tools.
"""
from __future__ import annotations

import json
import socket
from typing import Optional, Dict, Any, List

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 45124


class OpenReviewError(Exception):
    """Raised when an OpenReview SDK remote call fails."""
    pass


class OpenReviewClient:
    """
    High-level Python SDK client communicating with an active OpenReview instance via JSON-RPC 2.0.
    """

    def __init__(
        self,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        timeout: float = 4.0,
    ):
        self.host = host
        self.port = port
        self.timeout = timeout
        self._msg_id = 0

    def _call(self, method: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Send a synchronous JSON-RPC request and return the result."""
        self._msg_id += 1
        payload = {
            "jsonrpc": "2.0",
            "id": self._msg_id,
            "method": method,
            "params": params or {},
        }
        data = (json.dumps(payload) + "\n").encode("utf-8")

        try:
            with socket.create_connection((self.host, self.port), timeout=self.timeout) as s:
                s.sendall(data)
                response_data = b""
                while not response_data.endswith(b"\n"):
                    chunk = s.recv(4096)
                    if not chunk:
                        break
                    response_data += chunk
        except (ConnectionRefusedError, socket.timeout, OSError) as e:
            raise OpenReviewError(f"Could not connect to OpenReview on {self.host}:{self.port} - {e}") from e

        if not response_data:
            raise OpenReviewError("Empty response received from OpenReview IPC server.")

        try:
            resp = json.loads(response_data.decode("utf-8"))
        except Exception as e:
            raise OpenReviewError(f"Invalid JSON response: {response_data!r}") from e

        if "error" in resp:
            err = resp["error"]
            raise OpenReviewError(f"RPC Error [{err.get('code')}]: {err.get('message')}")

        return resp.get("result")

    # --------------------------------------------------------------------------
    # Public Client API
    # --------------------------------------------------------------------------
    def ping(self) -> bool:
        """Verify connection to OpenReview application."""
        try:
            res = self._call("ping")
            return res.get("status") == "pong"
        except OpenReviewError:
            return False

    def get_status(self) -> Dict[str, Any]:
        """Query current state: media path, frame numbers, fps, playback, and color adjustments."""
        return self._call("get_status")

    def load_media(self, path: str) -> bool:
        """Load a video file, image sequence, or session into OpenReview."""
        res = self._call("load_media", {"path": str(path)})
        return res.get("status") == "loaded"

    def play(self) -> bool:
        """Start playback."""
        res = self._call("play")
        return bool(res.get("is_playing", False))

    def pause(self) -> bool:
        """Pause playback."""
        res = self._call("pause")
        return not bool(res.get("is_playing", False))

    def toggle_play(self) -> bool:
        """Toggle between play and pause."""
        res = self._call("toggle_play")
        return bool(res.get("is_playing", False))

    def seek(self, frame: int) -> int:
        """Seek playhead to specific frame number."""
        res = self._call("seek", {"frame": int(frame)})
        return int(res.get("current_frame", frame))

    def set_fps(self, fps: float) -> float:
        """Set playback frame rate."""
        res = self._call("set_fps", {"fps": float(fps)})
        return float(res.get("fps", fps))

    def set_in_out(self, in_frame: int, out_frame: int) -> Dict[str, int]:
        """Set playback In and Out boundaries."""
        return self._call("set_in_out", {"in_frame": int(in_frame), "out_frame": int(out_frame)})

    def set_exposure(self, ev: float) -> float:
        """Adjust viewer exposure in EV stops."""
        res = self._call("set_color", {"exposure": float(ev)})
        return float(res.get("exposure", ev))

    def set_gain(self, gain: float) -> float:
        """Adjust viewer linear gain."""
        res = self._call("set_color", {"gain": float(gain)})
        return float(res.get("gain", gain))

    def set_gamma(self, gamma: float) -> float:
        """Adjust viewer gamma."""
        res = self._call("set_color", {"gamma": float(gamma)})
        return float(res.get("gamma", gamma))

    def set_saturation(self, sat: float) -> float:
        """Adjust viewer color saturation."""
        res = self._call("set_color", {"saturation": float(sat)})
        return float(res.get("saturation", sat))

    def set_color(
        self,
        gain: Optional[float] = None,
        gamma: Optional[float] = None,
        saturation: Optional[float] = None,
        exposure: Optional[float] = None,
    ) -> Dict[str, float]:
        """Adjust multiple viewer color grading parameters simultaneously."""
        params: Dict[str, float] = {}
        if gain is not None:
            params["gain"] = float(gain)
        if gamma is not None:
            params["gamma"] = float(gamma)
        if saturation is not None:
            params["saturation"] = float(saturation)
        if exposure is not None:
            params["exposure"] = float(exposure)
        return self._call("set_color", params)

    def add_bookmark(self, frame: Optional[int] = None, note: str = "") -> List[int]:
        """Add timeline bookmark at specified frame (or current frame if None)."""
        params: Dict[str, Any] = {}
        if frame is not None:
            params["frame"] = int(frame)
        if note:
            params["note"] = str(note)
        res = self._call("add_bookmark", params)
        return list(res.get("bookmarks", []))

    def clear_bookmarks(self) -> List[int]:
        """Clear all bookmarks on timeline."""
        res = self._call("clear_bookmarks")
        return list(res.get("bookmarks", []))

    def export_current_frame(self, destination: str) -> str:
        """Save a snapshot capture of the current viewport frame to destination path."""
        res = self._call("export_frame", {"destination": str(destination)})
        return str(res.get("destination", destination))

    def export_frame(self, destination: str, frame: Optional[int] = None) -> bool:
        """Save a snapshot capture of a frame to destination path."""
        params: Dict[str, Any] = {"destination": str(destination)}
        if frame is not None:
            params["frame"] = int(frame)
        res = self._call("export_frame", params)
        return bool(res.get("status") == "exported" or res.get("destination"))

