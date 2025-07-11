# Envars2: Environment Variable Management CLI

[![PyPI version](https://badge.fury.io/py/envars2.svg)](https://badge.fury.io/py/envars2)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Application Config As Code**

**Envars2** is a powerful command-line tool for managing environment variables across different applications, environments, and cloud providers.

**For detailed documentation, please visit our [documentation site](https://your-username.github.io/envars2).**

## Key Features

- **Centralized Configuration**: Manage all your environment variables in a single `envars.yml` file.
- **Hierarchical Scopes**: Define variables at different levels (default, environment, location).
- **Secrets Management**: Encrypt and decrypt sensitive values using AWS KMS or Google Cloud KMS.
- **Flexible Commands**: A rich set of commands for various workflows.
- **Validation**: Strict validation to prevent common mistakes.

## Installation

```bash
pip install envars
```

## Quick Start

1.  **Initialize a new project:**
    ```bash
    envars init --app "my-app" --env "dev,prod" --loc "aws:123456789012"
    ```

2.  **Add a variable:**
    ```bash
    envars add MY_VAR=my_value --description "This is my variable."
    ```

3.  **Execute a command with the environment:**
    ```bash
    envars exec --env dev --loc aws -- python my_script.py
    ```

## Development

To set up the development environment, clone the repository and install the dependencies using `uv`:

```bash
git clone https://github.com/your-username/envars2.git
cd envars2
uv sync
```

To run the tests:

```bash
uv run pytest
```

To build and serve the documentation site locally:

```bash
mkdocs serve
```
