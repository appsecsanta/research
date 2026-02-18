import pickle
import json
import os
import logging
from pathlib import Path
from typing import Any, Optional
from datetime import datetime
from copy import deepcopy

logger = logging.getLogger(__name__)


class StateManager:
    """Manages application state persistence to disk.
    
    Supports saving and loading complex Python objects including nested
    dictionaries, lists, custom class instances, and more using pickle
    serialization with optional JSON fallback for simple data.
    """

    def __init__(self, state_dir: str = ".app_state", app_name: str = "default"):
        self.state_dir = Path(state_dir)
        self.app_name = app_name
        self._state: dict[str, Any] = {}
        self._metadata: dict[str, Any] = {}
        self.state_dir.mkdir(parents=True, exist_ok=True)

    @property
    def _pickle_path(self) -> Path:
        return self.state_dir / f"{self.app_name}_state.pkl"

    @property
    def _json_path(self) -> Path:
        return self.state_dir / f"{self.app_name}_state.json"

    @property
    def _metadata_path(self) -> Path:
        return self.state_dir / f"{self.app_name}_metadata.json"

    def set(self, key: str, value: Any) -> None:
        """Set a value in the application state."""
        self._state[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        """Get a value from the application state."""
        return self._state.get(key, default)

    def delete(self, key: str) -> bool:
        """Delete a key from the application state. Returns True if key existed."""
        if key in self._state:
            del self._state[key]
            return True
        return False

    def clear(self) -> None:
        """Clear all state data."""
        self._state.clear()
        self._metadata.clear()

    def keys(self) -> list[str]:
        """Return all keys in the current state."""
        return list(self._state.keys())

    @property
    def state(self) -> dict[str, Any]:
        """Return a deep copy of the current state."""
        return deepcopy(self._state)

    def save(self, include_metadata: bool = True) -> bool:
        """Save the current application state to disk using pickle.
        
        Args:
            include_metadata: Whether to save metadata (timestamps, version info).
            
        Returns:
            True if save was successful, False otherwise.
        """
        try:
            if include_metadata:
                self._metadata = {
                    "saved_at": datetime.now().isoformat(),
                    "app_name": self.app_name,
                    "keys": list(self._state.keys()),
                    "num_entries": len(self._state),
                }
                with open(self._metadata_path, "w") as f:
                    json.dump(self._metadata, f, indent=2)

            # Write to a temp file first, then rename for atomicity
            tmp_path = self._pickle_path.with_suffix(".tmp")
            with open(tmp_path, "wb") as f:
                pickle.dump(self._state, f, protocol=pickle.HIGHEST_PROTOCOL)
            tmp_path.replace(self._pickle_path)

            logger.info(
                "State saved successfully with %d entries to %s",
                len(self._state),
                self._pickle_path,
            )
            return True

        except (OSError, pickle.PicklingError) as e:
            logger.error("Failed to save state: %s", e)
            # Clean up temp file if it exists
            tmp_path = self._pickle_path.with_suffix(".tmp")
            if tmp_path.exists():
                tmp_path.unlink()
            return False

    def load(self) -> bool:
        """Load application state from disk.
        
        Returns:
            True if load was successful, False otherwise.
        """
        if not self._pickle_path.exists():
            logger.warning("No saved state found at %s", self._pickle_path)
            return False

        try:
            with open(self._pickle_path, "rb") as f:
                self._state = pickle.load(f)

            if self._metadata_path.exists():
                with open(self._metadata_path, "r") as f:
                    self._metadata = json.load(f)

            logger.info(
                "State loaded successfully with %d entries from %s",
                len(self._state),
                self._pickle_path,
            )
            return True

        except (OSError, pickle.UnpicklingError, json.JSONDecodeError) as e:
            logger.error("Failed to load state: %s", e)
            return False

    def save_json(self) -> bool:
        """Save state as JSON (only works for JSON-serializable data).
        
        Useful for debugging or when you need human-readable state files.
        Falls back gracefully if data isn't JSON-serializable.
        
        Returns:
            True if save was successful, False otherwise.
        """
        try:
            tmp_path = self._json_path.with_suffix(".tmp")
            with open(tmp_path, "w") as f:
                json.dump(self._state, f, indent=2, default=str)
            tmp_path.replace(self._json_path)
            logger.info("State saved as JSON to %s", self._json_path)
            return True
        except (OSError, TypeError) as e:
            logger.error("Failed to save state as JSON: %s", e)
            if tmp_path.exists():
                tmp_path.unlink()
            return False

    def load_json(self) -> bool:
        """Load state from a JSON file.
        
        Returns:
            True if load was successful, False otherwise.
        """
        if not self._json_path.exists():
            logger.warning("No JSON state found at %s", self._json_path)
            return False

        try:
            with open(self._json_path, "r") as f:
                self._state = json.load(f)
            logger.info("State loaded from JSON: %s", self._json_path)
            return True
        except (OSError, json.JSONDecodeError) as e:
            logger.error("Failed to load JSON state: %s", e)
            return False

    def get_metadata(self) -> Optional[dict[str, Any]]:
        """Return metadata about the last saved state."""
        if self._metadata:
            return deepcopy(self._metadata)
        if self._metadata_path.exists():
            try:
                with open(self._metadata_path, "r") as f:
                    return json.load(f)
            except (OSError, json.JSONDecodeError):
                return None
        return None

    def delete_saved_state(self) -> bool:
        """Delete all saved state files from disk."""
        try:
            for path in [self._pickle_path, self._json_path, self._metadata_path]:
                if path.exists():
                    path.unlink()
            logger.info("Saved state files deleted.")
            return True
        except OSError as e:
            logger.error("Failed to delete saved state: %s", e)
            return False

    def __contains__(self, key: str) -> bool:
        return key in self._state

    def __repr__(self) -> str:
        return (
            f"StateManager(app_name={self.app_name!r}, "
            f"entries={len(self._state)}, "
            f"state_dir={str(self.state_dir)!r})"
        )


# Convenience functions for quick save/load without managing a StateManager instance

def save_state(data: Any, filepath: str = ".app_state/quicksave.pkl") -> bool:
    """Quick-save any Python object to a file."""
    try:
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(".tmp")
        with open(tmp_path, "wb") as f:
            pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)
        tmp_path.replace(path)
        return True
    except (OSError, pickle.PicklingError) as e:
        logger.error("Failed to save: %s", e)
        return False


