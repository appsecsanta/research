import pickle
import os

def save_state(state, filepath):
    """
    Save the application state to disk using pickle serialization.

    :param state: The Python object to serialize and save.
    :param filepath: The path to the file where the state will be saved.
    """
    # Ensure the directory exists
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    
    with open(filepath, 'wb') as f:
        pickle.dump(state, f)

def load_state(filepath):
    """
    Load the application state from disk using pickle deserialization.

    :param filepath: The path to the file from which to load the state.
    :return: The deserialized Python object.
    :raises FileNotFoundError: If the file does not exist.
    :raises pickle.UnpicklingError: If deserialization fails.
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"State file not found: {filepath}")
    
    with open(filepath, 'rb') as f:
        return pickle.load(f)
