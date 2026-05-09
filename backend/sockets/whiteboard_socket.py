"""HackForge — Whiteboard Socket"""
from datetime import datetime
from flask_socketio import join_room, leave_room, emit
from backend.services.supabase_service import get_supabase
from backend.services.redis_service import RedisService
from backend.utils.logger import get_logger
import json

logger = get_logger(__name__)
redis = RedisService()


def _resolve_whiteboard_id(data):
    return data.get("whiteboard_id") or data.get("boardId") or data.get("board_id")


def _resolve_user_id(data):
    return data.get("user_id") or data.get("userId")


def register_whiteboard_socket(socketio):

    @socketio.on("whiteboard:join")
    def on_wb_join(data):
        wb_id = _resolve_whiteboard_id(data)
        user_id = _resolve_user_id(data)
        if not wb_id:
            return

        room = f"wb:{wb_id}"
        join_room(room)

        # Load existing elements from DB
        supabase = get_supabase()
        wb = supabase.table("whiteboards").select("elements,background_color").eq("id", wb_id).execute()
        elements = []
        bg = "#0a0a0f"
        if wb.data:
            elements = wb.data[0].get("elements") or []
            bg = wb.data[0].get("background_color") or bg

        payload = {
            "whiteboard_id": wb_id,
            "elements": elements,
            "background_color": bg
        }

        emit("whiteboard:state", payload)
        emit("whiteboard:sync", payload)

        emit("whiteboard:user_joined", {"user_id": user_id}, to=room)

    @socketio.on("whiteboard:leave")
    def on_wb_leave(data):
        wb_id = _resolve_whiteboard_id(data)
        user_id = _resolve_user_id(data)
        if wb_id:
            leave_room(f"wb:{wb_id}")
            emit("whiteboard:user_left", {"user_id": user_id}, to=f"wb:{wb_id}")

    @socketio.on("whiteboard:draw")
    def on_wb_draw(data):
        from flask import request
        wb_id = _resolve_whiteboard_id(data)
        user_id = _resolve_user_id(data)
        element = data.get("element") or data.get("data")

        if not wb_id or not element:
            return

        room = f"wb:{wb_id}"
        payload = {
            "user_id": user_id,
            "whiteboard_id": wb_id,
            "element": element
        }

        emit("whiteboard:draw_update", payload, to=room, skip_sid=request.sid)
        emit("whiteboard:draw", payload, to=room, skip_sid=request.sid)

        # Persist draw event
        try:
            supabase = get_supabase()
            supabase.table("whiteboard_events").insert({
                "whiteboard_id": wb_id,
                "user_id": user_id,
                "event_type": "draw",
                "data": element,
                "created_at": datetime.utcnow().isoformat()
            }).execute()
        except Exception as e:
            logger.error(f"WB draw persist failed: {e}")

    @socketio.on("whiteboard:erase")
    def on_wb_erase(data):
        from flask import request
        wb_id = _resolve_whiteboard_id(data)
        user_id = _resolve_user_id(data)
        element_id = data.get("element_id") or data.get("elementId")

        if not wb_id:
            return

        room = f"wb:{wb_id}"
        payload = {
            "user_id": user_id,
            "whiteboard_id": wb_id,
            "element_id": element_id
        }

        emit("whiteboard:erase_update", payload, to=room, skip_sid=request.sid)
        emit("whiteboard:erase", payload, to=room, skip_sid=request.sid)

    @socketio.on("whiteboard:clear")
    def on_wb_clear(data):
        wb_id = _resolve_whiteboard_id(data)
        user_id = _resolve_user_id(data)

        if not wb_id:
            return

        try:
            supabase = get_supabase()
            supabase.table("whiteboards").update({
                "elements": [],
                "updated_at": datetime.utcnow().isoformat()
            }).eq("id", wb_id).execute()

            payload = {"cleared_by": user_id, "whiteboard_id": wb_id}
            emit("whiteboard:cleared", payload, to=f"wb:{wb_id}")
            emit("whiteboard:clear", payload, to=f"wb:{wb_id}")
        except Exception as e:
            logger.error(f"WB clear failed: {e}")

    @socketio.on("whiteboard:save")
    def on_wb_save(data):
        wb_id = _resolve_whiteboard_id(data)
        elements = data.get("elements", [])
        user_id = _resolve_user_id(data)

        if not wb_id:
            return

        try:
            supabase = get_supabase()
            supabase.table("whiteboards").update({
                "elements": elements,
                "updated_at": datetime.utcnow().isoformat(),
                "last_editor_id": user_id
            }).eq("id", wb_id).execute()

            payload = {"whiteboard_id": wb_id, "saved_by": user_id, "elements": elements}
            emit("whiteboard:saved", payload, to=f"wb:{wb_id}")
            emit("whiteboard:sync", payload, to=f"wb:{wb_id}")
        except Exception as e:
            logger.error(f"WB save failed: {e}")
            emit("whiteboard:save_error", {"error": str(e)})

    @socketio.on("whiteboard:cursor")
    def on_wb_cursor(data):
        from flask import request
        wb_id = _resolve_whiteboard_id(data)
        user_id = _resolve_user_id(data)
        x = data.get("x", 0)
        y = data.get("y", 0)
        color = data.get("color", "#00ffff")

        room = f"wb:{wb_id}"
        payload = {
            "user_id": user_id,
            "whiteboard_id": wb_id,
            "x": x, "y": y, "color": color
        }

        emit("whiteboard:cursor_update", payload, to=room, skip_sid=request.sid)
        emit("whiteboard:cursor", payload, to=room, skip_sid=request.sid)

    @socketio.on("whiteboard:element_update")
    def on_element_update(data):
        from flask import request
        wb_id = _resolve_whiteboard_id(data)
        user_id = _resolve_user_id(data)
        element = data.get("element") or data.get("data")

        room = f"wb:{wb_id}"
        payload = {
            "user_id": user_id,
            "whiteboard_id": wb_id,
            "element": element
        }

        emit("whiteboard:element_updated", payload, to=room, skip_sid=request.sid)
        emit("whiteboard:element_update", payload, to=room, skip_sid=request.sid)