"""Hardened WebSocket server for streaming live simulation state."""

from __future__ import annotations

import asyncio
import html
import http.server
import json
import logging
import os
import threading
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING

import websockets
from websockets.asyncio.server import serve

if TYPE_CHECKING:
    from .world import World

logger = logging.getLogger("aura.server")

# ── Security constants ────────────────────────────────────────
MAX_CLIENTS = 10
MAX_MESSAGE_SIZE = 1024          # 1 KB max inbound message
MAX_QUEUE_SIZE = 16              # backpressure on slow clients
ALLOWED_EXTENSIONS = {".html", ".css", ".js", ".png", ".ico", ".svg", ".json", ".webp", ".jpg", ".woff2", ".woff", ".ttf"}

# Path to viz/ static files
VIZ_DIR = Path(__file__).resolve().parent.parent / "viz"

# Connected clients
_clients: set = set()
_clients_lock = threading.Lock()


# ── Secure Static File Handler ────────────────────────────────

class _SecureStaticHandler(http.server.SimpleHTTPRequestHandler):
    """Serve static files with security headers and path traversal protection."""

    def __init__(self, *args, directory=None, **kwargs):
        super().__init__(*args, directory=str(VIZ_DIR), **kwargs)

    def do_GET(self):
        # Path traversal protection
        requested = self.translate_path(self.path)
        requested_path = Path(requested).resolve()
        viz_resolved = VIZ_DIR.resolve()

        if not str(requested_path).startswith(str(viz_resolved)):
            self.send_error(403, "Forbidden")
            return

        # Extension whitelist
        ext = requested_path.suffix.lower()
        if requested_path.is_file() and ext not in ALLOWED_EXTENSIONS:
            self.send_error(403, "Forbidden")
            return

        super().do_GET()

    def end_headers(self):
        # Security headers
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("X-XSS-Protection", "1; mode=block")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy",
                         "default-src 'self'; "
                         "script-src 'self' https://cdn.jsdelivr.net; "
                         "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                         "font-src https://fonts.gstatic.com; "
                         "connect-src 'self' ws://localhost:* ws://127.0.0.1:*; "
                         "img-src 'self' data:;")
        super().end_headers()

    def log_message(self, format, *args):
        pass  # Suppress HTTP logs


# ── WebSocket Handler ─────────────────────────────────────────

async def _handler(websocket) -> None:
    """Handle a new WebSocket connection with security checks."""
    # Enforce client cap
    with _clients_lock:
        if len(_clients) >= MAX_CLIENTS:
            await websocket.close(1013, "Max clients reached")
            return
        _clients.add(websocket)

    try:
        async for message in websocket:
            try:
                cmd = json.loads(message)
                # Whitelist allowed command types
                cmd_type = cmd.get("type", "")
                if cmd_type == "ping":
                    await websocket.send(json.dumps({"type": "pong"}))
                # Ignore all other commands
            except (json.JSONDecodeError, TypeError):
                pass
    except websockets.ConnectionClosed:
        pass
    except Exception as e:
        logger.warning("WebSocket error: %s", e)
    finally:
        with _clients_lock:
            _clients.discard(websocket)


async def broadcast(data: dict) -> None:
    """Broadcast world state to all connected clients."""
    with _clients_lock:
        clients_snapshot = _clients.copy()

    if clients_snapshot:
        message = json.dumps(data, default=_json_default)
        dead = []
        for client in clients_snapshot:
            try:
                await client.send(message)
            except Exception:
                dead.append(client)
        # Clean up dead connections
        if dead:
            with _clients_lock:
                for c in dead:
                    _clients.discard(c)


def _json_default(obj):
    """Handle numpy types in JSON serialization."""
    import numpy as np
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


# ── HTTP Server ───────────────────────────────────────────────

def _start_http_server(host: str, port: int) -> http.server.HTTPServer:
    """Start a secure HTTP server for static files in a background thread."""
    handler = partial(_SecureStaticHandler, directory=str(VIZ_DIR))
    server = http.server.HTTPServer((host, port), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


# ── Main Server Entry ─────────────────────────────────────────

async def run_simulation_with_server(world: World, host: str, port: int) -> None:
    """Run simulation and WebSocket server concurrently."""
    from rich.console import Console
    console = Console()

    ws_port = port + 1

    # Start HTTP server for static files
    _start_http_server(host, port)

    console.print(f"\n[bold cyan]🌐 AURA Dashboard:[/bold cyan] [link=http://localhost:{port}]http://localhost:{port}[/link]")
    console.print(f"[dim]   WebSocket on ws://{host}:{ws_port}[/dim]")
    console.print(f"[dim]   Max clients: {MAX_CLIENTS} | Binding: {host}[/dim]")
    console.print(f"[dim]   Press Ctrl+C to stop[/dim]\n")

    async def simulation_loop() -> None:
        """Run simulation ticks and broadcast state."""
        import time
        world.running = True
        broadcast_interval = world.config.server.broadcast_interval

        try:
            while world.running:
                start = time.time()
                world.tick()

                if world.tick_count % broadcast_interval == 0:
                    state = world.to_dict()
                    await broadcast(state)

                    if world.tick_count % 50 == 0 and world.stats:
                        console.print(
                            f"[dim]Tick {world.tick_count:>6}[/dim]  |  "
                            f"{world.stats.summary_string()}"
                        )

                elapsed = time.time() - start
                sleep_time = world.config.world.tick_speed - elapsed
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                else:
                    await asyncio.sleep(0)

        except asyncio.CancelledError:
            world.running = False

    async with serve(
        _handler,
        host,
        ws_port,
        max_size=MAX_MESSAGE_SIZE,
    ):
        await simulation_loop()
