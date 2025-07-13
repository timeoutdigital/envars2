# API Reference: Data Models

The core logic of `envars` is built around a set of simple, Pydantic-like data models that represent the different components of your configuration.

This section of the documentation is best generated automatically from the source code's docstrings. To do this, you can use a tool like [`mkdocstrings`](https://mkdocstrings.github.io/).

## Recommended Setup

1.  **Install `mkdocstrings`:**
    ```bash
    pip install mkdocstrings mkdocstrings-python
    ```

2.  **Configure `mkdocs.yml`:**
    Add the `mkdocstrings` plugin to your `mkdocs.yml` file.

    ```yaml
    # In mkdocs.yml
    plugins:
      - search
      - mkdocstrings:
          handlers:
            python:
              options:
                show_root_heading: yes
    ```

3.  **Add Auto-Generated Content:**
    You can then replace the content of this file with the following to automatically pull in the documentation for your models:

    ```markdown
    # Data Models

    ::: envars.models.Variable

    ---

    ::: envars.models.Environment

    ---

    ::: envars.models.Location

    ---

    ::: envars.models.VariableValue

    ---

    ::: envars.models.VariableManager
    ```

This setup will read the docstrings from your Python classes in `src/envars/models.py` and render them as clean, readable documentation whenever you build your site with `mkdocs build`.
