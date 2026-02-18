# File: model_loader.py
#
# Description: A script to download a machine learning model from a URL,
#              save it locally, and load it for inference.
#
# Dependencies: requests, tqdm, tensorflow
# To install:
# pip install requests tqdm tensorflow
#
# Usage:
# python model_loader.py <URL_TO_MODEL> [--output-dir /path/to/save]
#
# Example:
# python model_loader.py https://example.com/models/my_keras_model.h5
# python model_loader.py https://example.com/models/my_sklearn_model.pkl --output-dir ./models

import argparse
import logging
import pickle
import sys
from pathlib import Path
from typing import Any, List, Optional
from urllib.parse import urlparse

import requests
from tqdm import tqdm

# --- Constants ---
SUPPORTED_FORMATS = {".pkl", ".h5"}
CHUNK_SIZE = 8192  # 8 KB

# --- Logging Configuration ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)


def download_file(url: str, destination: Path) -> None:
    """
    Downloads a file from a URL to a local destination with a progress bar.

    Args:
        url: The URL of the file to download.
        destination: The local path to save the file.

    Raises:
        requests.exceptions.RequestException: For network-related errors.
    """
    logging.info(f"Starting download from {url}")
    try:
        with requests.get(url, stream=True, timeout=30) as response:
            response.raise_for_status()
            total_size = int(response.headers.get("content-length", 0))

            with open(destination, "wb") as f, tqdm(
                desc=destination.name,
                total=total_size,
                unit="iB",
                unit_scale=True,
                unit_divisor=1024,
            ) as bar:
                for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                    size = f.write(chunk)
                    bar.update(size)
        logging.info(f"Successfully downloaded model to {destination}")
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to download file: {e}")
        # Clean up partially downloaded file if it exists
        if destination.exists():
            destination.unlink()
        raise


def load_model_from_path(model_path: Path) -> Any:
    """
    Loads a machine learning model from a local file.

    Supports .pkl and .h5 formats.

    Args:
        model_path: The path to the model file.

    Returns:
        The loaded model object.

    Raises:
        ValueError: If the model format is not supported.
        ImportError: If required libraries for a format are not installed.
        Exception: For errors during model loading.
    """
    if not model_path.exists():
        raise FileNotFoundError(f"Model file not found at {model_path}")

    file_extension = model_path.suffix.lower()
    logging.info(f"Attempting to load model with format: {file_extension}")

    if file_extension == ".pkl":
        # For scikit-learn models, joblib can be more efficient with numpy arrays.
        # To use it, replace 'pickle' with 'joblib'.
        logging.warning(
            "SECURITY WARNING: Loading pickle files from untrusted sources "
            "can execute arbitrary code. Only load files you trust."
        )
        try:
            with open(model_path, "rb") as f:
                model = pickle.load(f)
            logging.info("Pickle model loaded successfully.")
            return model
        except pickle.UnpicklingError as e:
            logging.error(f"Failed to unpickle model: {e}")
            raise
        except Exception as e:
            logging.error(f"An unexpected error occurred while loading PKL model: {e}")
            raise

    elif file_extension == ".h5":
        try:
            from tensorflow.keras.models import load_model as keras_load_model
        except ImportError as e:
            logging.error(
                "TensorFlow is not installed. Please install it to load .h5 models: "
                "'pip install tensorflow'"
            )
            raise ImportError from e

        try:
            # Set compile=False for faster loading if you only need inference
            # and the model doesn't have custom objects.
            model = keras_load_model(model_path, compile=False)
            logging.info("H5 (Keras/TensorFlow) model loaded successfully.")
            return model
        except Exception as e:
            logging.error(f"Failed to load H5 model: {e}")
            raise
    else:
        raise ValueError(
            f"Unsupported model format: {file_extension}. "
            f"Supported formats are: {', '.join(SUPPORTED_FORMATS)}"
        )


def main(cli_args: Optional[List[str]] = None) -> int:
    """
    Main function to download and load a machine learning model.

    Args:
        cli_args: Command-line arguments (for testing purposes).

    Returns:
        0 on success, 1 on failure.
    """
    parser = argparse.ArgumentParser(
        description="Download and load a machine learning model from a URL.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "url",
        type=str,
        help="URL of the machine learning model file (.pkl or .h5).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path.cwd(),
        help="Directory to save the downloaded model.",
    )
    args = parser.parse_args(cli_args)

    try:
        # Ensure output directory exists
        args.output_dir.mkdir(parents=True, exist_ok=True)

        # Determine filename from URL
        url_path = urlparse(args.url).path
        file_name = Path(url_path).name
        if not file_name:
            logging.error("Could not determine filename from URL.")
            return 1

        local_model_path = args.output_dir / file_name

        if local_model_path.suffix.lower() not in SUPPORTED_FORMATS:
            logging.error(
                f"URL does not point to a supported model format "
                f"({', '.join(SUPPORTED_FORMATS)})."
            )
            return 1

        # Download the model
        download_file(args.url, local_model_path)

        # Load the model
        model = load_model_from_path(local_model_path)

        # Placeholder for inference
        logging.info(f"Model loaded successfully. Type: {type(model)}")
        logging.info("Ready for inference.")
        # Example of using the loaded model:
        # if hasattr(model, 'summary'):
        #     model.summary()

        return 0

    except (
        requests.exceptions.RequestException,
        FileNotFoundError,
        ValueError,
        ImportError,
    ) as e:
        logging.error(f"A critical error occurred: {e}")
        return 1
    except Exception as e:
        logging.error(f"An unexpected error occurred in the main process: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
