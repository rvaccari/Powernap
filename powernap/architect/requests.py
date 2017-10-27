import ipaddress

from flask import Request, current_app
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

    @property
    def remote_addr(self):
        """Safely get the originating ip of the request.

        See: https://stackoverflow.com/a/22936947/3453043
        """
        remote_addr = super(ApiRequest, self).remote_addr
        route = reversed(self.access_route + [remote_addr])
        route = map(ipaddress.ip_address, route)
        trusted_proxies = map(ipaddress.ip_network, self.trusted_proxies)

        if not route:
            return ''

        for ip in route:
            for proxy in trusted_proxies:
                if ip in trusted_proxies:
                    continue
            return str(ip)

    @property
    def trusted_proxies(self):
        return current_app.config.get('TRUSTED_PROXIES', [])
