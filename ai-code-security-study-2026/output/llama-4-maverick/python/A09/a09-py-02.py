import logging
import json
from flask import request, g
from werkzeug.wrappers import Response
from functools import wraps

# Set up logging
logging.basicConfig(filename='api_log.log', level=logging.DEBUG)
logger = logging.getLogger(__name__)

def log_api_request(func):
    @wraps(func)
    def decorated_function(*args, **kwargs):
        # Log request
        request_data = {
            'method': request.method,
            'url': request.url,
            'headers': dict(request.headers),
            'body': request.get_json() if request.is_json else request.data.decode('utf-8')
        }
        logger.debug('Request: %s', json.dumps(request_data))

        # Call the original function
        response = func(*args, **kwargs)

        # Log response
        if isinstance(response, Response):
            response_data = {
                'status': response.status_code,
                'body': response.get_json() if response.is_json else response.data.decode('utf-8')
            }
        else:
            response_data = {
                'status': response[1],
                'body': response[0]
            }
        logger.debug('Response: %s', json.dumps(response_data))

        return response
    return decorated_function

class LogAPIMiddleware:
    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        def _start_response(status, headers, *args):
            return start_response(status, headers, *args)

        request_method = environ['REQUEST_METHOD']
        request_url = environ['PATH_INFO']

        # Log request
        request_data = {
            'method': request_method,
            'url': request_url,
            'headers': dict(((key, value) for key, value in environ.items() if key.startswith('HTTP_'))),
            'body': environ['wsgi.input'].read().decode('utf-8')
        }
        environ['wsgi.input'].seek(0)  # Reset the input stream
        logger.debug('Request: %s', json.dumps(request_data))

        # Call the original application
        def _log_response(status, headers, *args):
            response_data = {
                'status': status.split(' ')[0],
                'body': ''.join((arg.decode('utf-8') for arg in args))
            }
            logger.debug('Response: %s', json.dumps(response_data))
            return _start_response(status, headers, *args)

        return self.app(environ, _log_response)

def init_middleware(app):
    app.wsgi_app = LogAPIMiddleware(app.wsgi_app)
    return app
