"""HackForge — Chat Socket"""
from datetime import datetime
from flask_socketio import join_room, leave_room, emit
from backend.services.supabase_service import get_supabase
from backend.services.notification_service import NotificationService
from backend.utils.logger import get_logger

logger = get_logger(__name__)
notif = NotificationService()


def register_chat_socket(socketio):

    @socketio.on("chat:join")
    def on_chat_join(data):
        room_id = data.get("room_id")
        user_id = data.get("user_id")
        if not room_id:
            return
        join_room(f"chat:{room_id}")
        emit("chat:joined", {"room_id": room_id, "user_id": user_id})

    @socketio.on("chat:leave")
    def on_chat_leave(data):
        room_id = data.get("room_id")
        user_id = data.get("user_id")
        if not room_id:
            return
        leave_room(f"chat:{room_id}")
        emit("chat:left", {"room_id": room_id, "user_id": user_id})

    @socketio.on("chat:message")
    def on_chat_message(data):
        from flask import request
        room_id = data.get("room_id")
        user_id = data.get("user_id")
        content = data.get("content", "").strip()
        message_type = data.get("type", "text")
        parent_id = data.get("parent_id")
        metadata = data.get("metadata", {})
        mentions = data.get("mentions", [])

        if not room_id or not user_id or not content:
            return

        try:
            supabase = get_supabase()

            # Verify room membership
            room = supabase.table("chat_rooms").select("team_id").eq("id", room_id).execute()
            if not room.data:
                return

            # Save message
            msg_data = {
                "room_id": room_id,
                "user_id": user_id,
                "content": content,
                "type": message_type,
                "parent_id": parent_id,
                "metadata": metadata,
                "mentions": mentions,
                "is_edited": False,
                "created_at": datetime.utcnow().isoformat()
            }
            result = supabase.table("chat_messages").insert(msg_data).execute()
            if not result.data:
                return

            message = result.data[0]

            # Get user info
            user_res = supabase.table("users").select(
                "id,username,full_name,avatar_url"
            ).eq("id", user_id).execute()
            user_info = user_res.data[0] if user_res.data else {}

            broadcast_msg = {**message, "user": user_info}

            # Broadcast to room
            emit("chat:new_message", broadcast_msg, to=f"chat:{room_id}")

            # Handle @mentions
            team_id = room.data[0]["team_id"]
            for mentioned_id in mentions:
                if mentioned_id != user_id:
                    notif.create(
                        user_id=mentioned_id,
                        title=f"{user_info.get('full_name', 'Someone')} mentioned you",
                        body=content[:100],
                        notif_type="mention",
                        team_id=team_id,
                        actor_id=user_id,
                        link=f"/chat/{room_id}"
                    )

        except Exception as e:
            logger.error(f"Chat message error: {e}")
            emit("chat:error", {"error": str(e)})

    @socketio.on("chat:typing")
    def on_typing(data):
        from flask import request
        room_id = data.get("room_id")
        user_id = data.get("user_id")
        is_typing = data.get("is_typing", True)
        user_name = data.get("user_name", "")

        emit("chat:typing_update", {
            "user_id": user_id,
            "user_name": user_name,
            "is_typing": is_typing
        }, to=f"chat:{room_id}", skip_sid=request.sid)

    @socketio.on("chat:reaction")
    def on_reaction(data):
        message_id = data.get("message_id")
        user_id = data.get("user_id")
        emoji = data.get("emoji")
        room_id = data.get("room_id")

        if not all([message_id, user_id, emoji]):
            return

        try:
            supabase = get_supabase()

            # Toggle reaction
            existing = supabase.table("message_reactions").select("id").eq(
                "message_id", message_id
            ).eq("user_id", user_id).eq("emoji", emoji).execute()

            if existing.data:
                supabase.table("message_reactions").delete().eq("id", existing.data[0]["id"]).execute()
                action = "removed"
            else:
                supabase.table("message_reactions").insert({
                    "message_id": message_id,
                    "user_id": user_id,
                    "emoji": emoji,
                    "created_at": datetime.utcnow().isoformat()
                }).execute()
                action = "added"

            # Get all reactions for message
            reactions = supabase.table("message_reactions").select("emoji,user_id").eq(
                "message_id", message_id
            ).execute()

            emit("chat:reaction_update", {
                "message_id": message_id,
                "reactions": reactions.data or [],
                "action": action
            }, to=f"chat:{room_id}")

        except Exception as e:
            logger.error(f"Chat reaction error: {e}")

    @socketio.on("chat:edit")
    def on_edit_message(data):
        message_id = data.get("message_id")
        user_id = data.get("user_id")
        content = data.get("content", "").strip()
        room_id = data.get("room_id")

        if not all([message_id, user_id, content]):
            return

        try:
            supabase = get_supabase()
            result = supabase.table("chat_messages").update({
                "content": content,
                "is_edited": True,
                "edited_at": datetime.utcnow().isoformat()
            }).eq("id", message_id).eq("user_id", user_id).execute()

            if result.data:
                emit("chat:message_edited", {
                    "message_id": message_id,
                    "content": content,
                    "edited_at": result.data[0]["edited_at"]
                }, to=f"chat:{room_id}")
        except Exception as e:
            logger.error(f"Chat edit error: {e}")

    @socketio.on("chat:delete")
    def on_delete_message(data):
        message_id = data.get("message_id")
        user_id = data.get("user_id")
        room_id = data.get("room_id")

        try:
            supabase = get_supabase()
            supabase.table("chat_messages").update({
                "is_deleted": True,
                "content": "[Message deleted]"
            }).eq("id", message_id).eq("user_id", user_id).execute()

            emit("chat:message_deleted", {"message_id": message_id}, to=f"chat:{room_id}")
        except Exception as e:
            logger.error(f"Chat delete error: {e}")