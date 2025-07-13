import base64
from unittest.mock import patch

import boto3
import yaml
from botocore.stub import Stubber
from typer.testing import CliRunner

from envars.cli import app

runner = CliRunner()


def create_envars_file(tmp_path, content=""):
    file_path = tmp_path / "envars.yml"
    file_path.write_text(content)
    return str(file_path)


def read_yaml_file(file_path):
    with open(file_path) as f:
        return yaml.safe_load(f)


def test_init_command(tmp_path):
    file_path = tmp_path / "envars.yml"
    result = runner.invoke(
        app,
        [
            "--file",
            str(file_path),
            "init",
            "--app",
            "MyApp",
            "--env",
            "dev,prod",
            "--loc",
            "aws:123,gcp:456",
            "--description-mandatory",
        ],
    )
    assert result.exit_code == 0
    assert "Successfully initialized" in result.stdout

    data = read_yaml_file(file_path)
    assert data["configuration"]["app"] == "MyApp"
    assert data["configuration"]["environments"] == ["dev", "prod"]
    assert {"aws": "123"} in data["configuration"]["locations"]
    assert {"gcp": "456"} in data["configuration"]["locations"]
    assert data["configuration"]["description_mandatory"] is True

    # Test with default value (False)
    file_path_default = tmp_path / "envars_default.yml"
    result = runner.invoke(
        app,
        [
            "--file",
            str(file_path_default),
            "init",
            "--app",
            "MyApp",
            "--env",
            "dev,prod",
            "--loc",
            "aws:123,gcp:456",
        ],
    )
    assert result.exit_code == 0
    data = read_yaml_file(file_path_default)
    assert data["configuration"]["description_mandatory"] is False


def test_add_default_variable(tmp_path):
    file_path = create_envars_file(tmp_path)
    result = runner.invoke(app, ["--file", file_path, "add", "MY_VAR=my_value"])
    assert result.exit_code == 0
    assert "Successfully added/updated MY_VAR in" in result.stdout

    data = read_yaml_file(file_path)
    assert data["environment_variables"]["MY_VAR"]["default"] == "my_value"


def test_add_env_variable(tmp_path):
    initial_content = """
configuration:
  environments:
    - dev
"""
    file_path = create_envars_file(tmp_path, initial_content)
    result = runner.invoke(app, ["--file", file_path, "add", "MY_VAR=dev_value", "--env", "dev"])
    assert result.exit_code == 0
    assert "Successfully added/updated MY_VAR in" in result.stdout

    data = read_yaml_file(file_path)
    assert data["environment_variables"]["MY_VAR"]["dev"] == "dev_value"


def test_add_loc_variable(tmp_path):
    initial_content = """
configuration:
  locations:
    - my_loc: "loc123"
"""
    file_path = create_envars_file(tmp_path, initial_content)
    result = runner.invoke(app, ["--file", file_path, "add", "MY_VAR=loc_value", "--loc", "my_loc"])
    assert result.exit_code == 0
    assert "Successfully added/updated MY_VAR in" in result.stdout

    data = read_yaml_file(file_path)
    assert data["environment_variables"]["MY_VAR"]["my_loc"] == "loc_value"


def test_add_specific_variable(tmp_path):
    initial_content = """
configuration:
  environments:
    - dev
  locations:
    - my_loc: "loc123"
"""
    file_path = create_envars_file(tmp_path, initial_content)
    result = runner.invoke(
        app, ["--file", file_path, "add", "MY_VAR=specific_value", "--env", "dev", "--loc", "my_loc"]
    )
    assert result.exit_code == 0
    assert "Successfully added/updated MY_VAR in" in result.stdout

    data = read_yaml_file(file_path)
    assert data["environment_variables"]["MY_VAR"]["dev"]["my_loc"] == "specific_value"


def test_add_secret_variable(tmp_path):
    initial_content = """
configuration:
  app: MyApp
  kms_key: "arn:aws:kms:us-east-1:123456789012:key/mrk-12345"
  environments:
    - dev
  locations:
    - my_loc: "loc123"
"""
    file_path = create_envars_file(tmp_path, initial_content)

    kms_client = boto3.client("kms", region_name="us-east-1")
    with Stubber(kms_client) as stubber:
        encrypted_value = base64.b64encode(b"encrypted_value").decode("utf-8")
        stubber.add_response(
            "encrypt",
            {"CiphertextBlob": b"encrypted_value"},
            {
                "KeyId": "arn:aws:kms:us-east-1:123456789012:key/mrk-12345",
                "Plaintext": b"super_secret_value",
                "EncryptionContext": {"app": "MyApp", "environment": "dev", "location": "my_loc"},
            },
        )
        with patch("boto3.client", return_value=kms_client):
            result = runner.invoke(
                app,
                [
                    "--file",
                    file_path,
                    "add",
                    "MY_SECRET=super_secret_value",
                    "--env",
                    "dev",
                    "--loc",
                    "my_loc",
                    "--secret",
                ],
            )
            assert result.exit_code == 0
            assert "Successfully added/updated MY_SECRET in" in result.stdout
            stubber.assert_no_pending_responses()

    with open(file_path) as f:
        content = f.read()
        assert "!secret" in content
        assert encrypted_value in content


