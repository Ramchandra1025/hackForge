# HackForge Workspace

A production-grade collaborative developer platform built with Python Flask, Supabase, and vanilla JavaScript.

## Features

### Core Capabilities
- **Live Collaborative Code Editor** - VS Code Live Share style real-time collaboration
- **Integrated Terminal** - xterm.js based terminal with isolated execution
- **Browser Sandbox** - Execute HTML/CSS/JS directly in browser
- **Backend Runner** - Isolated Python/JS/C++/Java execution environment
- **Team Workspace** - Private team workspaces with strict tenant isolation
- **File Management** - Complete file manager with versioning and cloud storage

### Collaboration Features
- **Real-time Chat** - Team chat with threads and reactions
- **Presence Tracking** - See who's online and live cursors
- **Screen Share** - Share your screen with team members
- **Meetings** - Integrated video calls using Jitsi Meet
- **Whiteboard** - Real-time collaborative whiteboard
- **Activity Feed** - Track all team activities and changes

### Project Management
- **Kanban Board** - Drag-and-drop task board
- **Sprint Planning** - AI-powered sprint optimization
- **Task Comments** - Threaded discussions on tasks
- **Deployments** - One-click deployments to Netlify/Railway/GitHub Pages
- **Wiki/Docs** - Team documentation and knowledge base

### AI Features
- **AI Copilot** - Context-aware coding assistant
- **Code Review** - Automated code review by AI
- **Bug Finder** - AI-powered bug detection
- **Task Planner** - AI sprint planning
- **README Generator** - Auto-generate project documentation
- **PPT Generator** - Create presentation outlines

### Admin & Analytics
- **RBAC** - Full role-based access control
- **Audit Logs** - Complete audit trail of all actions
- **Analytics** - Team activity and productivity metrics
- **Search** - Full-text search across all resources
- **API Keys** - Manage integration API keys
- **Settings** - Granular team and user settings

## Tech Stack

### Backend
- **Python 3.9+** with Flask
- **Supabase PostgreSQL** for database
- **Supabase Storage** for file storage
- **Redis** for caching and real-time features
- **Socket.IO** for real-time communication
- **Google Gemini API** for AI features
- **JWT** for authentication
- **bcrypt** for password hashing

### Frontend
- **Pure HTML/CSS/JavaScript** - No frameworks
- **Monaco Editor** for code editing
- **xterm.js** for terminal
- **Socket.IO Client** for real-time updates
- **Responsive Design** - Mobile and desktop
- **Dark Cyberpunk Theme** - Premium UI/UX

### Deployment
- **Docker** - Containerized deployment
- **Gunicorn** - Production WSGI server
- **Nginx** - Reverse proxy
- **Redis** - Session and cache storage

## Installation

### Prerequisites
- Python 3.9+
- Node.js 16+ (for frontend tools)
- PostgreSQL (via Supabase)
- Redis (optional, for caching)

### Setup

1. **Clone the repository**
```bash
git clone https://github.com/yourusername/hackforge-workspace.git
cd hackforge-workspace
```

2. **Create virtual environment**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Configure environment**
```bash
cp .env.example .env
# Edit .env with your configuration
```

5. **Setup database**
```bash
# Run SQL migrations from sql/ directory
# Import schema.sql, storage_policies.sql, rls_policies.sql into Supabase
```

6. **Run development server**
```bash
python app.py
```

Server will run on `http://localhost:5000`

## Project Structure

```
hackforge-workspace/
├── app.py                 # Flask application entry point
├── requirements.txt       # Python dependencies
├── .env.example          # Environment variables template
├── config/               # Configuration files
│   ├── development.py
│   ├── production.py
│   └── testing.py
├── backend/              # Backend application
│   ├── routes/          # API routes
│   ├── services/        # Business logic
│   ├── models/          # Data models
│   ├── middleware/      # Flask middleware
│   ├── sockets/         # Socket.IO handlers
│   ├── workers/         # Background workers
│   └── utils/           # Helper functions
├── templates/           # HTML templates
├── static/              # Frontend assets
│   ├── css/            # Stylesheets
│   ├── js/             # JavaScript
│   ├── assets/         # Images, fonts, etc
│   └── vendors/        # Third-party libraries
├── sql/                # Database SQL
│   ├── schema.sql
│   ├── storage_policies.sql
│   └── rls_policies.sql
├── docker/             # Docker configuration
│   ├── Dockerfile
│   ├── docker-compose.yml
│   └── nginx.conf
└── tests/              # Test files
```

