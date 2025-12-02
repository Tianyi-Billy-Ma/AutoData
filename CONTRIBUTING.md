# Contributing to AutoData

Thank you for your interest in contributing to AutoData! This document provides guidelines and information for contributors.

## 🤝 How to Contribute

We welcome contributions from everyone, regardless of experience level. Here are some ways you can contribute:

- **Bug Reports**: Report bugs and issues
- **Feature Requests**: Suggest new features or improvements
- **Code Contributions**: Submit pull requests with bug fixes or new features
- **Documentation**: Improve or add documentation
- **Testing**: Help test the project and report issues
- **Community Support**: Help other users in discussions and issues

## 🚀 Getting Started

### Prerequisites

- Python 3.11 or higher
- Git
- uv (recommended) or pip

### Setting Up Your Development Environment

1. **Fork the Repository**
   ```bash
   # Go to https://github.com/Tianyi-Billy-Ma/AutoData_DEV and click "Fork"
   # Then clone your fork
   git clone https://github.com/YOUR_USERNAME/autodata.git
   cd autodata
   ```

2. **Set Up the Upstream Remote**
   ```bash
   git remote add upstream https://github.com/Tianyi-Billy-Ma/AutoData.git
   git fetch upstream
   ```

3. **Install Dependencies**
   ```bash
   # Using uv (recommended)
   uv sync --group dev,test,docs
   uv shell
   
   # Or using pip
   pip install -e ".[dev,test]"
   ```

4. **Install Pre-commit Hooks**
   ```bash
   uv run pre-commit install
   ```

5. **Verify Setup**
```bash
uv run pytest --version
uv run ruff --version
uv run black --version
uv run mypy --version
uv run python -m autodata.scripts.cleanup_unused --check
```

## 📝 Development Workflow

Always run `uv run python -m autodata.scripts.cleanup_unused --check` (see `docs/dev/cleanup_unused.md`) before submitting changes that touch `autodata/`. The command exits non-zero if unused imports, functions, or classes remain, preventing dead code from shipping.

### 1. Create a Feature Branch

Always work on a feature branch, never directly on `main`:

```bash
git checkout -b feature/your-feature-name
# or for bug fixes
git checkout -b fix/bug-description
```

### 2. Make Your Changes

- Write clean, readable code
- Follow our coding standards (see below)
- Add tests for new functionality
- Update documentation as needed

### 3. Test Your Changes

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=autodata

# Run specific test categories
uv run pytest -m "not slow"
uv run pytest -m unit
uv run pytest -m integration

# Run code quality checks
uv run ruff check .
uv run black --check .
uv run mypy autodata/
```

### 4. Commit Your Changes

Use conventional commit messages:

```bash
git commit -m "feat: add new crawling agent type"
git commit -m "fix: resolve rate limiting issue"
git commit -m "docs: update API documentation"
git commit -m "test: add tests for data processor"
```

**Commit Message Format:**
```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

### 5. Push and Create a Pull Request

```bash
git push origin feature/your-feature-name
```

Then go to GitHub and create a Pull Request.

## 🎯 Coding Standards

### Python Code Style

We use several tools to maintain code quality:

- **Ruff**: Linting and formatting (replaces flake8, isort, and black)
- **Pre-commit**: Automated checks before commits

### Code Quality Requirements

1. **Type Annotations**: All functions, methods, and class members must have type annotations
   ```python
   def process_data(data: List[Dict[str, Any]]) -> ProcessedData:
       """Process raw data into structured format."""
       pass
   ```

2. **Docstrings**: Use Google-style docstrings for all public functions and classes
   ```python
   def extract_content(html: str, selector: str) -> Optional[str]:
       """Extract content from HTML using CSS selector.
       
       Args:
           html: Raw HTML content
           selector: CSS selector string
           
       Returns:
           Extracted content or None if not found
           
       Raises:
           ValueError: If selector is invalid
       """
       pass
   ```

3. **Error Handling**: Use specific exception types and provide informative messages
   ```python
   if not url.startswith(('http://', 'https://')):
       raise ValueError(f"Invalid URL format: {url}")
   ```

4. **Logging**: Use structured logging for important events
   ```python
   import structlog
   
   logger = structlog.get_logger()
   logger.info("Starting crawl task", task_id=task.id, urls_count=len(task.urls))
   ```

### Import Organization