def test_update_existing_variable(tmp_path):
    initial_content = """
environment_variables:
  MY_VAR:
    default: "old_value"
"""
    file_path = create_envars_file(tmp_path, initial_content)
    result = runner.invoke(app, ["--file", file_path, "add", "MY_VAR=new_value"])
    assert result.exit_code == 0
    assert "Successfully added/updated MY_VAR in" in result.stdout

    data = read_yaml_file(file_path)
    assert data["environment_variables"]["MY_VAR"]["default"] == "new_value"


def test_add_variable_invalid_format(tmp_path):
    file_path = create_envars_file(tmp_path)
    result = runner.invoke(app, ["--file", file_path, "add", "MY_VAR_no_equal_sign"])
    assert result.exit_code == 1
    assert "Invalid variable assignment format" in result.stderr


def test_add_variable_non_existent_location(tmp_path):
    file_path = create_envars_file(tmp_path)
    result = runner.invoke(app, ["--file", file_path, "add", "MY_VAR=value", "--loc", "non_existent_loc"])
    assert result.exit_code == 1
    assert "Location 'non_existent_loc' not found" in result.stderr


def test_add_variable_non_existent_environment_for_specific(tmp_path):
    initial_content = """
configuration:
  locations:
    - my_loc: "loc123"
"""
    file_path = create_envars_file(tmp_path, initial_content)
    result = runner.invoke(
        app, ["--file", file_path, "add", "MY_VAR=value", "--env", "non_existent_env", "--loc", "my_loc"]
    )
    assert (
        result.exit_code == 0
    )  # Should add the variable, but the environment won't be recognized by get_variable_value
    assert "Successfully added/updated MY_VAR in" in result.stdout

    data = read_yaml_file(file_path)
    assert data["environment_variables"]["MY_VAR"]["non_existent_env"]["my_loc"] == "value"


def test_print_decrypt_secret(tmp_path):
    encrypted_string = base64.b64encode(b"some_encrypted_bytes").decode("utf-8")
    initial_content = f"""
configuration:
  app: MyApp
  kms_key: "arn:aws:kms:us-east-1:123456789012:key/mrk-12345"
  environments:
    - dev
  locations:
    - my_loc: "loc123"
environment_variables:
  MY_SECRET:
    dev:
      my_loc: !secret {encrypted_string}
"""
    file_path = create_envars_file(tmp_path, initial_content)

    kms_client = boto3.client("kms", region_name="us-east-1")
    with Stubber(kms_client) as stubber:
        stubber.add_response(
            "decrypt",
            {"Plaintext": b"decrypted_value"},
            {
                "CiphertextBlob": b"some_encrypted_bytes",
                "EncryptionContext": {"app": "MyApp", "environment": "dev", "location": "my_loc"},
            },
        )
        with patch("boto3.client", return_value=kms_client):
            result = runner.invoke(
                app,
                [
                    "--file",
                    file_path,
                    "output",
                    "--env",
                    "dev",
                    "--loc",
                    "my_loc",
                ],
            )
            assert result.exit_code == 0, result.stderr
            assert "MY_SECRET=decrypted_value" in result.stdout
            stubber.assert_no_pending_responses()


@patch("os.execvpe")
def test_exec_command_with_envars_env_var(mock_execvpe, tmp_path):
    initial_content = """
configuration:
  environments:
    - dev
  locations:
    - my_loc: "loc123"
environment_variables:
  MY_VAR:
    default: "default_value"
    dev:
      my_loc: "dev_loc_value"
"""
    file_path = create_envars_file(tmp_path, initial_content)

    with patch.dict("os.environ", {"ENVARS_ENV": "dev"}):
        result = runner.invoke(
            app,
            [
                "--file",
                file_path,
                "exec",
                "--loc",
                "my_loc",
                "sh",
                "-c",
                "echo $MY_VAR",
            ],
        )
    assert result.exit_code == 0

    # Assert that execvpe was called with the correct command and environment
    mock_execvpe.assert_called_once()
    call_args = mock_execvpe.call_args[0]
    assert call_args[0] == "sh"
    assert call_args[1] == [
        "sh",
        "-c",
        "echo $MY_VAR",
    ]
    assert "MY_VAR" in call_args[2]
    assert call_args[2]["MY_VAR"] == "dev_loc_value"


@patch("os.execvpe")
def test_exec_command_greedy(mock_execvpe, tmp_path):
    initial_content = """
configuration:
  environments:
    - dev
  locations:
    - my_loc: "loc123"
environment_variables:
  MY_VAR:
    default: "default_value"
    dev:
      my_loc: "dev_loc_value"
"""
    file_path = create_envars_file(tmp_path, initial_content)

    # The command to execute is `sh -c 'echo $MY_VAR'`.
    # This will print the value of the environment variable MY_VAR.
    result = runner.invoke(
        app,
        [
            "--file",
            file_path,
            "exec",
            "--env",
            "dev",
            "--loc",
            "my_loc",
            "sh",
            "-c",
            "echo $MY_VAR",
        ],
    )
    assert result.exit_code == 0

    # Assert that execvpe was called with the correct command and environment
    mock_execvpe.assert_called_once()
    call_args = mock_execvpe.call_args[0]
    assert call_args[0] == "sh"
    assert call_args[1] == [
        "sh",
        "-c",
        "echo $MY_VAR",
    ]
    assert "MY_VAR" in call_args[2]
    assert call_args[2]["MY_VAR"] == "dev_loc_value"

    # Test with a command that has its own flags
    mock_execvpe.reset_mock()
    result = runner.invoke(
        app,
        [
            "--file",
            file_path,
            "exec",
            "--env",
            "dev",
            "--loc",
            "my_loc",
            "sh",
            "-c",
            'echo "var=$MY_VAR, args=$@"',
            "--",
            "--my-flag",
            "my-value",
        ],
    )
    assert result.exit_code == 0
    mock_execvpe.assert_called_once()
    call_args = mock_execvpe.call_args[0]
    assert call_args[0] == "sh"
    assert call_args[1] == [
        "sh",
        "-c",
        'echo "var=$MY_VAR, args=$@"',
        "--my-flag",
        "my-value",
    ]
    assert "MY_VAR" in call_args[2]
    assert call_args[2]["MY_VAR"] == "dev_loc_value"


