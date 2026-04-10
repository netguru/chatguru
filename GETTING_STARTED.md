# Getting Started with chatguru Agent

This guide will walk you through setting up chatguru Agent from scratch, step by step.

> Note: The React/Vite frontend lives in the `frontend/` directory. Run `make frontend-dev` to start it at http://localhost:5173.

## 📋 Prerequisites

Before you begin, ensure you have the following installed on your system:

### Required Software

1. **Python 3.12 or higher**
   - Check version: `python --version` or `python3 --version`
   - Download: [python.org](https://www.python.org/downloads/)
   - **Note**: Python 3.11+ is required, but 3.12+ is recommended

2. **uv (Python Package Manager)**
   - Installation: [uv installation guide](https://github.com/astral-sh/uv#installation)
   - Quick install:
     ```bash
     curl -LsSf https://astral.sh/uv/install.sh | sh
     ```
   - Verify: `uv --version`

4. **Node.js 20+** (required by React 19)
   - Check version: `node --version`
   - Download: [nodejs.org](https://nodejs.org/)

5. **Git**
   - Check version: `git --version`
   - Download: [git-scm.com](https://git-scm.com/downloads)

### Optional Software

- **Docker and Docker Compose** (for containerized deployment)
  - Download: [docker.com](https://www.docker.com/get-started)

### Required Accounts

1. **Azure OpenAI Account**
   - Sign up: [Azure OpenAI Service](https://azure.microsoft.com/en-us/products/cognitive-services/openai-service)
   - You'll need:
     - An Azure subscription
     - Access to Azure OpenAI service
     - API endpoint URL
     - API key
     - Deployment name (e.g., `gpt-4o-mini`)

2. **Langfuse Account** (for observability)
   - Sign up: [langfuse.com](https://langfuse.com/)
   - You'll need:
     - Public key
     - Secret key
     - Host URL (usually `https://cloud.langfuse.com`)

## 🚀 Step-by-Step Setup

### Step 1: Clone the Repository

```bash
# Clone the repository
git clone <repository-url>
cd chatguru-agent

# Verify you're in the correct directory
ls -la
```

You should see files like `Makefile`, `pyproject.toml`, `README.md`, etc.

### Step 2: Install Dependencies

Run the setup command to install all dependencies:

```bash
make setup
```

This command will:
- Install Python dependencies using `uv`
- Install and configure pre-commit hooks
- Set up the development environment

**Expected output:**
```
📦 Installing production dependencies...
🔧 Installing pre-commit hooks...
🎉 Development setup completed!
```

**Troubleshooting:**
- If `uv` is not found: Install uv (see Prerequisites)
- If Python version is wrong: Ensure Python 3.12+ is installed and in PATH
- If pre-commit fails: Run `uv sync --extra dev` manually

### Step 3: Configure Environment Variables

1. **Copy the environment template:**
   ```bash
   make env-setup
   ```

2. **Edit the `.env` file** with your credentials:
   ```bash
   # On macOS/Linux
   nano .env
   # or
   vim .env

   # On Windows
   notepad .env
   ```

3. **Fill in required variables:**

   ```bash
   # Azure OpenAI Configuration (REQUIRED)
   LLM_ENDPOINT=https://your-resource.openai.azure.com/
   LLM_API_KEY=your-api-key-here
   LLM_DEPLOYMENT_NAME=gpt-4o-mini
   LLM_API_VERSION=2024-02-15-preview

   # Langfuse Configuration (REQUIRED)
   LANGFUSE_PUBLIC_KEY=pk-lf-...
   LANGFUSE_SECRET_KEY=sk-lf-...
   LANGFUSE_HOST=https://cloud.langfuse.com
   ```

   **Important Notes:**
   - `LLM_ENDPOINT` must end with a trailing slash `/`
   - `LLM_DEPLOYMENT_NAME` must match your Azure deployment exactly
   - Keep your `.env` file secure - never commit it to git

### Step 4: Verify Configuration

Test that your configuration is correct:

```bash
# Check that environment variables are loaded
python -c "from src.config import settings; print('Config loaded successfully')"
```

If you see an error, check your `.env` file for typos or missing variables.

### Step 5: Run Tests

Verify everything is working:

```bash
make test
```

**Expected output:**
```
🧪 Running tests...
======================== test session starts ========================
...
======================== passed in X.XXs ============================
```

If tests fail, check:
- All dependencies are installed (`make install`)
- Environment variables are set correctly
- Python version is 3.12+

### Step 6: Start the Development Servers

Start the backend:

```bash
make dev
```

Start the frontend in a separate terminal:

```bash
make frontend-dev
```

**Expected output:**
```
🚀 Starting backend development server with auto-reload...
📡 WebSocket streaming enabled at ws://localhost:8000/ws
🌐 API docs available at http://localhost:8000/docs
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### Step 7: Access the Application

Open your browser and navigate to:

- **Frontend**: http://localhost:5173
- **Minimal test UI**: http://localhost:8000/ (smoke testing only)
- **Backend API Docs**: http://localhost:8000/docs
- **Backend Health Check**: http://localhost:8000/health

You should see the chat interface! Try sending a message to test the connection.

## ✅ Verification Checklist

- [ ] Python 3.12+ installed and verified
- [ ] Node.js 20+ installed and verified
- [ ] uv installed and verified
- [ ] Repository cloned successfully
- [ ] Dependencies installed (`make setup`)
- [ ] Environment variables configured (`.env` file)
- [ ] Tests passing (`make test`)
- [ ] Backend server running (`make dev`)
- [ ] Frontend server running (`make frontend-dev`)
- [ ] Can access frontend at http://localhost:5173
- [ ] Can access API docs at http://localhost:8000/docs
- [ ] Chat interface loads and responds

## 🐛 Common Issues and Solutions

### Issue 1: "uv: command not found"

**Solution:**
```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Reload your shell
source ~/.bashrc  # or ~/.zshrc
```

### Issue 2: "Python version 3.X is not supported"

**Solution:**
- Install Python 3.12+ from [python.org](https://www.python.org/downloads/)
- Ensure it's in your PATH
- Verify: `python3 --version`

### Issue 3: "Module not found" errors

**Solution:**
```bash
# Reinstall dependencies
make install

# Or manually
uv sync
```

### Issue 4: Azure OpenAI authentication errors

**Symptoms:**
- `401 Unauthorized` errors
- `Invalid API key` messages

**Solution:**
- Verify `LLM_ENDPOINT` ends with `/`
- Check `LLM_API_KEY` is correct (no extra spaces)
- Ensure `LLM_DEPLOYMENT_NAME` matches Azure deployment
- Verify `LLM_API_VERSION` is supported (e.g., `2024-02-15-preview`)

### Issue 5: Langfuse connection errors

**Symptoms:**
- `Connection refused` errors
- `Invalid credentials` messages

**Solution:**
- Verify `LANGFUSE_PUBLIC_KEY` starts with `pk-lf-`
- Verify `LANGFUSE_SECRET_KEY` starts with `sk-lf-`
- Check `LANGFUSE_HOST` is correct (usually `https://cloud.langfuse.com`)
- Ensure network connectivity

### Issue 6: Port already in use

- `Address already in use` errors on port 8000

**Solution:**

```bash
# Find process using port 8000
lsof -i :8000  # macOS/Linux
netstat -ano | findstr :8000  # Windows

# Kill the process or change port in .env
FASTAPI_PORT=8001 make dev
```
- Check browser console for errors
- Verify CORS settings in `.env`

### Issue 8: Pre-commit hooks fail

**Symptoms:**
- Git commit fails with pre-commit errors

**Solution:**
```bash
# Reinstall hooks
make pre-commit-install

# Run checks manually
make pre-commit

# Fix issues, then commit again
```

### Issue 9: Docker build fails

**Symptoms:**
- `uv.lock` not found
- Build errors

**Solution:**
```bash
# Generate lock file first
uv sync

# Then build
make docker-build
```

## 🎓 Next Steps

Now that you're set up, here are some things to try:

1. **Explore the API:**
   - Visit http://localhost:8000/docs
   - Try the interactive API documentation
   - Test the WebSocket endpoint

2. **Read the Documentation:**
   - [Architecture Guide](docs/architecture.md)
   - [Contributing Guide](CONTRIBUTING.md)
   - [README](README.md)

3. **Run Tests:**
   ```bash
   make test
   make coverage
   ```

4. **Try LLM Evaluation:**
   ```bash
   make promptfoo-eval
   make promptfoo-view
   ```

5. **Explore the Code:**
   - Start with `src/api/main.py` (FastAPI app)
   - Check `src/agent/service.py` (Agent implementation)
   - Look at `src/api/routes/chat.py` (WebSocket endpoint)

## 📚 Additional Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [LangChain Documentation](https://python.langchain.com/)
- [uv Documentation](https://github.com/astral-sh/uv)
- [Azure OpenAI Documentation](https://learn.microsoft.com/en-us/azure/ai-services/openai/)

## 💬 Getting Help

If you're stuck:

1. **Check the Troubleshooting section** above
2. **Review the documentation** in `docs/`
3. **Search existing issues** on GitHub
4. **Open a new issue** with details about your problem

## 🎉 Congratulations!

You've successfully set up chatguru Agent! You're now ready to:

- Develop new features
- Fix bugs
- Improve documentation
- Contribute to the project

Happy coding! 🚀
