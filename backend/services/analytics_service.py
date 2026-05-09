"""HackForge — Analytics Service"""
from datetime import datetime, timedelta
from typing import Dict, Any, List
from backend.services.supabase_service import get_supabase
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class AnalyticsService:

    def __init__(self):
        self.supabase = get_supabase()

    def get_project_stats(self, project_id: str) -> Dict[str, Any]:
        tasks = self.supabase.table("tasks").select("id,status,priority,story_points,created_at,completed_at").eq("project_id", project_id).execute()
        task_list = tasks.data or []

        total = len(task_list)
        by_status = {}
        by_priority = {}
        total_points = 0
        done_points = 0

        for t in task_list:
            s = t.get("status", "backlog")
            p = t.get("priority", "medium")
            pts = t.get("story_points") or 0
            by_status[s] = by_status.get(s, 0) + 1
            by_priority[p] = by_priority.get(p, 0) + 1
            total_points += pts
            if s == "done":
                done_points += pts

        progress = round((by_status.get("done", 0) / total * 100) if total else 0, 1)

        return {
            "total_tasks": total,
            "by_status": by_status,
            "by_priority": by_priority,
            "total_story_points": total_points,
            "completed_story_points": done_points,
            "completion_percentage": progress,
            "velocity": self._calculate_velocity(project_id)
        }

    def get_team_stats(self, team_id: str) -> Dict[str, Any]:
        members = self.supabase.table("memberships").select("user_id").eq("team_id", team_id).execute()
        projects = self.supabase.table("projects").select("id").eq("team_id", team_id).execute()
        files = self.supabase.table("files").select("id,size").eq("team_id", team_id).execute()

        total_storage = sum(f.get("size") or 0 for f in (files.data or []))

        return {
            "member_count": len(members.data or []),
            "project_count": len(projects.data or []),
            "file_count": len(files.data or []),
            "total_storage_bytes": total_storage,
            "total_storage_mb": round(total_storage / 1024 / 1024, 2)
        }

    def get_activity_timeline(self, team_id: str, days: int = 7) -> List[Dict]:
        since = (datetime.utcnow() - timedelta(days=days)).isoformat()
        result = self.supabase.table("activities").select("*").eq(
            "team_id", team_id
        ).gte("created_at", since).order("created_at", desc=True).limit(100).execute()
        return result.data or []

    def get_member_contributions(self, team_id: str) -> List[Dict]:
        members = self.supabase.table("memberships").select(
            "user_id, users(username, full_name, avatar_url)"
        ).eq("team_id", team_id).execute()

        contributions = []
        for m in (members.data or []):
            uid = m["user_id"]
            tasks_done = self.supabase.table("tasks").select("id", count="exact").eq(
                "assignee_id", uid
            ).eq("status", "done").execute()
            comments = self.supabase.table("task_comments").select("id", count="exact").eq(
                "user_id", uid
            ).execute()

            user_info = m.get("users") or {}
            contributions.append({
                "user_id": uid,
                "username": user_info.get("username"),
                "full_name": user_info.get("full_name"),
                "avatar_url": user_info.get("avatar_url"),
                "tasks_completed": tasks_done.count or 0,
                "comments": comments.count or 0
            })

        return sorted(contributions, key=lambda x: x["tasks_completed"], reverse=True)

    def _calculate_velocity(self, project_id: str) -> float:
        sprints = self.supabase.table("sprints").select("id").eq(
            "project_id", project_id
        ).eq("status", "completed").limit(3).execute()

        if not sprints.data:
            return 0.0

        total_points = 0
        count = 0
        for sprint in sprints.data:
            tasks = self.supabase.table("tasks").select("story_points").eq(
                "sprint_id", sprint["id"]
            ).eq("status", "done").execute()
            sprint_pts = sum(t.get("story_points") or 0 for t in (tasks.data or []))
            total_points += sprint_pts
            count += 1

        return round(total_points / count, 1) if count else 0.0

    def log_activity(self, team_id: str, user_id: str, action: str,
                     resource_type: str, resource_id: str = None,
                     description: str = "", metadata: dict = None) -> None:
        try:
            self.supabase.table("activities").insert({
                "team_id": team_id,
                "user_id": user_id,
                "action": action,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "description": description,
                "metadata": metadata or {},
                "created_at": datetime.utcnow().isoformat()
            }).execute()
        except Exception as e:
            logger.error(f"Activity log failed: {e}")