def test_print_with_env_and_loc(tmp_path):
    initial_content = """
configuration:
  environments:
    - dev
  locations:
    - my_loc: "loc123"
environment_variables:
  MY_VAR:
    default: "default_value"
    dev:
      my_loc: "dev_loc_value"
"""
    file_path = create_envars_file(tmp_path, initial_content)
    result = runner.invoke(app, ["--file", file_path, "output", "--env", "dev", "--loc", "my_loc"])
    assert result.exit_code == 0
    assert "MY_VAR=dev_loc_value" in result.stdout

    # Test with ENVARS_ENV environment variable
    with patch.dict("os.environ", {"ENVARS_ENV": "dev"}):
        result = runner.invoke(app, ["--file", file_path, "output", "--loc", "my_loc"])
    assert result.exit_code == 0
    assert "MY_VAR=dev_loc_value" in result.stdout


def test_tree_command(tmp_path):
    initial_content = """
configuration:
  environments:
    - dev
  locations:
    - my_loc: "loc123"
environment_variables:
  MY_VAR:
    default: "default_value"
    dev:
      my_loc: "dev_loc_value"
"""
    file_path = create_envars_file(tmp_path, initial_content)
    result = runner.invoke(app, ["--file", file_path, "tree"])
    assert result.exit_code == 0
    assert "Envars Configuration" in result.stdout
    assert "MY_VAR" in result.stdout


def test_print_invalid_env(tmp_path):
    initial_content = """
configuration:
  environments:
    - dev
  locations:
    - my_loc: "loc123"
"""
    file_path = create_envars_file(tmp_path, initial_content)
    result = runner.invoke(app, ["--file", file_path, "output", "--env", "prod", "--loc", "my_loc"])
    assert result.exit_code == 1
    assert "Environment 'prod' not found" in result.stderr


def test_print_invalid_loc(tmp_path):
    initial_content = """
configuration:
  environments:
    - dev
  locations:
    - my_loc: "loc123"
"""
    file_path = create_envars_file(tmp_path, initial_content)
    result = runner.invoke(app, ["--file", file_path, "output", "--env", "dev", "--loc", "other_loc"])
    assert result.exit_code == 1
    assert "Location 'other_loc' not found" in result.stderr


def test_exec_invalid_env(tmp_path):
    initial_content = """
configuration:
  environments:
    - dev
  locations:
    - my_loc: "loc123"
"""
    file_path = create_envars_file(tmp_path, initial_content)
    result = runner.invoke(app, ["--file", file_path, "exec", "--env", "prod", "--loc", "my_loc", "echo", "hello"])
    assert result.exit_code == 1
    assert "Environment 'prod' not found" in result.stderr


def test_exec_invalid_loc(tmp_path):
    initial_content = """
configuration:
  environments:
    - dev
  locations:
    - my_loc: "loc123"
"""
    file_path = create_envars_file(tmp_path, initial_content)
    result = runner.invoke(app, ["--file", file_path, "exec", "--env", "dev", "--loc", "other_loc", "echo", "hello"])
    assert result.exit_code == 1
    assert "Location 'other_loc' not found" in result.stderr


def test_output_yaml_command(tmp_path):
    encrypted_string = base64.b64encode(b"some_encrypted_bytes").decode("utf-8")
    initial_content = f"""
configuration:
  app: MyApp
  kms_key: "arn:aws:kms:us-east-1:123456789012:key/mrk-12345"
  environments:
    - dev
  locations:
    - my_loc: "loc123"
environment_variables:
  MY_VAR:
    default: "default_value"
    dev:
      my_loc: "dev_loc_value"
  MY_SECRET:
    dev:
      my_loc: !secret {encrypted_string}
"""
    file_path = create_envars_file(tmp_path, initial_content)

    kms_client = boto3.client("kms", region_name="us-east-1")
    with Stubber(kms_client) as stubber:
        stubber.add_response(
            "decrypt",
            {"Plaintext": b"decrypted_value"},
            {
                "CiphertextBlob": b"some_encrypted_bytes",
                "EncryptionContext": {"app": "MyApp", "environment": "dev", "location": "my_loc"},
            },
        )
        with patch("boto3.client", return_value=kms_client):
            result = runner.invoke(
                app, ["--file", file_path, "output", "--format", "yaml", "--env", "dev", "--loc", "my_loc"]
            )
            assert result.exit_code == 0
            expected_yaml = """
envars:
  MY_VAR: dev_loc_value
  MY_SECRET: decrypted_value
"""
            output_dict = yaml.safe_load(result.stdout)
            expected_dict = yaml.safe_load(expected_yaml)
            assert output_dict == expected_dict
            stubber.assert_no_pending_responses()


