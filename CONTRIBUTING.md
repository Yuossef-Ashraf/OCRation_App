# Contributing to OCRation

Thank you for your interest in contributing to **OCRation**! We welcome contributions from the community to help improve the optical character recognition, translation pipeline, web interface, desktop GUI, and developer tooling.

---

## How to Contribute

Please follow these numbered steps to submit your contributions:

1. **Fork the Repository**: Click the **Fork** button at the top right of the repository page on GitHub.
2. **Clone Your Fork**: Clone your fork locally:
   ```bash
   git clone https://github.com/YOUR_USERNAME/OCRation_App.git
   cd OCRation_App
   ```
3. **Create a Feature Branch**: Create a descriptive branch for your work:
   ```bash
   git checkout -b feature/your-feature
   ```
4. **Make Your Changes**: Implement your bug fixes, features, or documentation updates with clean, readable code.
5. **Write Tests**: Add unit or integration tests in the `tests/` directory covering your changes.
6. **Commit Your Changes**: Follow our commit message conventions (see below):
   ```bash
   git commit -m "feat: add batch processing"
   ```
7. **Push to Your Fork**: Push your branch to GitHub:
   ```bash
   git push origin feature/your-feature
   ```
8. **Open a Pull Request**: Submit a Pull Request (PR) against the `main` branch with a clear description of the problem solved and test results.

---

## Branch Naming Convention

Use clear prefixes to indicate the type of contribution:

- `feature/your-feature` — New features or substantial functionality (e.g., `feature/pdf-export`)
- `fix/bug-name` — Bug fixes and patches (e.g., `fix/empty-image-handler`)
- `docs/what-you-documented` — Documentation changes or additions (e.g., `docs/api-guide`)
- `refactor/scope` — Code refactoring without behavioral changes
- `test/test-scope` — Adding or improving automated tests

---

## Commit Message Format

We follow the Conventional Commits specification. Structure your commit messages as:

```
<type>: <short summary in present tense>

[optional body with details]
```

### Examples:
- `feat: add batch processing`
- `fix: handle empty image`
- `docs: update README`
- `test: add OCR unit tests`
- `ci: add GitHub Actions workflow for automated testing`

---

## Code Style Guidelines

- **PEP 8 Compliance**: Follow the standard PEP 8 Python style guide.
- **Line Length**: Limit all lines to a maximum of **88 characters**.
- **Formatter**: Use the `black` code formatter before submitting code:
  ```bash
  pip install black
  black .
  ```
- **Type Annotations**: Use Python type hints (`typing`) wherever practical.
- **Clean Architecture**: Keep modules focused and loosely coupled (`image_ocr.py` for OCR, `llm_model.py` for LLM translation).

---

## Testing Requirements

- All pull requests that add new features or modify existing logic must include corresponding tests in `tests/`.
- Ensure all tests pass cleanly before submitting a PR:
  ```bash
  pytest tests/ -v
  ```
- PRs that fail continuous integration (CI) tests will not be merged until resolved.

---

## Reporting Bugs

If you discover a bug, please open an Issue on GitHub with the following details:

1. **Python Version**: (e.g., Python 3.10.12)
2. **Operating System**: (e.g., Windows 11, Ubuntu 22.04 LTS, macOS Sonoma)
3. **Steps to Reproduce**: Clear, numbered step-by-step guide to reproduce the issue.
4. **Expected Behavior**: What you expected to happen.
5. **Actual Behavior**: What actually happened.
6. **Full Error Traceback**: Paste the complete terminal traceback inside triple backticks (```).
