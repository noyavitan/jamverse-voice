"""OSC sender for Jamverse integration.

Uses port 9100 (NOT 9000 — that's Unity avatars) and namespace /stt/* exclusively.
This keeps the STT sidecar fully decoupled from the avatar OSC channel.

Disabled by default; pass --osc on the CLI to enable.
"""
from typing import Optional
from pythonosc.udp_client import SimpleUDPClient

from ..config import OSC_HOST, OSC_PORT, OSC_NAMESPACE
from ..parser.command_parser import Command


class OscSender:
    def __init__(self, host: str = OSC_HOST, port: int = OSC_PORT,
                 namespace: str = OSC_NAMESPACE):
        self._client = SimpleUDPClient(host, port)
        self._namespace = namespace
        self._endpoint = f"{host}:{port}"

    @property
    def endpoint(self) -> str:
        return f"{self._endpoint}{self._namespace}/*"

    def send_command(self, cmd: Command) -> None:
        suffix, args = cmd.as_osc()
        self._client.send_message(self._namespace + suffix, args)

    def send_partial(self, text: str) -> None:
        self._client.send_message(self._namespace + "/partial", [text])