def load_state(filepath: str = ".app_state/quicksave.pkl", default: Any = None) -> Any:
    """Quick-load a Python object from a file."""
    path = Path(filepath)
    if not path.exists():
        return default
    try:
        with open(path, "rb") as f:
            return pickle.load(f)
    except (OSError, pickle.UnpicklingError) as e:
        logger.error("Failed to load: %s", e)
        return default


# --- Demo / Usage Example ---

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Example custom class
    class UserProject:
        def __init__(self, name: str, files: list[str], settings: dict):
            self.name = name
            self.files = files
            self.settings = settings
            self.created_at = datetime.now()

        def __repr__(self):
            return f"UserProject(name={self.name!r}, files={len(self.files)})"

    # Create a state manager
    sm = StateManager(state_dir=".demo_state", app_name="my_app")

    # Store complex nested data
    sm.set("user_preferences", {
        "theme": "dark",
        "font_size": 14,
        "recent_files": ["/path/to/file1.py", "/path/to/file2.py"],
        "window": {"x": 100, "y": 200, "width": 1200, "height": 800},
    })

    # Store a custom object
    project = UserProject(
        name="My Project",
        files=["main.py", "utils.py", "config.yaml"],
        settings={"auto_save": True, "lint_on_save": True},
    )
    sm.set("current_project", project)

    # Store various data types
    sm.set("open_tabs", ["file1.py", "file2.py", "README.md"])
    sm.set("cursor_positions", {
        "file1.py": (42, 10),
        "file2.py": (100, 0),
    })
    sm.set("undo_history", [
        {"action": "insert", "text": "hello", "pos": 0},
        {"action": "delete", "text": "h", "pos": 0},
    ])

    # Save to disk
    print(f"State manager: {sm}")
    sm.save()

    # Also save a JSON version for debugging
    sm.save_json()

    # Simulate app restart - create a new manager and load
    sm2 = StateManager(state_dir=".demo_state", app_name="my_app")
    sm2.load()

    print(f"\nLoaded state manager: {sm2}")
    print(f"Keys: {sm2.keys()}")
    print(f"Preferences: {sm2.get('user_preferences')}")
    print(f"Project: {sm2.get('current_project')}")
    print(f"Tabs: {sm2.get('open_tabs')}")
    print(f"Cursors: {sm2.get('cursor_positions')}")
    print(f"Metadata: {sm2.get_metadata()}")

    # Quick save/load demo
    print("\n--- Quick save/load ---")
    data = {"key": "value", "nested": {"a": [1, 2, 3]}}
    save_state(data, ".demo_state/quick.pkl")
    loaded = load_state(".demo_state/quick.pkl")
    print(f"Quick loaded: {loaded}")

    # Cleanup demo files
    sm2.delete_saved_state()
    import shutil
    shutil.rmtree(".demo_state", ignore_errors=True)
    print("\nDemo state cleaned up.")
