# RIMOS - Setup & Installation Guide

> Complete setup instructions for developers working on RIMOS

---

## Table of Contents

- [System Requirements](#system-requirements)
- [Backend Setup (Python/FastAPI)](#backend-setup)
- [Frontend Setup (Next.js)](#frontend-setup)
- [Running the Application](#running-the-application)
- [Database & Data Setup](#database--data-setup)
- [Testing Setup](#testing-setup)
- [IDE Configuration](#ide-configuration)
- [Troubleshooting](#troubleshooting)

---

## System Requirements

### Hardware

- **CPU:** Intel Core i5 or equivalent (4+ cores for RIM-OS processing)
- **RAM:** 8 GB minimum (16 GB recommended)
- **Disk:** 30 GB free (backend: 5 GB, frontend: 1 GB, node_modules: 1 GB, test files: 20+ GB)
- **Network:** Stable internet connection (for Solana devnet, IPFS)

### Software

#### Windows

- Windows 10 or 11 (or WSL2 with Ubuntu)
- Python 3.9 or 3.11
- Node.js 18+ (comes with npm)
- Git

#### macOS

- macOS 11 or newer
- Python 3.9 or 3.11 (via Homebrew: `brew install python3`)
- Node.js 18+ (via Homebrew: `brew install node`)
- Git

#### Linux (Ubuntu/Debian)

- Ubuntu 20.04 or newer
- Python 3.9 or 3.11: `sudo apt-get install python3 python3-pip python3-venv`
- Node.js 18+: `sudo apt-get install nodejs npm`
- Git: `sudo apt-get install git`

---

## Backend Setup

### Step 1: Clone Repository

```bash
cd d:\wamp64\www\pass97
# or your preferred location
git clone <repository_url> .
```

### Step 2: Install Python

**Check Python version:**

```bash
python --version  # or python3 on macOS/Linux
```

**Required:** Python 3.9 or 3.11

If not installed:

- Windows: Download from https://www.python.org/downloads/
- macOS: `brew install python3@3.11`
- Linux: `sudo apt-get install python3.11 python3.11-venv`

### Step 3: Create Virtual Environment

```bash
cd backend

# Windows
python -m venv venv
venv\Scripts\activate

# macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

**Verify activation:**

```bash
which python  # Should show venv path
```

### Step 4: Install Dependencies

```bash
pip install --upgrade pip setuptools wheel

pip install -r requirements.txt
```

**What gets installed:**

| Package            | Purpose                |
| ------------------ | ---------------------- |
| `fastapi`          | Web framework          |
| `uvicorn`          | ASGI server            |
| `pydantic`         | Data validation        |
| `python-multipart` | File upload handling   |
| `aiofiles`         | Async file operations  |
| `fpdf2`            | PDF generation         |
| `slowapi`          | Rate limiting          |
| `python-nacl`      | Signature verification |
| `solders`          | Solana SDK             |
| `pytest`           | Testing framework      |

**Installation time:** ~2-5 minutes

### Step 5: Create Data Directories

```bash
# In backend folder
mkdir -p data/uploads data/temp_uploads data/report_cache logs
```

**Directories created:**

- `data/uploads/` - Persistent uploaded files
- `data/temp_uploads/` - Temporary chunk storage
- `data/report_cache/` - Generated reports cache
- `logs/` - Application logs

### Step 6: Configure Environment (Optional)

Create `backend/.env` file:

```env
# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
DEBUG=True

# File Upload
MAX_FILE_SIZE=10737418240
CHUNK_SIZE=20971520
UPLOAD_DIR=data/uploads
TEMP_DIR=data/temp_uploads

# Reports
REPORT_CACHE_DIR=data/report_cache
REPORT_CACHE_TTL=86400

# Logging
LOG_LEVEL=INFO
LOG_FILE=logs/app.log

# Security
RATE_LIMIT_ENABLED=True
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_PERIOD=60

# Solana (for NFT minting)
SOLANA_RPC_URL=https://api.devnet.solana.com
SOLANA_NETWORK=devnet
```

### Step 7: Test Backend Installation

```bash
cd backend

# Quick test
python -c "import fastapi; print(f'FastAPI {fastapi.__version__} installed')"
python -c "import pydantic; print(f'Pydantic {pydantic.__version__} installed')"
python -c "import rim_os_v2; print('RIM-OS available')"
```

**Expected output:**

```
FastAPI 0.100.0 installed
Pydantic v2.4.2 installed
RIM-OS available
```

---

## Frontend Setup

### Step 1: Install Node.js

**Check version:**

```bash
node --version  # Should be 18.0.0 or higher
npm --version   # Should be 9.0.0 or higher
```

**Installation:**

- Windows: Download from https://nodejs.org/ (LTS version)
- macOS: `brew install node`
- Linux: `sudo apt-get install nodejs npm`

### Step 2: Navigate to Frontend Directory

```bash
cd web
```

### Step 3: Install Node Dependencies

```bash
npm install
```

**What gets installed:**

| Package               | Purpose           |
| --------------------- | ----------------- |
| `next`                | React framework   |
| `react` / `react-dom` | React library     |
| `typescript`          | Type checking     |
| `tailwindcss`         | CSS framework     |
| `@solana/web3.js`     | Solana blockchain |
| `framer-motion`       | Animations        |
| `lucide-react`        | Icons             |
| `axios`               | HTTP client       |

**Installation time:** ~3-10 minutes (depends on internet)

### Step 4: Create Environment Configuration

Create `web/.env.local` file:

```env
# API Configuration
NEXT_PUBLIC_API_URL=http://localhost:8000

# Solana Configuration
NEXT_PUBLIC_SOLANA_NETWORK=devnet
NEXT_PUBLIC_SOLANA_RPC_URL=https://api.devnet.solana.com

# Application
NEXT_PUBLIC_APP_NAME=RIMOS
NEXT_PUBLIC_APP_VERSION=1.0.0

# Debug (optional)
NEXT_DEBUG_MODE=false
```

### Step 5: Build TypeScript Types

```bash
npm run type-check
```

**Expected output:**

```
✓ Compiled successfully
✓ No type errors
```

### Step 6: Test Frontend Installation

```bash
# Linting
npm run lint

# Type checking
npm run type-check

# Build
npm run build
```

All should complete successfully.

---

## Running the Application

### Start Backend

**Terminal 1 - Backend:**

```bash
cd backend

# Activate virtual environment (if not already)
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate

# Start server
uvicorn app.main:app --reload --port 8000
```

**Expected output:**

```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete
Press CTRL+C to quit
```

**API Documentation available at:**

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### Start Frontend

**Terminal 2 - Frontend:**

```bash
cd web

# Start development server
npm run dev
```

**Expected output:**

```
▲ Next.js 16.0.0
- Local:        http://localhost:3000
- Environments: .env.local
```

### Access Application

**Open browser:**

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

**You should see:**

1. Landing page with file upload interface
2. Penrose background animation
3. Drag-and-drop file upload zone

### Test Upload

1. Click on file upload area
2. Select any file (or use test file from `examples/`)
3. Upload should complete and show:
    - Integrity Score (0-100)
    - Risk Level badge
    - Anomalies found
    - Blockchain information

---

## Database & Data Setup

### Artifact Chain (Blockchain Ledger)

**Location:** `backend/data/artifact_chain.json`

**Initialize (if doesn't exist):**

```json
{
    "blocks": [],
    "genesis_mints": {
        "fine_structure_constant": 137.0359991,
        "boltzmann_entropy": 1.380649e-23,
        "einstein_tensors": [1.0, 0.5, 0.333]
    }
}
```

**Auto-created:** First upload will create this file.

### Report Cache

**Location:** `backend/data/report_cache/`

**Files stored:**

- `{upload_id}.json` - Report data cache

**Auto-managed:** Old reports deleted after 24 hours.

### Temporary Upload Files

**Location:** `backend/data/temp_uploads/`

**Files stored:**

- `{upload_id}_chunk_{index}.tmp` - Individual chunks

**Auto-cleaned:** Deleted when upload completes or expires.

---

## Testing Setup

### Backend Tests

#### Run All Tests

```bash
cd backend
pytest
```

**Output:**

```
tests/ ... passed in 45.23 seconds
```

#### Run Specific Test

```bash
pytest tests/test_upload.py -v
pytest tests/test_pipeline.py::test_single_file_audit
```

#### Run with Coverage

```bash
pip install pytest-cov
pytest --cov=app --cov-report=html tests/
```

**Coverage report:** `htmlcov/index.html`

#### Run Specific Test Category

```bash
pytest -k "upload" -v          # All upload-related tests
pytest -k "chunked" -v         # Chunked upload tests
pytest -k "signature" -v       # Signature verification tests
```

### Frontend Tests (Optional)

```bash
cd web

# Linting
npm run lint

# Type checking
npm run type-check

# Build (production build test)
npm run build
```

### Integration Testing

**Test the full flow manually:**

1. Open http://localhost:3000
2. Upload test file from `examples/`
3. Wait for processing (5-15 seconds)
4. Verify KPIs display correctly
5. Download PDF report
6. View SVG visualization
7. Optional: Test NFT minting (requires Phantom wallet)

---

## IDE Configuration

### Visual Studio Code

**Recommended Extensions:**

```json
{
    "extensions": [
        "ms-python.python", // Python support
        "ms-python.vscode-pylance", // Python language server
        "charliermarsh.ruff", // Python linter
        "ms-vscode.makefile-tools", // Make support
        "dbaeumer.vscode-eslint", // JavaScript linting
        "esbenp.prettier-vscode", // Code formatter
        "bradlc.vscode-tailwindcss", // Tailwind CSS
        "ms-vscode.remote-explorer" // Remote debugging
    ]
}
```

**Install extensions:**

1. Open VS Code Extensions (Ctrl+Shift+X)
2. Search and install each extension above

**Workspace Settings** (`pass97/.vscode/settings.json`):

```json
{
    "[python]": {
        "editor.formatOnSave": true,
        "editor.defaultFormatter": "ms-python.python",
        "editor.codeActionsOnSave": {
            "source.organizeImports": "explicit"
        }
    },
    "[typescript]": {
        "editor.formatOnSave": true,
        "editor.defaultFormatter": "esbenp.prettier-vscode"
    },
    "[json]": {
        "editor.formatOnSave": true,
        "editor.defaultFormatter": "esbenp.prettier-vscode"
    },
    "python.linting.enabled": true,
    "python.linting.pylintEnabled": false,
    "python.linting.flake8Enabled": false,
    "python.linting.mypyEnabled": false,
    "files.exclude": {
        "**/__pycache__": true,
        "**/*.pyc": true,
        "**/node_modules": true
    }
}
```

**Python Path Settings:**

1. Press `Ctrl+Shift+P`
2. Search "Python: Select Interpreter"
3. Choose `backend/venv/bin/python` (or `venv\Scripts\python.exe` on Windows)

**First-Time Setup in VS Code:**

1. Open folder: `File → Open Folder → pass97`
2. Install recommended extensions
3. Select Python interpreter
4. Open integrated terminal (Ctrl+`)
5. Run `cd backend && venv\Scripts\activate` (or `source venv/bin/activate`)
6. Run `cd web && npm install`

### PyCharm

**Setup:**

1. Open Project: `File → Open → pass97`
2. Configure Python interpreter:
    - `File → Settings → Project → Python Interpreter`
    - Click ⚙️ → Add
    - Select `Existing Environment`
    - Browse to `backend/venv/bin/python` (or Windows equivalent)
3. Mark folders:
    - Right-click `backend` → Mark Directory as → Sources Root
    - Right-click `web/src` → Mark Directory as → Resource Root

### WebStorm (for Frontend)

**Setup:**

1. Open Project: `File → Open → pass97/web`
2. Configure Node.js: `File → Settings → Languages & Frameworks → Node.js`
3. Set Node interpreter to your system Node.js

---

## Troubleshooting

### Python/Backend Issues

#### Issue: "Python not found" or "python is not recognized"

**Solution:**

```bash
# Windows - verify Python is in PATH
py --version

# macOS/Linux
python3 --version

# Add to PATH if needed and run with full path
C:\Python311\python.exe --version
```

#### Issue: Virtual environment not activating

**Solution:**

```bash
# Windows - try full path
cd backend
D:\wamp64\www\pass97\backend\venv\Scripts\activate

# macOS/Linux
source /path/to/venv/bin/activate

# Verify
which python  # Should show venv path
```

#### Issue: "ModuleNotFoundError: No module named 'fastapi'"

**Solution:**

```bash
# Ensure virtual environment is activated
which python  # Should show venv

# Reinstall dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

#### Issue: Port 8000 already in use

**Solution:**

```bash
# Change port
uvicorn app.main:app --reload --port 8001

# Or kill process using port
# Windows
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# macOS/Linux
lsof -ti:8000 | xargs kill -9
```

#### Issue: Slow RIM-OS audit (taking > 1 minute)

**Solution:**

- Normal for files > 100 MB
- Close other applications to free CPU
- Check disk I/O: `iostat` (macOS/Linux) or Task Manager (Windows)

### Node.js/Frontend Issues

#### Issue: "npm not found"

**Solution:**

```bash
# Verify Node.js installation
node --version
npm --version

# If not found, reinstall from https://nodejs.org/
# macOS
brew install node

# Linux
sudo apt-get install nodejs npm
```

#### Issue: Port 3000 already in use

**Solution:**

```bash
cd web
npm run dev -- -p 3001  # Use different port

# Or kill process
# Windows
netstat -ano | findstr :3000
taskkill /PID <PID> /F

# macOS/Linux
lsof -ti:3000 | xargs kill -9
```

#### Issue: "npm install" hangs or times out

**Solution:**

```bash
# Clear npm cache
npm cache clean --force

# Install with more verbose output
npm install --verbose

# Try with different registry
npm install --registry https://registry.npmjs.org/
```

#### Issue: Tailwind CSS not compiling

**Solution:**

```bash
cd web

# Rebuild Tailwind
npm run build:css

# Or reinstall dependencies
rm -rf node_modules package-lock.json
npm install
```

### General Issues

#### Issue: CORS errors in browser console

**Solution:**
The backend likely didn't start. Verify:

```bash
# Check backend is running
curl http://localhost:8000/docs

# Should load API documentation
```

If not:

1. Terminal 1: `cd backend && source venv/bin/activate && uvicorn app.main:app --reload`
2. Terminal 2: `cd web && npm run dev`

#### Issue: File upload stuck on "Processing"

**Solution:**

1. Wait 10-30 seconds (RIM-OS is CPU-intensive)
2. Check backend logs: `tail -f backend/logs/app.log`
3. Verify disk space: `df -h` (macOS/Linux) or `dir C:\` (Windows)
4. If still stuck, restart both servers

#### Issue: Can't connect to Solana wallet for NFT minting

**Solution:**

1. Verify Phantom wallet installed (Chrome/Firefox)
2. Switch wallet to **Solana Devnet** (not Mainnet)
3. Request devnet SOL from: https://faucet.solana.com/
4. Refresh browser page
5. Try connecting again

---

## Development Workflow

### Day-to-Day Development

**Terminal 1 - Backend:**

```bash
cd backend
source venv/bin/activate  # or Windows: venv\Scripts\activate
uvicorn app.main:app --reload --port 8000
```

**Terminal 2 - Frontend:**

```bash
cd web
npm run dev
```

**Terminal 3 - Tests (optional):**

```bash
cd backend
pytest --watch  # requires pip install pytest-watch
```

### Common Development Commands

**Backend:**

```bash
# Format code
black app tests

# Lint
flake8 app tests

# Type check
mypy app

# Run tests
pytest
pytest -v tests/test_upload.py
```

**Frontend:**

```bash
# Format
npm run format

# Lint
npm run lint

# Type check
npm run type-check

# Build
npm run build
```

### Before Committing

**Checklist:**

```bash
cd backend
pytest
black app tests
flake8 app tests
mypy app

cd ../web
npm run lint
npm run type-check
npm run build
```

All should pass before committing.

---

## Performance Optimization

### Backend Optimization

1. **Enable Production Mode:**

    ```bash
    uvicorn app.main:app --workers 4 --port 8000
    ```

2. **Monitor Performance:**

    ```bash
    # Watch resource usage
    top -p $(pgrep -f uvicorn)  # macOS/Linux
    # or use Task Manager (Windows)
    ```

3. **View Logs:**
    ```bash
    tail -f backend/logs/app.log
    grep ERROR backend/logs/app.log
    ```

### Frontend Optimization

1. **Build Production Bundle:**

    ```bash
    cd web
    npm run build
    npm run start
    ```

2. **Analyze Bundle:**
    ```bash
    npm install -g @next/bundle-analyzer
    npm run analyze  # if configured in next.config.ts
    ```

---

## Docker Setup (Optional)

If you want to run in containers:

**Backend Dockerfile** (`backend/Dockerfile`):

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Frontend Dockerfile** (`web/Dockerfile`):

```dockerfile
FROM node:18-alpine

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .
RUN npm run build

EXPOSE 3000
CMD ["npm", "start"]
```

**docker-compose.yml:**

```yaml
version: '3.8'

services:
    backend:
        build: ./backend
        ports:
            - '8000:8000'
        volumes:
            - ./backend/data:/app/data

    frontend:
        build: ./web
        ports:
            - '3000:3000'
        environment:
            - NEXT_PUBLIC_API_URL=http://backend:8000
```

**Run with Docker:**

```bash
docker-compose up
```

---

## Next Steps

After setup is complete:

1. **Read Documentation:**
    - [COMPREHENSIVE_DEVELOPER_GUIDE.md](./COMPREHENSIVE_DEVELOPER_GUIDE.md) - Architecture & detailed pipeline
    - [QUICK_REFERENCE.md](./QUICK_REFERENCE.md) - Quick lookup guide
    - [API_INTEGRATION_GUIDE.md](./API_INTEGRATION_GUIDE.md) - API reference

2. **Run Tests:**

    ```bash
    cd backend
    pytest
    ```

3. **Try Upload:**
    - Visit http://localhost:3000
    - Upload a test file
    - View audit results

4. **Explore Code:**
    - Start with [app/main.py](../backend/app/main.py)
    - Then [rim_os_v2.py](../backend/rim_os_v2.py)
    - Then [web/src/components](../web/src/components)

5. **Make Changes:**
    - Pick a small improvement from the issue tracker
    - Create a branch: `git checkout -b feature/your-feature`
    - Make changes with tests
    - Create pull request

---

**Last Updated:** March 18, 2026
**Version:** 1.0
**Audience:** New developers setting up RIMOS
