from datetime import date
from decimal import Decimal
from unittest.mock import patch, Mock

import pytest
from flask import Response, Flask
from flask_sqlalchemy import Pagination

from powernap.architect.responses import APIEncoder, ApiResponse
from powernap.http_codes import success_code, error_code


class StubUser:
    def __init__(self, id_=1, user_id=1, name='user'):
        self.id = id_
        self.user_id = user_id
        self.name = name


class StubUserApiResponse(StubUser):
    def __init__(self, id_=1, user_id=1, name='user'):
        self.id = id_
        self.user_id = user_id
        self.name = name

    def api_response(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
        }


class TestAPIEncoder:

    def test_default_api_encoder_is_float(self):
        """Should return a float when it receives a decimal"""

    assert type(APIEncoder().default(Decimal(1.5))) is float

    def test_default_api_encoder_is_isoformat(self):
        """Should return a str when it receives a isoformt"""

        dt = APIEncoder().default(date(2019, 1, 1))
        assert type(dt) is str
        assert '2019-01-01' == dt

    def test_default_api_not_serializable(self):
        """Should return a TypeError when when can not convert the parameter"""

        with pytest.raises(TypeError) as exc_info:
            APIEncoder().default("test")

        exception_raised = exc_info.value
        expected = 'test is not json serilaizable. Did you add an "api_response" method?'
        assert str(exception_raised) == expected

    def test_api_encoder_is_api_reponse(self):
        """Should must return the formatted object according to api_reponse"""

        stub_user = StubUserApiResponse()
        resp = APIEncoder().default(stub_user)
        assert not hasattr(resp, 'name')

    def test_api_encoder_erro_not_serilaizable(self):
        """Should return a TypeError when the object is not serializable"""

        stub_user = StubUser()
        with pytest.raises(TypeError) as exc_info:
            APIEncoder().default(stub_user)
        assert exc_info.type is TypeError


class TestApiResponse:
    app = Flask(__name__)

    @pytest.fixture
    @patch('powernap.architect.responses.session')
    def api_response(self, mock_session):
        mock_session.exclude_properties = ['id']
        data = dict(id=1, name='Test')
        return ApiResponse(data, success_code)

    def test_response_status_code(self, api_response):
        """Should return status code."""
        with self.app.app_context():
            resp, status_code = api_response.response
            assert status_code == success_code

    def test_response_minetype(self, api_response):
        """Should return application/json."""
        with self.app.app_context():
            resp, status_code = api_response.response
            assert resp.mimetype == 'application/json'

    def test_response_type_reponse(self, api_response):
        """Should return an Response."""
        with self.app.app_context():
            resp, status_code = api_response.response
            assert type(resp) is Response

    @patch('powernap.architect.responses.session')
    def test_pagination(self, mock_session):
        """Should return page when a list is sent"""
        with self.app.app_context():
            mocked_pagination = Mock(spec=Pagination)
            mocked_pagination.page = 1
            mocked_pagination.pages = 2
            mocked_pagination.has_next = True
            mocked_pagination.next_num = 2
            mocked_pagination.per_page = 5
            mocked_pagination.has_prev = False
            mocked_pagination.total = 8
            mocked_pagination.items = (
                StubUserApiResponse(id_=1, user_id=1, name='David Bledsoe'),
                StubUserApiResponse(id_=2, user_id=2, name='Larry Farnell'),
            )
            resp, status = ApiResponse(mocked_pagination, success_code).response
            assert resp.json == [{'id': 1, 'user_id': 1}, {'id': 2, 'user_id': 2}]
            assert 'X-Pagination' in resp.headers

    @patch('powernap.architect.responses.logging')
    @patch('powernap.architect.responses.request')
    @patch('powernap.architect.responses.session')
    @patch('flask_login.utils._get_user')
    def test_log_warning_when_user_admin_and_not_debug(self, current_user,
                                                       mock_session,
                                                       mock_request,
                                                       mock_logging):
        """Should generate warning when user is admin and not DEBUG"""
        self.app.config['DEBUG'] = False
        with self.app.app_context():
            current_user.is_admin = True
            current_user.return_value = current_user
            ApiResponse('', error_code).response
            assert mock_logging.warning.called

    @patch('powernap.architect.responses.logging')
    @patch('powernap.architect.responses.request')
    @patch('powernap.architect.responses.session')
    @patch('flask_login.utils._get_user')
    def test_not_log_warning_when_user_not_admin_and_not_debug(self, current_user,
                                                               mock_session,
                                                               mock_request,
                                                               mock_logging):
        """Should not generate a warning when the user is not admin and not DEBUG"""
        self.app.config['DEBUG'] = False
        with self.app.app_context():
            current_user.is_admin = False
            current_user.return_value = current_user
            ApiResponse('', error_code).response
            assert not mock_logging.warning.called
