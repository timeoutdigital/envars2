# Envars2 Architecture

Welcome to the Envars2 project! This document provides a comprehensive overview of the application's architecture, key design decisions, and instructions for new developers.

## High-Level Overview

Envars2 is a Python-based command-line interface (CLI) tool designed to simplify the management of environment variables and secrets across multiple environments and cloud providers. It uses a single `envars.yml` file as the source of truth and provides a set of commands to interact with this file and the environment.

The application is built using the `typer` library for the CLI, `pyyaml` for YAML parsing, `jinja2` for templating, and `boto3` and `google-cloud-secret-manager` for cloud integrations.

## C4 Model

The C4 model is used to describe the architecture of a software system at different levels of abstraction.

### Level 1: System Context Diagram

This diagram shows how the `envars2` CLI interacts with users and external systems.

```mermaid
graph TD
    subgraph "Envars2 System"
        A[envars2 CLI]
    end

    B(User) -- "Manages environment variables" --> A
    A -- "Reads/writes envars.yml" --> C(File System)
    A -- "Fetches secrets from" --> D(AWS Parameter Store)
    A -- "Fetches secrets from" --> E(GCP Secret Manager)
    A -- "Encrypts/decrypts secrets with" --> F(AWS KMS)
    A -- "Encrypts/decrypts secrets with" --> G(GCP KMS)
```

### Level 2: Container Diagram

This diagram breaks down the `envars2` application into its major components.

```mermaid
graph TD
    subgraph "Envars2 Application"
        A["CLI (cli.py)"] -- "Uses" --> B["Core Logic (src/envars/main.py)"]
        B -- "Uses" --> C["Data Models (src/envars/models.py)"]
        B -- "Uses" --> D["Cloud Integrations (src/envars/aws_*, src/envars/gcp_*)"]
    end
```

### Level 3: Component Diagram

This diagram zooms in on the `envars-cli` container and shows the key components and their interactions.

```mermaid
graph TD
    subgraph "CLI (cli.py)"
        A["Commands (init, add, etc.)"] -- "Use" --> B["Helper Functions"]
        B["_get_resolved_variables"] -- "Uses" --> C["Jinja2 Templating"]
        B -- "Uses" --> D["Cloud Clients"]
    end
```

## Sequence Diagrams

These diagrams illustrate the flow of control for key commands.

### `add` Command

```mermaid
sequenceDiagram
    participant User
    participant CLI
    participant CoreLogic
    participant FileSystem

    User->>CLI: envars2 add MY_VAR=my_value
    CLI->>CoreLogic: load_from_yaml()
    CoreLogic->>FileSystem: Read envars.yml
    FileSystem-->>CoreLogic: Return file content
    CoreLogic-->>CLI: Return VariableManager
    CLI->>CoreLogic: add_variable()
    CLI->>CoreLogic: add_variable_value()
    CLI->>CoreLogic: write_envars_yml()
    CoreLogic->>FileSystem: Write to envars.yml
```

### `exec` Command

```mermaid
sequenceDiagram
    participant User
    participant CLI
    participant CoreLogic
    participant CloudServices

    User->>CLI: envars2 exec --env dev --loc aws -- my_script.py
    CLI->>CoreLogic: _get_resolved_variables()
    CoreLogic->>CloudServices: Fetch secrets (if any)
    CloudServices-->>CoreLogic: Return secret values
    CoreLogic-->>CLI: Return resolved variables
    CLI->>CLI: Populate environment
    CLI->>CLI: Execute my_script.py
```

```

### `exec` Command

```mermaid
sequenceDiagram
    participant User
    participant CLI
    participant CoreLogic
    participant CloudServices

    User->>CLI: envars2 exec --env dev --loc aws -- my_script.py
    CLI->>CoreLogic: _get_resolved_variables()
    CoreLogic->>CloudServices: Fetch secrets (if any)
    CloudServices-->>CoreLogic: Return secret values
    CoreLogic-->>CLI: Return resolved variables
    CLI->>CLI: Populate environment
    CLI->>CLI: Execute my_script.py
```

## Onboarding Guide

This guide will help new developers get up and running with the `envars2` project.

### Prerequisites

- Python 3.10+
- `uv`

### Setup

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/your-username/envars2.git
    cd envars2
    ```

2.  **Install dependencies:**
    ```bash
    uv sync --all-extras
    ```

3.  **Set up pre-commit hooks:**
    ```bash
    pre-commit install
    ```

### Running Tests

To run the test suite, use the following command:

```bash
uv run pytest
```

### Code Style

This project uses `ruff` for linting and formatting. The pre-commit hooks will automatically format your code and run the linter before each commit.

### Key Modules

-   **`cli.py`**: This file contains all the command-line interface logic, built using `typer`. It's the main entry point for the application.
-   **`src/envars/main.py`**: This file contains the core logic for loading and writing the `envars.yml` file.
-   **`src/envars/models.py`**: This file defines the data models for the application, such as `Variable`, `Environment`, and `Location`.
-   **`src/envars/aws_*.py` and `src/envars/gcp_*.py`**: These files contain the logic for interacting with AWS and GCP services.
-   **`tests/`**: This directory contains all the tests for the application.
