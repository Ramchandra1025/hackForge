"""HackForge — Task Service"""
from datetime import datetime
from typing import Dict, Any, List, Optional
from backend.services.supabase_service import get_supabase
from backend.services.notification_service import NotificationService
from backend.services.search_service import SearchService
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class TaskService:

    def __init__(self):
        self.supabase = get_supabase()
        self.notifications = NotificationService()
        self.search = SearchService()

    def create_task(self, project_id: str, team_id: str, creator_id: str,
                    data: Dict[str, Any]) -> Dict[str, Any]:
        task = {
            "project_id": project_id,
            "team_id": team_id,
            "creator_id": creator_id,
            "title": data["title"],
            "description": data.get("description", ""),
            "status": data.get("status", "backlog"),
            "priority": data.get("priority", "medium"),
            "story_points": data.get("story_points"),
            "assignee_id": data.get("assignee_id"),
            "sprint_id": data.get("sprint_id"),
            "due_date": data.get("due_date"),
            "labels": data.get("labels", []),
            "order_index": data.get("order_index", 0),
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }
        result = self.supabase.table("tasks").insert(task).execute()
        if not result.data:
            raise RuntimeError("Failed to create task")

        created = result.data[0]

        # Index for search
        self.search.index(
            team_id=team_id,
            resource_type="task",
            resource_id=created["id"],
            title=created["title"],
            body=created.get("description", ""),
            project_id=project_id,
            author_id=creator_id
        )

        # Notify assignee
        if created.get("assignee_id") and created["assignee_id"] != creator_id:
            self.notifications.create(
                user_id=created["assignee_id"],
                title="New task assigned",
                body=f"You've been assigned: {created['title']}",
                notif_type="task",
                team_id=team_id,
                actor_id=creator_id,
                link=f"/projects/{project_id}/tasks/{created['id']}"
            )

        # Record history
        self._log_history(created["id"], creator_id, "created", None, created)

        return created

    def update_task(self, task_id: str, user_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        # Fetch current state
        current = self.supabase.table("tasks").select("*").eq("id", task_id).execute()
        if not current.data:
            raise ValueError("Task not found")

        old = current.data[0]

        updates["updated_at"] = datetime.utcnow().isoformat()
        if updates.get("status") == "done" and old.get("status") != "done":
            updates["completed_at"] = datetime.utcnow().isoformat()

        result = self.supabase.table("tasks").update(updates).eq("id", task_id).execute()
        if not result.data:
            raise RuntimeError("Failed to update task")

        updated = result.data[0]

        # Track history
        changed_fields = {k: {"from": old.get(k), "to": v}
                          for k, v in updates.items() if old.get(k) != v and k != "updated_at"}
        if changed_fields:
            self._log_history(task_id, user_id, "updated", old, changed_fields)

        # Notify if assignee changed
        if updates.get("assignee_id") and updates["assignee_id"] != old.get("assignee_id"):
            self.notifications.create(
                user_id=updates["assignee_id"],
                title="Task assigned to you",
                body=f"Task assigned: {updated['title']}",
                notif_type="task",
                team_id=old.get("team_id"),
                actor_id=user_id
            )

        # Update search index
        self.search.index(
            team_id=old.get("team_id", ""),
            resource_type="task",
            resource_id=task_id,
            title=updated.get("title", ""),
            body=updated.get("description", ""),
            project_id=old.get("project_id")
        )

        return updated

    def delete_task(self, task_id: str, user_id: str) -> bool:
        task = self.supabase.table("tasks").select("team_id,project_id").eq("id", task_id).execute()
        if not task.data:
            return False

        self.supabase.table("tasks").delete().eq("id", task_id).execute()
        self.search.remove(task_id, "task")
        return True

    def get_tasks(self, project_id: str, status: str = None,
                  sprint_id: str = None, assignee_id: str = None) -> List[Dict]:
        q = self.supabase.table("tasks").select(
            "*, assignee:assignee_id(id,username,full_name,avatar_url), "
            "creator:creator_id(id,username,full_name,avatar_url)"
        ).eq("project_id", project_id)

        if status:
            q = q.eq("status", status)
        if sprint_id:
            q = q.eq("sprint_id", sprint_id)
        if assignee_id:
            q = q.eq("assignee_id", assignee_id)

        result = q.order("order_index").order("created_at").execute()
        return result.data or []

    def get_task(self, task_id: str) -> Optional[Dict]:
        result = self.supabase.table("tasks").select(
            "*, assignee:assignee_id(id,username,full_name,avatar_url), "
            "creator:creator_id(id,username,full_name,avatar_url)"
        ).eq("id", task_id).execute()
        return result.data[0] if result.data else None

    def add_comment(self, task_id: str, user_id: str, content: str,
                    parent_id: str = None) -> Dict[str, Any]:
        task = self.get_task(task_id)
        if not task:
            raise ValueError("Task not found")

        comment = {
            "task_id": task_id,
            "user_id": user_id,
            "content": content,
            "parent_id": parent_id,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }
        result = self.supabase.table("task_comments").insert(comment).execute()
        if not result.data:
            raise RuntimeError("Failed to create comment")

        # Notify task creator/assignee
        notify_users = set()
        if task.get("creator_id") and task["creator_id"] != user_id:
            notify_users.add(task["creator_id"])
        if task.get("assignee_id") and task["assignee_id"] != user_id:
            notify_users.add(task["assignee_id"])

        for uid in notify_users:
            self.notifications.create(
                user_id=uid,
                title="New comment on task",
                body=f"Comment on: {task['title']}",
                notif_type="comment",
                team_id=task.get("team_id"),
                actor_id=user_id,
                link=f"/projects/{task['project_id']}/tasks/{task_id}"
            )

        return result.data[0]

    def get_comments(self, task_id: str) -> List[Dict]:
        result = self.supabase.table("task_comments").select(
            "*, user:user_id(id,username,full_name,avatar_url)"
        ).eq("task_id", task_id).order("created_at").execute()
        return result.data or []

    def get_kanban_board(self, project_id: str) -> Dict[str, List]:
        tasks = self.get_tasks(project_id)
        columns = {
            "backlog": [],
            "todo": [],
            "in_progress": [],
            "review": [],
            "done": []
        }
        for task in tasks:
            status = task.get("status", "backlog")
            if status in columns:
                columns[status].append(task)
        return columns

    def reorder_tasks(self, task_ids: List[str], user_id: str) -> bool:
        for i, task_id in enumerate(task_ids):
            self.supabase.table("tasks").update({"order_index": i}).eq("id", task_id).execute()
        return True

    def create_sprint(self, project_id: str, team_id: str, creator_id: str,
                      data: Dict) -> Dict[str, Any]:
        sprint = {
            "project_id": project_id,
            "team_id": team_id,
            "creator_id": creator_id,
            "name": data["name"],
            "goal": data.get("goal", ""),
            "start_date": data.get("start_date"),
            "end_date": data.get("end_date"),
            "status": "planned",
            "created_at": datetime.utcnow().isoformat()
        }
        result = self.supabase.table("sprints").insert(sprint).execute()
        return result.data[0] if result.data else sprint

    def get_sprints(self, project_id: str) -> List[Dict]:
        result = self.supabase.table("sprints").select("*").eq(
            "project_id", project_id
        ).order("created_at", desc=True).execute()
        return result.data or []

    def _log_history(self, task_id: str, user_id: str, action: str,
                     old_state: Any, new_state: Any) -> None:
        try:
            self.supabase.table("task_history").insert({
                "task_id": task_id,
                "user_id": user_id,
                "action": action,
                "old_state": old_state,
                "new_state": new_state,
                "created_at": datetime.utcnow().isoformat()
            }).execute()
        except Exception as e:
            logger.error(f"Task history log failed: {e}")