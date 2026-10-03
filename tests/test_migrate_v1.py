import os
import shutil
import stat
import sys
import textwrap
from types import SimpleNamespace

import pytest
import yaml

from scripts import migrate_v1 as m

LEAK_CANARY = "s3cr3t-value-that-must-not-leak"


def test_redact_hides_values_and_keeps_flags():
    cmd = ["envars", "-f", "x.yml", "add", f"API_KEY={LEAK_CANARY}", "--env", "prod", "--description", "a=b"]
    shown = m.redact(cmd)
    assert LEAK_CANARY not in shown
    assert "API_KEY=<hidden>" in shown
    assert "--env prod" in shown
    # Lower-case "a=b" is not a VAR=value assignment, so it is shown as is.
    assert "a=b" in shown


def test_has_secrets_and_uses_account():
    data = {"A": {"prod": m.Secret("x")}, "B": {"default": {"master": "1"}}}
    assert m.has_secrets(data)
    assert not m.has_secrets({"A": {"prod": "plain"}})
    assert m.uses_account(data, "master")
    assert not m.uses_account(data, "sandbox")


def test_fix_value_and_stage_detection():
    assert m.fix_value("{{ STAGE }}-x") == '{{ env.get("ENVARS_ENV") }}-x'
    assert m.fix_value('{{ RELEASE|default("not-set") }}') == '{{ env.get("RELEASE", "not-set") }}'
    assert m.fix_value("{{ RELEASE }}") == '{{ env.get("RELEASE") }}'
    assert m.fix_value(None) is None
    assert m.uses_stage_template({"environment_variables": {"A": {"default": "x-{{ STAGE }}"}}})
    assert not m.uses_stage_template({"environment_variables": {"A": {"default": "x"}}})


def test_subprocess_env(monkeypatch):
    monkeypatch.delenv("GOOGLE_CLOUD_QUOTA_PROJECT", raising=False)
    env = m.subprocess_env("tog-prod-sec-core-0")
    assert env["_TYPER_STANDARD_TRACEBACK"] == "1"
    assert env["GOOGLE_CLOUD_QUOTA_PROJECT"] == "tog-prod-sec-core-0"
    assert "GOOGLE_CLOUD_QUOTA_PROJECT" not in m.subprocess_env(None)


def test_run_command_hides_stderr_for_value_commands(capsys):
    # The child gets the value from its environment, as a decrypted value would reach it, not from argv.
    script = "import os, sys; sys.stderr.write('template error near ' + os.environ['CANARY']); sys.exit(1)"
    with pytest.raises(SystemExit):
        m.run_command(
            [sys.executable, "-c", script], dict(os.environ, CANARY=LEAK_CANARY), verbose=False, show_stderr=False
        )
    err = capsys.readouterr().err
    assert LEAK_CANARY not in err
    assert "Stderr hidden" in err


def test_writer_passes_secrets_by_file_not_argv(tmp_path, monkeypatch, capsys):
    calls = []

    def fake_run(cmd, env, verbose=True, show_stderr=True):
        path = cmd[cmd.index("--value-from-file") + 1]
        mode = stat.S_IMODE(os.stat(path).st_mode)
        with open(path) as f:
            calls.append((cmd, f.read(), mode, show_stderr))
        print(f"Running: {m.redact(cmd)}")

    monkeypatch.setattr(m, "run_command", fake_run)
    writer = m.V2Writer("envars", "out.yml", str(tmp_path), {})
    writer.add("API_KEY", LEAK_CANARY, "desc", stage="prod", secret=True)

    cmd, written, mode, show_stderr = calls[0]
    assert LEAK_CANARY not in " ".join(cmd)
    assert written == LEAK_CANARY
    assert mode == 0o600
    assert show_stderr is False
    assert "--secret" in cmd and "--no-secret" not in cmd
    assert not os.listdir(tmp_path), "the value file must be removed"
    assert LEAK_CANARY not in capsys.readouterr().out


