from flask import Request
from werkzeug.datastructures import MultiDict
from werkzeug.exceptions import BadRequest

from powernap.exceptions import InvalidJsonError


class ApiRequest(Request):
    def _load_form_data(self):
        """Makes request.form access the JSON body"""
        try:
            formdata = self.get_json(force=True)
        except BadRequest:
            formdata = {}
        if not formdata:
            formdata = {}
        if not isinstance(formdata, dict):
            raise InvalidJsonError(description="Form not JSON compatible.")
        formdata = MultiDict(list(formdata.items()))

        d = self.__dict__
        d['form'] = formdata
        d['files'], d['stream'] = None, None
