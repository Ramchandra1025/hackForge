"""HackForge — Collaboration Service (real-time editing)"""
from datetime import datetime
from typing import Dict, Any, List, Optional
from backend.services.supabase_service import get_supabase
from backend.services.redis_service import RedisService
from backend.utils.logger import get_logger
import json

logger = get_logger(__name__)


class CollaborationService:

    def __init__(self):
        self.supabase = get_supabase()
        self.redis = RedisService()

    def get_or_create_file(self, project_id: str, team_id: str,
                            file_path: str, creator_id: str) -> Dict[str, Any]:
        result = self.supabase.table("files").select("*").eq(
            "project_id", project_id
        ).eq("file_path", file_path).execute()

        if result.data:
            return result.data[0]

        # Create
        parts = file_path.rsplit("/", 1)
        name = parts[-1] if parts else file_path
        ext = name.rsplit(".", 1)[-1] if "." in name else "txt"

        file_data = {
            "project_id": project_id,
            "team_id": team_id,
            "creator_id": creator_id,
            "name": name,
            "file_path": file_path,
            "content": "",
            "language": self._detect_language(ext),
            "mime_type": f"text/{ext}",
            "size": 0,
            "is_directory": False,
            "version": 1,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }
        result = self.supabase.table("files").insert(file_data).execute()
        return result.data[0] if result.data else file_data

    def get_file_content(self, file_id: str) -> str:
        # Check Redis cache first
        cached = self.redis.get(f"file_content:{file_id}")
        if cached:
            return cached

        result = self.supabase.table("files").select("content").eq("id", file_id).execute()
        if result.data:
            content = result.data[0].get("content", "")
            self.redis.setex(f"file_content:{file_id}", 300, content)
            return content
        return ""

    def save_file_content(self, file_id: str, content: str,
                           user_id: str, create_version: bool = False) -> Dict:
        updates = {
            "content": content,
            "size": len(content.encode()),
            "updated_at": datetime.utcnow().isoformat(),
            "last_editor_id": user_id
        }

        result = self.supabase.table("files").update(updates).eq("id", file_id).execute()

        # Invalidate cache
        self.redis.delete(f"file_content:{file_id}")

        if create_version and result.data:
            self._create_version(file_id, content, user_id, result.data[0].get("version", 1))

        return result.data[0] if result.data else {}

    def _create_version(self, file_id: str, content: str, user_id: str, version: int):
        try:
            self.supabase.table("file_versions").insert({
                "file_id": file_id,
                "content": content,
                "author_id": user_id,
                "version_number": version,
                "created_at": datetime.utcnow().isoformat()
            }).execute()
            # Increment version
            self.supabase.table("files").update({"version": version + 1}).eq("id", file_id).execute()
        except Exception as e:
            logger.error(f"Version create failed: {e}")

    def get_active_editors(self, file_id: str) -> List[Dict]:
        key = f"editors:{file_id}"
        data = self.redis.hgetall(key)
        return list(data.values()) if data else []

    def join_file(self, file_id: str, user_id: str, user_info: Dict) -> None:
        key = f"editors:{file_id}"
        self.redis.hset(key, user_id, {
            **user_info,
            "joined_at": datetime.utcnow().isoformat()
        })
        self.redis.expire(key, 3600)

    def leave_file(self, file_id: str, user_id: str) -> None:
        key = f"editors:{file_id}"
        self.redis.hdel(key, user_id)

    def get_project_files(self, project_id: str, folder_id: str = None) -> List[Dict]:
        q = self.supabase.table("files").select("*").eq("project_id", project_id)
        if folder_id:
            q = q.eq("folder_id", folder_id)
        else:
            q = q.is_("folder_id", None)
        result = q.order("is_directory", desc=True).order("name").execute()
        return result.data or []

    def get_file_versions(self, file_id: str, limit: int = 20) -> List[Dict]:
        result = self.supabase.table("file_versions").select(
            "*, author:author_id(id,username,full_name,avatar_url)"
        ).eq("file_id", file_id).order("version_number", desc=True).limit(limit).execute()
        return result.data or []

    def create_folder(self, project_id: str, team_id: str,
                       name: str, parent_id: str, creator_id: str) -> Dict:
        folder = {
            "project_id": project_id,
            "team_id": team_id,
            "creator_id": creator_id,
            "name": name,
            "parent_id": parent_id,
            "created_at": datetime.utcnow().isoformat()
        }
        result = self.supabase.table("folders").insert(folder).execute()
        return result.data[0] if result.data else folder

    def delete_file(self, file_id: str) -> bool:
        self.supabase.table("files").delete().eq("id", file_id).execute()
        self.redis.delete(f"file_content:{file_id}")
        return True

    def _detect_language(self, ext: str) -> str:
        mapping = {
            "py": "python", "js": "javascript", "ts": "typescript",
            "jsx": "javascript", "tsx": "typescript", "html": "html",
            "css": "css", "json": "json", "md": "markdown", "sql": "sql",
            "sh": "shell", "yml": "yaml", "yaml": "yaml", "java": "java",
            "cpp": "cpp", "c": "c", "cs": "csharp", "go": "go",
            "rs": "rust", "rb": "ruby", "php": "php", "swift": "swift",
            "kt": "kotlin", "r": "r", "dockerfile": "dockerfile"
        }
        return mapping.get(ext.lower(), "plaintext")