@pytest.mark.parametrize("missing", [None, ""])
def test_writer_rejects_missing_or_empty_secret(tmp_path, monkeypatch, missing):
    monkeypatch.setattr(m, "run_command", lambda *a, **k: pytest.fail("must not run"))
    writer = m.V2Writer("envars", "out.yml", str(tmp_path), {})
    with pytest.raises(SystemExit):
        writer.add("API_KEY", missing, "desc", stage="prod", secret=True)
    writer.add("PLAIN", None, "desc", stage="prod")  # a null plain value is skipped, not an error


class FakeWriter:
    def __init__(self):
        self.added = []

    def add(self, var_name, val, description, stage=None, loc=None, secret=False):
        self.added.append((var_name, val, stage, loc, secret))


def test_write_v2_scopes_secret_defaults_per_env():
    raw = {
        "environment_variables": {
            "TOKEN": {"description": "d", "default": m.Secret("ct")},
            "HOST": {"description": "h", "default": "a", "prod": "b"},
        }
    }
    extracted = {"TOKEN": {"staging": "t-stg", "prod": "t-prd"}, "HOST": {}}
    w = FakeWriter()
    m.write_v2(raw, extracted, ["staging", "prod"], w)

    assert ("TOKEN", "t-stg", "staging", None, True) in w.added
    assert ("TOKEN", "t-prd", "prod", None, True) in w.added
    assert not any(a[0] == "TOKEN" and a[2] is None for a in w.added), "secrets must not get a global default"
    assert ("HOST", "a", None, None, False) in w.added
    assert ("HOST", "b", "prod", None, False) in w.added


def test_write_v2_handles_top_level_scalar_secret():
    raw = {"environment_variables": {"TOKEN": m.Secret("ct")}}
    w = FakeWriter()
    m.write_v2(raw, {"TOKEN": {"staging": "t-stg", "prod": "t-prd"}}, ["staging", "prod"], w)
    assert ("TOKEN", "t-stg", "staging", None, True) in w.added
    assert ("TOKEN", "t-prd", "prod", None, True) in w.added


def test_write_v2_location_secret_default_uses_each_scopes_own_value():
    # prod overrides master; staging inherits the master default. The master default must not take
    # prod's value, and staging/master must get its own resolved value.
    raw = {
        "environment_variables": {
            "TOKEN": {"description": "d", "default": {"master": m.Secret("a")}, "prod": {"master": m.Secret("b")}}
        }
    }
    extracted = {"TOKEN": {"staging:master": "A", "prod:master": "B"}}
    w = FakeWriter()
    m.write_v2(raw, extracted, ["prod", "staging"], w)
    assert ("TOKEN", "B", "prod", "master", True) in w.added
    assert ("TOKEN", "A", "staging", "master", True) in w.added
    assert not any(a[2] is None for a in w.added), "no unscoped location default for a secret"
    assert len(w.added) == 2


def test_write_v2_partial_location_override_keeps_env_fallback():
    # A secret default plus a prod/master override: prod/sandbox must still get the inherited value.
    raw = {"environment_variables": {"TOKEN": {"default": m.Secret("d"), "prod": {"master": m.Secret("o")}}}}
    extracted = {"TOKEN": {"prod": "D", "prod:master": "O"}}
    w = FakeWriter()
    m.write_v2(raw, extracted, ["prod"], w)
    assert ("TOKEN", "O", "prod", "master", True) in w.added
    assert ("TOKEN", "D", "prod", None, True) in w.added


def test_extract_uses_target_envs_only(monkeypatch):
    seen = []

    def fake_v1_values(args, path, stage, account, env):
        seen.append((stage, account))
        return {"TOKEN": f"v-{stage}"}

    monkeypatch.setattr(m, "v1_values", fake_v1_values)
    data = {
        "configuration": {"ENVIRONMENTS": ["dev", "staging", "prod"]},
        "environment_variables": {"TOKEN": m.Secret("x")},
    }
    out = m.extract_data(data, SimpleNamespace(v1_file="f"), ["prod"], [], {})
    assert seen == [("prod", None)]
    assert out == {"TOKEN": {"prod": "v-prod"}}


