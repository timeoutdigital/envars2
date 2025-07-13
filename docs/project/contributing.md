# Contributing to Envars

We welcome contributions from the community! Whether you're fixing a bug, improving documentation, or proposing a new feature, your help is appreciated.

## Getting Started

1.  **Fork the repository** on GitHub.
2.  **Clone your fork** locally: `git clone https://github.com/your-username/envars.git`
3.  **Install dependencies** for development. We use `uv` for package management.
    ```bash
    pip install uv
    uv sync
    ```
4.  **Create a new branch** for your changes: `git checkout -b my-feature-branch`

## Running Tests

To ensure your changes don't break existing functionality, please run the test suite:

```bash
uv run pytest
```

## Code Style and Linting

This project uses `ruff` for linting and formatting. Before committing, please run the linter to ensure your code conforms to the project's style.

```bash
uv run ruff check .
uv run ruff format .
```

We also use `pre-commit` to automatically run these checks before each commit. You can set it up with:

```bash
uv run pre-commit install
```

## Submitting a Pull Request

1.  **Commit your changes** with a clear and descriptive commit message.
2.  **Push your branch** to your fork on GitHub: `git push origin my-feature-branch`
3.  **Open a pull request** from your branch to the `main` branch of the original repository.
4.  In the pull request description, please explain the changes you made and why.

Thank you for contributing!
