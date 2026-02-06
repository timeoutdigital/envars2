# Technology Stack - Envars

## Core Development
- **Language:** Python (>=3.10) - Leverages modern Python features and type hinting for a robust codebase.
- **CLI Framework:** [Typer](https://typer.tiangolo.com/) - Provides a powerful and intuitive CLI experience with automatic help generation and type validation.

## Cloud & Security
- **AWS Integration:** [Boto3](https://aws.amazon.com/sdk-for-python/) - Used for interacting with AWS KMS and SSM Parameter Store.
- **GCP Integration:** [Google Cloud SDK](https://cloud.google.com/python/docs/reference) - Used for Google Cloud KMS and Secret Manager.
- **Openbao Integration:** [hvac](https://hvac.readthedocs.io/en/stable/) or direct API - Used for interacting with Openbao KMS. Configuration uses a simplified `kms_key` string format (e.g., `openbao:<key>`) instead of nested objects.

## Utilities
- **Templating:** [Jinja2](https://palletsprojects.com/p/jinja/) - Enables dynamic variable resolution and complex configuration logic.
- **YAML Processing:** [PyYAML](https://pyyaml.org/) - Handles the parsing and serialization of the `envars.yml` configuration file.
- **CLI Enhancement:** [Rich](https://github.com/Textualize/rich) - Used for beautiful and informative terminal output, including tables and progress indicators.

## Tooling & Infrastructure
- **Dependency Management:** [uv](https://github.com/astral-sh/uv) - A fast Python package installer and resolver.
- **Linting & Formatting:** [Ruff](https://github.com/astral-sh/ruff) - An extremely fast Python linter and code formatter, configured in `pyproject.toml`.
- **Testing:** [Pytest](https://docs.pytest.org/) - The standard framework for running unit and integration tests.
