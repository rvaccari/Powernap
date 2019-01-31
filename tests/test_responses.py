from datetime import date
from decimal import Decimal

import pytest
from flask import Response

from powernap.architect.responses import APIEncoder, ApiResponse


class TestAPIEncoder:

    def test_default_api_encoder_is_float(self):
        assert type(APIEncoder().default(Decimal(1.5))) is float

    def test_default_api_encoder_is_isoformat(self):
        dt = APIEncoder().default(date(2019, 1, 1))
        assert type(dt) is str
        assert '2019-01-01' == dt

    def test_default_api_not_serializable(self):
        with pytest.raises(TypeError) as exc_info:
            APIEncoder().default("test")

        exception_raised = exc_info.value
        expected = 'test is not json serilaizable. Did you add an "api_response" method?'
        assert str(exception_raised) == expected


class TestApiResponse:
    @pytest.fixture
    def api_response(self):
        data = dict(name='Test')
        return ApiResponse(data, 400)

    def test_response_status_code(self, flask_session, api_response):
        resp, status_code = api_response.response
        assert status_code == 400

    def test_response_minetype(self, flask_session, api_response):
        resp, status_code = api_response.response
        assert resp.mimetype == 'application/json'

    def test_response_type_reponse(self, flask_session, api_response):
        resp, status_code = api_response.response
        assert type(resp) is Response
