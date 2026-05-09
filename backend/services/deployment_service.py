"""HackForge — Deployment Services"""
import os
import requests
from datetime import datetime
from typing import Dict, Any, List, Optional
from backend.services.supabase_service import get_supabase
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class NetlifyService:
    BASE = "https://api.netlify.com/api/v1"

    def __init__(self, token: str = None):
        self.token = token or os.getenv("NETLIFY_TOKEN", "")
        self.headers = {"Authorization": f"Bearer {self.token}"}

    def list_sites(self) -> List[Dict]:
        try:
            r = requests.get(f"{self.BASE}/sites", headers=self.headers, timeout=10)
            return r.json() if r.ok else []
        except Exception as e:
            logger.error(f"Netlify list sites: {e}")
            return []

    def create_site(self, name: str) -> Dict:
        try:
            r = requests.post(f"{self.BASE}/sites",
                              headers=self.headers,
                              json={"name": name}, timeout=10)
            return r.json()
        except Exception as e:
            logger.error(f"Netlify create site: {e}")
            return {"error": str(e)}

    def deploy(self, site_id: str, zip_content: bytes) -> Dict:
        try:
            r = requests.post(
                f"{self.BASE}/sites/{site_id}/deploys",
                headers={**self.headers, "Content-Type": "application/zip"},
                data=zip_content, timeout=60
            )
            return r.json()
        except Exception as e:
            logger.error(f"Netlify deploy: {e}")
            return {"error": str(e)}

    def get_deploy_status(self, deploy_id: str) -> Dict:
        try:
            r = requests.get(f"{self.BASE}/deploys/{deploy_id}", headers=self.headers, timeout=10)
            return r.json()
        except Exception as e:
            return {"error": str(e)}


class RailwayService:
    GRAPHQL_URL = "https://backboard.railway.app/graphql/v2"

    def __init__(self, token: str = None):
        self.token = token or os.getenv("RAILWAY_TOKEN", "")
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

    def _gql(self, query: str, variables: dict = None) -> Dict:
        try:
            r = requests.post(
                self.GRAPHQL_URL,
                headers=self.headers,
                json={"query": query, "variables": variables or {}},
                timeout=15
            )
            return r.json()
        except Exception as e:
            logger.error(f"Railway GQL error: {e}")
            return {"errors": [{"message": str(e)}]}

    def list_projects(self) -> List[Dict]:
        result = self._gql("query { me { projects { edges { node { id name } } } } }")
        try:
            return result["data"]["me"]["projects"]["edges"]
        except Exception:
            return []

    def get_deployments(self, project_id: str) -> List[Dict]:
        q = """query($id: String!) {
            project(id: $id) {
                deployments { edges { node { id status createdAt } } }
            }
        }"""
        result = self._gql(q, {"id": project_id})
        try:
            return result["data"]["project"]["deployments"]["edges"]
        except Exception:
            return []


class GitHubService:
    BASE = "https://api.github.com"

    def __init__(self, token: str = None):
        self.token = token
        self.headers = {
            "Authorization": f"Bearer {token}" if token else "",
            "Accept": "application/vnd.github.v3+json"
        }

    def get_repos(self) -> List[Dict]:
        try:
            r = requests.get(f"{self.BASE}/user/repos?per_page=100&sort=updated",
                             headers=self.headers, timeout=10)
            return r.json() if r.ok else []
        except Exception as e:
            logger.error(f"GitHub get repos: {e}")
            return []

    def get_repo(self, owner: str, repo: str) -> Dict:
        try:
            r = requests.get(f"{self.BASE}/repos/{owner}/{repo}",
                             headers=self.headers, timeout=10)
            return r.json() if r.ok else {}
        except Exception as e:
            return {"error": str(e)}

    def list_branches(self, owner: str, repo: str) -> List[Dict]:
        try:
            r = requests.get(f"{self.BASE}/repos/{owner}/{repo}/branches",
                             headers=self.headers, timeout=10)
            return r.json() if r.ok else []
        except Exception as e:
            return []

    def get_commits(self, owner: str, repo: str, branch: str = "main", per_page: int = 20) -> List[Dict]:
        try:
            r = requests.get(
                f"{self.BASE}/repos/{owner}/{repo}/commits?sha={branch}&per_page={per_page}",
                headers=self.headers, timeout=10
            )
            return r.json() if r.ok else []
        except Exception as e:
            return []

    def create_webhook(self, owner: str, repo: str, webhook_url: str, events: List[str]) -> Dict:
        try:
            r = requests.post(
                f"{self.BASE}/repos/{owner}/{repo}/hooks",
                headers=self.headers,
                json={
                    "name": "web",
                    "active": True,
                    "events": events,
                    "config": {"url": webhook_url, "content_type": "json"}
                },
                timeout=10
            )
            return r.json()
        except Exception as e:
            return {"error": str(e)}


class DeploymentService:

    def __init__(self):
        self.supabase = get_supabase()
        self.netlify = NetlifyService()
        self.railway = RailwayService()

    def get_deployments(self, project_id: str, limit: int = 20) -> List[Dict]:
        result = self.supabase.table("deployments").select(
            "*, deployer:deployed_by(id,username,full_name,avatar_url)"
        ).eq("project_id", project_id).order("created_at", desc=True).limit(limit).execute()
        return result.data or []

    def create_deployment(self, project_id: str, team_id: str, user_id: str,
                          platform: str, config: Dict) -> Dict[str, Any]:
        deployment = {
            "project_id": project_id,
            "team_id": team_id,
            "deployed_by": user_id,
            "platform": platform,
            "status": "pending",
            "config": config,
            "environment": config.get("environment", "production"),
            "branch": config.get("branch", "main"),
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }
        result = self.supabase.table("deployments").insert(deployment).execute()
        return result.data[0] if result.data else deployment

    def update_deployment_status(self, deployment_id: str, status: str,
                                 url: str = None, error: str = None,
                                 logs: str = None) -> Dict:
        updates = {
            "status": status,
            "updated_at": datetime.utcnow().isoformat()
        }
        if status == "success":
            updates["deployed_at"] = datetime.utcnow().isoformat()
        if url:
            updates["deploy_url"] = url
        if error:
            updates["error_message"] = error
        if logs:
            updates["build_logs"] = logs

        result = self.supabase.table("deployments").update(updates).eq(
            "id", deployment_id
        ).execute()
        return result.data[0] if result.data else {}

    def get_deployment_logs(self, deployment_id: str) -> List[Dict]:
        result = self.supabase.table("deployment_logs").select("*").eq(
            "deployment_id", deployment_id
        ).order("created_at").execute()
        return result.data or []

    def add_log(self, deployment_id: str, message: str, level: str = "info") -> None:
        try:
            self.supabase.table("deployment_logs").insert({
                "deployment_id": deployment_id,
                "message": message,
                "level": level,
                "created_at": datetime.utcnow().isoformat()
            }).execute()
        except Exception as e:
            logger.error(f"Deployment log failed: {e}")