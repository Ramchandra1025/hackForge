"""Indexing Worker for search indexing"""
import os
from datetime import datetime
from supabase import create_client

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

class IndexingWorker:
    @staticmethod
    def index_documents():
        """Index documents for search"""
        try:
            # Index tasks
            IndexingWorker.index_tasks()
            # Index files
            IndexingWorker.index_files()
            # Index wiki pages
            IndexingWorker.index_wiki_pages()
            print("Indexing completed successfully")
        except Exception as e:
            print(f"Error during indexing: {e}")

    @staticmethod
    def index_tasks():
        """Index tasks for search"""
        try:
            response = supabase.table("tasks").select("id, title, description").execute()
            tasks = response.data
            
            for task in tasks:
                content = f"{task.get('title')} {task.get('description', '')}"
                supabase.table("search_index").insert({
                    "resource_type": "task",
                    "resource_id": task.get("id"),
                    "content": content,
                    "indexed_at": datetime.utcnow().isoformat()
                }).execute()
        except Exception as e:
            print(f"Error indexing tasks: {e}")

    @staticmethod
    def index_files():
        """Index files for search"""
        try:
            response = supabase.table("files").select("id, name, mime_type").execute()
            files = response.data
            
            for file in files:
                supabase.table("search_index").insert({
                    "resource_type": "file",
                    "resource_id": file.get("id"),
                    "content": file.get("name"),
                    "indexed_at": datetime.utcnow().isoformat()
                }).execute()
        except Exception as e:
            print(f"Error indexing files: {e}")

    @staticmethod
    def index_wiki_pages():
        """Index wiki pages for search"""
        try:
            response = supabase.table("wiki_pages").select("id, title, content").execute()
            pages = response.data
            
            for page in pages:
                content = f"{page.get('title')} {page.get('content', '')}"
                supabase.table("search_index").insert({
                    "resource_type": "wiki",
                    "resource_id": page.get("id"),
                    "content": content,
                    "indexed_at": datetime.utcnow().isoformat()
                }).execute()
        except Exception as e:
            print(f"Error indexing wiki pages: {e}")

if __name__ == "__main__":
    IndexingWorker.index_documents()
