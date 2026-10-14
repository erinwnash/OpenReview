"""
Multi-User Remote Dailies Sync Engine for OpenReview.
Provides real-time synchronized playback, collaborative whiteboard markup,
color grade mirroring, and group review chat across studio workstations.
"""
from __future__ import annotations

import json
from typing import Optional, List, Dict, Any, Set
from PySide6.QtCore import QObject, Signal, QByteArray
from PySide6.QtNetwork import QTcpServer, QTcpSocket, QHostAddress


class DailiesSyncEngine(QObject):
    """
    Studio Network Synchronization Engine.
    Operates as either a Dailies Host Server or a Participating Client.
    """

    # Connection & Session Signals
    status_changed = Signal(bool, str)       # (connected, status_text)
    mode_changed = Signal(str)               # 'offline', 'host', 'client'
    peer_joined = Signal(str)                # username
    peer_left = Signal(str)                  # username
    peer_list_updated = Signal(list)         # list of usernames
    presenter_changed = Signal(str)          # current presenter username
    room_info_updated = Signal(str)          # room name

    # Remote Action Signals
    remote_playback_received = Signal(dict)  # playback payload (frame, is_playing, etc.)
    remote_media_received = Signal(str)      # media path / filename
    remote_color_received = Signal(dict)      # color grade payload
    remote_stroke_received = Signal(int, dict) # (frame, stroke dict)
    remote_annotations_cleared = Signal(int) # frame (-1 for all)
    remote_note_received = Signal(int, str)  # (frame, note text)
    chat_message_received = Signal(str, str) # (sender, text)

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._mode: str = "offline"  # 'offline', 'host', 'client'
        self._username: str = "Artist"
        self._room_name: str = "VFX Review Main"
        self._presenter: str = "Artist"
        self._is_following: bool = True

        # Host components
        self._server: Optional[QTcpServer] = None
        self._client_sockets: List[QTcpSocket] = []
        self._client_names: Dict[QTcpSocket, str] = {}
        self._socket_buffers: Dict[QTcpSocket, bytearray] = {}

        # Client components
        self._client_socket: Optional[QTcpSocket] = None
        self._client_buffer: bytearray = bytearray()

    # --------------------------------------------------------------------------
    # Properties & State
    # --------------------------------------------------------------------------
    @property
    def mode(self) -> str:
        return self._mode

    @property
    def is_connected(self) -> bool:
        return self._mode in ("host", "client")

    @property
    def is_host(self) -> bool:
        return self._mode == "host"

    @property
    def is_presenter(self) -> bool:
        return self._presenter == self._username

    @property
    def username(self) -> str:
        return self._username

    @property
    def presenter(self) -> str:
        return self._presenter

    @property
    def room_name(self) -> str:
        return self._room_name

    @room_name.setter
    def room_name(self, name: str) -> None:
        self._room_name = name.strip() or "VFX Review Main"
        if self._mode == "host":
            self._send_raw_message({
                "type": "ROOM_INFO",
                "sender": self._username,
                "payload": {"room_name": self._room_name, "presenter": self._presenter},
            })
            self.room_info_updated.emit(self._room_name)

    @property
    def is_following(self) -> bool:
        return self._is_following

    def set_following(self, following: bool) -> None:
        self._is_following = bool(following)

    # --------------------------------------------------------------------------
    # Host Server Management
    # --------------------------------------------------------------------------
    def start_host(self, port: int = 9090, username: str = "Host", room_name: str = "VFX Review Main") -> bool:
        """Start hosting a local Dailies Review session on given port."""
        self.disconnect_session()
        self._username = username.strip() or "Host"
        self._room_name = room_name.strip() or "VFX Review Main"
        self._presenter = self._username

        self._server = QTcpServer(self)
        self._server.newConnection.connect(self._on_new_incoming_connection)

        if not self._server.listen(QHostAddress.SpecialAddress.Any, port):
            err = self._server.errorString()
            self._server = None
            self.status_changed.emit(False, f"Host failed: {err}")
            return False

        self._mode = "host"
        self.mode_changed.emit("host")
        self.status_changed.emit(True, f"Hosting Dailies on port {port}")
        self._broadcast_peer_list()
        return True

    def _on_new_incoming_connection(self) -> None:
        if not self._server:
            return
        socket = self._server.nextPendingConnection()
        if not socket:
            return
        socket.setParent(self)

        self._client_sockets.append(socket)
        self._client_names[socket] = f"Peer_{socket.peerPort()}"
        self._socket_buffers[socket] = bytearray()

        socket.readyRead.connect(lambda s=socket: self._on_socket_ready_read(s))
        socket.disconnected.connect(lambda s=socket: self._on_socket_disconnected(s))

    def _on_socket_ready_read(self, socket: QTcpSocket) -> None:
        buf = self._socket_buffers.get(socket)
        if buf is None:
            return

        try:
            data = bytes(socket.readAll().data())
        except (RuntimeError, AttributeError):
            return
        buf.extend(data)

        # Parse newline delimited JSON
        while b"\n" in buf:
            line, _, rest = buf.partition(b"\n")
            buf.clear()
            buf.extend(rest)
            if line.strip():
                try:
                    msg = json.loads(line.decode("utf-8"))
                    self._handle_incoming_message(msg, source_socket=socket)
                except Exception as e:
                    print(f"[DailiesSyncEngine] Error parsing packet: {e}")

    def _on_socket_disconnected(self, socket: QTcpSocket) -> None:
        peer_name = self._client_names.pop(socket, "Peer")
        if socket in self._client_sockets:
            self._client_sockets.remove(socket)
        self._socket_buffers.pop(socket, None)
        try:
            socket.deleteLater()
        except RuntimeError:
            pass

        try:
            self.peer_left.emit(peer_name)
            self._broadcast_peer_list()
        except RuntimeError:
            pass

    # --------------------------------------------------------------------------
    # Client Join Management
    # --------------------------------------------------------------------------
    def join_host(self, host: str, port: int = 9090, username: str = "Reviewer", room_name: str = "") -> bool:
        """Connect to an existing Dailies Review host."""
        self.disconnect_session()
        self._username = username.strip() or "Reviewer"
        if room_name.strip():
            self._room_name = room_name.strip()

        self._client_socket = QTcpSocket(self)
        self._client_buffer = bytearray()
        self._client_socket.readyRead.connect(self._on_client_ready_read)
        self._client_socket.connected.connect(self._on_client_connected)
        self._client_socket.disconnected.connect(self._on_client_disconnected)

        self._client_socket.connectToHost(host, port)
        self.status_changed.emit(False, f"Connecting to {host}:{port}...")
        return True

    def _on_client_connected(self) -> None:
        self._mode = "client"
        try:
            self.mode_changed.emit("client")
            self.status_changed.emit(True, "Connected to Dailies Session")
        except RuntimeError:
            pass

        # Send JOIN handshake
        self._send_raw_message({
            "type": "JOIN",
            "sender": self._username,
            "payload": {
                "username": self._username,
                "room_name": self._room_name,
            },
        })

    def _on_client_ready_read(self) -> None:
        if not self._client_socket:
            return
        try:
            data = bytes(self._client_socket.readAll().data())
        except (RuntimeError, AttributeError):
            return
        self._client_buffer.extend(data)

        while b"\n" in self._client_buffer:
            line, _, rest = self._client_buffer.partition(b"\n")
            self._client_buffer.clear()
            self._client_buffer.extend(rest)
            if line.strip():
                try:
                    msg = json.loads(line.decode("utf-8"))
                    self._handle_incoming_message(msg, source_socket=None)
                except Exception as e:
                    print(f"[DailiesSyncEngine] Client error parsing packet: {e}")

    def _on_client_disconnected(self) -> None:
        self.disconnect_session()
        try:
            self.status_changed.emit(False, "Disconnected from Dailies Host")
        except RuntimeError:
            pass

    def disconnect_session(self) -> None:
        """Disconnect active host or client session."""
        if self._mode == "host":
            for s in list(self._client_sockets):
                try:
                    s.blockSignals(True)
                    s.readyRead.disconnect()
                except Exception:
                    pass
                try:
                    s.disconnected.disconnect()
                except Exception:
                    pass
                try:
                    s.disconnectFromHost()
                    s.deleteLater()
                except Exception:
                    pass
            self._client_sockets.clear()
            self._client_names.clear()
            self._socket_buffers.clear()
            if self._server:
                try:
                    self._server.newConnection.disconnect()
                except Exception:
                    pass
                self._server.close()
                self._server.deleteLater()
                self._server = None

        if self._mode == "client" and self._client_socket:
            try:
                self._client_socket.blockSignals(True)
                self._client_socket.readyRead.disconnect()
            except Exception:
                pass
            try:
                self._client_socket.connected.disconnect()
            except Exception:
                pass
            try:
                self._client_socket.disconnected.disconnect()
            except Exception:
                pass
            try:
                self._client_socket.disconnectFromHost()
                self._client_socket.deleteLater()
            except Exception:
                pass
            self._client_socket = None
            self._client_buffer.clear()

        self._mode = "offline"
        try:
            self.mode_changed.emit("offline")
            self.status_changed.emit(False, "Offline")
        except RuntimeError:
            pass

    # --------------------------------------------------------------------------
    # Message Dispatcher & Relay
    # --------------------------------------------------------------------------
    def _handle_incoming_message(self, msg: Dict[str, Any], source_socket: Optional[QTcpSocket] = None) -> None:
        msg_type = msg.get("type")
        sender = msg.get("sender", "Unknown")
        payload = msg.get("payload", {})

        # If we are host, relay packet to all other client sockets
        if self._mode == "host":
            if msg_type == "JOIN" and source_socket:
                joined_name = payload.get("username", sender)
                self._client_names[source_socket] = joined_name
                self.peer_joined.emit(joined_name)
                # Send room info & current presenter to newly connected client
                welcome_packet = (json.dumps({
                    "type": "ROOM_INFO",
                    "sender": self._username,
                    "payload": {
                        "room_name": self._room_name,
                        "presenter": self._presenter,
                    },
                }) + "\n").encode("utf-8")
                try:
                    source_socket.write(welcome_packet)
                    source_socket.flush()
                except RuntimeError:
                    pass
                self._broadcast_peer_list()
                return

            self._relay_to_other_clients(msg, exclude_socket=source_socket)

        # Process locally
        if msg_type == "ROOM_INFO":
            r_name = payload.get("room_name", "")
            if r_name:
                self._room_name = r_name
                self.room_info_updated.emit(self._room_name)
            pres = payload.get("presenter", "")
            if pres:
                self._presenter = pres
                self.presenter_changed.emit(pres)

        elif msg_type == "PEER_LIST":
            peers = payload.get("peers", [])
            presenter = payload.get("presenter", self._presenter)
            self._presenter = presenter
            self.presenter_changed.emit(presenter)
            self.peer_list_updated.emit(peers)

        elif msg_type == "PLAYBACK":
            if self._is_following or sender == self._presenter:
                self.remote_playback_received.emit(payload)

        elif msg_type == "MEDIA":
            if self._is_following:
                path = payload.get("path", "")
                if path:
                    self.remote_media_received.emit(path)

        elif msg_type == "COLOR":
            if self._is_following:
                self.remote_color_received.emit(payload)

        elif msg_type == "STROKE":
            frame = payload.get("frame", 1001)
            stroke_data = payload.get("stroke", {})
            self.remote_stroke_received.emit(frame, stroke_data)

        elif msg_type == "CLEAR_ANNOTATIONS":
            frame = payload.get("frame", -1)
            self.remote_annotations_cleared.emit(frame)

        elif msg_type == "NOTE":
            frame = payload.get("frame", 1001)
            note = payload.get("note", "")
            self.remote_note_received.emit(frame, note)

        elif msg_type == "CHAT":
            text = payload.get("text", "")
            self.chat_message_received.emit(sender, text)

        elif msg_type in ("PRESENTER_TAKE", "PRESENTER_ASSIGN"):
            new_pres = payload.get("username", sender)
            self._presenter = new_pres
            self.presenter_changed.emit(new_pres)

    def _relay_to_other_clients(self, msg: Dict[str, Any], exclude_socket: Optional[QTcpSocket] = None) -> None:
        data = (json.dumps(msg) + "\n").encode("utf-8")
        for s in self._client_sockets:
            try:
                if s != exclude_socket and s.state() == QTcpSocket.SocketState.ConnectedState:
                    s.write(data)
                    s.flush()
            except RuntimeError:
                pass

    def _send_raw_message(self, msg: Dict[str, Any]) -> None:
        data = (json.dumps(msg) + "\n").encode("utf-8")
        if self._mode == "host":
            for s in list(self._client_sockets):
                try:
                    if s.state() == QTcpSocket.SocketState.ConnectedState:
                        s.write(data)
                        s.flush()
                except RuntimeError:
                    pass
        elif self._mode == "client" and self._client_socket:
            try:
                if self._client_socket.state() == QTcpSocket.SocketState.ConnectedState:
                    self._client_socket.write(data)
                    self._client_socket.flush()
            except RuntimeError:
                pass

    def _broadcast_peer_list(self) -> None:
        if self._mode != "host":
            return
        peers = [f"{self._username} (Host)"]
        for name in self._client_names.values():
            peers.append(name)
        msg = {
            "type": "PEER_LIST",
            "sender": self._username,
            "payload": {
                "peers": peers,
                "presenter": self._presenter,
            },
        }
        self._send_raw_message(msg)
        self.peer_list_updated.emit(peers)

    # --------------------------------------------------------------------------
    # Public Broadcast API (Called by Local App)
    # --------------------------------------------------------------------------
    def broadcast_playback(
        self,
        frame: int,
        is_playing: bool,
        fps: float = 24.0,
        shuttle_speed: float = 1.0,
        in_frame: int = 1001,
        out_frame: int = 1200,
    ) -> None:
        if not self.is_connected:
            return
        self._send_raw_message({
            "type": "PLAYBACK",
            "sender": self._username,
            "payload": {
                "frame": frame,
                "is_playing": is_playing,
                "fps": fps,
                "shuttle_speed": shuttle_speed,
                "in_frame": in_frame,
                "out_frame": out_frame,
            },
        })

    def broadcast_media(self, media_path: str) -> None:
        if not self.is_connected:
            return
        self._send_raw_message({
            "type": "MEDIA",
            "sender": self._username,
            "payload": {"path": media_path},
        })

    def broadcast_color(
        self,
        exposure_ev: float,
        gamma: float,
        channel_mode: int = 0,
        input_space: int = 0,
        view_transform: int = 0,
    ) -> None:
        if not self.is_connected:
            return
        self._send_raw_message({
            "type": "COLOR",
            "sender": self._username,
            "payload": {
                "exposure_ev": exposure_ev,
                "gamma": gamma,
                "channel_mode": channel_mode,
                "input_space": input_space,
                "view_transform": view_transform,
            },
        })

    def broadcast_stroke(self, frame: int, stroke_dict: Dict[str, Any]) -> None:
        if not self.is_connected:
            return
        self._send_raw_message({
            "type": "STROKE",
            "sender": self._username,
            "payload": {
                "frame": frame,
                "stroke": stroke_dict,
            },
        })

    def broadcast_clear_annotations(self, frame: int = -1) -> None:
        if not self.is_connected:
            return
        self._send_raw_message({
            "type": "CLEAR_ANNOTATIONS",
            "sender": self._username,
            "payload": {"frame": frame},
        })

    def broadcast_note(self, frame: int, note: str) -> None:
        if not self.is_connected:
            return
        self._send_raw_message({
            "type": "NOTE",
            "sender": self._username,
            "payload": {
                "frame": frame,
                "note": note,
            },
        })

    def broadcast_chat(self, text: str) -> None:
        if not self.is_connected:
            return
        self._send_raw_message({
            "type": "CHAT",
            "sender": self._username,
            "payload": {"text": text},
        })
        # Emit locally as well
        self.chat_message_received.emit(self._username, text)

    def request_presenter(self) -> None:
        if not self.is_connected:
            return
        self._presenter = self._username
        self._send_raw_message({
            "type": "PRESENTER_TAKE",
            "sender": self._username,
            "payload": {"username": self._username},
        })
        self.presenter_changed.emit(self._username)

    def grant_presenter(self, target_username: str) -> None:
        """Host or presenter delegates presenter control to a specific peer."""
        if not self.is_connected or not target_username:
            return
        clean_user = target_username.replace(" (Host)", "").replace(" 👑", "").strip()
        self._presenter = clean_user
        self._send_raw_message({
            "type": "PRESENTER_ASSIGN",
            "sender": self._username,
            "payload": {"username": clean_user},
        })
        self.presenter_changed.emit(clean_user)
