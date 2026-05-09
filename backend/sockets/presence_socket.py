"""HackForge — Presence Socket"""
from flask_socketio import join_room, leave_room, emit
from backend.services.presence_service import PresenceService
from backend.utils.logger import get_logger

logger = get_logger(__name__)
presence = PresenceService()


def register_presence_socket(socketio):

    @socketio.on("presence:join")
    def on_presence_join(data):
        from flask import request
        user_id = data.get("user_id")
        team_id = data.get("team_id")
        metadata = data.get("metadata", {})

        if not user_id or not team_id:
            return

        join_room(f"team:{team_id}")
        presence.set_online(user_id, team_id, metadata)

        online_members = presence.get_online_members(team_id)
        emit("presence:online_members", {
            "team_id": team_id,
            "members": online_members
        })

        emit("presence:user_online", {
            "user_id": user_id,
            "team_id": team_id,
            "metadata": metadata
        }, to=f"team:{team_id}", skip_sid=request.sid)

    @socketio.on("presence:leave")
    def on_presence_leave(data):
        from flask import request
        user_id = data.get("user_id")
        team_id = data.get("team_id")

        if not user_id or not team_id:
            return

        leave_room(f"team:{team_id}")
        presence.set_offline(user_id, team_id)

        emit("presence:user_offline", {
            "user_id": user_id,
            "team_id": team_id
        }, to=f"team:{team_id}")

    @socketio.on("presence:heartbeat")
    def on_heartbeat(data):
        user_id = data.get("user_id")
        team_id = data.get("team_id")

        if user_id and team_id:
            presence.heartbeat(user_id, team_id)

    @socketio.on("presence:status_update")
    def on_status_update(data):
        from flask import request
        user_id = data.get("user_id")
        team_id = data.get("team_id")
        status = data.get("status", "online")  # online, away, busy, dnd

        if not user_id or not team_id:
            return

        presence.set_online(user_id, team_id, {"status": status})

        emit("presence:user_status", {
            "user_id": user_id,
            "status": status
        }, to=f"team:{team_id}", skip_sid=request.sid)

    @socketio.on("disconnect")
    def on_disconnect():
        # Best-effort: we don't have user context here without auth
        # Heartbeat TTL will handle cleanup
        logger.debug("Socket disconnected")