def test_output_json_command(tmp_path):
    initial_content = """
configuration:
  environments:
    - dev
  locations:
    - my_loc: "loc123"
environment_variables:
  MY_VAR:
    default: "default_value"
    dev:
      my_loc: "dev_loc_value"
"""
    file_path = create_envars_file(tmp_path, initial_content)
    result = runner.invoke(app, ["--file", file_path, "output", "--format", "json", "--env", "dev", "--loc", "my_loc"])
    assert result.exit_code == 0
    import json

    output_dict = json.loads(result.stdout)
    assert output_dict == {"envars": {"MY_VAR": "dev_loc_value"}}


@patch("google.auth.default", return_value=(None, None))
@patch("subprocess.run")
def test_set_systemd_env_command(mock_run, mock_google_auth, tmp_path):
    mock_run.return_value.stdout = ""
    initial_content = """
configuration:
  environments:
    - dev
  locations:
    - my_loc: "loc123"
environment_variables:
  MY_VAR:
    default: "default_value"
    dev:
      my_loc: "dev_loc_value"
  ANOTHER_VAR:
    default: "another_value"
"""
    file_path = create_envars_file(tmp_path, initial_content)
    result = runner.invoke(app, ["--file", file_path, "set-systemd-env", "--env", "dev", "--loc", "my_loc"])
    assert result.exit_code == 0
    assert "Successfully set systemd environment variables" in result.stdout

    mock_run.assert_called_once()
    call_args = mock_run.call_args[0]
    assert call_args[0] == [
        "systemctl",
        "--user",
        "set-environment",
        "MY_VAR=dev_loc_value",
        "ANOTHER_VAR=another_value",
    ]


def test_validate_command_success(tmp_path):
    initial_content = """
configuration:
  environments:
    - dev
  locations:
    - my_loc: "loc123"
environment_variables:
  MY_VAR:
    description: "A test variable"
    dev:
      my_loc: "dev_loc_value"
"""
    file_path = create_envars_file(tmp_path, initial_content)
    result = runner.invoke(app, ["--file", file_path, "validate"])
    assert result.exit_code == 0
    assert "Validation successful!" in result.stdout


def test_validate_command_missing_variable_definition(tmp_path):
    # The `load_from_yaml` will load it, but `validate` should catch it.
    file_path = tmp_path / "invalid_vars.yml"
    with open(file_path, "w") as f:
        f.write(
            """
environment_variables:
  MY_VAR:
    description: "This is fine"
  # ANOTHER_VAR is not defined here, but has values below
  ANOTHER_VAR:
    default: "another_value"
"""
        )

    # To make this test work, we need to create a manager that has the inconsistency.
    # We'll add a value for a variable that is not in the manager's `variables` dict.
    from src.envars.models import VariableManager, VariableValue

    manager = VariableManager()
    manager.add_variable_value(VariableValue(variable_name="UNDEFINED_VAR", value="some_value", scope_type="DEFAULT"))

    with patch("envars.cli.load_from_yaml", return_value=manager):
        result = runner.invoke(app, ["--file", str(file_path), "validate"])

    assert result.exit_code == 1
    assert "Variable 'UNDEFINED_VAR' has values but is not defined as a top-level variable." in result.stderr.replace(
        "\n", ""
    )


def test_add_variable_lowercase(tmp_path):
    file_path = create_envars_file(tmp_path)
    result = runner.invoke(app, ["--file", file_path, "add", "my_var=my_value"])
    assert result.exit_code == 1
    assert "Variable names must be uppercase." in result.stderr


def test_validate_command_lowercase_variable(tmp_path):
    initial_content = """
environment_variables:
  my_var:
    default: "my_value"
"""
    file_path = create_envars_file(tmp_path, initial_content)
    result = runner.invoke(app, ["--file", file_path, "validate"])
    assert result.exit_code == 1
    assert "Variable name 'my_var' must be uppercase." in result.stderr


def test_load_from_yaml_lowercase_variable(tmp_path):
    initial_content = """
environment_variables:
  my_var:
    default: "my_value"
"""
    file_path = create_envars_file(tmp_path, initial_content)
    result = runner.invoke(app, ["--file", file_path, "output"])
    assert result.exit_code == 1
    assert "Variable name 'my_var' must be uppercase." in result.stderr


def test_add_variable_description_mandatory(tmp_path):
    initial_content = """
configuration:
  description_mandatory: true
"""
    file_path = create_envars_file(tmp_path, initial_content)
    result = runner.invoke(app, ["--file", file_path, "add", "MY_VAR=my_value"])
    assert result.exit_code == 1
    assert "Description is mandatory for new variable 'MY_VAR'." in result.stderr

    result = runner.invoke(app, ["--file", file_path, "add", "MY_VAR=my_value", "--description", "My description"])
    assert result.exit_code == 0


def test_validate_command_description_mandatory(tmp_path):
    initial_content = """
configuration:
  description_mandatory: true
environment_variables:
  MY_VAR:
    default: "my_value"
"""
    file_path = create_envars_file(tmp_path, initial_content)
    result = runner.invoke(app, ["--file", file_path, "validate"])
    assert result.exit_code == 1
    assert "Variable 'MY_VAR' is missing a description." in result.stderr


