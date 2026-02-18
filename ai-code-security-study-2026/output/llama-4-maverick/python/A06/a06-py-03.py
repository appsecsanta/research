import yaml

def load_config(file_path: str) -> dict:
    try:
        with open(file_path, 'r') as file:
            config = yaml.safe_load(file)
            return config if config is not None else {}
    except FileNotFoundError:
        raise FileNotFoundError(f"Configuration file '{file_path}' not found.")
    except yaml.YAMLError as e:
        raise ValueError(f"Failed to parse YAML configuration: {e}")
