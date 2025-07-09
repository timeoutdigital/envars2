from unittest.mock import patch

import yaml
from typer.testing import CliRunner

from cli import app

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
        ],
    )
    assert result.exit_code == 0
    assert "Successfully initialized" in result.stdout

    data = read_yaml_file(file_path)
    assert data["configuration"]["app"] == "MyApp"
    assert data["configuration"]["environments"] == ["dev", "prod"]
    assert {"aws": "123"} in data["configuration"]["locations"]
    assert {"gcp": "456"} in data["configuration"]["locations"]


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


@patch("cli.AWSKMSAgent")
def test_add_secret_variable(mock_aws_kms_agent, tmp_path):
    mock_agent_instance = mock_aws_kms_agent.return_value
    mock_agent_instance.encrypt.return_value = "encrypted_value"

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

    # Verify the agent was called correctly
    mock_agent_instance.encrypt.assert_called_once_with(
        "super_secret_value",
        "arn:aws:kms:us-east-1:123456789012:key/mrk-12345",
        {"app": "MyApp", "environment": "dev", "location": "my_loc"},
    )

    # Verify the output YAML
    with open(file_path) as f:
        content = f.read()
        assert "!secret |" in content
        assert "      encrypted_value" in content


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


@patch("cli.AWSKMSAgent")
def test_print_decrypt_secret(mock_aws_kms_agent, tmp_path):
    mock_agent_instance = mock_aws_kms_agent.return_value
    mock_agent_instance.decrypt.return_value = "decrypted_value"

    initial_content = """
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
      my_loc: !secret |
        encrypted_value
"""
    file_path = create_envars_file(tmp_path, initial_content)

    # Test with --decrypt flag
    result = runner.invoke(
        app,
        [
            "--file",
            file_path,
            "print",
            "--env",
            "dev",
            "--loc",
            "my_loc",
            "--decrypt",
        ],
    )
    assert result.exit_code == 0
    assert "decrypted_value" in result.stdout
    assert "encrypted_value" not in result.stdout

    # Verify the agent was called correctly
    mock_agent_instance.decrypt.assert_called_once_with(
        "encrypted_value\n",
        {"app": "MyApp", "environment": "dev", "location": "my_loc"},
    )

    # Test without --decrypt flag
    result = runner.invoke(
        app,
        [
            "--file",
            file_path,
            "print",
            "--env",
            "dev",
            "--loc",
            "my_loc",
        ],
    )
    assert result.exit_code == 0
    assert "encrypted_value" in result.stdout
    assert "decrypted_value" not in result.stdout


@patch("os.execvpe")
def test_exec_command_with_stage_env_var(mock_execvpe, tmp_path):
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

    with patch.dict("os.environ", {"STAGE": "dev"}):
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


def test_print_no_options(tmp_path):
    initial_content = """
configuration:
  environments:
    - dev
    - prod
  locations:
    - aws: "123"
    - gcp: "456"
environment_variables:
  VAR1:
    default: "default1"
    dev: "dev1"
    prod: "prod1"
  VAR2:
    default: "default2"
    aws: "aws2"
    gcp:
      dev: "gcp_dev2"
"""
    file_path = create_envars_file(tmp_path, initial_content)
    result = runner.invoke(app, ["--file", file_path, "print"])
    assert result.exit_code == 0
    assert "default1" in result.stdout
    assert "dev1" in result.stdout
    assert "prod1" in result.stdout
    assert "default2" in result.stdout
    assert "aws2" in result.stdout
    assert "gcp_dev2" in result.stdout


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
    result = runner.invoke(app, ["--file", file_path, "print", "--env", "dev", "--loc", "my_loc"])
    assert result.exit_code == 0
    assert "MY_VAR=dev_loc_value" in result.stdout
    assert "Envars Configuration" not in result.stdout


def test_print_invalid_env(tmp_path):
    initial_content = """
configuration:
  environments:
    - dev
"""
    file_path = create_envars_file(tmp_path, initial_content)
    result = runner.invoke(app, ["--file", file_path, "print", "--env", "prod"])
    assert result.exit_code == 1
    assert "Environment 'prod' not found" in result.stderr


def test_print_invalid_loc(tmp_path):
    initial_content = """
configuration:
  locations:
    - my_loc: "loc123"
"""
    file_path = create_envars_file(tmp_path, initial_content)
    result = runner.invoke(app, ["--file", file_path, "print", "--loc", "other_loc"])
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


def test_yaml_command(tmp_path):
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
    result = runner.invoke(app, ["--file", file_path, "yaml", "--env", "dev", "--loc", "my_loc"])
    assert result.exit_code == 0
    expected_yaml = """
envars:
  MY_VAR: dev_loc_value
  ANOTHER_VAR: another_value
"""
    output_dict = yaml.safe_load(result.stdout)
    expected_dict = yaml.safe_load(expected_yaml)
    assert output_dict == expected_dict


@patch("subprocess.run")
def test_set_systemd_env_command(mock_run, tmp_path):
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
