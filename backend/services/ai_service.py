"""HackForge — AI Service (orchestration layer)"""
import os
from datetime import datetime
from typing import Dict, Any, List, Optional

from backend.services.gemini_service import GeminiService
from backend.services.supabase_service import get_supabase
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class AIService:

    def __init__(self):
        self.gemini = GeminiService()
        self.supabase = get_supabase()

    def _save_memory(self, user_id: str, team_id: str, memory_type: str,
                     content: str, metadata: dict = None):
        try:
            self.supabase.table("ai_memory").insert({
                "user_id": user_id,
                "team_id": team_id,
                "memory_type": memory_type,
                "content": content,
                "metadata": metadata or {},
                "created_at": datetime.utcnow().isoformat()
            }).execute()
        except Exception as e:
            logger.error(f"Failed to save AI memory: {e}")

    def _get_recent_memory(self, team_id: str, memory_type: str = None, limit: int = 10) -> List[Dict]:
        try:
            q = self.supabase.table("ai_memory").select("*").eq("team_id", team_id)
            if memory_type:
                q = q.eq("memory_type", memory_type)
            result = q.order("created_at", desc=True).limit(limit).execute()
            return result.data or []
        except Exception:
            return []

    def _log_action(self, user_id: str, team_id: str, action_type: str,
                    input_data: dict, output_data: dict, status: str = "success"):
        try:
            self.supabase.table("ai_actions").insert({
                "user_id": user_id,
                "team_id": team_id,
                "action_type": action_type,
                "input_data": input_data,
                "output_data": output_data,
                "status": status,
                "created_at": datetime.utcnow().isoformat()
            }).execute()
        except Exception as e:
            logger.error(f"Failed to log AI action: {e}")

    # ─────────────────────────────────
    # CODE REVIEW
    # ─────────────────────────────────

    def review_code(self, user_id: str, team_id: str, code: str,
                    language: str, context: str = "") -> Dict[str, Any]:
        result = self.gemini.review_code(code, language, context)
        self._log_action(user_id, team_id, "code_review",
                         {"language": language, "lines": len(code.splitlines())}, result)
        self._save_memory(user_id, team_id, "code_review",
                          f"Reviewed {language} code. Score: {result.get('score')}")
        return result

    def find_bugs(self, user_id: str, team_id: str, code: str, language: str) -> Dict[str, Any]:
        result = self.gemini.find_bugs(code, language)
        self._log_action(user_id, team_id, "bug_finder",
                         {"language": language}, result)
        return result

    # ─────────────────────────────────
    # TASK / PROJECT MANAGEMENT
    # ─────────────────────────────────

    def plan_sprint(self, user_id: str, team_id: str, project_id: str,
                    sprint_days: int = 14) -> Dict[str, Any]:
        # Fetch open tasks
        tasks_result = self.supabase.table("tasks").select(
            "id,title,description,story_points,priority,assignee_id"
        ).eq("project_id", project_id).eq("status", "backlog").execute()

        tasks = tasks_result.data or []

        members_result = self.supabase.table("project_members").select(
            "user_id,role"
        ).eq("project_id", project_id).execute()

        team_size = len(members_result.data or [])

        result = self.gemini.plan_sprint(tasks, team_size, sprint_days)
        self._log_action(user_id, team_id, "sprint_planner",
                         {"project_id": project_id, "task_count": len(tasks)}, result)
        return result

    def assign_tasks(self, user_id: str, team_id: str, project_id: str) -> Dict[str, Any]:
        tasks_result = self.supabase.table("tasks").select("*").eq(
            "project_id", project_id
        ).is_("assignee_id", None).execute()

        members_result = self.supabase.table("memberships").select(
            "user_id, role"
        ).eq("team_id", team_id).execute()

        tasks = tasks_result.data or []
        members = members_result.data or []

        result = self.gemini.assign_tasks(tasks, members)
        self._log_action(user_id, team_id, "task_assignment",
                         {"task_count": len(tasks)}, result)
        return result

    def predict_deadline(self, user_id: str, team_id: str, task: Dict) -> Dict[str, Any]:
        # Get similar completed tasks
        similar = self.supabase.table("tasks").select(
            "title,story_points,actual_hours,completed_at,created_at"
        ).eq("team_id", team_id).eq("status", "done").limit(10).execute()

        result = self.gemini.predict_deadline(task, similar.data or [])
        self._log_action(user_id, team_id, "deadline_predictor", task, result)
        return result

    # ─────────────────────────────────
    # CONTENT GENERATION
    # ─────────────────────────────────

    def generate_readme(self, user_id: str, team_id: str, project_id: str) -> str:
        project = self.supabase.table("projects").select("*").eq("id", project_id).execute()
        if not project.data:
            raise ValueError("Project not found")
        p = project.data[0]

        result = self.gemini.generate_readme(
            p.get("name", ""),
            p.get("description", ""),
            p.get("tech_stack", []),
            p.get("features", [])
        )
        self._log_action(user_id, team_id, "readme_generator",
                         {"project_id": project_id}, {"readme": result[:100]})
        return result

    def generate_ppt(self, user_id: str, team_id: str,
                     topic: str, context: str, slide_count: int = 10) -> Dict[str, Any]:
        result = self.gemini.generate_ppt_outline(topic, context, slide_count)
        self._log_action(user_id, team_id, "ppt_generator",
                         {"topic": topic, "slides": slide_count}, result)
        return result

    # ─────────────────────────────────
    # ASSISTANT / COPILOT
    # ─────────────────────────────────

    def chat(self, user_id: str, team_id: str, messages: List[Dict],
             project_context: str = "") -> str:
        memory = self._get_recent_memory(team_id, limit=5)
        memory_context = "\n".join([m["content"] for m in memory])

        system = f"""You are HackForge AI Copilot — an expert assistant for software development teams.
You help with coding, planning, debugging, architecture decisions, and team productivity.

Team context: {project_context}
Recent memory: {memory_context}

Be concise, practical, and actionable. Use code blocks when sharing code."""

        response = self.gemini.chat(messages, system)

        # Save to memory
        if messages:
            last_q = messages[-1].get("content", "")[:200]
            self._save_memory(user_id, team_id, "chat",
                              f"Q: {last_q} | A: {response[:200]}")

        self._log_action(user_id, team_id, "copilot_chat",
                         {"message_count": len(messages)}, {"response_len": len(response)})
        return response

    def research(self, user_id: str, team_id: str, topic: str, context: str = "") -> str:
        result = self.gemini.research_topic(topic, context)
        self._log_action(user_id, team_id, "research", {"topic": topic}, {"length": len(result)})
        return result

    def simulate_judge(self, user_id: str, team_id: str,
                       project: Dict, criteria: List[Dict]) -> Dict[str, Any]:
        result = self.gemini.simulate_judge(project, criteria)
        self._log_action(user_id, team_id, "judge_simulator", project, result)
        return result

    def answer_coding_question(self, user_id: str, team_id: str,
                                question: str, code: str = "", language: str = "") -> str:
        result = self.gemini.answer_coding_question(question, code, language)
        self._log_action(user_id, team_id, "coding_assistant",
                         {"question": question[:100]}, {"length": len(result)})
        return result

    # ─────────────────────────────────
    # MEMORY MANAGEMENT
    # ─────────────────────────────────

    def get_memory(self, team_id: str, memory_type: str = None,
                   limit: int = 20) -> List[Dict]:
        return self._get_recent_memory(team_id, memory_type, limit)

    def clear_memory(self, user_id: str, team_id: str, memory_type: str = None):
        q = self.supabase.table("ai_memory").delete().eq("team_id", team_id)
        if memory_type:
            q = q.eq("memory_type", memory_type)
        q.execute()
        logger.info(f"AI memory cleared for team {team_id} by {user_id}")