```python
# Standard library imports
import asyncio
import logging
from typing import List, Optional

# Third-party imports
import aiohttp
import pandas as pd
from pydantic import BaseModel

# Local imports
from autodata.core.models import CrawlTask
from autodata.utils.validators import validate_url
```

## 🧪 Testing Guidelines

### Test Requirements

- **Coverage**: Aim for at least 90% test coverage
- **Test Types**: Include unit tests, integration tests, and edge cases
- **Naming**: Test files should start with `test_` and test functions should be descriptive
- **Isolation**: Tests should be independent and not rely on external services

### Test Structure

```python
import pytest
from unittest.mock import Mock, patch
from autodata.agents import CrawlerAgent

class TestCrawlerAgent:
    """Test cases for CrawlerAgent class."""
    
    @pytest.fixture
    def agent(self):
        """Create a test agent instance."""
        return CrawlerAgent()
    
    @pytest.mark.asyncio
    async def test_crawl_single_url(self, agent):
        """Test crawling a single URL."""
        # Test implementation
        pass
    
    @pytest.mark.asyncio
    async def test_crawl_with_invalid_url(self, agent):
        """Test crawling with invalid URL raises appropriate error."""
        with pytest.raises(ValueError, match="Invalid URL"):
            await agent.crawl("not-a-url")
```

### Running Tests

```bash
# Run all tests
uv run pytest

# Run specific test file
uv run pytest tests/test_agents.py

# Run tests with coverage report
uv run pytest --cov=autodata --cov-report=html

# Run tests in parallel
uv run pytest -n auto

# Run only fast tests
uv run pytest -m "not slow"
```

## 📚 Documentation Standards

### Code Documentation

- All public APIs must be documented
- Use Google-style docstrings
- Include usage examples for complex functions
- Document exceptions and edge cases

### Project Documentation

- Keep README.md up to date
- Document configuration options
- Provide clear examples and tutorials
- Update CHANGELOG.md for all releases

## 🔍 Pull Request Process

### Before Submitting

1. **Ensure Tests Pass**: All tests must pass locally
2. **Code Quality**: Run all linting and formatting tools
3. **Documentation**: Update documentation as needed
4. **Rebase**: Rebase your branch on the latest main branch

### Pull Request Template

When creating a PR, use this template:

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Documentation update
- [ ] Test addition/update
- [ ] Other (please describe)

## Testing
- [ ] All tests pass
- [ ] New tests added for new functionality
- [ ] Manual testing completed

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Documentation updated
- [ ] Changelog updated (if applicable)

## Related Issues
Closes #(issue number)
```

### Review Process

1. **Automated Checks**: CI/CD will run tests and code quality checks
2. **Code Review**: At least one maintainer must approve
3. **Address Feedback**: Respond to review comments and make requested changes
4. **Merge**: Once approved, maintainers will merge the PR

## 🐛 Bug Reports

When reporting bugs, please include:

- **Clear Description**: What happened vs. what you expected
- **Steps to Reproduce**: Detailed steps to reproduce the issue
- **Environment**: OS, Python version, package versions
- **Error Messages**: Full error messages and stack traces
- **Minimal Example**: Minimal code example that reproduces the issue

## 💡 Feature Requests

For feature requests:

- **Clear Description**: What you want to achieve
- **Use Case**: Why this feature would be useful
- **Proposed Solution**: How you think it should work
- **Alternatives**: Any alternatives you've considered

## 📞 Getting Help

- **Issues**: Use GitHub Issues for bugs and feature requests
- **Discussions**: Use GitHub Discussions for questions and general discussion
- **Documentation**: Check the project documentation first
- **Community**: Join our community channels (if available)

## 🏆 Recognition

Contributors will be recognized in:

- Project README.md
- Release notes
- Contributor acknowledgments
- GitHub contributors list

## 📋 Code of Conduct

We are committed to providing a welcoming and inclusive environment for all contributors. Please read our [Code of Conduct](CODE_OF_CONDUCT.md) for details.

## 🚀 Quick Reference

```bash
# Development setup
uv sync --group dev,test
uv run pre-commit install

# Running tests
uv run pytest
uv run pytest --cov=autodata

# Code quality
uv run ruff check .
uv run black --check .
uv run mypy autodata/

# Creating a PR
git checkout -b feature/your-feature
# ... make changes ...
git commit -m "feat: your feature description"
git push origin feature/your-feature
# Create PR on GitHub
```

Thank you for contributing to AutoData! 🎉
