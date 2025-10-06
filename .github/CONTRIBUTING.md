# Contributing to Rediacc CLI

Thank you for your interest in contributing to the Rediacc CLI! This document provides guidelines and workflows for contributing to the project.

## 🔒 Branch Protection & Workflow

### Protected Branches

The following branches are protected and require pull requests:

- **`main`** - Production-ready code, always deployable
- **`develop`** - Integration branch (if used)

### Direct Push = Blocked ⛔

You **cannot** push directly to protected branches. All changes must go through the pull request process.

## 📝 Contribution Process

### 1. Create a Feature Branch

```bash
# Update your local main branch
git checkout main
git pull origin main

# Create a new feature branch
git checkout -b feature/your-feature-name

# Or for bug fixes
git checkout -b fix/issue-description
```

### 2. Make Your Changes

- Write clean, well-documented code
- Follow existing code style and conventions
- Add tests for new functionality
- Update documentation as needed

### 3. Commit Your Changes

Follow the [Conventional Commits](https://www.conventionalcommits.org/) format:

```bash
git add .
git commit -m "feat: add new feature description"

# Commit types:
# feat: New feature
# fix: Bug fix
# docs: Documentation changes
# style: Code style changes (formatting, etc.)
# refactor: Code refactoring
# test: Adding or updating tests
# chore: Maintenance tasks
```

### 4. Push to GitHub

```bash
git push -u origin feature/your-feature-name
```

### 5. Create a Pull Request

```bash
# Using GitHub CLI (recommended)
gh pr create --fill

# Or manually via GitHub web interface
```

### 6. Wait for CI & Reviews

Your PR must meet the following requirements before it can be merged:

#### ✅ Required Checks (All Must Pass)

- **Linux Tests** - Tests on Ubuntu with all Python versions
- **Windows Tests** - Tests on Windows with all Python versions
- **macOS Tests** - Tests on macOS with all Python versions
- **Code Quality** - Linting and type checking
- **Test Summary** - Overall test status

#### ✅ Required Reviews

- At least **1 approval** from a team member
- All review comments must be **resolved**

#### ✅ Branch Requirements

- Branch must be **up-to-date** with main
- **No merge conflicts**

### 7. Merge Your PR

Once all checks pass and you have approval:

1. Click **"Squash and merge"** button on GitHub
2. Edit the commit message if needed (uses PR title and description by default)
3. Confirm the merge

Your feature branch will be **automatically deleted** after merge.

## 🚫 What NOT to Do

❌ **Don't push directly to main** - All changes require PRs
❌ **Don't force push to main** - Protected and will be rejected
❌ **Don't merge without CI passing** - Merges are blocked
❌ **Don't merge without approval** - At least 1 review required
❌ **Don't leave unresolved conversations** - All must be resolved

## 🧪 Testing Locally

Before pushing your changes, test locally:

```bash
# Run tests
python -m pytest tests/ -v

# Run code quality checks
black --check src/ tests/
flake8 src/
mypy src/cli --ignore-missing-imports

# Run specific test file
python -m pytest tests/gui/test_gui_login_basic.py -v
```

## 🐛 Reporting Issues

Found a bug? Please create an issue with:

- Clear description of the problem
- Steps to reproduce
- Expected vs actual behavior
- Environment details (OS, Python version)
- Error messages or screenshots

## 💡 Suggesting Features

Have an idea? Create an issue with:

- Clear description of the feature
- Use case and motivation
- Proposed implementation (optional)
- Examples of similar features (if applicable)

## 📚 Code Style Guidelines

### Python Code

- Follow [PEP 8](https://pep8.org/) style guide
- Use meaningful variable and function names
- Add docstrings to all public functions/classes
- Keep functions focused and short
- Add type hints where appropriate

### Example:

```python
def process_user_data(user_id: str, data: dict) -> bool:
    """
    Process user data and update database.

    Args:
        user_id: Unique identifier for the user
        data: Dictionary containing user data to process

    Returns:
        bool: True if processing successful, False otherwise
    """
    # Implementation here
    pass
```

### Git Commits

- Use present tense ("Add feature" not "Added feature")
- Use imperative mood ("Move cursor to..." not "Moves cursor to...")
- Keep first line under 72 characters
- Reference issues and PRs in commit body when relevant

## 🔄 Keeping Your Branch Updated

If your branch falls behind main:

```bash
# Update main
git checkout main
git pull origin main

# Rebase your feature branch
git checkout feature/your-feature-name
git rebase main

# Force push (only to your feature branch!)
git push --force-with-lease origin feature/your-feature-name
```

## ❓ FAQ

### Q: What if CI fails on my PR?

**A:** Fix the issues and push new commits. CI will automatically re-run.

### Q: Can I force push to my feature branch?

**A:** Yes! Only main/develop branches are protected. Use `--force-with-lease` for safety.

### Q: What if I need to make an urgent hotfix?

**A:** Create an emergency PR, request expedited review, and use auto-merge once approved.

### Q: How long do reviews usually take?

**A:** We aim to review PRs within 1-2 business days. Ping in Slack if urgent.

### Q: Can I merge my own PR?

**A:** You can click merge after approval, but you cannot approve your own PR.

### Q: What happens to my branch after merge?

**A:** It's automatically deleted from GitHub. Clean up locally with `git branch -d feature-name`.

## 🎯 Workflow Summary

```
1. Create branch     → git checkout -b feature/name
2. Make changes      → code, test, commit
3. Push branch       → git push -u origin feature/name
4. Create PR         → gh pr create --fill
5. Wait for CI       → All 5 checks must pass ✅
6. Get review        → At least 1 approval required ✅
7. Resolve comments  → All conversations resolved ✅
8. Squash & merge    → Click button, branch auto-deleted ✅
```

## 📞 Getting Help

- **Documentation**: Check `/docs` directory
- **Issues**: Search existing issues first
- **Discussions**: Use GitHub Discussions for questions
- **Slack**: #rediacc-cli channel (if applicable)

## 📄 License

By contributing, you agree that your contributions will be licensed under the same license as the project.

---

Thank you for contributing to Rediacc CLI! 🚀
