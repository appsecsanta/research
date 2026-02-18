import pickle
import os

def save_state(state, filename):
    with open(filename, 'wb') as f:
        pickle.dump(state, f)

def load_state(filename):
    if os.path.exists(filename):
        with open(filename, 'rb') as f:
            return pickle.load(f)
    else:
        return None

class CustomClass:
    def __init__(self, value):
        self.value = value

def main():
    state = {
        'nested_dict': {'a': 1, 'b': 2},
        'list': [1, 2, 3],
        'custom_class': CustomClass('test')
    }
    filename = 'state.pkl'
    save_state(state, filename)
    loaded_state = load_state(filename)
    print(loaded_state)

if __name__ == "__main__":
    main()
