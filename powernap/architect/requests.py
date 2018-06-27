# pylint: disable=too-many-ancestors
"""Extend Flask's Request class with fixes and helpers"""

import ipaddress
from contextlib import suppress

from flask import Request, current_app
from werkzeug.datastructures import MultiDict
from werkzeug.exceptions import BadRequest
from werkzeug.utils import cached_property

from powernap.exceptions import InvalidJsonError


class ApiRequest(Request):
    """Extended Request class with fixes and helpers"""

    @cached_property
    def jsonform(self):
        """Parses and returns form for JSON body"""
        formdata = {}
        with suppress(BadRequest):
            formdata = self.get_json(force=True) or {}
            if not isinstance(formdata, dict):
                raise InvalidJsonError(description="Form not API compatible: must be JSON object.")
            if formdata and self.mimetype != 'application/json':
                current_app.logger.warning(
                    'JSON data with incorrect mimetype! {} {} {} {}'.format(
                        self.remote_addr, self.method, self.scheme, self.full_path,
                    ))
        return MultiDict(formdata)

    @property
    def remote_addr(self):
        """Safely get the originating ip of the request.

        See: https://stackoverflow.com/a/22936947/3453043

        Walks a list of originating IP addresses backwards until
        one is found from outside of all trusted proxy networks.
        Return the most recent address, remote_addr, if all are
        trusted.
        """
        remote_addr = super(ApiRequest, self).remote_addr

        if not remote_addr:
            return '127.0.0.1'

        route = reversed(self.access_route + [remote_addr])
        route = map(ipaddress.ip_address, route)
        trusted_proxies = map(ipaddress.ip_network, self.trusted_proxies)

        def untrusted(addr):
            "Return True if addr is NOT included inside any trusted networks"
            return not any(addr in net for net in trusted_proxies)

        untrusted_routes = filter(untrusted, route)
        return str(next(untrusted_routes, remote_addr))

    @property
    def trusted_proxies(self):
        """Return list of trusted proxy networks, e.g. ['192.168.1.0/24']"""
        return current_app.config.get('TRUSTED_PROXIES', [])
