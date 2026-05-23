---
description: Steps and guidelines to validate, format, and safely commit changes to the repository
---

# Committing Changes

This workflow outlines the standard procedure for validating, formatting, and committing changes in the codebase to ensure repository health, clean history, and high-quality standards.

## Pre-Commit Checklist

Before staging or committing any files, ensure that the proposed changes are fully validated.

1. **Format & Style Checks**:
   - Ensure the code complies with PEP 8 standards.
   - Limit all modified or newly introduced lines to a maximum of 100 characters.
   - Run the linting checks as defined in the `/code-validation` workflow:
     ```bash
     venv/bin/flake8 custom_components/bytewatt --max-line-length=100
     ```

2. **Syntax Verification**:
   - Compile modified files to verify no syntax errors exist:
     ```bash
     venv/bin/python -m py_compile custom_components/bytewatt/**/*.py
     ```

3. **Verify API / Standalone Scripts**:
   - If any API modifications or new endpoints are implemented, run their corresponding standalone test scripts:
     ```bash
     venv/bin/python tests/test_feed_strategy.py
     ```

---

## Commit Process

Follow these steps to stage and commit your changes securely.

### 1. Review Status and Diffs

Always inspect the exact lines of code being changed to ensure no extraneous modifications or debug logs are included.

```bash
# Check modified and untracked files
git status

# Review line-by-line differences
git diff
```

### 2. Stage Intended Files

Stage files selectively. Do not commit temporary directories, virtual environments, or environment variables (`.env`).

```bash
# Stage a specific file
git add path/to/file.py

# Stage all files in a specific directory
git add tests/
```

### 3. Write a Conventional Commit Message

Use the Conventional Commits specification to format your commit messages. The message should explain "why" the change was made rather than "what".

Structure:
```text
<type>(<scope>): <short summary>

[optional body explaining rationale and decisions]
```

#### Allowed Types:
- `feat`: A new feature (e.g., adding a sensor, custom service, or API support)
- `fix`: A bug fix
- `docs`: Documentation-only changes (e.g., updating `README.md` or adding comments)
- `style`: Formatting, missing semi-colons, etc.; no production code change
- `refactor`: A code change that neither fixes a bug nor adds a feature
- `test`: Adding missing tests or correcting existing tests
- `chore`: Changes to the build process or auxiliary tools/libraries

#### Example Commit:
```bash
git commit -m "feat(api): add feed-in strategy setting lookup and standalone test script"
```

### 4. Confirm Clean Working Tree

Run `git status` one last time to make sure all intended files were successfully committed and that no unwanted files are left untracked.

```bash
git status
```
