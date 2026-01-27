# Contributing to chatguru Agent

Thank you for your interest in contributing to chatguru Agent! This document provides guidelines and instructions for contributing to the project.

## 📋 Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Code Style Guidelines](#code-style-guidelines)
- [Testing Requirements](#testing-requirements)
- [Pull Request Process](#pull-request-process)
- [Issue Reporting](#issue-reporting)

## 📜 Code of Conduct

By participating in this project, you agree to maintain a respectful and inclusive environment for all contributors.

## 🚀 Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/your-username/chatguru-agent.git
   cd chatguru-agent
   ```
3. **Add upstream remote**:
   ```bash
   git remote add upstream https://github.com/original-org/chatguru-agent.git
   ```
4. **Create a branch** for your changes:
   ```bash
   git checkout -b feature/your-feature-name
   ```

## 🛠️ Development Setup

### Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) package manager
- Git

> Note: The full React frontend now lives in a separate repository. This repo only contains the backend and a minimal HTML page for smoke testing.

### Initial Setup

1. **Complete development setup**:
   ```bash
   make setup
   ```

2. **Configure environment variables**:
   ```bash
   make env-setup
   # Edit .env with your credentials
   ```

3. **Verify installation**:
   ```bash
   make test
   ```

### Development Workflow

1. **Start backend development server**:
   ```bash
   make dev
   ```

2. **Run tests** before committing:
   ```bash
   make test
   make pre-commit
   ```

## 📝 Code Style Guidelines

### Python Code Style

We use automated tools to enforce code style:

- **ruff**: Code formatting and linting
- **mypy**: Type checking
- **pre-commit**: Git hooks for automatic checks

#### Running Code Quality Checks

```bash
# Install pre-commit hooks (runs automatically on git commit)
make pre-commit-install

# Run checks manually
make pre-commit
```

#### Python Style Rules

1. **Type Hints**: All functions must have type hints
   ```python
   def process_message(message: str) -> str:
       ...
   ```

2. **Async First**: Use `async def` for all async operations
   ```python
   async def stream_response(message: str) -> AsyncIterator[str]:
       ...
   ```

3. **Docstrings**: Use Google-style docstrings for public functions
   ```python
   def process_message(message: str) -> str:
       """Process a chat message and return response.

       Args:
           message: The user's message

       Returns:
           The agent's response
       """
   ```

4. **Imports**: Organize imports (handled automatically by ruff)
   - Standard library
   - Third-party packages
   - Local imports

### Frontend Code Style

The production frontend is maintained in a separate repository. Follow that project's guidelines for frontend contributions.

## ✅ Testing Requirements

### Unit Tests

All new features must include unit tests:

```bash
# Run all tests
make test

# Run with coverage
make coverage
```

#### Test Structure

- Tests should be in `tests/` directory
- Test files should be named `test_*.py`
- Use pytest fixtures from `conftest.py`
- Mock external dependencies (use `GenericFakeChatModel` for LLM)

#### Example Test

```python
import pytest
from agent.service import Agent

@pytest.mark.asyncio
async def test_agent_response():
    agent = Agent()
    response = await agent.astream("Hello")
    assert response is not None
```

### LLM Evaluation Tests

For changes affecting agent behavior, add promptfoo tests:

```bash
# Run evaluation
make promptfoo-eval

# View results
make promptfoo-view
```

Test files are in `promptfoo/tests/` directory.

### Test Coverage

- Aim for >80% code coverage
- Critical paths should have 100% coverage
- Run `make coverage` to check coverage

## 🔄 Pull Request Process

### Before Submitting

1. **Update documentation** if needed
2. **Add tests** for new features
3. **Run all checks**:
   ```bash
   make test
   make pre-commit
   make coverage
   ```
4. **Update CHANGELOG.md** (if applicable)

### PR Checklist

- [ ] Code follows style guidelines
- [ ] Tests pass (`make test`)
- [ ] Pre-commit checks pass (`make pre-commit`)
- [ ] Documentation updated
- [ ] CHANGELOG updated (if applicable)
- [ ] No merge conflicts with `main`

### Submitting a PR

1. **Push your branch**:
   ```bash
   git push origin feature/your-feature-name
   ```

2. **Create Pull Request** on GitHub:
   - Use clear, descriptive title
   - Reference related issues
   - Describe changes in detail
   - Include screenshots for UI changes

3. **Wait for review**:
   - Address review comments
   - Update PR as needed
   - Ensure CI checks pass

### PR Title Format

Use conventional commits format:

- `feat: Add new feature`
- `fix: Fix bug description`
- `docs: Update documentation`
- `test: Add tests for feature`
- `refactor: Refactor code`
- `chore: Update dependencies`

### Review Process

1. **Automated checks** run on PR creation
2. **Maintainers review** code and tests
3. **Address feedback** and update PR
4. **Approval** required from at least one maintainer
5. **Merge** by maintainer (squash and merge preferred)

## 🐛 Issue Reporting

### Before Creating an Issue

1. **Search existing issues** to avoid duplicates
2. **Check documentation** for solutions
3. **Verify** it's not a configuration issue

### Bug Reports

Use the bug report template and include:

- **Description**: Clear description of the bug
- **Steps to Reproduce**: Minimal steps to reproduce
- **Expected Behavior**: What should happen
- **Actual Behavior**: What actually happens
- **Environment**: Python version, OS, dependencies
- **Logs**: Relevant error messages or logs
- **Screenshots**: If applicable

### Feature Requests

Include:

- **Use Case**: Why is this feature needed?
- **Proposed Solution**: How should it work?
- **Alternatives**: Other solutions considered
- **Additional Context**: Any other relevant information

### Issue Labels

- `bug`: Something isn't working
- `enhancement`: New feature or improvement
- `documentation`: Documentation improvements
- `question`: Questions or discussions
- `good first issue`: Good for newcomers
- `help wanted`: Extra attention needed

## 📚 Additional Resources

- [Architecture Documentation](docs/architecture.md)
- [Getting Started Guide](GETTING_STARTED.md)
- [API Documentation](http://localhost:8000/docs) (when running locally)

## 💡 Tips for Contributors

1. **Start Small**: Look for `good first issue` labels
2. **Ask Questions**: Don't hesitate to ask for clarification
3. **Follow Patterns**: Match existing code style and patterns
4. **Test Thoroughly**: Write tests for your changes
5. **Document Changes**: Update docs for user-facing changes

## 🙏 Thank You!

Your contributions make chatguru Agent better for everyone. Thank you for taking the time to contribute!