def test_config_command(tmp_path):
    initial_content = """
configuration:
  app: MyApp
  kms_key: "old-kms-key"
  description_mandatory: false
  environments:
    - dev
  locations:
    - my_loc: "loc123"
"""
    file_path = create_envars_file(tmp_path, initial_content)

    # Test updating kms_key
    result = runner.invoke(app, ["--file", file_path, "config", "--kms-key", "new-kms-key"])
    assert result.exit_code == 0
    data = read_yaml_file(file_path)
    assert data["configuration"]["kms_key"] == "new-kms-key"

    # Test adding an environment
    result = runner.invoke(app, ["--file", file_path, "config", "--add-env", "prod"])
    assert result.exit_code == 0
    data = read_yaml_file(file_path)
    assert "prod" in data["configuration"]["environments"]

    # Test removing an environment
    result = runner.invoke(app, ["--file", file_path, "config", "--remove-env", "dev"])
    assert result.exit_code == 0
    data = read_yaml_file(file_path)
    assert "dev" not in data["configuration"]["environments"]

    # Test adding a location
    result = runner.invoke(app, ["--file", file_path, "config", "--add-loc", "new_loc:loc456"])
    assert result.exit_code == 0
    data = read_yaml_file(file_path)
    assert {"new_loc": "loc456"} in data["configuration"]["locations"]

    # Test removing a location
    result = runner.invoke(app, ["--file", file_path, "config", "--remove-loc", "my_loc"])
    assert result.exit_code == 0
    data = read_yaml_file(file_path)
    assert {"my_loc": "loc123"} not in data["configuration"]["locations"]

    # Test updating description_mandatory
    result = runner.invoke(app, ["--file", file_path, "config", "--description-mandatory"])
    assert result.exit_code == 0
    data = read_yaml_file(file_path)
    assert data["configuration"]["description_mandatory"] is True

    result = runner.invoke(app, ["--file", file_path, "config", "--no-description-mandatory"])
    assert result.exit_code == 0
    data = read_yaml_file(file_path)
    assert data["configuration"]["description_mandatory"] is False


def test_add_sensitive_variable_no_flag(tmp_path):
    file_path = create_envars_file(tmp_path)
    result = runner.invoke(app, ["--file", file_path, "add", "MY_PASSWORD=my_value"])
    assert result.exit_code == 1
    assert "Variable 'MY_PASSWORD' may be sensitive." in result.stderr


def test_add_sensitive_variable_no_secret_flag(tmp_path):
    file_path = create_envars_file(tmp_path)
    result = runner.invoke(app, ["--file", file_path, "add", "MY_PASSWORD=my_value", "--no-secret"])
    assert result.exit_code == 0
    data = read_yaml_file(file_path)
    assert data["environment_variables"]["MY_PASSWORD"]["default"] == "my_value"


def test_add_default_secret_fails(tmp_path):
    initial_content = """
configuration:
  kms_key: "some-key"
"""
    file_path = create_envars_file(tmp_path, initial_content)
    result = runner.invoke(app, ["--file", file_path, "add", "MY_SECRET=my_value", "--secret"])
    assert result.exit_code == 1
    assert "Secrets must be scoped to an environment and/or location." in result.stderr


def test_validate_default_secret_fails(tmp_path):
    initial_content = """
configuration:
  kms_key: "some-key"
environment_variables:
  MY_SECRET:
    default: !secret "my_value"
"""
    file_path = create_envars_file(tmp_path, initial_content)
    result = runner.invoke(app, ["--file", file_path, "validate"])
    assert result.exit_code == 1
    assert "Variable 'MY_SECRET' is a secret and cannot have a default value." in result.stderr


def test_validate_default_secret_fails_with_ignore_flag(tmp_path):
    initial_content = """
configuration:
  kms_key: "some-key"
environment_variables:
  MY_SECRET:
    default: !secret "my_value"
"""
    file_path = create_envars_file(tmp_path, initial_content)
    result = runner.invoke(app, ["--file", file_path, "validate", "--ignore-default-secrets"])
    assert result.exit_code == 0
    assert "Validation successful!" in result.stdout


def test_variable_templating_with_jinja(tmp_path):
    initial_content = """
configuration:
  environments:
    - dev
  locations:
    - my_loc: "loc123"
environment_variables:
  DOMAIN:
    default: "example.com"
  HOSTNAME:
    default: "my-app.{{ DOMAIN }}"
  DATABASE_URL:
    default: "postgres://user:pass@{{ HOSTNAME }}:5432/db"
  DEFAULT_PORT:
    default: "5432"
  PORT:
    default: "{{ env.get('PORT', DEFAULT_PORT) }}"
"""
    file_path = create_envars_file(tmp_path, initial_content)
    result = runner.invoke(app, ["--file", file_path, "output", "--format", "yaml", "--env", "dev", "--loc", "my_loc"])
    assert result.exit_code == 0
    output_dict = yaml.safe_load(result.stdout)
    assert output_dict["envars"]["HOSTNAME"] == "my-app.example.com"
    assert output_dict["envars"]["DATABASE_URL"] == "postgres://user:pass@my-app.example.com:5432/db"
    assert output_dict["envars"]["PORT"] == "5432"


@patch("envars.main.GCPSecretManager")
@patch("envars.main.SSMParameterStore")
def test_variable_from_parameter_store(mock_ssm_store, mock_gcp_secret_manager, tmp_path):
    mock_ssm_instance = mock_ssm_store.return_value
    mock_ssm_instance.get_parameter.return_value = "ssm_value"

    initial_content = """
configuration:
  environments:
    - dev
  locations:
    - my_loc: "loc123"
environment_variables:
  MY_VAR:
    default: "parameter_store:/my/parameter"
"""
    file_path = create_envars_file(tmp_path, initial_content)
    result = runner.invoke(app, ["--file", file_path, "output", "--format", "yaml", "--env", "dev", "--loc", "my_loc"])
    assert result.exit_code == 0
    output_dict = yaml.safe_load(result.stdout)
    assert output_dict["envars"]["MY_VAR"] == "ssm_value"
    mock_ssm_instance.get_parameter.assert_called_once_with("/my/parameter")


