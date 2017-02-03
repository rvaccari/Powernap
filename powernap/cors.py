def init_cors(app):
    """Allow intial pre-flight "OPTIONS" request globally on app."""
    @app.after_request
    def add_cors(resp):
        from flask import request
        if request.method == "OPTIONS":
            resp.status_code = 200
            allow_origin = request.headers.get('Origin', '*')
            allow_headers = request.headers.get(
                'Access-Control-Request-Headers', 'Authorization'
            )
            resp.headers['Access-Control-Allow-Origin'] = allow_origin
            resp.headers['Access-Control-Allow-Credentials'] = 'true'
            resp.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS, GET, PUT, DELETE'
            resp.headers['Access-Control-Allow-Headers'] = allow_headers
            if app.debug:
                resp.headers['Access-Control-Max-Age'] = '1'
        return resp
