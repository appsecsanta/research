import yaml
from pathlib import Path
from typing import Any, Dict

class ConfigError(Exception):
    """Custom exception for configuration loading errors."""
    pass

def load_config_from_yaml(file_path: str | Path) -> Dict[str, Any]:
    """
    Loads application configuration from a YAML file.

    The function reads a YAML file from the given path, parses its content,
    and returns it as a dictionary. It ensures the root of the YAML
    document is a mapping (dictionary).

    Args:
        file_path: The path to the YAML configuration file. Can be a string
                   or a pathlib.Path object.

    Returns:
        A dictionary containing the configuration values.

    Raises:
        FileNotFoundError: If the configuration file is not found at the
                           specified path.
        ConfigError: If the file is not valid YAML, cannot be read, or if
                     the root element is not a dictionary.
    """
    config_path = Path(file_path)

    try:
        with config_path.open('r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        raise
    except yaml.YAMLError as e:
        raise ConfigError(f"Error parsing YAML file: {config_path}") from e
    except IOError as e:
        raise ConfigError(f"Error reading configuration file: {config_path}") from e

    if not isinstance(config, dict):
        raise ConfigError(
            f"YAML file's root element must be a dictionary: {config_path}"
        )

    return config

if __name__ == '__main__':
    # Example Usage:
    # 1. Create a dummy config file for demonstration.
    config_content = """
    # Application Configuration
    app:
      name: "My Awesome App"
      version: "1.0.2"
      debug: true

    database:
      host: "localhost"
      port: 5432
      user: "admin"
      credentials:
        password: "secure_password_placeholder"

    features:
      - "user_authentication"
      - "data_processing"
      - "api_access"
    """
    dummy_config_path = Path("config.yaml")
    dummy_config_path.write_text(config_content, encoding='utf-8')

    # 2. Load the configuration
    try:
        app_config = load_config_from_yaml(dummy_config_path)
        print("Configuration loaded successfully:")
        import json
        print(json.dumps(app_config, indent=2))

        # Access nested values
        db_host = app_config.get('database', {}).get('host')
        app_name = app_config.get('app', {}).get('name')
        print(f"\nApp Name: {app_name}")
        print(f"Database Host: {db_host}")

    except (FileNotFoundError, ConfigError) as e:
        print(f"Error: {e}")
    finally:
        # 3. Clean up the dummy file
        if dummy_config_path.exists():
            dummy_config_path.unlink()
            print(f"\nCleaned up {dummy_config_path}")

    # Example of error handling
    print("\n--- Testing Error Handling ---")
    try:
        load_config_from_yaml("non_existent_file.yaml")
    except FileNotFoundError as e:
        print(f"Caught expected error: {e}")

    invalid_yaml_path = Path("invalid.yaml")
    invalid_yaml_path.write_text("app: name: 'missing colon'", encoding='utf-8')
    try:
        load_config_from_yaml(invalid_yaml_path)
    except ConfigError as e:
        print(f"Caught expected error: {e}")
    finally:
        if invalid_yaml_path.exists():
            invalid_yaml_path.unlink()