## API Documentation

### Authentication Endpoints
- `POST /api/auth/signup` - Create account with OTP
- `POST /api/auth/verify-otp` - Verify OTP code
- `POST /api/auth/login` - Login with email/username
- `POST /api/auth/logout` - Logout user
- `POST /api/auth/forgot-password` - Reset password via OTP

### Team Endpoints
- `GET /api/teams` - Get user's teams
- `POST /api/teams` - Create new team
- `GET /api/teams/<id>` - Get team details
- `POST /api/teams/<id>/members` - Add team member
- `DELETE /api/teams/<id>/members/<user_id>` - Remove member

### Project Endpoints
- `GET /api/projects` - List projects
- `POST /api/projects` - Create project
- `GET /api/projects/<id>` - Get project details
- `PATCH /api/projects/<id>` - Update project
- `DELETE /api/projects/<id>` - Archive project

### Task Endpoints
- `GET /api/tasks` - List tasks
- `POST /api/tasks` - Create task
- `PATCH /api/tasks/<id>` - Update task
- `POST /api/tasks/<id>/comments` - Add comment
- `GET /api/tasks/<id>/comments` - Get comments

### File Endpoints
- `POST /api/files/upload` - Upload file
- `GET /api/files/<id>` - Get file
- `DELETE /api/files/<id>` - Delete file
- `GET /api/files/<id>/versions` - File versions

### AI Endpoints
- `POST /api/ai/review` - Code review
- `POST /api/ai/generate-readme` - Generate README
- `POST /api/ai/find-bugs` - Bug detection
- `POST /api/ai/plan-sprint` - Sprint planning
- `GET /api/ai/memory` - Get AI memory

## Socket.IO Events

### Real-time Collaboration
- `editor:change` - Code editor changes
- `cursor:move` - Live cursor positions
- `selection:change` - Selection changes

### Presence
- `presence:online` - User came online
- `presence:offline` - User went offline
- `presence:idle` - User idle status

### Chat
- `chat:message` - New chat message
- `chat:typing` - User typing indicator
- `chat:reaction` - Message reaction

### Notifications
- `notification:new` - New notification
- `notification:read` - Notification marked read

### Whiteboard
- `whiteboard:draw` - Drawing event
- `whiteboard:clear` - Clear whiteboard
- `whiteboard:sync` - Sync state

## Environment Variables

See `.env.example` for all required environment variables:

- `SUPABASE_URL` - Supabase project URL
- `SUPABASE_KEY` - Supabase anon key
- `GEMINI_API_KEY` - Google Gemini API key
- `JWT_SECRET` - JWT signing secret
- `REDIS_URL` - Redis connection string
- `EMAILJS_*` - EmailJS credentials

## Database

The application uses Supabase PostgreSQL with the following key tables:

- `users` - User accounts and profiles
- `teams` - Team workspaces
- `projects` - Projects within teams
- `tasks` - Task management
- `files` - File metadata
- `chat_rooms` - Chat conversations
- `meetings` - Meeting records
- `deployments` - Deployment tracking
- `ai_memory` - AI context memory
- `audit_logs` - Activity audit trail

## Authentication

The application uses:
- **Custom JWT** for API authentication
- **HttpOnly cookies** for secure token storage
- **OTP** for email verification
- **bcrypt** for password hashing
- **Token rotation** for security

## Deployment

### Docker Deployment

```bash
# Build image
docker build -f docker/Dockerfile -t hackforge:latest .

# Run container
docker run -p 5000:8000 -e FLASK_ENV=production hackforge:latest
```

### Docker Compose

```bash
docker-compose -f docker/docker-compose.yml up -d
```

### Production Checklist
- [ ] Set `FLASK_ENV=production`
- [ ] Generate strong `SECRET_KEY`
- [ ] Configure `SUPABASE_URL` and `SUPABASE_KEY`
- [ ] Set up Redis for caching
- [ ] Configure email service
- [ ] Enable HTTPS
- [ ] Set up monitoring
- [ ] Configure backups
- [ ] Set rate limits

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Write/update tests
5. Submit a pull request

## License

MIT License - see LICENSE file for details

## Support

For support, email support@hackforge.dev or open an issue on GitHub.

## Roadmap

- [ ] Mobile app (React Native)
- [ ] Advanced analytics dashboard
- [ ] Custom AI model training
- [ ] Advanced security features
- [ ] Enterprise SSO
- [ ] Advanced reporting
- [ ] Webhook system
- [ ] Plugin marketplace
