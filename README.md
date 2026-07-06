# AI Video Note Taker

AI-powered meeting note taker with Google Meet bot, bilingual (Hindi/English) transcription, and admin dashboard.

## Quick Start

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager
- Docker & Docker Compose
- OpenSSL (for JWT key generation)

### 1. Setup Environment

```bash
# Copy environment template
cp .env.example .env
# Edit .env with your values (especially API keys)

# Generate JWT RS256 key pair
make keys

# Install all dependencies
make install
```

### 2. Start Infrastructure

```bash
# Start PostgreSQL, Redis, and MinIO
make infra
```

Services will be available at:
| Service | URL |
|---------|-----|
| PostgreSQL | `localhost:5432` |
| Redis | `localhost:6379` |
| MinIO API | `localhost:9000` |
| MinIO Console | `localhost:9001` |

### 3. Initialize Database

```bash
# Run migrations
make db-upgrade

# Seed with initial org + admin user
make db-seed
```

### 4. Start API Server

```bash
make api
# Alternative for Windows without make:
# cd apps\api
# uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API docs available at: http://localhost:8000/docs

### 5. Start Web Dashboard (Frontend)

```bash
cd apps/web
npm run dev
```

Dashboard available at: http://localhost:3000

### 6. Test Auth Flow

**Default Login Credentials:**
- Email: `admin@company.com`
- Password: `admin123456`

```bash
# Login
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@company.com", "password": "admin123456"}'

# Use the accessToken in subsequent requests
curl http://localhost:8000/health \
  -H "Authorization: Bearer <accessToken>"
```

## Project Structure

```
ai-video-note-taker/
├── apps/
│   ├── api/              # FastAPI backend API
│   ├── web/              # Django admin dashboard (Sprint 9)
│   ├── bot_worker/       # Playwright Meet bot (Sprint 4)
│   ├── transcription_worker/  # faster-whisper STT (Sprint 6)
│   ├── summarization_worker/  # Gemini/Ollama reports (Sprint 7)
│   └── pdf_worker/       # WeasyPrint PDF export (Sprint 9)
├── packages/
│   ├── common/           # Shared utilities (logging)
│   ├── contracts/        # Shared enums & Pydantic schemas
│   └── auth/             # JWT + password hashing
├── db/
│   └── alembic/          # Database migrations
├── docker-compose.yml    # Local dev infrastructure
├── Makefile              # Dev commands
└── pyproject.toml        # uv workspace config
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| API | FastAPI (Python 3.12) |
| Dashboard | Django 5 + HTMX + Tailwind |
| Database | PostgreSQL 16 |
| Cache/Broker | Redis 7 |
| Object Storage | MinIO (S3-compatible) |
| Task Queue | Celery |
| Speech-to-Text | faster-whisper (local) |
| LLM | Gemini API / Ollama (local) |
| PDF | WeasyPrint |
| Bot | Playwright |

## Development Commands

```bash
make help          # Show all available commands
make install       # Install dependencies
make infra         # Start Docker services
make api           # Start FastAPI dev server
make lint          # Run linter
make format        # Format code
make test          # Run tests
make db-migrate    # Generate migration
make db-seed       # Seed database
make clean         # Clean caches
```

## Architecture

The system follows a **service-oriented monorepo** architecture:

- **FastAPI** handles all REST API traffic and WebSocket connections
- **Django** serves the admin dashboard (server-rendered with HTMX)
- **Celery workers** process background jobs (bot, transcription, summarization, PDF)
- **Redis** serves as cache, Celery broker, rate limiter, and pub/sub for WebSocket
- **PostgreSQL** is the primary data store with JSONB for flexible report data
- **MinIO** stores audio chunks and PDF artifacts

All inter-service communication uses API keys for authentication.
