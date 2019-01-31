import os

import pytest
from flask import Flask


@pytest.fixture
def app():
    app_ = Flask(__name__)
    app_.config.update(
        TESTING=True,
        SECRET_KEY=os.urandom(24)
    )
    return app_


@pytest.fixture
def flask_session(app):
    with app.test_client() as test_client:
        test_client.get('/')
        yield test_client.session_transaction()
