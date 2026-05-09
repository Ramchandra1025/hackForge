"""HackForge — Notification Socket"""
from flask_socketio import join_room, leave_room, emit
from backend.services.notification_service import NotificationService
from backend.utils.logger import get_logger

logger = get_logger(__name__)
notif_svc = NotificationService()


def register_notification_socket(socketio):

    @socketio.on("notifications:subscribe")
    def on_subscribe(data):
        user_id = data.get("user_id")
        if not user_id:
            return

        join_room(f"notif:{user_id}")
        unread = notif_svc.get_unread_count(user_id)
        emit("notifications:unread_count", {"count": unread})

    @socketio.on("notifications:unsubscribe")
    def on_unsubscribe(data):
        user_id = data.get("user_id")
        if user_id:
            leave_room(f"notif:{user_id}")

    @socketio.on("notifications:mark_read")
    def on_mark_read(data):
        notification_id = data.get("notification_id")
        user_id = data.get("user_id")

        if not notification_id or not user_id:
            return

        notif_svc.mark_read(notification_id, user_id)
        unread = notif_svc.get_unread_count(user_id)
        emit("notifications:unread_count", {"count": unread})

    @socketio.on("notifications:mark_all_read")
    def on_mark_all_read(data):
        user_id = data.get("user_id")
        team_id = data.get("team_id")

        if not user_id:
            return

        notif_svc.mark_all_read(user_id, team_id)
        emit("notifications:unread_count", {"count": 0})


def push_notification(socketio, user_id: str, notification: dict) -> None:
    """Push a real-time notification to a specific user."""
    socketio.emit("notifications:new", notification, to=f"notif:{user_id}")
    unread = notif_svc.get_unread_count(user_id)
    socketio.emit("notifications:unread_count", {"count": unread}, to=f"notif:{user_id}")