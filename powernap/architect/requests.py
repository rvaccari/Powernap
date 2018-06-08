import ipaddress

from flask import Request, current_app
from werkzeug.datastructures import MultiDict
from werkzeug.exceptions import BadRequest
from werkzeug.utils import cached_property

from powernap.exceptions import InvalidJsonError


class ApiRequest(Request):
    @cached_property
    def form(self):
        """Parses and requires request.form to be a JSON dict/map"""
        formdata = self.get_json(force=True, silent=True) or {}
        if not isinstance(formdata, dict):
            raise InvalidJsonError(description="Form not API compatible JSON.")
        return MultiDict(formdata)

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
