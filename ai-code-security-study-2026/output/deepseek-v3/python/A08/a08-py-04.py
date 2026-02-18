import pickle
import os

def save_state(state, filepath):
    with open(filepath, 'wb') as file:
        pickle.dump(state, file)

def load_state(filepath):
    if not os.path.exists(filepath):
        return None
    with open(filepath, 'rb') as file:
        return pickle.load(file)
