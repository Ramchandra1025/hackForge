"""HackForge — Search Service"""
from datetime import datetime
from typing import Dict, Any, List, Optional
from backend.services.supabase_service import get_supabase
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class SearchService:

    def __init__(self):
        self.supabase = get_supabase()

    def index(self, team_id: str, resource_type: str, resource_id: str,
              title: str, body: str = "", tags: list = None,
              author_id: str = None, project_id: str = None) -> None:
        try:
            self.supabase.table("search_index").upsert({
                "team_id": team_id,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "title": title,
                "body": body[:2000],
                "tags": tags or [],
                "author_id": author_id,
                "project_id": project_id,
                "indexed_at": datetime.utcnow().isoformat()
            }, on_conflict="resource_id,resource_type").execute()
        except Exception as e:
            logger.error(f"Search index failed: {e}")

    def search(self, team_id: str, query: str,
               resource_types: List[str] = None,
               project_id: str = None,
               page: int = 1, per_page: int = 20) -> Dict[str, Any]:
        try:
            q = self.supabase.table("search_index").select("*").eq("team_id", team_id)

            if resource_types:
                q = q.in_("resource_type", resource_types)
            if project_id:
                q = q.eq("project_id", project_id)

            # Text search across title and body
            q = q.or_(f"title.ilike.%{query}%,body.ilike.%{query}%")

            offset = (page - 1) * per_page
            result = q.order("indexed_at", desc=True).range(offset, offset + per_page - 1).execute()

            return {
                "results": result.data or [],
                "query": query,
                "page": page,
                "per_page": per_page,
                "total": len(result.data or [])
            }
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return {"results": [], "query": query, "page": page, "per_page": per_page, "total": 0}

    def remove(self, resource_id: str, resource_type: str) -> None:
        try:
            self.supabase.table("search_index").delete().eq(
                "resource_id", resource_id
            ).eq("resource_type", resource_type).execute()
        except Exception as e:
            logger.error(f"Search remove failed: {e}")