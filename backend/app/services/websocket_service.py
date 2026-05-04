import asyncio
import json
from typing import List, Set

from fastapi import WebSocket


class WebSocketService:
    def __init__(self) -> None:
        self.connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.connections.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self.connections.discard(websocket)

    async def broadcast(self, event: str, steps: List[str]) -> None:
        payload = {"event": event, "pipeline_steps": steps}
        stale = []
        for websocket in list(self.connections):
            try:
                await websocket.send_text(json.dumps(payload, ensure_ascii=False))
            except Exception:
                stale.append(websocket)
        for websocket in stale:
            self.disconnect(websocket)


websocket_service = WebSocketService()
