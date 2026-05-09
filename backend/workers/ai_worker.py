"""AI Worker for background AI tasks"""
import os
import json
from datetime import datetime
from supabase import create_client
import google.generativeai as genai

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
genai.configure(api_key=GEMINI_API_KEY)

class AIWorker:
    @staticmethod
    def process_pending_actions():
        """Process pending AI actions"""
        try:
            # Get pending actions
            response = supabase.table("ai_actions").select("*").eq("status", "pending").execute()
            actions = response.data
            
            for action in actions:
                AIWorker.process_action(action)
                
        except Exception as e:
            print(f"Error processing AI actions: {e}")

    @staticmethod
    def process_action(action):
        """Process a single AI action"""
        try:
            action_type = action.get("action_type")
            action_id = action.get("id")
            
            # Update status to processing
            supabase.table("ai_actions").update({
                "status": "processing"
            }).eq("id", action_id).execute()
            
            if action_type == "generate_readme":
                AIWorker.generate_readme(action)
            elif action_type == "review_code":
                AIWorker.review_code(action)
            elif action_type == "plan_sprint":
                AIWorker.plan_sprint(action)
            elif action_type == "find_bugs":
                AIWorker.find_bugs(action)
            elif action_type == "generate_ppt":
                AIWorker.generate_ppt(action)
            
        except Exception as e:
            print(f"Error processing action: {e}")
            supabase.table("ai_actions").update({
                "status": "failed",
                "description": str(e)
            }).eq("id", action["id"]).execute()

    @staticmethod
    def generate_readme(action):
        """Generate README using Gemini"""
        try:
            description = action.get("description", "")
            model = genai.GenerativeModel("gemini-pro")
            
            prompt = f"Generate a professional README.md file for a project with the following description:\n{description}"
            response = model.generate_content(prompt)
            
            result = response.text
            
            supabase.table("ai_actions").update({
                "status": "completed",
                "description": result
            }).eq("id", action["id"]).execute()
            
        except Exception as e:
            print(f"Error generating README: {e}")

    @staticmethod
    def review_code(action):
        """Review code using Gemini"""
        try:
            code = action.get("description", "")
            model = genai.GenerativeModel("gemini-pro")
            
            prompt = f"Provide a detailed code review with suggestions for improvement:\n{code}"
            response = model.generate_content(prompt)
            
            result = response.text
            
            supabase.table("ai_actions").update({
                "status": "completed",
                "description": result
            }).eq("id", action["id"]).execute()
            
        except Exception as e:
            print(f"Error reviewing code: {e}")

    @staticmethod
    def plan_sprint(action):
        """Plan sprint using Gemini"""
        try:
            tasks = action.get("description", "")
            model = genai.GenerativeModel("gemini-pro")
            
            prompt = f"Create an optimized sprint plan for the following tasks:\n{tasks}"
            response = model.generate_content(prompt)
            
            result = response.text
            
            supabase.table("ai_actions").update({
                "status": "completed",
                "description": result
            }).eq("id", action["id"]).execute()
            
        except Exception as e:
            print(f"Error planning sprint: {e}")

    @staticmethod
    def find_bugs(action):
        """Find bugs in code using Gemini"""
        try:
            code = action.get("description", "")
            model = genai.GenerativeModel("gemini-pro")
            
            prompt = f"Analyze this code for potential bugs and security issues:\n{code}"
            response = model.generate_content(prompt)
            
            result = response.text
            
            supabase.table("ai_actions").update({
                "status": "completed",
                "description": result
            }).eq("id", action["id"]).execute()
            
        except Exception as e:
            print(f"Error finding bugs: {e}")

    @staticmethod
    def generate_ppt(action):
        """Generate PPT outline using Gemini"""
        try:
            topic = action.get("description", "")
            model = genai.GenerativeModel("gemini-pro")
            
            prompt = f"Create a detailed PowerPoint presentation outline for: {topic}"
            response = model.generate_content(prompt)
            
            result = response.text
            
            supabase.table("ai_actions").update({
                "status": "completed",
                "description": result
            }).eq("id", action["id"]).execute()
            
        except Exception as e:
            print(f"Error generating PPT: {e}")

if __name__ == "__main__":
    AIWorker.process_pending_actions()
