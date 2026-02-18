import pickle
from pathlib import Path
from typing import Any, Union

# It is recommended to define custom exceptions for better error handling.
class StateManagerError(Exception):
    """Base exception for state management errors."""
    pass

class StateSaveError(StateManagerError):
    """Raised when saving the application state fails."""
    pass

class StateLoadError(StateManagerError):
    """Raised when loading the application state fails."""
    pass


def save_state(state: Any, filepath: Union[str, Path]) -> None:
    """
    Serializes and saves a Python object to a file.

    This function uses the pickle module, which can serialize complex Python
    objects, including custom class instances.

    Args:
        state: The Python object to save (e.g., a dictionary, list, or custom object).
        filepath: The path to the file where the state will be saved.

    Raises:
        StateSaveError: If an error occurs during file writing or serialization.
    """
    path = Path(filepath)
    try:
        # Ensure the parent directory exists.
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as f:
            # Use the highest protocol for efficiency and compatibility.
            pickle.dump(state, f, protocol=pickle.HIGHEST_PROTOCOL)
    except (IOError, pickle.PicklingError) as e:
        raise StateSaveError(f"Failed to save state to {path}: {e}") from e


def load_state(filepath: Union[str, Path]) -> Any:
    """
    Loads and deserializes a Python object from a file.

    Args:
        filepath: The path to the file from which to load the state.

    Returns:
        The deserialized Python object.

    Raises:
        StateLoadError: If the file does not exist or an error occurs
                        during file reading or deserialization.
    """
    path = Path(filepath)
    if not path.is_file():
        raise StateLoadError(f"State file not found: {path}")

    try:
        with path.open("rb") as f:
            return pickle.load(f)
    except (IOError, pickle.UnpicklingError, EOFError) as e:
        raise StateLoadError(f"Failed to load state from {path}: {e}") from e


if __name__ == '__main__':
    # --- Example Usage ---

    # 1. Define a custom class to demonstrate complex object serialization.
    class UserSettings:
        def __init__(self, username: str, theme: str, notifications_enabled: bool):
            self.username = username
            self.theme = theme
            self.notifications_enabled = notifications_enabled
            self.login_timestamps = []

        def __repr__(self) -> str:
            return (
                f"UserSettings(username='{self.username}', theme='{self.theme}', "
                f"notifications_enabled={self.notifications_enabled}, "
                f"logins={len(self.login_timestamps)})"
            )

        def __eq__(self, other):
            if not isinstance(other, UserSettings):
                return NotImplemented
            return self.username == other.username and self.theme == other.theme

    # 2. Create a complex application state object.
    user_prefs = UserSettings(
        username="test_user",
        theme="dark",
        notifications_enabled=True
    )
    user_prefs.login_timestamps.extend([1672531200, 1672617600])

    original_app_state = {
        "version": "1.2.0",
        "session_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
        "user_settings": user_prefs,
        "open_documents": [
            Path("/home/user/docs/project_plan.txt"),
            Path("/home/user/docs/api_notes.md"),
        ],
        "window_layout": {
            "main_panel": {"size": 0.7, "visible": True},
            "side_panel": {"size": 0.3, "visible": False},
        },
        "history": ("item1", "item2", "item3", "item1")
    }

    STATE_FILE = Path("./app_state.pkl")

    # 3. Save the state to a file.
    try:
        print(f"Saving application state to {STATE_FILE}...")
        print("Original state:", original_app_state)
        save_state(original_app_state, STATE_FILE)
        print("State saved successfully.")
    except StateSaveError as e:
        print(f"Error: {e}")

    # 4. Load the state from the file.
    loaded_app_state = None
    try:
        print(f"\nLoading application state from {STATE_FILE}...")
        loaded_app_state = load_state(STATE_FILE)
        print("State loaded successfully.")
        print("Loaded state:  ", loaded_app_state)
    except StateLoadError as e:
        print(f"Error: {e}")

    # 5. Verify that the loaded state is identical to the original.
    if loaded_app_state:
        assert loaded_app_state["version"] == original_app_state["version"]
        assert loaded_app_state["user_settings"] == original_app_state["user_settings"]
        assert loaded_app_state["open_documents"] == original_app_state["open_documents"]
        print("\nVerification successful: Loaded state matches original state.")

    # 6. Demonstrate error handling for a non-existent file.
    non_existent_file = Path("./non_existent_state.pkl")
    print(f"\nAttempting to load from a non-existent file: {non_existent_file}")
    try:
        load_state(non_existent_file)
    except StateLoadError as e:
        print(f"Caught expected error: {e}")

    # 7. Clean up the created state file.
    if STATE_FILE.exists():
        STATE_FILE.unlink()
        print(f"\nCleaned up {STATE_FILE}.")
