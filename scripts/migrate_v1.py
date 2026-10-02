#!/usr/bin/env python3
"""Migrate an envars v1 `envars.yml` to envars2, re-encrypting secrets with a GCP KMS key.

envars v1 and envars2 both install a command called `envars`, so they must live in separate
environments and both paths are passed in. Secrets are decrypted with envars v1 (this needs AWS
credentials for the old KMS key) and handed to envars2 through mode-600 temp files, never on the
command line. Nothing this script prints contains a value.

Example:
    KMS_KEY=projects/tog-prod-sec-core-0/locations/europe-west2/keyRings/prod-europe-west2/cryptoKeys/tog-data-apps
    AWS_PROFILE=TOMaster python scripts/migrate_v1.py \
        --envars-v1-cmd ~/.local/bin/envars \
        --envars-v2-cmd .venv/bin/envars \
        --kms-key "$KMS_KEY" \
        --quota-project tog-prod-sec-core-0
"""

import argparse
import os
import shutil
import subprocess  # noqa: S404
import sys
import tempfile

import yaml

V1_ACCOUNTS = ["master", "sandbox"]
V2_LOCATION_IDS = {"master": "511042647617", "sandbox": "253613363555"}


class Secret:
    """A v1 `!secret` value. Only the ciphertext is held, and it is never printed."""

    def __init__(self, value):
        self.value = value

    def __repr__(self):
        """Never show the ciphertext."""
        return "SECRET_PLACEHOLDER"


def _secret_constructor(loader, node):
    return Secret(loader.construct_scalar(node))


yaml.add_constructor("!secret", _secret_constructor, Loader=yaml.SafeLoader)


def subprocess_env(quota_project=None):
    """Return the environment for envars subprocesses.

    Typer's rich tracebacks can show local variables, which may hold decrypted values, so plain
    tracebacks are forced. A quota project is set when the caller's ADC default has KMS disabled.
    """
    env = dict(os.environ, _TYPER_STANDARD_TRACEBACK="1")
    if quota_project:
        env["GOOGLE_CLOUD_QUOTA_PROJECT"] = quota_project
    return env


def redact(cmd):
    """Return cmd for display, with the value of any VAR=value argument hidden."""
    shown = []
    for arg in cmd:
        if "=" in arg and not arg.startswith("-") and arg.split("=", 1)[0].isupper():
            arg = arg.split("=", 1)[0] + "=<hidden>"
        shown.append(arg)
    return " ".join(shown)