@patch("envars.main.GCPSecretManager")
def test_variable_from_gcp_secret_manager(mock_gcp_secret_manager, tmp_path):
    mock_gcp_instance = mock_gcp_secret_manager.return_value
    mock_gcp_instance.access_secret_version.return_value = "gcp_secret_value"

    initial_content = """
configuration:
  environments:
    - dev
  locations:
    - my_loc: "loc123"
environment_variables:
  MY_VAR:
    default: "gcp_secret_manager:projects/my-project/secrets/my-secret/versions/latest"
"""
    file_path = create_envars_file(tmp_path, initial_content)
    result = runner.invoke(app, ["--file", file_path, "output", "--format", "yaml", "--env", "dev", "--loc", "my_loc"])
    assert result.exit_code == 0
    output_dict = yaml.safe_load(result.stdout)
    assert output_dict["envars"]["MY_VAR"] == "gcp_secret_value"
    mock_gcp_instance.access_secret_version.assert_called_once_with(
        "projects/my-project/secrets/my-secret/versions/latest"
    )


def test_add_mismatched_remote_variable(tmp_path):
    initial_content = """
configuration:
  kms_key: "arn:aws:kms:us-east-1:123456789012:key/mrk-12345"
"""
    file_path = create_envars_file(tmp_path, initial_content)
    result = runner.invoke(
        app,
        [
            "--file",
            file_path,
            "add",
            "MY_VAR=gcp_secret_manager:projects/my-project/secrets/my-secret/versions/latest",
        ],
    )
    assert result.exit_code == 1
    assert "Cannot use 'gcp_secret_manager:' with an AWS KMS key." in result.stderr


def test_validate_mismatched_remote_variable(tmp_path):
    initial_content = """
configuration:
  kms_key: "arn:aws:kms:us-east-1:123456789012:key/mrk-12345"
environment_variables:
  MY_VAR:
    default: "gcp_secret_manager:projects/my-project/secrets/my-secret/versions/latest"
"""
    file_path = create_envars_file(tmp_path, initial_content)
    result = runner.invoke(app, ["--file", file_path, "validate"])
    assert result.exit_code == 1
    assert "Variable 'MY_VAR' uses 'gcp_secret_manager:' with an AWS KMS key." in result.stderr


def test_validate_mismatched_remote_variable_cf(tmp_path):
    initial_content = """
configuration:
  kms_key: "projects/my-gcp-project/locations/us-central1/keyRings/my-key-ring/cryptoKeys/my-key"
environment_variables:
  MY_VAR:
    default: "cloudformation_export:my-export"
"""
    file_path = create_envars_file(tmp_path, initial_content)
    result = runner.invoke(app, ["--file", file_path, "validate"])
    assert result.exit_code == 1
    assert "uses 'parameter_store:' or 'cloudformation_export:' with a GCP KMS key." in result.stderr.replace("\n", "")


def test_load_from_yaml_invalid_structure(tmp_path):
    initial_content = """
configuration:
  environments:
    - prod
    - staging
  locations:
    - master: "511042647617"
environment_variables:
  PROD_ONLY_VAR:
    prod:
      master:
        staging: abc
"""
    file_path = create_envars_file(tmp_path, initial_content)
    result = runner.invoke(app, ["--file", file_path, "output"])
    assert result.exit_code == 1
    assert "Invalid nesting in 'PROD_ONLY_VAR' -> 'prod' -> 'master'" in result.stderr.replace("\n", "")


@patch("envars.main.GCPSecretManager")
@patch("envars.main.SSMParameterStore")
def test_remote_variable_templating(mock_ssm_store, mock_gcp_secret_manager, tmp_path):
    mock_ssm_instance = mock_ssm_store.return_value
    mock_ssm_instance.get_parameter.return_value = "ssm_value"
    mock_gcp_instance = mock_gcp_secret_manager.return_value
    mock_gcp_instance.access_secret_version.return_value = "gcp_secret_value"

    initial_content = """
configuration:
  environments:
    - dev
  locations:
    - my_loc: "loc123"
environment_variables:
  SECRET_NAME:
    default: "my-secret"
  SSM_PATH:
    default: "/path/to/{{ SECRET_NAME }}"
  GCP_PROJECT:
    default: "my-gcp-project"
  SSM_VAR:
    default: "parameter_store:{{ SSM_PATH }}"
  GCP_VAR:
    default: "gcp_secret_manager:projects/{{ GCP_PROJECT }}/secrets/{{ SECRET_NAME }}/versions/latest"
"""
    file_path = create_envars_file(tmp_path, initial_content)
    result = runner.invoke(app, ["--file", file_path, "output", "--format", "yaml", "--env", "dev", "--loc", "my_loc"])

    assert result.exit_code == 0
    output_dict = yaml.safe_load(result.stdout)

    # Verify that the resolved values are correct
    assert output_dict["envars"]["SSM_VAR"] == "ssm_value"
    assert output_dict["envars"]["GCP_VAR"] == "gcp_secret_value"

    # Verify that the lookup methods were called with the rendered paths
    mock_ssm_instance.get_parameter.assert_called_once_with("/path/to/my-secret")
    mock_gcp_instance.access_secret_version.assert_called_once_with(
        "projects/my-gcp-project/secrets/my-secret/versions/latest"
    )


