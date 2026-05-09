"""HackForge — Wiki Service"""
from datetime import datetime
from typing import Dict, Any, List, Optional
from backend.services.supabase_service import get_supabase
from backend.services.search_service import SearchService
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class WikiService:

    def __init__(self):
        self.supabase = get_supabase()
        self.search = SearchService()

    def create_page(self, team_id: str, project_id: str, author_id: str,
                    data: Dict) -> Dict[str, Any]:
        page = {
            "team_id": team_id,
            "project_id": project_id,
            "author_id": author_id,
            "title": data["title"],
            "content": data.get("content", ""),
            "slug": data.get("slug") or self._slugify(data["title"]),
            "parent_id": data.get("parent_id"),
            "tags": data.get("tags", []),
            "is_published": data.get("is_published", True),
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }
        result = self.supabase.table("wiki_pages").insert(page).execute()
        if not result.data:
            raise RuntimeError("Failed to create wiki page")

        created = result.data[0]

        self.search.index(
            team_id=team_id,
            resource_type="wiki",
            resource_id=created["id"],
            title=created["title"],
            body=created["content"],
            project_id=project_id,
            author_id=author_id
        )

        return created

    def update_page(self, page_id: str, user_id: str, data: Dict) -> Dict[str, Any]:
        current = self.supabase.table("wiki_pages").select("*").eq("id", page_id).execute()
        if not current.data:
            raise ValueError("Wiki page not found")

        old = current.data[0]

        # Save revision
        self.supabase.table("wiki_revisions").insert({
            "page_id": page_id,
            "author_id": old["author_id"],
            "title": old["title"],
            "content": old["content"],
            "revision_number": self._next_revision(page_id),
            "created_at": datetime.utcnow().isoformat()
        }).execute()

        updates = {
            "title": data.get("title", old["title"]),
            "content": data.get("content", old["content"]),
            "tags": data.get("tags", old["tags"]),
            "is_published": data.get("is_published", old["is_published"]),
            "last_editor_id": user_id,
            "updated_at": datetime.utcnow().isoformat()
        }

        result = self.supabase.table("wiki_pages").update(updates).eq("id", page_id).execute()
        updated = result.data[0] if result.data else {**old, **updates}

        self.search.index(
            team_id=old["team_id"],
            resource_type="wiki",
            resource_id=page_id,
            title=updates["title"],
            body=updates["content"],
            project_id=old.get("project_id")
        )

        return updated

    def get_pages(self, team_id: str, project_id: str = None) -> List[Dict]:
        q = self.supabase.table("wiki_pages").select(
            "*, author:author_id(id,username,full_name,avatar_url)"
        ).eq("team_id", team_id).eq("is_published", True)

        if project_id:
            q = q.eq("project_id", project_id)

        result = q.order("updated_at", desc=True).execute()
        return result.data or []

    def get_page(self, page_id: str) -> Optional[Dict]:
        result = self.supabase.table("wiki_pages").select(
            "*, author:author_id(id,username,full_name,avatar_url)"
        ).eq("id", page_id).execute()
        return result.data[0] if result.data else None

    def delete_page(self, page_id: str) -> bool:
        self.supabase.table("wiki_pages").delete().eq("id", page_id).execute()
        self.search.remove(page_id, "wiki")
        return True

    def get_revisions(self, page_id: str) -> List[Dict]:
        result = self.supabase.table("wiki_revisions").select(
            "*, author:author_id(id,username,full_name)"
        ).eq("page_id", page_id).order("revision_number", desc=True).execute()
        return result.data or []

    def _next_revision(self, page_id: str) -> int:
        result = self.supabase.table("wiki_revisions").select(
            "revision_number"
        ).eq("page_id", page_id).order("revision_number", desc=True).limit(1).execute()
        if result.data:
            return (result.data[0]["revision_number"] or 0) + 1
        return 1

    def _slugify(self, text: str) -> str:
        import re
        slug = text.lower().strip()
        slug = re.sub(r'[^\w\s-]', '', slug)
        slug = re.sub(r'[\s_-]+', '-', slug)
        return slug[:100]