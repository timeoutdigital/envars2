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


def test_fix_value():
    assert m.fix_value("{{ STAGE }}-x") == '{{ env.get("ENVARS_ENV") }}-x'
    assert m.fix_value('{{ RELEASE|default("not-set") }}') == '{{ env.get("RELEASE", "not-set") }}'
    assert m.fix_value("{{ RELEASE }}") == '{{ env.get("RELEASE") }}'
    assert m.fix_value(None) is None


def test_subprocess_env(monkeypatch):
    monkeypatch.delenv("GOOGLE_CLOUD_QUOTA_PROJECT", raising=False)
    env = m.subprocess_env("tog-prod-sec-core-0")
    assert env["_TYPER_STANDARD_TRACEBACK"] == "1"
    assert env["GOOGLE_CLOUD_QUOTA_PROJECT"] == "tog-prod-sec-core-0"
    assert "GOOGLE_CLOUD_QUOTA_PROJECT" not in m.subprocess_env(None)


def test_writer_passes_secrets_by_file_not_argv(tmp_path, monkeypatch, capsys):
    calls = []

    def fake_run(cmd, env, verbose=True):
        path = cmd[cmd.index("--value-from-file") + 1]
        mode = stat.S_IMODE(os.stat(path).st_mode)
        with open(path) as f:
            calls.append((cmd, f.read(), mode))
        print(f"Running: {m.redact(cmd)}")

    monkeypatch.setattr(m, "run_command", fake_run)
    writer = m.V2Writer("envars", "out.yml", str(tmp_path), {})
    writer.add("API_KEY", LEAK_CANARY, "desc", stage="prod", secret=True)

    cmd, written, mode = calls[0]
    assert LEAK_CANARY not in " ".join(cmd)
    assert written == LEAK_CANARY
    assert mode == 0o600
    assert "--secret" in cmd and "--no-secret" not in cmd
    assert not os.listdir(tmp_path), "the value file must be removed"
    assert LEAK_CANARY not in capsys.readouterr().out


def test_writer_fails_on_missing_secret_and_skips_null_plain(tmp_path, monkeypatch):
    monkeypatch.setattr(m, "run_command", lambda *a, **k: pytest.fail("must not run"))
    writer = m.V2Writer("envars", "out.yml", str(tmp_path), {})
    with pytest.raises(SystemExit):
        writer.add("API_KEY", None, "desc", stage="prod", secret=True)
    writer.add("PLAIN", None, "desc", stage="prod")


def test_write_v2_scopes_secret_defaults_per_env(monkeypatch):
    added = []

    class FakeWriter:
        def add(self, var_name, val, description, stage=None, loc=None, secret=False):
            added.append((var_name, val, stage, loc, secret))

    raw = {
        "environment_variables": {
            "TOKEN": {"description": "d", "default": m.Secret("ct")},
            "HOST": {"description": "h", "default": "a", "prod": "b"},
        }
    }
    extracted = {"TOKEN": {"staging": "t-stg", "prod": "t-prd"}, "HOST": {}}
    m.write_v2(raw, extracted, ["staging", "prod"], FakeWriter())

    assert ("TOKEN", "t-stg", "staging", None, True) in added
    assert ("TOKEN", "t-prd", "prod", None, True) in added
    assert not any(a[0] == "TOKEN" and a[2] is None for a in added), "secrets must not get a global default"
    assert ("HOST", "a", None, None, False) in added
    assert ("HOST", "b", "prod", None, False) in added


def test_verify_prints_key_names_not_values(monkeypatch, capsys):
    outputs = iter(["A=1\n", "A=1\n", f"B={LEAK_CANARY}\n", "B=other\n"])

    def fake_run(cmd, env, verbose=True):
        return SimpleNamespace(stdout="" if "validate" in cmd else next(outputs))

    monkeypatch.setattr(m, "run_command", fake_run)
    args = SimpleNamespace(envars_v1_cmd="v1", envars_v2_cmd="v2", output="out.yml")
    with pytest.raises(SystemExit):
        m.verify_migration(args, "bk", ["staging", "prod"], [None], {})
    out = capsys.readouterr().out
    assert "staging/-: match" in out
    assert "B: value differs" in out
    assert LEAK_CANARY not in out


FAKE_V1 = textwrap.dedent(
    """\
    import sys, yaml
    args = sys.argv[1:]
    data = yaml.safe_load(open(args[args.index("-f") + 1]))
    env = args[args.index("-e") + 1]
    for name, details in data["environment_variables"].items():
        val = details.get(env, details.get("default")) if isinstance(details, dict) else details
        if val is not None:
            print(f"{name}={val}")
    """
)


@pytest.mark.skipif(shutil.which("envars") is None, reason="envars2 CLI not on PATH")
def test_end_to_end_plain_file(tmp_path, monkeypatch):
    v1_file = tmp_path / "envars.yml"
    v1_file.write_text(
        yaml.safe_dump(
            {
                "configuration": {"APP": "da-test", "ENVIRONMENTS": ["dev", "prod"], "KMS_KEY_ARN": "arn:aws:kms:x"},
                "environment_variables": {
                    "LAND_PRJ": {"description": "Landing project", "dev": "tog-dev-dt-lnd"},
                    "LOG_LEVEL": {"description": "Log level", "default": "INFO", "prod": "WARNING"},
                },
            }
        )
    )
    fake_v1 = tmp_path / "fake_v1"
    fake_v1.write_text(f"#!{sys.executable}\n{FAKE_V1}")
    fake_v1.chmod(0o755)
    monkeypatch.chdir(tmp_path)

    m.migrate(
        m.parse_args(
            [
                "--envars-v1-cmd",
                str(fake_v1),
                "--envars-v2-cmd",
                shutil.which("envars") or "envars",
                "--kms-key",
                "projects/p/locations/l/keyRings/r/cryptoKeys/k",
            ]
        )
    )

    out = yaml.safe_load((tmp_path / "envars.yml.v2").read_text())
    assert out["configuration"]["kms_key"] == "projects/p/locations/l/keyRings/r/cryptoKeys/k"
    assert "locations" not in out["configuration"], "no v1 accounts used, so no v2 locations"
    assert out["environment_variables"]["LAND_PRJ"]["dev"] == "tog-dev-dt-lnd"
    assert out["environment_variables"]["LOG_LEVEL"]["default"] == "INFO"
    assert out["environment_variables"]["LOG_LEVEL"]["prod"] == "WARNING"