def test_circular_dependency_in_templates(tmp_path):
    initial_content = """
configuration:
  environments:
    - dev
  locations:
    - my_loc: "loc123"
environment_variables:
  VAR_A:
    default: "Value is {{ VAR_B }}"
  VAR_B:
    default: "Value is {{ VAR_C }}"
  VAR_C:
    default: "Value is {{ VAR_A }}"
  VAR_D:
    default: "I am not in a cycle"
"""
    file_path = create_envars_file(tmp_path, initial_content)
    result = runner.invoke(app, ["--file", file_path, "output", "--format", "yaml", "--env", "dev", "--loc", "my_loc"])
    assert result.exit_code == 1
    assert "Circular dependency detected" in result.stderr
    assert "VAR_A" in result.stderr
    assert "VAR_B" in result.stderr
    assert "VAR_C" in result.stderr
    assert "VAR_D" not in result.stderr


def test_validate_circular_dependency(tmp_path):
    initial_content = """
configuration:
  environments:
    - dev
  locations:
    - my_loc: "loc123"
environment_variables:
  VAR_A:
    default: "Value is {{ VAR_B }}"
  VAR_B:
    default: "Value is {{ VAR_A }}"
"""
    file_path = create_envars_file(tmp_path, initial_content)
    result = runner.invoke(app, ["--file", file_path, "validate"])
    assert result.exit_code == 1
    assert "Circular dependency detected" in result.stderr


def test_default_location_aws(tmp_path):
    initial_content = """
configuration:
  kms_key: "arn:aws:kms:us-east-1:123456789012:key/mrk-12345"
  environments:
    - dev
  locations:
    - aws-prod: "123456789012"
environment_variables:
  MY_VAR:
    default: "default_value"
"""
    file_path = create_envars_file(tmp_path, initial_content)
    sts_client = boto3.client("sts", region_name="us-east-1")
    with Stubber(sts_client) as stubber:
        stubber.add_response("get_caller_identity", {"Account": "123456789012"})
        with patch("boto3.client", return_value=sts_client):
            result = runner.invoke(app, ["--file", file_path, "output", "--env", "dev"])
            assert result.exit_code == 0
            assert "MY_VAR=default_value" in result.stdout
            stubber.assert_no_pending_responses()


@patch("envars.cli.get_default_location_name", return_value="gcp-prod")
def test_default_location_gcp(mock_get_default_location_name, tmp_path):
    initial_content = """
configuration:
  kms_key: "projects/my-gcp-project/locations/us-central1/keyRings/my-key-ring/cryptoKeys/my-key"
  environments:
    - dev
  locations:
    - gcp-prod: "my-gcp-project"
environment_variables:
  MY_VAR:
    default: "default_value"
"""
    file_path = create_envars_file(tmp_path, initial_content)
    result = runner.invoke(app, ["--file", file_path, "output", "--env", "dev"])
    assert result.exit_code == 0
    assert "MY_VAR=default_value" in result.stdout


def test_default_location_not_found(tmp_path):
    initial_content = """
configuration:
  kms_key: "arn:aws:kms:us-east-1:123456789012:key/mrk-12345"
  environments:
    - dev
  locations:
    - aws-prod: "another-account"
"""
    file_path = create_envars_file(tmp_path, initial_content)
    sts_client = boto3.client("sts", region_name="us-east-1")
    with Stubber(sts_client) as stubber:
        stubber.add_response("get_caller_identity", {"Account": "123456789012"})
        with patch("boto3.client", return_value=sts_client):
            result = runner.invoke(app, ["--file", file_path, "output", "--env", "dev"])
            assert result.exit_code == 1
            assert "Could not determine default location" in result.stderr
            stubber.assert_no_pending_responses()


@patch("boto3.client")
def test_debug_output(mock_boto_client, tmp_path):
    mock_sts_client = mock_boto_client.return_value
    mock_sts_client.get_caller_identity.return_value = {"Account": "123456789012"}
    initial_content = """
configuration:
  kms_key: "arn:aws:kms:us-east-1:123456789012:key/mrk-12345"
  environments:
    - dev
  locations:
    - aws-prod: "123456789012"
"""
    file_path = create_envars_file(tmp_path, initial_content)
    with patch.dict("os.environ", {"ENVARS_DEBUG": "1"}):
        result = runner.invoke(app, ["--file", file_path, "output", "--env", "dev"])
    assert result.exit_code == 0
    assert "DEBUG: Attempting to detect default location..." in result.stderr
    assert "DEBUG: Cloud provider is AWS." in result.stderr
    assert "DEBUG: Found AWS Account ID: 123456789012" in result.stderr
    assert "DEBUG: Checking location: aws-prod with ID: 123456789012" in result.stderr
    assert "DEBUG: Default location found: aws-prod" in result.stderr


def test_config_command_no_options_prints_help(tmp_path):
    file_path = create_envars_file(tmp_path)
    result = runner.invoke(app, ["--file", file_path, "config"])
    assert result.exit_code == 0
    assert "Usage: " in result.stdout
    assert "config [OPTIONS]" in result.stdout


