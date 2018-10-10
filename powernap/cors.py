"""Add CORS support to all of Flask."""

import flask.logging
import logging
from flask_cors import CORS


def init_cors(app):
    """Allow intial pre-flight "OPTIONS" request globally on app."""
    logging.getLogger('flask_cors').addHandler(flask.logging.default_handler)
    # Uncomment to debug CORS
    # logging.getLogger('flask_cors').setLevel(logging.DEBUG)

    CORS(app)
