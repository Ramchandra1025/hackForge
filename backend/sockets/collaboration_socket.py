"""HackForge — Collaboration Socket (real-time code editor)"""
from flask_socketio import join_room, leave_room, emit
from backend.services.collaboration_service import CollaborationService
from backend.services.presence_service import PresenceService
from backend.utils.logger import get_logger

logger = get_logger(__name__)
collab = CollaborationService()
presence = PresenceService()


def register_collaboration_socket(socketio):

    @socketio.on("editor:join")
    def on_editor_join(data):
        from flask import request
        file_id = data.get("file_id")
        user_id = data.get("user_id")
        user_info = data.get("user_info", {})

        if not file_id or not user_id:
            return

        room = f"editor:{file_id}"
        join_room(room)
        collab.join_file(file_id, user_id, user_info)

        content = collab.get_file_content(file_id)
        editors = collab.get_active_editors(file_id)

        emit("editor:joined", {
            "file_id": file_id,
            "content": content,
            "editors": editors
        })

        emit("editor:user_joined", {
            "user_id": user_id,
            "user_info": user_info
        }, to=room, skip_sid=request.sid)

        logger.debug(f"User {user_id} joined editor:{file_id}")

    @socketio.on("editor:leave")
    def on_editor_leave(data):
        from flask import request
        file_id = data.get("file_id")
        user_id = data.get("user_id")

        if not file_id or not user_id:
            return

        room = f"editor:{file_id}"
        leave_room(room)
        collab.leave_file(file_id, user_id)

        emit("editor:user_left", {"user_id": user_id}, to=room)

    @socketio.on("editor:change")
    def on_editor_change(data):
        from flask import request
        file_id = data.get("file_id")
        user_id = data.get("user_id")
        changes = data.get("changes")
        version = data.get("version", 0)

        if not file_id:
            return

        room = f"editor:{file_id}"

        # Broadcast change to all other editors
        emit("editor:remote_change", {
            "user_id": user_id,
            "changes": changes,
            "version": version
        }, to=room, skip_sid=request.sid)

    @socketio.on("editor:save")
    def on_editor_save(data):
        file_id = data.get("file_id")
        user_id = data.get("user_id")
        content = data.get("content", "")
        create_version = data.get("create_version", False)

        if not file_id or not user_id:
            return

        try:
            updated = collab.save_file_content(file_id, content, user_id, create_version)
            room = f"editor:{file_id}"
            emit("editor:saved", {
                "file_id": file_id,
                "saved_by": user_id,
                "updated_at": updated.get("updated_at")
            }, to=room)
        except Exception as e:
            logger.error(f"Editor save failed: {e}")
            emit("editor:save_error", {"error": str(e)})

    @socketio.on("editor:cursor")
    def on_cursor_move(data):
        from flask import request
        file_id = data.get("file_id")
        user_id = data.get("user_id")
        cursor = data.get("cursor")

        room = f"editor:{file_id}"
        emit("editor:cursor_update", {
            "user_id": user_id,
            "cursor": cursor
        }, to=room, skip_sid=request.sid)

    @socketio.on("editor:selection")
    def on_selection(data):
        from flask import request
        file_id = data.get("file_id")
        user_id = data.get("user_id")
        selection = data.get("selection")

        room = f"editor:{file_id}"
        emit("editor:selection_update", {
            "user_id": user_id,
            "selection": selection
        }, to=room, skip_sid=request.sid)