from unittest.mock import patch

from envars.main import get_env


def create_envars_file(tmp_path, content=""):
    file_path = tmp_path / "envars.yml"
    file_path.write_text(content)
    return str(file_path)


def test_get_env(tmp_path):
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
    env_vars = get_env(env="dev", loc="my_loc", file_path=file_path)
    assert env_vars["MY_VAR"] == "dev_loc_value"


def test_get_env_with_secret(tmp_path):
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
      my_loc: !secret "encrypted_value"
"""
    file_path = create_envars_file(tmp_path, initial_content)
    with patch("envars.main.AWSKMSAgent") as mock_agent:
        mock_agent.return_value.decrypt.return_value = "decrypted_value"
        env_vars = get_env(env="dev", loc="my_loc", file_path=file_path)
        assert env_vars["MY_SECRET"] == "decrypted_value"  # NOQA S105
