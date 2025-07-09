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
