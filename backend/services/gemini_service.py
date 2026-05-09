"""HackForge — Google Gemini AI Service"""
import os
import json
from typing import Optional, List, Dict, Any
import google.generativeai as genai
from backend.utils.logger import get_logger

logger = get_logger(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-pro")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)


class GeminiService:

    def __init__(self):
        self.model_name = GEMINI_MODEL
        self._model = None

    def _get_model(self):
        if not self._model:
            self._model = genai.GenerativeModel(self.model_name)
        return self._model

    def generate(self, prompt: str, system_prompt: str = None,
                 temperature: float = 0.7, max_tokens: int = 2048) -> str:
        try:
            model = self._get_model()
            full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
            response = model.generate_content(
                full_prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=temperature,
                    max_output_tokens=max_tokens
                )
            )
            return response.text
        except Exception as e:
            logger.error(f"Gemini generate error: {e}")
            raise RuntimeError(f"AI generation failed: {str(e)}")

    def generate_json(self, prompt: str, system_prompt: str = None) -> Any:
        """Generate and parse JSON response."""
        json_system = (system_prompt or "") + "\nRespond ONLY with valid JSON. No markdown, no explanation."
        raw = self.generate(prompt, json_system)
        raw = raw.strip()
        if raw.startswith("```"):
            lines = raw.split("\n")
            raw = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
        return json.loads(raw)

    def chat(self, messages: List[Dict[str, str]], system_prompt: str = None) -> str:
        """Multi-turn conversation."""
        try:
            model = self._get_model()
            chat_session = model.start_chat(history=[])

            if system_prompt:
                chat_session.send_message(f"System: {system_prompt}")

            for msg in messages[:-1]:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if role == "user":
                    chat_session.send_message(content)
                # assistant messages are handled by history

            last = messages[-1]["content"] if messages else "Hello"
            response = chat_session.send_message(last)
            return response.text
        except Exception as e:
            logger.error(f"Gemini chat error: {e}")
            raise RuntimeError(f"AI chat failed: {str(e)}")

    # ────────────────────────────
    # SPECIALIZED AI WORKERS
    # ────────────────────────────

    def review_code(self, code: str, language: str, context: str = "") -> Dict[str, Any]:
        prompt = f"""Review this {language} code:

```{language}
{code}
```

Context: {context}

Provide:
1. Overall quality score (0-100)
2. Critical issues (bugs, security problems)
3. Style improvements
4. Performance suggestions
5. Refactored snippet if needed

Return as JSON with keys: score, critical_issues, style_suggestions, performance_tips, refactored_code, summary"""

        return self.generate_json(prompt,
            "You are an expert code reviewer. Be precise, constructive, and specific.")

    def find_bugs(self, code: str, language: str) -> Dict[str, Any]:
        prompt = f"""Analyze this {language} code for bugs:

```{language}
{code}
```

Find:
- Runtime errors
- Logic errors  
- Security vulnerabilities
- Edge case failures
- Memory leaks

Return JSON: {{ bugs: [{{line, severity, description, fix}}], risk_level, summary }}"""

        return self.generate_json(prompt,
            "You are a senior debugging expert. Find all issues precisely.")

    def generate_readme(self, project_name: str, description: str,
                        tech_stack: List[str], features: List[str]) -> str:
        prompt = f"""Generate a professional README.md for:

Project: {project_name}
Description: {description}
Tech Stack: {', '.join(tech_stack)}
Features: {', '.join(features)}

Include: badges, overview, features, installation, usage, API docs structure, contributing, license."""

        return self.generate(prompt,
            "You are a technical writer. Create stunning, professional README files.")

    def plan_sprint(self, tasks: List[Dict], team_size: int,
                    sprint_days: int, velocity: float = None) -> Dict[str, Any]:
        prompt = f"""Plan a sprint with these tasks:

Tasks: {json.dumps(tasks, indent=2)}
Team size: {team_size}
Sprint duration: {sprint_days} days
Historical velocity: {velocity or 'unknown'}

Create an optimal sprint plan with:
- Selected tasks for sprint
- Story point allocation
- Daily workload distribution
- Risk assessment
- Success metrics

Return JSON: {{ selected_tasks, total_points, daily_plan, risks, success_criteria }}"""

        return self.generate_json(prompt,
            "You are an agile sprint planning expert.")

    def assign_tasks(self, tasks: List[Dict], team_members: List[Dict]) -> Dict[str, Any]:
        prompt = f"""Assign these tasks to team members optimally:

Tasks: {json.dumps(tasks, indent=2)}
Team: {json.dumps(team_members, indent=2)}

Consider: skills, workload, task complexity, deadlines.
Return JSON: {{ assignments: [{{task_id, assignee_id, reasoning}}], workload_balance, warnings }}"""

        return self.generate_json(prompt,
            "You are an AI project manager specializing in optimal task assignment.")

    def generate_ppt_outline(self, topic: str, context: str, slide_count: int = 10) -> Dict[str, Any]:
        prompt = f"""Create a {slide_count}-slide presentation outline for:

Topic: {topic}
Context: {context}

For each slide provide: title, key_points (3-5), speaker_notes, suggested_visual.
Return JSON: {{ title, slides: [...], summary }}"""

        return self.generate_json(prompt,
            "You are a professional presentation designer and public speaker coach.")

    def predict_deadline(self, task: Dict, similar_tasks: List[Dict]) -> Dict[str, Any]:
        prompt = f"""Predict realistic deadline for this task:

Task: {json.dumps(task, indent=2)}
Similar completed tasks: {json.dumps(similar_tasks[:5], indent=2)}

Consider: complexity, dependencies, team velocity.
Return JSON: {{ estimated_hours, confidence_level, risk_factors, recommended_deadline }}"""

        return self.generate_json(prompt,
            "You are an AI deadline prediction expert using historical data.")

    def research_topic(self, topic: str, context: str = "") -> str:
        prompt = f"""Research and summarize: {topic}
Context: {context}

Provide: overview, key concepts, best practices, common pitfalls, resources."""

        return self.generate(prompt,
            "You are an expert researcher. Provide accurate, well-structured information.")

    def simulate_judge(self, project: Dict, criteria: List[Dict]) -> Dict[str, Any]:
        prompt = f"""Evaluate this hackathon project as a judge:

Project: {json.dumps(project, indent=2)}
Criteria: {json.dumps(criteria, indent=2)}

Score each criterion (0-10) with detailed reasoning.
Return JSON: {{ scores: [{{criterion, score, feedback}}], total_score, overall_feedback, recommendation }}"""

        return self.generate_json(prompt,
            "You are an experienced hackathon judge. Be fair, thorough, and constructive.")

    def answer_coding_question(self, question: str, code_context: str = "",
                                language: str = "") -> str:
        prompt = f"""Answer this coding question:

Question: {question}
{"Language: " + language if language else ""}
{"Code context:\n```\n" + code_context + "\n```" if code_context else ""}"""

        return self.generate(prompt,
            "You are an expert software engineer. Give clear, accurate, practical answers with code examples.")