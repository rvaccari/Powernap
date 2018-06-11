import ipaddress

from flask import Request, current_app
from werkzeug.datastructures import MultiDict
from werkzeug.exceptions import BadRequest
from werkzeug.utils import cached_property

from powernap.exceptions import InvalidJsonError


class ApiRequest(Request):
    @cached_property
    def data(self):
        """Contains the incoming request data as string in case it came with
        a mimetype Werkzeug does not handle.

        Note: This is a complete clone of `werkzeug.wrappers.data()` changing
        only `parse_form_data` from True to False. This fixes the recursion
        error, `self.stream == None`, caused by Sentry raven calling
        `get_json_data`."""
        if self.disable_data_descriptor:
            raise AttributeError('data descriptor is disabled')
        return self.get_data(parse_form_data=False)

    def _load_form_data(self):
        """Makes request.form access the JSON body"""
        try:
            formdata = self.get_json(force=True)
        except BadRequest:
            formdata = {}
        if not formdata:
            formdata = {}
        if not isinstance(formdata, dict):
            raise InvalidJsonError(description="Form not API compatible JSON.")
        formdata = MultiDict(list(formdata.items()))

        d = self.__dict__
        d['form'] = formdata
        d['files'], d['stream'] = None, None

    @property
    def remote_addr(self):
        """Safely get the originating ip of the request.

        See: https://stackoverflow.com/a/22936947/3453043
        """
        remote_addr = super(ApiRequest, self).remote_addr

        if not remote_addr:
            return '127.0.0.1'

        route = reversed(self.access_route + [remote_addr])
        route = map(ipaddress.ip_address, route)
        trusted_proxies = map(ipaddress.ip_network, self.trusted_proxies)

        for ip in route:
            for proxy in trusted_proxies:
                if ip in trusted_proxies:
                    continue
            return str(ip)

    @property
    def trusted_proxies(self):
        return current_app.config.get('TRUSTED_PROXIES', [])
