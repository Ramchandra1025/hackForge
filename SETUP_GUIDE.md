# HackForge Workspace - Setup Guide

## ✅ Completed Files

### Backend Models
- `backend/models/user_model.py` - User data operations
- `backend/models/team_model.py` - Team management
- `backend/models/project_model.py` - Project operations
- `backend/models/task_model.py` - Task management
- `backend/models/file_model.py` - File operations
- `backend/models/deployment_model.py` - Deployment tracking
- `backend/models/ai_model.py` - AI memory and actions
- `backend/models/notification_model.py` - Notification handling
- `backend/models/meeting_model.py` - Meeting management
- `backend/models/wiki_model.py` - Wiki/documentation
- `backend/models/audit_model.py` - Audit logging

### Backend Workers
- `backend/workers/ai_worker.py` - AI task processing
- `backend/workers/upload_worker.py` - File upload processing
- `backend/workers/cleanup_worker.py` - Database cleanup
- `backend/workers/indexing_worker.py` - Search indexing
- `backend/workers/notification_worker.py` - Notification sending

### Configuration
- `config/development.py` - Development settings
- `config/production.py` - Production settings
- `config/testing.py` - Testing settings

### Docker & Deployment
- `docker/Dockerfile` - Container image
- `docker/docker-compose.yml` - Docker Compose setup
- `docker/nginx.conf` - Nginx configuration

### Frontend JavaScript
- `static/js/api.js` - API client with all endpoints
- `static/js/socket.js` - Socket.IO client
- `static/js/toast.js` - Toast notification system

#### Utils
- `static/js/modules/utils/helpers.js` - Helper functions
- `static/js/modules/utils/validators.js` - Input validation
- `static/js/modules/utils/constants.js` - App constants
- `static/js/modules/utils/formatter.js` - Data formatting
- `static/js/modules/utils/storage.js` - IndexedDB management

#### UI Components
- `static/js/modules/ui/modal.js` - Modal dialogs
- `static/js/modules/ui/dropdown.js` - Dropdown menus
- `static/js/modules/ui/tooltip.js` - Tooltips
- `static/js/modules/ui/tabs.js` - Tab system
- `static/js/modules/ui/context-menu.js` - Context menus

#### Upload System
- `static/js/modules/uploads/upload-manager.js` - Upload management
- `static/js/modules/uploads/upload-queue.js` - Queue processing

### Frontend CSS
- `static/css/whiteboard.css` - Whiteboard styling

### Root Files
- `requirements.txt` - Python dependencies
- `.env.example` - Environment variables template
- `README.md` - Project documentation

### Backend Utilities
- `backend/utils/db.py` - Database utilities
- `backend/utils/redis_client.py` - Redis integration
- `backend/utils/error_handlers.py` - Error handling
- `backend/routes/file_routes.py` - File management routes
- `backend/routes/analytics_routes.py` - Analytics routes

## 📋 Still Need to Create

### Backend Routes (stubs exist, need implementation)
The following route files need complete implementation:
- `auth_routes.py` - Authentication endpoints
- `user_routes.py` - User profile endpoints
- `team_routes.py` - Team management endpoints
- `project_routes.py` - Project endpoints
- `task_routes.py` - Task endpoints
- `chat_routes.py` - Chat endpoints
- `ai_routes.py` - AI endpoints
- `deployment_routes.py` - Deployment endpoints
- `meeting_routes.py` - Meeting endpoints
- `notification_routes.py` - Notification endpoints
- `wiki_routes.py` - Wiki endpoints
- `search_routes.py` - Search endpoints
- `admin_routes.py` - Admin endpoints

### Backend Sockets (stubs exist, need implementation)
- `sockets/chat_socket.py`
- `sockets/collaboration_socket.py`
- `sockets/presence_socket.py`
- `sockets/whiteboard_socket.py`
- `sockets/notification_socket.py`
- `sockets/terminal_socket.py`

### Backend Middleware
- `middleware/rbac_middleware.py` - Role-based access control
- `middleware/tenant_middleware.py` - Multi-tenancy
- `middleware/security_middleware.py` - Security checks

### Frontend JavaScript (partially complete)
- `static/js/router.js` - Frontend routing
- `static/js/state.js` - Global state management
- `static/js/auth.js` - Authentication logic
- `static/js/editor.js` - Code editor integration
- `static/js/terminal.js` - Terminal integration
- `static/js/chat.js` - Chat functionality
- `static/js/notifications.js` - Notification handling
- `static/js/whiteboard.js` - Whiteboard drawing
- `static/js/kanban.js` - Kanban board
- And many more...

