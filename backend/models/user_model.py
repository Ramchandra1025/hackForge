"""User data model and database operations"""
from datetime import datetime
from supabase import create_client
import os

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

class UserModel:
    @staticmethod
    def create_user(email, username, password_hash, avatar_url=None):
        """Create a new user"""
        try:
            response = supabase.table("users").insert({
                "email": email,
                "username": username,
                "password_hash": password_hash,
                "avatar_url": avatar_url,
                "bio": "",
                "skills": [],
                "github_link": "",
                "portfolio_link": "",
                "badges": [],
                "reputation_score": 0,
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
                "is_active": True
            }).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            print(f"Error creating user: {e}")
            return None

    @staticmethod
    def get_user_by_email(email):
        """Get user by email"""
        try:
            response = supabase.table("users").select("*").eq("email", email).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            print(f"Error getting user by email: {e}")
            return None

    @staticmethod
    def get_user_by_username(username):
        """Get user by username"""
        try:
            response = supabase.table("users").select("*").eq("username", username).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            print(f"Error getting user by username: {e}")
            return None

    @staticmethod
    def get_user_by_id(user_id):
        """Get user by ID"""
        try:
            response = supabase.table("users").select("*").eq("id", user_id).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            print(f"Error getting user by ID: {e}")
            return None

    @staticmethod
    def update_user(user_id, updates):
        """Update user data"""
        try:
            updates["updated_at"] = datetime.utcnow().isoformat()
            response = supabase.table("users").update(updates).eq("id", user_id).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            print(f"Error updating user: {e}")
            return None

    @staticmethod
    def get_user_profile(user_id):
        """Get user profile with reputation"""
        try:
            response = supabase.table("users").select(
                "id, email, username, avatar_url, bio, skills, github_link, portfolio_link, badges, reputation_score, created_at"
            ).eq("id", user_id).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            print(f"Error getting user profile: {e}")
            return None

    @staticmethod
    def search_users(query):
        """Search users by username or email"""
        try:
            response = supabase.table("users").select(
                "id, email, username, avatar_url, reputation_score"
            ).ilike("username", f"%{query}%").execute()
            return response.data
        except Exception as e:
            print(f"Error searching users: {e}")
            return []

    @staticmethod
    def update_profile(user_id, bio, skills, github_link, portfolio_link, avatar_url):
        """Update user profile"""
        return UserModel.update_user(user_id, {
            "bio": bio,
            "skills": skills,
            "github_link": github_link,
            "portfolio_link": portfolio_link,
            "avatar_url": avatar_url
        })

    @staticmethod
    def add_badge(user_id, badge):
        """Add badge to user"""
        user = UserModel.get_user_by_id(user_id)
        if user:
            badges = user.get("badges", [])
            if badge not in badges:
                badges.append(badge)
            return UserModel.update_user(user_id, {"badges": badges})
        return None

    @staticmethod
    def update_reputation(user_id, points):
        """Update reputation score"""
        user = UserModel.get_user_by_id(user_id)
        if user:
            current_score = user.get("reputation_score", 0)
            return UserModel.update_user(user_id, {
                "reputation_score": current_score + points
            })
        return None
