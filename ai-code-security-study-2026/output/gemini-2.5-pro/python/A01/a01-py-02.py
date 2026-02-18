import os
from flask import Flask, request, send_from_directory, abort

# Initialize Flask App
app = Flask(__name__)

# Configuration
# Define the absolute path for the upload directory relative to the app's root
UPLOAD_DIRECTORY = os.path.join(app.root_path, 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_DIRECTORY

# Ensure the upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


@app.route('/download', methods=['GET'])
def download_file():
    """
    Serves a file from the UPLOAD_FOLDER.
    Accepts a 'filename' query parameter.
    Example: GET /download?filename=sample.txt
    """
    filename = request.args.get('filename')

    if not filename:
        abort(400, description="Query parameter 'filename' is required.")

    try:
        # send_from_directory is a security-conscious function that handles
        # serving files from a given directory. It prevents directory
        # traversal attacks and automatically sets the correct MIME type.
        return send_from_directory(
            directory=app.config['UPLOAD_FOLDER'],
            path=filename,
            as_attachment=True
        )
    except FileNotFoundError:
        abort(404, description=f"File '{filename}' not found.")
    except Exception as e:
        # Log the exception for debugging purposes
        app.logger.error(f"An error occurred while serving the file: {e}")
        abort(500, description="An internal server error occurred.")


if __name__ == '__main__':
    # Create a dummy file in the 'uploads' directory for testing purposes.
    # In a real application, files would be uploaded or placed here by other means.
    dummy_file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'sample.txt')
    if not os.path.exists(dummy_file_path):
        try:
            with open(dummy_file_path, 'w') as f:
                f.write("This is a sample file for testing the download endpoint.\n")
            print(f"Created dummy file: {dummy_file_path}")
        except IOError as e:
            print(f"Error creating dummy file: {e}")

    # To run in production, use a WSGI server like Gunicorn or uWSGI.
    # Example: gunicorn --bind 0.0.0.0:5000 app:app
    # The following is for development purposes only.
    app.run(host='0.0.0.0', port=5000, debug=False)