def test_config_remove_env_in_use(tmp_path):
    initial_content = """
configuration:
  environments:
    - dev
    - prod
environment_variables:
  MY_VAR:
    dev: "dev_value"
"""
    file_path = create_envars_file(tmp_path, initial_content)
    result = runner.invoke(app, ["--file", file_path, "config", "--remove-env", "dev"])
    assert result.exit_code == 1
    assert "Cannot remove environment 'dev' because it is in use" in result.stderr
    assert "MY_VAR" in result.stderr

    data = read_yaml_file(file_path)
    assert "dev" in data["configuration"]["environments"]


def test_config_remove_loc_in_use(tmp_path):
    initial_content = """
configuration:
  locations:
    - my_loc: "loc123"
environment_variables:
  MY_VAR:
    my_loc: "loc_value"
"""
    file_path = create_envars_file(tmp_path, initial_content)
    result = runner.invoke(app, ["--file", file_path, "config", "--remove-loc", "my_loc"])
    assert result.exit_code == 1
    assert "Cannot remove location 'my_loc' because it is in use" in result.stderr
    assert "MY_VAR" in result.stderr

    data = read_yaml_file(file_path)
    assert {"my_loc": "loc123"} in data["configuration"]["locations"]


def test_add_value_from_file(tmp_path):
    file_path = create_envars_file(tmp_path)
    value_file = tmp_path / "value.txt"
    file_content = """-----BEGIN OPENSSH PRIVATE KEY-----
b3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAABAAAAaAAAABNlY2RzYS
1zaGEyLW5pc3RwMjU2AAAACG5pc3RwMjU2AAAAQQR9QJ/pZ7E/w3N8z2Z5Y8V8W8X8Y8V8
W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8
V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8
Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8
V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8
Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8
X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8
W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8
V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8
Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8V8W8X8Y8
V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8
Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8
X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8
W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8
V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8
Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8
X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8
W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8
V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8
Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8
X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8
W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8
V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8
Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8
X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8
W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8
V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8
Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8
X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8
W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8
V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8
Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8X8Y8V8W8
XAXAXAXAXAXAXAXAXAXAXAXAXAXAXAXAXAXAXAXAXAXAXAXAXAXAXAXAXAXAXAXAXAXA
-----END OPENSSH PRIVATE KEY-----"""
    value_file.write_text(file_content)

    result = runner.invoke(
        app,
        [
            "--file",
            file_path,
            "add",
            "--var-name",
            "MY_VAR",
            "--value-from-file",
            str(value_file),
        ],
    )
    assert result.exit_code == 0
    assert "Successfully added/updated MY_VAR" in result.stdout

    data = read_yaml_file(file_path)
    assert data["environment_variables"]["MY_VAR"]["default"] == file_content


class TestCircularDependency:
    def test_add_circular_dependency(self, tmp_path):
        initial_content = """
configuration:
  environments:
    - dev
  locations:
    - my_loc: "loc123"
environment_variables:
  VAR_A:
    default: "Value is {{ VAR_B }}"
"""
        file_path = create_envars_file(tmp_path, initial_content)
        result = runner.invoke(app, ["--file", file_path, "add", "VAR_B=Value is {{ VAR_A }}"])
        assert result.exit_code == 1
        assert "Circular dependency detected" in result.stderr
        assert "VAR_A" in result.stderr
        assert "VAR_B" in result.stderr

    def test_add_context_specific_circular_dependency(self, tmp_path):
        initial_content = """
configuration:
  environments:
    - dev
    - prod
  locations:
    - loc1: "1"
    - loc2: "2"
environment_variables:
  VAR_A:
    default: "ok"
    dev:
      loc1: "{{ VAR_B }}"
  VAR_B:
    default: "ok"
"""
        file_path = create_envars_file(tmp_path, initial_content)

        # This should be fine
        result = runner.invoke(app, ["--file", file_path, "add", "VAR_B=ok for now", "--env", "prod"])
        assert result.exit_code == 0

        # This should create a circular dependency in the dev/loc1 context
        result = runner.invoke(app, ["--file", file_path, "add", "VAR_B={{ VAR_A }}", "--env", "dev", "--loc", "loc1"])
        assert result.exit_code == 1
        assert "Circular dependency detected in context env='dev', loc='loc1'" in result.stderr


class TestValidation:
    def test_add_variable_with_validation(self, tmp_path):
        file_path = create_envars_file(tmp_path)
        result = runner.invoke(
            app,
            [
                "--file",
                file_path,
                "add",
                "MY_VAR=valid_value",
                "--validation",
                "^valid_value$",
            ],
        )
        assert result.exit_code == 0
        data = read_yaml_file(file_path)
        assert data["environment_variables"]["MY_VAR"]["validation"] == "^valid_value$"

    def test_add_variable_with_failing_validation(self, tmp_path):
        initial_content = """
environment_variables:
  MY_VAR:
    validation: "^valid_value$"
"""
        file_path = create_envars_file(tmp_path, initial_content)
        result = runner.invoke(app, ["--file", file_path, "add", "MY_VAR=invalid_value"])
        assert result.exit_code == 1
        assert (
            "Value 'invalid_value' for variable 'MY_VAR' does not match validation regex: ^valid_value$"
            in result.stderr.replace("\n", "")
        )

    def test_validate_command_with_invalid_value(self, tmp_path):
        initial_content = """
environment_variables:
  MY_VAR:
    validation: "^valid_value$"
    default: "invalid_value"
"""
        file_path = create_envars_file(tmp_path, initial_content)
        result = runner.invoke(app, ["--file", file_path, "validate"])
        assert result.exit_code == 1
        assert "Value 'invalid_value' for variable 'MY_VAR' does not match validation regex" in result.stderr
