import io
import logging
from werkzeug.wrappers import Request

class LoggingMiddleware:
    def __init__(self, app, log_file='api_logs.log'):
        self.app = app
        logging.basicConfig(
            filename=log_file,
            level=logging.INFO,
            format='%(asctime)s %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

    def __call__(self, environ, start_response):
        req = Request(environ)
        body = req.get_data()
        log_entry = {
            'method': req.method,
            'url': req.url,
            'headers': dict(req.headers),
            'body': body.decode('utf-8', errors='ignore')
        }
        environ['wsgi.input'] = io.BytesIO(body)

        response_body = bytearray()
        status = [None]
        headers = [None]

        def logging_start_response(resp_status, resp_headers, exc_info=None):
            status[0] = resp_status
            headers[0] = resp_headers
            return start_response(resp_status, resp_headers, exc_info)

        app_iter = self.app(environ, logging_start_response)

        def generate():
            nonlocal response_body
            try:
                for chunk in app_iter:
                    response_body.extend(chunk)
                    yield chunk
            finally:
                if hasattr(app_iter, 'close'):
                    app_iter.close()

        output = generate()

        for chunk in output:
            yield chunk

        log_entry.update({
            'status': status[0],
            'response_headers': headers[0],
            'response_body': bytes(response_body).decode('utf-8', errors='ignore')
        })
        logging.info(log_entry)
