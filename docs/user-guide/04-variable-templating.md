# User Guide: Variable Templating

`envars` uses the powerful **Jinja2** templating engine to allow you to create dynamic variables based on the values of other variables. This is extremely useful for reducing duplication and creating complex, context-aware configurations.

## How it Works

When you use `envars output` or `envars exec`, `envars` performs a two-pass resolution:

1.  **First Pass:** It resolves the initial values of all variables based on the specified environment and location context.
2.  **Second Pass:** It iterates through the resolved values and renders any that contain Jinja2 template syntax (`{{ ... }}`).

## Basic Templating

You can reference any other variable within a template. `envars` automatically handles the dependency resolution.

### Example: Building a URL

Instead of hardcoding the domain in multiple URL variables, you can define it once and reference it.

```yaml
# In envars.yml
environment_variables:
  DOMAIN:
    default: "example.com"
    prod: "prod.example.com"

  API_ENDPOINT:
    default: "https://api.{{ DOMAIN }}/v1"

  FRONTEND_URL:
    default: "https://app.{{ DOMAIN }}"
```

When you resolve for the `dev` environment:

```bash
$ envars output --env dev --loc any-loc
DOMAIN=example.com
API_ENDPOINT=https://api.example.com/v1
FRONTEND_URL=https://app.example.com
```

When you resolve for `prod`:

```bash
$ envars output --env prod --loc any-loc
DOMAIN=prod.example.com
API_ENDPOINT=https://api.prod.example.com/v1
FRONTEND_URL=https://app.prod.example.com
```

## Accessing Shell Environment Variables

You can also access the shell's environment variables from within your templates using the `env` object. This is useful for incorporating system-level configuration.

### Example: Using `STAGE` and `PORT`

```yaml
# In envars.yml
environment_variables:
  # Use the STAGE env var if it exists, otherwise default to 'dev'
  APP_ENV:
    default: "{{ env.get('STAGE', 'dev') }}"

  # Use the PORT env var if it exists, otherwise default to 8080
  LISTEN_PORT:
    default: "{{ env.get('PORT', '8080') }}"
```

If you run `envars` in a shell where `STAGE=staging` and `PORT=3000`:

```bash
$ STAGE=staging PORT=3000 envars output --env dev --loc any-loc
APP_ENV=staging
LISTEN_PORT=3000
```

If those environment variables are not set, the defaults will be used:

```bash
$ envars output --env dev --loc any-loc
APP_ENV=dev
LISTEN_PORT=8080
```

## Circular Dependencies

`envars` will automatically detect if you create a circular dependency (e.g., `VAR_A` depends on `VAR_B`, and `VAR_B` depends on `VAR_A`). If a circular dependency is found, `envars` will exit with an error, telling you which variables are part of the cycle. This check is performed by both `envars add` and `envars validate`.