def run_command(cmd, env, verbose=True):
    """Run cmd and stop the migration on failure. Output that may hold values is never printed."""
    if verbose:
        print(f"Running: {redact(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, env=env)  # noqa: S603
    if result.returncode != 0:
        print(f"Error: command failed ({result.returncode}): {redact(cmd)}", file=sys.stderr)
        print(f"Stderr: {result.stderr}", file=sys.stderr)
        raise SystemExit(1)
    return result


def parse_env_output(output):
    """Parse KEY=value lines into a dict."""
    values = {}
    for line in output.splitlines():
        if "=" in line:
            key, val = line.split("=", 1)
            values[key.strip()] = val.strip()
    return values


def has_secrets(node):
    """Return True if node contains any `!secret` value."""
    if isinstance(node, Secret):
        return True
    if isinstance(node, dict):
        return any(has_secrets(v) for v in node.values())
    return False


def uses_account(node, account):
    """Return True if any value in node is scoped to the v1 account."""
    if isinstance(node, dict):
        return account in node or any(uses_account(v, account) for v in node.values())
    return False


def extract_data(data, args, env):
    """Decrypt every env and env:account combination the file needs. Skipped if there are no secrets."""
    original_vars = data.get("environment_variables", {})
    envs = data.get("configuration", {}).get("ENVIRONMENTS", [])
    extracted = {var: {} for var in original_vars}
    if not has_secrets(original_vars):
        print("No !secret values: nothing to decrypt.", file=sys.stderr)
        return extracted

    accounts = [a for a in V1_ACCOUNTS if uses_account(original_vars, a)]
    for stage in envs:
        for account in [None, *accounts]:
            cmd = [args.envars_v1_cmd, "-f", args.v1_file, "print", "-d", "-e", stage]
            key_suffix = ""
            if account:
                cmd.extend(["-a", account])
                key_suffix = f":{account}"
            print(f"Fetching decrypted values for {stage}{key_suffix}...", file=sys.stderr)
            resolved = parse_env_output(run_command(cmd, env, verbose=False).stdout)
            for var in extracted:
                if var in resolved:
                    extracted[var][f"{stage}{key_suffix}"] = resolved[var]
    return extracted


def fix_value(val):
    """Rewrite v1 template references that would be circular in envars2."""
    if val is None:
        return val
    val_str = str(val)
    if "{{ STAGE }}" in val_str:
        val_str = val_str.replace("{{ STAGE }}", '{{ env.get("ENVARS_ENV") }}')
    if '{{ RELEASE|default("not-set") }}' in val_str:
        val_str = val_str.replace('{{ RELEASE|default("not-set") }}', '{{ env.get("RELEASE", "not-set") }}')
    elif "{{ RELEASE }}" in val_str:
        val_str = val_str.replace("{{ RELEASE }}", '{{ env.get("RELEASE") }}')
    return val_str


class V2Writer:
    """Adds values to the v2 file. Secrets go through a mode-600 temp file, not argv."""

    def __init__(self, envars_v2_cmd, output, tmpdir, env):
        self.base_cmd = [envars_v2_cmd, "-f", output]
        self.tmpdir = tmpdir
        self.env = env
        self.described = set()

    def add(self, var_name, val, description, stage=None, loc=None, secret=False):
        scope = "/".join(s for s in (stage, loc) if s) or "default"
        if val is None:
            if secret:
                print(f"Error: no decrypted value for secret {var_name} ({scope}).", file=sys.stderr)
                raise SystemExit(1)
            print(f"Warning: {var_name} ({scope}) is null in v1, skipped.", file=sys.stderr)
            return
        path = os.path.join(self.tmpdir, "value")
        if secret:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w") as f:
                f.write(val)
            cmd = [*self.base_cmd, "add", "--var-name", var_name, "--value-from-file", path, "--secret"]
        else:
            cmd = [*self.base_cmd, "add", f"{var_name}={val}", "--no-secret"]
        if stage:
            cmd.extend(["--env", stage])
        if loc:
            cmd.extend(["--loc", loc])
        if var_name not in self.described:
            cmd.extend(["--description", description])
            self.described.add(var_name)
        try:
            run_command(cmd, self.env)
        finally:
            if secret and os.path.exists(path):
                os.remove(path)


def write_v2(raw_v1_data, extracted_data, target_envs, writer):
    """Add every v1 value to the v2 file, scoping secret defaults per environment."""
    for var_name, env_details in raw_v1_data.get("environment_variables", {}).items():
        description = "Description for " + var_name
        if isinstance(env_details, dict) and "description" in env_details:
            description = env_details["description"]

        # 1. Default
        v1_default = env_details.get("default") if isinstance(env_details, dict) else env_details
        if isinstance(v1_default, dict):
            for loc, val in v1_default.items():
                is_secret = isinstance(val, Secret)
                if is_secret:
                    # Resolve a location-scoped secret default from the first environment.
                    val = extracted_data[var_name].get(f"{target_envs[0]}:{loc}")
                writer.add(var_name, fix_value(val), description, loc=loc, secret=is_secret)
        elif v1_default is not None and not isinstance(v1_default, Secret):
            # Secrets must be scoped in v2, so a secret default is added per environment below.
            writer.add(var_name, fix_value(v1_default), description)

        # 2. Environment overrides
        if not isinstance(env_details, dict):
            continue
        for stage in target_envs:
            if stage in env_details:
                v1_val = env_details[stage]
                if isinstance(v1_val, dict):
                    for loc, val in v1_val.items():
                        is_secret = isinstance(val, Secret)
                        if is_secret:
                            val = extracted_data[var_name].get(f"{stage}:{loc}")
                        writer.add(var_name, fix_value(val), description, stage=stage, loc=loc, secret=is_secret)
                else:
                    is_secret = isinstance(v1_val, Secret)
                    val = extracted_data[var_name].get(stage) if is_secret else v1_val
                    writer.add(var_name, fix_value(val), description, stage=stage, secret=is_secret)
            elif isinstance(v1_default, Secret):
                # Propagate a secret default to every environment without its own override.
                writer.add(
                    var_name, fix_value(extracted_data[var_name].get(stage)), description, stage=stage, secret=True
                )


def verify_migration(args, backup_path, envs, accounts, env):
    """Compare resolved v1 and v2 output for every env x location. Prints key names only, never values."""
    print("\nVerifying migration...")
    run_command([args.envars_v2_cmd, "-f", args.output, "validate"], env)

    failed = False
    for stage in envs:
        for account in accounts:
            v1_cmd = [args.envars_v1_cmd, "-f", backup_path, "print", "-e", stage, "-d"]
            v2_cmd = [args.envars_v2_cmd, "-f", args.output, "output", "-e", stage]
            if account:
                v1_cmd += ["-a", account]
                v2_cmd += ["-l", account]
            v1 = parse_env_output(run_command(v1_cmd, env, verbose=False).stdout)
            v2 = parse_env_output(run_command(v2_cmd, env, verbose=False).stdout)
            diffs = []
            for key in sorted(set(v1) | set(v2)):
                if v1.get(key) == v2.get(key):
                    continue
                if key == "RELEASE" and "{{ RELEASE" in str(v1.get(key)) and v2.get(key) == "not-set":
                    continue
                state = "missing in v2" if key not in v2 else "missing in v1" if key not in v1 else "value differs"
                diffs.append(f"  {key}: {state}")
            label = f"{stage}/{account or '-'}"
            if diffs:
                failed = True
                print(f"{label}: FAILED")
                print("\n".join(diffs))
            else:
                print(f"{label}: match ({len(v1)} vars)")
    if failed:
        print("Verification FAILED.")
        raise SystemExit(1)
    print("Verification SUCCESS: v1 and v2 outputs match for every env and location.")


def migrate(args):
    env = subprocess_env(args.quota_project)

    print(f"Reading {args.v1_file}...")
    with open(args.v1_file) as f:
        raw_v1_data = yaml.safe_load(f)

    config = raw_v1_data.get("configuration", {})
    if not ("KMS_KEY_ARN" in config or "APP" in config or "ENVIRONMENTS" in config):
        print(f"Error: {args.v1_file} does not appear to be a v1 file. Aborting.", file=sys.stderr)
        raise SystemExit(1)

    extracted_data = extract_data(raw_v1_data, args, env)

    backup_path = f"{args.v1_file}.v1.bk"
    print(f"Backing up {args.v1_file} to {backup_path} (do not commit it)")
    shutil.copy2(args.v1_file, backup_path)

    target_app = args.app or config.get("APP", "myapp")
    target_envs = args.environments.split(",") if args.environments else config.get("ENVIRONMENTS", [])
    v1_vars = raw_v1_data.get("environment_variables", {})
    # Only declare v2 locations for v1 accounts the file actually scopes values by.
    locations = [a for a in V1_ACCOUNTS if uses_account(v1_vars, a)]

    if os.path.exists(args.output):
        print(f"{args.output} exists. Overwriting.")
        os.remove(args.output)

    print(f"Initializing {args.output}...")
    init_cmd = [
        args.envars_v2_cmd,
        "-f",
        args.output,
        "init",
        "--app",
        target_app,
        "--env",
        ",".join(target_envs),
        "--kms-key",
        args.kms_key,
        "--description-mandatory",
    ]
    if locations:
        init_cmd += ["--loc", ",".join(f"{a}:{V2_LOCATION_IDS[a]}" for a in locations)]
    run_command(init_cmd, env)

    with tempfile.TemporaryDirectory() as tmpdir:
        os.chmod(tmpdir, 0o700)
        write_v2(raw_v1_data, extracted_data, target_envs, V2Writer(args.envars_v2_cmd, args.output, tmpdir, env))

    print(f"Migration complete. Created {args.output}.")
    verify_migration(args, backup_path, target_envs, locations or [None], env)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Migrate envars.yml from envars v1 to envars2")
    parser.add_argument("--v1-file", default="envars.yml", help="Path to the v1 envars file")
    parser.add_argument("--output", default="envars.yml.v2", help="Path to write the v2 envars file")
    parser.add_argument("--envars-v1-cmd", default="envars", help="Command for envars v1")
    parser.add_argument(
        "--envars-v2-cmd", required=True, help="Command for envars2 (both versions install a command called `envars`)"
    )
    parser.add_argument(
        "--kms-key",
        required=True,
        help="GCP KMS key for v2, e.g. .../cryptoKeys/tog-data-apps for data-apps or .../tog-gp-apps for gp apps",
    )
    parser.add_argument(
        "--quota-project",
        help="GCP quota project for KMS calls, if your ADC default project has the KMS API disabled",
    )
    parser.add_argument("--app", help="Application name (overrides v1)")
    parser.add_argument("--environments", help="Comma-separated environments (overrides v1)")
    return parser.parse_args(argv)


def main():
    migrate(parse_args())


if __name__ == "__main__":
    main()
