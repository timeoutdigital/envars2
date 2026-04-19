# envars2

## Purpose
`envars2` is a CLI and library for resolving application config from an `envars.yml` file, with hierarchical scoping and cloud-provider-aware secret handling (AWS KMS and GCP Secret Manager).

## Local Development
- Setup dependencies: `uv sync`
- Run tests: `uv run pytest`
- Lint & format: `uv run ruff check .` / `uv run ruff format .`
- Type check: `uv run ty check .`
- Pre-commit (run before pushing): `uv run pre-commit run --all-files`

## Architecture Notes
- **Resolution Pipeline:** Scope resolution (specific match based on env/loc) -> KMS decryption (AWS or GCP) -> Jinja2 templating -> Remote lookup prefixes (parameter_store, gcp_secret_manager).
- **Data Model:** `VariableManager` holds scopes. Variable names must be uppercase.
- **YAML Round-Trip:** Flattened shape, preserves canonical order on write.
- **CLI:** Typer app (`src/envars/cli.py`). The `add` command has safety nets for secret-like variable names.
