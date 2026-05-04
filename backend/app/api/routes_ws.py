from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.websocket_service import websocket_service

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/pipeline")
async def pipeline_websocket(websocket: WebSocket):
    await websocket_service.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        websocket_service.disconnect(websocket)
