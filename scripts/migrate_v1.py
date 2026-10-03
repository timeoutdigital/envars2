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
import json
import os
import shutil
import subprocess  # noqa: S404
import sys
import tempfile

import yaml

V1_ACCOUNTS = ["master", "sandbox"]
V2_LOCATION_IDS = {"master": "511042647617", "sandbox": "253613363555"}
VERIFY_RELEASE = "migrate-v1-verify"


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


def run_command(cmd, env, verbose=True, show_stderr=True):
    """Run cmd and stop the migration on failure.

    Set show_stderr=False for any command that handles values: its error text (for example a
    template error) can quote part of a decrypted value.
    """
    if verbose:
        print(f"Running: {redact(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, env=env)  # noqa: S603
    if result.returncode != 0:
        print(f"Error: command failed ({result.returncode}): {redact(cmd)}", file=sys.stderr)
        if show_stderr:
            print(f"Stderr: {result.stderr}", file=sys.stderr)
        else:
            print("Stderr hidden: this command handles values. Re-run it by hand to see the error.", file=sys.stderr)
        raise SystemExit(1)
    return result


def _as_str(value):
    return None if value is None else str(value)


def v1_values(args, path, stage, account, env):
    """Return the resolved v1 values for stage (and account), losslessly, from `envars print -y`."""
    cmd = [args.envars_v1_cmd, "-f", path, "print", "-d", "-y", "-e", stage]
    if account:
        cmd.extend(["-a", account])
    out = yaml.safe_load(run_command(cmd, env, verbose=False, show_stderr=False).stdout) or {}
    return {k: _as_str(v) for k, v in (out.get("envars") or {}).items()}


def v2_values(args, stage, account, env):
    """Return the resolved v2 values for stage (and location), losslessly, from `envars output --format json`."""
    cmd = [args.envars_v2_cmd, "-f", args.output, "output", "-e", stage, "--format", "json"]
    if account:
        cmd.extend(["-l", account])
    out = json.loads(run_command(cmd, env, verbose=False, show_stderr=False).stdout)
    return {k: _as_str(v) for k, v in out["envars"].items()}


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


def extract_data(data, args, target_envs, accounts, env):
    """Decrypt every target env and env:account the file needs. Skipped if there are no secrets."""
    original_vars = data.get("environment_variables", {})
    extracted = {var: {} for var in original_vars}
    if not has_secrets(original_vars):
        print("No !secret values: nothing to decrypt.", file=sys.stderr)
        return extracted

    for stage in target_envs:
        for account in [None, *accounts]:
            key = f"{stage}:{account}" if account else stage
            print(f"Fetching decrypted values for {key}...", file=sys.stderr)
            resolved = v1_values(args, args.v1_file, stage, account, env)
            for var in extracted:
                if var in resolved:
                    extracted[var][key] = resolved[var]
    return extracted


def fix_value(val):
    """Rewrite v1 template references that would be circular in envars2."""
    if val is None:
        return val
    val_str = str(val)
    if "{{ STAGE }}" in val_str:
        val_str = val_str.replace("{{ STAGE }}", '{{ env.get("ENVARS_ENV") }}')
    # v1 rendered {{ RELEASE }} from RELEASE_SHA. Keep that input, and accept RELEASE too.
    val_str = val_str.replace(
        '{{ RELEASE|default("not-set") }}', '{{ env.get("RELEASE") or env.get("RELEASE_SHA", "not-set") }}'
    )
    val_str = val_str.replace("{{ RELEASE }}", '{{ env.get("RELEASE") or env.get("RELEASE_SHA") }}')
    return val_str


def uses_stage_template(data):
    """Return True if any plain v1 value uses {{ STAGE }} (it becomes env.get("ENVARS_ENV") in v2)."""

    def walk(node):
        if isinstance(node, dict):
            return any(walk(v) for v in node.values())
        return isinstance(node, str) and "{{ STAGE }}" in node

    return walk(data.get("environment_variables", {}))


class V2Writer:
    """Adds values to the v2 file. Secrets go through a mode-600 temp file, not argv."""

    def __init__(self, envars_v2_cmd, output, tmpdir, env):
        self.base_cmd = [envars_v2_cmd, "-f", output]
        self.tmpdir = tmpdir
        self.env = env
        self.described = set()

    def add(self, var_name, val, description, stage=None, loc=None, secret=False):
        scope = "/".join(s for s in (stage, loc) if s) or "default"
        if secret and not val:
            # None means no decrypted value; "" would be written as an empty encrypted secret.
            print(f"Error: no decrypted value for secret {var_name} ({scope}).", file=sys.stderr)
            raise SystemExit(1)
        if val is None:
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
            run_command(cmd, self.env, show_stderr=not secret)
        finally:
            if secret and os.path.exists(path):
                os.remove(path)


class _Collector:
    """Records add() calls so that they can be written later in a different order."""

    def __init__(self):
        self.calls = []

    def add(self, var_name, val, description, stage=None, loc=None, secret=False):
        self.calls.append((var_name, val, description, stage, loc, secret))


def _specificity(call):
    """env+loc first, then env, then loc, then default."""
    stage, loc = call[3], call[4]
    return 0 if stage and loc else 1 if stage else 2 if loc else 3


def write_v2(raw_v1_data, extracted_data, target_envs, writer):
    """Add every v1 value to the v2 file, most specific scope first.

    envars2 needs a secret to be scoped, so an inherited secret default is written for each
    environment (and location) that has no override of its own, with that scope's own value.
    `envars add` checks template dependencies as it goes, so overrides are written before the
    defaults they replace: a default alone can look circular until its override exists.
    """
    collector = _Collector()
    _collect_v2(raw_v1_data, extracted_data, target_envs, collector)
    for var_name, val, description, stage, loc, secret in sorted(collector.calls, key=_specificity):
        writer.add(var_name, val, description, stage=stage, loc=loc, secret=secret)


def _collect_v2(raw_v1_data, extracted_data, target_envs, writer):
    for var_name, details in raw_v1_data.get("environment_variables", {}).items():
        if not isinstance(details, dict):
            details = {"default": details}
        description = details.get("description") or "Description for " + var_name
        default = details.get("default")
        values = extracted_data.get(var_name, {})

        # 1. Plain defaults. Secret defaults are written per environment below.
        if isinstance(default, dict):
            for loc, val in default.items():
                if not isinstance(val, Secret):
                    writer.add(var_name, fix_value(val), description, loc=loc)
        elif default is not None and not isinstance(default, Secret):
            writer.add(var_name, fix_value(default), description)

        # 2. Environment overrides, then inherited secret defaults
        for stage in target_envs:
            overridden_locs = set()
            if stage in details:
                override = details[stage]
                if isinstance(override, dict):
                    for loc, val in override.items():
                        is_secret = isinstance(val, Secret)
                        val = values.get(f"{stage}:{loc}") if is_secret else val
                        writer.add(var_name, fix_value(val), description, stage=stage, loc=loc, secret=is_secret)
                    overridden_locs = set(override)
                else:
                    is_secret = isinstance(override, Secret)
                    val = values.get(stage) if is_secret else override
                    writer.add(var_name, fix_value(val), description, stage=stage, secret=is_secret)
                    continue  # a scalar override covers every location
            if isinstance(default, Secret):
                writer.add(var_name, fix_value(values.get(stage)), description, stage=stage, secret=True)
            elif isinstance(default, dict):
                for loc, val in default.items():
                    if isinstance(val, Secret) and loc not in overridden_locs:
                        writer.add(
                            var_name,
                            fix_value(values.get(f"{stage}:{loc}")),
                            description,
                            stage=stage,
                            loc=loc,
                            secret=True,
                        )


def compare(v1, v2):
    """Return the differing keys as "KEY: state" lines. Values are never included."""
    diffs = []
    for key in sorted(set(v1) | set(v2)):
        if key in v1 and key in v2 and v1[key] == v2[key]:
            continue
        state = "missing in v2" if key not in v2 else "missing in v1" if key not in v1 else "value differs"
        diffs.append(f"  {key}: {state}")
    return diffs


def verify_migration(args, backup_path, envs, accounts, env):
    """Compare resolved v1 and v2 values for every env x location. Prints key names only, never values."""
    print("\nVerifying migration...")
    # Only the v1 input (RELEASE_SHA) is set, so the check proves that the old input still works.
    env = {k: v for k, v in env.items() if k != "RELEASE"}
    env["RELEASE_SHA"] = VERIFY_RELEASE
    run_command([args.envars_v2_cmd, "-f", args.output, "validate"], env)

    failed = False
    for stage in envs:
        for account in accounts:
            v1 = v1_values(args, backup_path, stage, account, env)
            v2 = v2_values(args, stage, account, env)
            diffs = compare(v1, v2)
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
    print("Verification SUCCESS: v1 and v2 values match exactly for every env and location.")


def migrate(args):
    env = subprocess_env(args.quota_project)

    print(f"Reading {args.v1_file}...")
    with open(args.v1_file) as f:
        raw_v1_data = yaml.safe_load(f)

    config = raw_v1_data.get("configuration", {})
    if not ("KMS_KEY_ARN" in config or "APP" in config or "ENVIRONMENTS" in config):
        print(f"Error: {args.v1_file} does not appear to be a v1 file. Aborting.", file=sys.stderr)
        raise SystemExit(1)

    target_app = args.app or config.get("APP", "myapp")
    target_envs = (
        [e.strip() for e in args.environments.split(",") if e.strip()]
        if args.environments
        else config.get("ENVIRONMENTS", [])
    )
    if not target_envs:
        print("Error: no environments (set ENVIRONMENTS in the v1 file or pass --environments).", file=sys.stderr)
        raise SystemExit(1)
    v1_vars = raw_v1_data.get("environment_variables", {})
    # Only declare v2 locations for v1 accounts the file actually scopes values by.
    locations = [a for a in V1_ACCOUNTS if uses_account(v1_vars, a)]

    extracted_data = extract_data(raw_v1_data, args, target_envs, locations, env)

    backup_path = f"{args.v1_file}.v1.bk"
    print(f"Backing up {args.v1_file} to {backup_path} (do not commit it)")
    shutil.copy2(args.v1_file, backup_path)

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
    if locations:
        print(
            f"\nNote: the v2 file has locations ({', '.join(locations)}) with AWS account IDs. With a GCP KMS key, "
            "get_env() matches locations against the GCP project, so it cannot find the location by itself: "
            'pass it, for example get_env(env=env, loc="master").'
        )
    if uses_stage_template(raw_v1_data):
        print(
            '\nNote: {{ STAGE }} became {{ env.get("ENVARS_ENV") }}. The envars CLI sets ENVARS_ENV, '
            "but the library's get_env() does not: set os.environ['ENVARS_ENV'] = env before calling it."
        )


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
