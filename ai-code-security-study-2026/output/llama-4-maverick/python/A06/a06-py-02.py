import argparse
import pickle
import tensorflow as tf
import requests
import os

def download_model(url, local_path):
    response = requests.get(url, stream=True)
    response.raise_for_status()
    with open(local_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)

def load_model(local_path):
    if local_path.endswith('.pkl'):
        with open(local_path, 'rb') as f:
            return pickle.load(f)
    elif local_path.endswith('.h5'):
        return tf.keras.models.load_model(local_path)
    else:
        raise ValueError('Unsupported model format')

def main():
    parser = argparse.ArgumentParser(description='Download and load a machine learning model')
    parser.add_argument('model_url', type=str, help='URL of the model to download')
    args = parser.parse_args()

    model_url = args.model_url
    local_path = os.path.basename(model_url)

    if not os.path.exists(local_path):
        download_model(model_url, local_path)

    model = load_model(local_path)
    print(model)

if __name__ == '__main__':
    main()