### Frontend CSS
- `static/css/responsive.css` - Mobile responsiveness
- `static/css/theme.css` - Color themes
- `static/css/animations.css` - Animations
- Component CSS files

### Frontend Modules (partial)
- `static/js/modules/monaco/monaco-init.js` - Monaco editor
- `static/js/modules/terminal/xterm-init.js` - xterm initialization
- `static/js/modules/ai/*` - AI modules
- `static/js/modules/realtime/*` - Realtime sync
- And more...

### Frontend Assets
- Icons in `static/assets/icons/`
- Fonts in `static/assets/fonts/`
- Images in `static/assets/images/`
- Vendor libraries in `static/vendors/`

### Templates
- `templates/index.html` - Home page
- `templates/auth.html` - Auth page
- `templates/dashboard.html` - Dashboard
- `templates/workspace.html` - Workspace
- `templates/error.html` - Error page
- `templates/loading.html` - Loading page

### Database
- `sql/schema.sql` - Database schema
- `sql/storage_policies.sql` - Storage policies
- `sql/rls_policies.sql` - Row-level security

## 🚀 Next Steps

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Setup Environment
```bash
cp .env.example .env
# Edit .env with your actual values
```

### Supabase service role key

The app must be able to perform privileged (server-side) operations such as creating teams. Supabase row-level security (RLS) will block these operations when using the anonymous key. Provide the Supabase "service role" key to the server using the `SUPABASE_SERVICE_ROLE_KEY` environment variable.

Add the key in PowerShell (temporary for current session):
```powershell
$Env:SUPABASE_SERVICE_ROLE_KEY = "your-service-role-key-here"
```

To make it persistent for the app, add it to your `.env` or your Docker Compose file under the service environment section:

`.env`:
```
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key-here
```

`docker/docker-compose.yml` (example snippet):
```yaml
services:
    web:
        environment:
            - SUPABASE_URL=${SUPABASE_URL}
            - SUPABASE_SERVICE_ROLE_KEY=${SUPABASE_SERVICE_ROLE_KEY}
```

If you cannot provide a service role key, configure Supabase RLS policies in `sql/rls_policies.sql` to allow the specific server-side inserts your app requires (not recommended for production).


### 3. Setup Supabase
- Create a Supabase project at https://supabase.com
- Run the SQL schemas from `sql/` directory
- Set up storage buckets
- Enable RLS policies

### 4. Implement Routes
Each route file needs:
- Authentication checks
- Data validation
- Database queries
- Error handling
- Audit logging

### 5. Implement Sockets
Socket event handlers need:
- Connection/disconnection logic
- Room management
- Event broadcasting
- State synchronization

### 6. Build Frontend Pages
HTML templates need:
- Semantic HTML structure
- Form elements
- Loading states
- Error displays
- Responsive layout

### 7. Implement Frontend Logic
JavaScript files need:
- Event handlers
- API integration
- State management
- Real-time updates
- UI interactions

### 8. Add CSS Styling
- Complete responsive design
- Dark cyberpunk theme
- Animations
- Component styling
- Mobile support

## 📚 Architecture Overview

```
Frontend (SPA)
    ↓
API Routes (/api/*)
    ↓
Backend Services (Business Logic)
    ↓
Models (Data Layer)
    ↓
Supabase (PostgreSQL + Storage)
    ↑
Redis (Caching)
    ↑
Socket.IO (Real-time)
```

## 🔒 Security Features

- Custom JWT authentication
- Supabase RLS policies for multi-tenancy
- RBAC system with multiple roles
- Rate limiting on API endpoints
- Input validation on all forms
- SQL injection prevention
- CSRF protection
- Secure file upload with validation

## 📊 Key Technologies

- **Backend**: Python Flask + Socket.IO
- **Database**: Supabase PostgreSQL
- **Cache**: Redis
- **Storage**: Supabase Storage
- **Frontend**: Vanilla JS + HTML5 + CSS3
- **Editor**: Monaco Editor
- **Terminal**: xterm.js
- **AI**: Google Gemini API
- **Deployment**: Docker + Nginx

## 🎯 Priority Implementation Order

1. Complete authentication (auth_routes.py)
2. Implement user profiles (user_routes.py)
3. Setup team management (team_routes.py)
4. Add project functionality (project_routes.py)
5. Implement tasks (task_routes.py)
6. Add file uploads (file_routes.py)
7. Real-time chat (chat_routes.py + chat_socket.py)
8. Implement whiteboard (whiteboard_routes.py + whiteboard_socket.py)
9. Add deployments (deployment_routes.py)
10. Integrate AI features (ai_routes.py)

---

**Last Updated**: May 8, 2026
**Version**: 1.0.0-beta
**Status**: Framework Complete, Implementation In Progress
