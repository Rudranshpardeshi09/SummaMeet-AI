import asyncio
import json
import uuid
import structlog
from typing import Annotated

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.pubsub import redis_client
from app.core.security import get_current_user
from app.models.user import User
from app.models.meeting import Meeting
from app.schemas.ws import TicketResponse
from app.db.session import get_db

logger = structlog.get_logger("websocket")

router = APIRouter(tags=["WebSockets"])

@router.post("/ws/ticket", response_model=TicketResponse)
async def generate_ws_ticket(
    current_user: User = Depends(get_current_user),
):
    """Generate a short-lived, one-time ticket for WebSocket authentication."""
    ticket = str(uuid.uuid4())
    # Store ticket with 60 second TTL, associated with the user_id
    await redis_client.setex(f"ws_ticket:{ticket}", 60, str(current_user.id))
    
    return TicketResponse(
        ticket=ticket,
        expires_in=60
    )

@router.websocket("/ws/meetings/{meeting_id}")
async def meeting_websocket(
    websocket: WebSocket,
    meeting_id: uuid.UUID,
    ticket: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """WebSocket endpoint to listen for real-time meeting events."""
    await websocket.accept()

    # 1. Validate Ticket
    user_id_str = await redis_client.get(f"ws_ticket:{ticket}")
    if not user_id_str:
        await websocket.send_json({"type": "ERROR", "payload": {"detail": "Invalid or expired ticket"}})
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # Delete ticket (one-time use)
    await redis_client.delete(f"ws_ticket:{ticket}")
    
    # 2. Check Authorization (User can access meeting)
    stmt = select(Meeting).where(
        Meeting.id == meeting_id,
        Meeting.deleted_at.is_(None)
    )
    result = await db.execute(stmt)
    meeting = result.scalar_one_or_none()

    if not meeting:
        await websocket.send_json({"type": "ERROR", "payload": {"detail": "Meeting not found"}})
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    user_stmt = select(User).where(User.id == uuid.UUID(user_id_str))
    user_result = await db.execute(user_stmt)
    user = user_result.scalar_one_or_none()
    
    if not user or user.organization_id != meeting.organization_id:
        await websocket.send_json({"type": "ERROR", "payload": {"detail": "Forbidden"}})
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # 3. Subscribe to Redis Pub/Sub channel
    channel = f"meeting:{meeting.id}"
    pubsub = redis_client.pubsub()
    await pubsub.subscribe(channel)
    
    logger.info("WebSocket connected", meeting_id=str(meeting.id), user_id=user_id_str)
    
    try:
        async def redis_listener():
            while True:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message:
                    data = message["data"]
                    if isinstance(data, bytes):
                        data = data.decode('utf-8')
                    await websocket.send_text(data)
                await asyncio.sleep(0.01)

        async def ws_receiver():
            try:
                while True:
                    await websocket.receive_text()
            except WebSocketDisconnect:
                pass

        redis_task = asyncio.create_task(redis_listener())
        ws_task = asyncio.create_task(ws_receiver())
        
        done, pending = await asyncio.wait(
            [redis_task, ws_task],
            return_when=asyncio.FIRST_COMPLETED
        )
        for task in pending:
            task.cancel()
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected", meeting_id=str(meeting.id), user_id=user_id_str)
    except Exception as e:
        logger.error("WebSocket error", error=str(e))
    finally:
        await pubsub.close()

@router.websocket("/ws/meetings")
async def organization_meetings_websocket(
    websocket: WebSocket,
    ticket: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """WebSocket endpoint to listen for real-time events for all meetings in an organization."""
    await websocket.accept()

    # 1. Validate Ticket
    user_id_str = await redis_client.get(f"ws_ticket:{ticket}")
    if not user_id_str:
        await websocket.send_json({"type": "ERROR", "payload": {"detail": "Invalid or expired ticket"}})
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # Delete ticket (one-time use)
    await redis_client.delete(f"ws_ticket:{ticket}")

    # 2. Check Authorization
    user_stmt = select(User).where(User.id == uuid.UUID(user_id_str))
    user_result = await db.execute(user_stmt)
    user = user_result.scalar_one_or_none()
    
    if not user:
        await websocket.send_json({"type": "ERROR", "payload": {"detail": "Forbidden"}})
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # Get all active meetings for this org
    stmt = select(Meeting.id).where(
        Meeting.organization_id == user.organization_id,
        Meeting.deleted_at.is_(None)
    )
    result = await db.execute(stmt)
    meeting_ids = result.scalars().all()

    pubsub = redis_client.pubsub()
    channels = [f"meeting:{m_id}" for m_id in meeting_ids]
    
    if channels:
        await pubsub.subscribe(*channels)
        
    # We also subscribe to a pattern so if new meetings are added, we can catch them?
    # Redis psubscribe doesn't support subscribing to specific meeting IDs dynamically 
    # without unsubscribing/resubscribing. For a simple dashboard, subscribing to 
    # current meetings is usually enough, or we can use psubscribe and filter.
    # To keep it simple and secure, we'll use psubscribe("meeting:*") and filter in memory!
    await pubsub.psubscribe("meeting:*")
    
    # Cache meeting ownership in memory to avoid DB lookups for every event
    allowed_meetings = set(str(m_id) for m_id in meeting_ids)

    logger.info("Org WebSocket connected", user_id=user_id_str)
    
    try:
        async def redis_listener():
            while True:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message:
                    channel = message["channel"]
                    if isinstance(channel, bytes):
                        channel = channel.decode('utf-8')
                    
                    if channel.startswith("meeting:"):
                        msg_meeting_id = channel.split(":")[1]
                        
                        if msg_meeting_id not in allowed_meetings:
                            m_stmt = select(Meeting).where(Meeting.id == uuid.UUID(msg_meeting_id))
                            m_res = await db.execute(m_stmt)
                            m_obj = m_res.scalar_one_or_none()
                            if m_obj and m_obj.organization_id == user.organization_id:
                                allowed_meetings.add(msg_meeting_id)
                            
                        if msg_meeting_id in allowed_meetings:
                            data = message["data"]
                            if isinstance(data, bytes):
                                data = data.decode('utf-8')
                            
                            try:
                                json_data = json.loads(data)
                                json_data["meeting_id"] = msg_meeting_id
                                await websocket.send_text(json.dumps(json_data))
                            except Exception:
                                await websocket.send_text(data)
                
                await asyncio.sleep(0.01)

        async def ws_receiver():
            try:
                while True:
                    await websocket.receive_text()
            except WebSocketDisconnect:
                pass

        redis_task = asyncio.create_task(redis_listener())
        ws_task = asyncio.create_task(ws_receiver())
        
        done, pending = await asyncio.wait(
            [redis_task, ws_task],
            return_when=asyncio.FIRST_COMPLETED
        )
        for task in pending:
            task.cancel()
    except WebSocketDisconnect:
        logger.info("Org WebSocket disconnected", user_id=user_id_str)
    except Exception as e:
        logger.error("Org WebSocket error", error=str(e))
    finally:
        await pubsub.punsubscribe("meeting:*")
        if channels:
            await pubsub.unsubscribe(*channels)
        await pubsub.close()