def test_verify_compares_exact_values_and_prints_key_names_only(monkeypatch, capsys):
    v1 = iter([{"A": "1"}, {"B": LEAK_CANARY, "C": " padded "}])
    v2 = iter([{"A": "1"}, {"B": "other", "C": "padded"}])
    monkeypatch.setattr(m, "run_command", lambda *a, **k: SimpleNamespace(stdout=""))
    monkeypatch.setattr(m, "v1_values", lambda *a: next(v1))
    monkeypatch.setattr(m, "v2_values", lambda *a: next(v2))
    args = SimpleNamespace(envars_v1_cmd="v1", envars_v2_cmd="v2", output="out.yml")
    with pytest.raises(SystemExit):
        m.verify_migration(args, "bk", ["staging", "prod"], [None], {})
    out = capsys.readouterr().out
    assert "staging/-: match" in out
    assert "B: value differs" in out
    assert "C: value differs" in out, "whitespace is significant"
    assert LEAK_CANARY not in out


def test_migrate_rejects_no_environments(tmp_path):
    v1_file = tmp_path / "envars.yml"
    v1_file.write_text(yaml.safe_dump({"configuration": {"APP": "x"}, "environment_variables": {}}))
    with pytest.raises(SystemExit):
        m.migrate(m.parse_args(["--v1-file", str(v1_file), "--envars-v2-cmd", "envars", "--kms-key", "k"]))


# A small stand-in for envars v1 `print -y`: resolves default + env override, dumps {"envars": ...}.
FAKE_V1 = textwrap.dedent(
    """\
    import sys, yaml
    args = sys.argv[1:]
    data = yaml.safe_load(open(args[args.index("-f") + 1]))
    env = args[args.index("-e") + 1]
    out = {}
    for name, details in data["environment_variables"].items():
        val = details.get(env, details.get("default")) if isinstance(details, dict) else details
        if val is not None:
            out[name] = val
    print(yaml.dump({"envars": out}, default_flow_style=False))
    """
)


@pytest.mark.skipif(shutil.which("envars") is None, reason="envars2 CLI not on PATH")
def test_end_to_end_plain_file(tmp_path):
    v1_file = tmp_path / "envars.yml"
    output = tmp_path / "envars.yml.v2"
    v1_file.write_text(
        yaml.safe_dump(
            {
                "configuration": {"APP": "da-test", "ENVIRONMENTS": ["dev", "prod"], "KMS_KEY_ARN": "arn:aws:kms:x"},
                "environment_variables": {
                    "LAND_PRJ": {"description": "Landing project", "dev": "tog-dev-dt-lnd"},
                    "LOG_LEVEL": {"description": "Log level", "default": "INFO", "prod": "WARNING"},
                    "BANNER": {"description": "Multi-line value", "default": "line one\nline two"},
                    "PADDED": {"description": "Significant spaces", "default": "  keep me  "},
                },
            }
        )
    )
    fake_v1 = tmp_path / "fake_v1"
    fake_v1.write_text(f"#!{sys.executable}\n{FAKE_V1}")
    fake_v1.chmod(0o755)

    # No chdir: CI sets GOOGLE_APPLICATION_CREDENTIALS to a path relative to the repo root.
    m.migrate(
        m.parse_args(
            [
                "--v1-file",
                str(v1_file),
                "--output",
                str(output),
                "--envars-v1-cmd",
                str(fake_v1),
                "--envars-v2-cmd",
                shutil.which("envars") or "envars",
                "--kms-key",
                "projects/p/locations/l/keyRings/r/cryptoKeys/k",
            ]
        )
    )

    out = yaml.safe_load(output.read_text())
    assert out["configuration"]["kms_key"] == "projects/p/locations/l/keyRings/r/cryptoKeys/k"
    assert "locations" not in out["configuration"], "no v1 accounts used, so no v2 locations"
    assert out["environment_variables"]["LAND_PRJ"]["dev"] == "tog-dev-dt-lnd"
    assert out["environment_variables"]["LOG_LEVEL"]["prod"] == "WARNING"
    assert out["environment_variables"]["BANNER"]["default"] == "line one\nline two"
    assert out["environment_variables"]["PADDED"]["default"] == "  keep me  "
