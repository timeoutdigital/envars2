# Migrating from envars v1

`scripts/migrate_v1.py` converts an envars v1 `envars.yml` to the envars2 format. It also encrypts the secrets again with a GCP KMS key.

## What it does

1. It reads the v1 file. If the file has `!secret` values, it decrypts them with envars v1. This needs AWS credentials for the old AWS KMS key.
2. It makes a new envars2 file with `envars init`, then adds every value with `envars add`.
   - envars2 needs a secret to be scoped to an environment or a location. So an inherited v1 secret default gets one encrypted value for each environment (and location) that has no override of its own, and each one uses that scope's own value.
   - v2 locations are only added for the v1 accounts (`master`, `sandbox`) that the file uses. Data-apps use none.
   - `{{ STAGE }}` and `{{ RELEASE }}` become `env.get(...)`, so that they are not circular. `{{ RELEASE }}` becomes `env.get("RELEASE") or env.get("RELEASE_SHA")`: v1 read `RELEASE_SHA`, and that input still works.
3. It runs `envars validate`. Then it compares the v1 values (`envars print -y`) with the v2 values (`envars output --format json`) for every environment and location. The comparison is exact, so spaces at the start or end of a value and multi-line values are checked too. If anything is different, it stops.

The output goes to `envars.yml.v2`. Your `envars.yml` does not change. The script also writes a copy of the v1 file to `envars.yml.v1.bk`. Do not commit that copy.

## Secret values are never shown

- Secret values go to envars2 through a temporary file that only you can read (mode 600). The script deletes the file immediately. Values are never on the command line, so `ps` cannot show them.
- Printed commands show `VAR=<hidden>`. The output of `envars print -d` is never printed.
- If the comparison fails, the script prints the key names and "value differs", not the values.
- The envars subprocesses get `_TYPER_STANDARD_TRACEBACK=1`. A Typer traceback then cannot show local variables, which can hold decrypted values.
- If a decrypt fails, or a secret has no value or an empty value, the script stops. It does not write an empty or `None` secret.
- When a command that handles values fails, the script does not print its error text, because the text can quote part of a value. Run that command by hand to see the error.

## How to run it

envars v1 and envars2 both install a command called `envars`. Install them in different environments, and give the path to each one.

```bash
AWS_PROFILE=TOMaster AWS_REGION=eu-west-1 python scripts/migrate_v1.py \
    --envars-v1-cmd ~/.local/bin/envars \
    --envars-v2-cmd /path/to/envars2-venv/bin/envars \
    --kms-key projects/tog-prod-sec-core-0/locations/europe-west2/keyRings/prod-europe-west2/cryptoKeys/tog-data-apps
```

- `--kms-key` is required. Use `tog-data-apps` for data-apps and `tog-gp-apps` for gp apps. The key controls who can decrypt the secrets later. For example, the Composer service accounts can decrypt only with `tog-data-apps`.
- `--quota-project tog-prod-sec-core-0`: use this if KMS calls fail with `SERVICE_DISABLED` / "API has not been used in project …". This happens when your ADC default quota project has the KMS API disabled.
- `--environments` migrates (and decrypts) only the environments you name.
- `--v1-file`, `--output` and `--app` change the defaults.

When you see `Verification SUCCESS`, move `envars.yml.v2` to `envars.yml` and delete `envars.yml.v1.bk`.

## After the file

The application must then read its settings with envars2. For a data-app, replace the `envars print --decrypt` subprocess with `get_env(env=env)` from `envars.main` (see [Library Usage](../api-reference/index.md)). Then:

- change the requirement from envars v1 to envars2. The package name is `envars` in both, so use the Git requirement from the README, for example `envars @ git+https://github.com/timeoutdigital/envars2@1.0.4` (or `git+https://github.com/timeoutdigital/envars2@1.0.4` in `requirements.in`);
- add the `envars-validate` pre-commit hook;
- change the CI build so that it installs envars2.

**If the v1 file uses `{{ STAGE }}`:** the script changes it to `{{ env.get("ENVARS_ENV") }}`. The envars CLI sets `ENVARS_ENV`, but `get_env()` does not. So before you call `get_env(env=env)`, set `os.environ["ENVARS_ENV"] = env`. If you do not, the value is `None`. The script prints a note when this applies.

**If the v2 file has locations:** they keep the v1 AWS account IDs. With a GCP KMS key, `get_env()` tries to find the location from the GCP project, and fails. Pass the location: `get_env(env=env, loc="master")`. The script prints a note when this applies. Data-apps have no locations.
