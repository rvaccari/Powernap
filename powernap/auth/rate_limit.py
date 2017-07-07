import ipaddress

from flask import current_app, request
from flask_login import current_user

from powernap.exceptions import RequestLimitError
from powernap.helpers import redis_connection


def check_rate_limit():
    rl = RateLimiter(current_user)
    if rl.is_rate_limited():
        msg = "You have hit the rate limit. Don't worry it will reset soon."
        raise RequestLimitError(description=msg)


class RateLimiter:
    """Handles rate limit functionality: count, session, & headers."""
    def __init__(self, user, db=0):
        """
        :param user: A user who inherits from
            :class`core.shepherd.mixins.PermissionsMixin`
        :param db: The redis db num to connect to.
        """
        self.ip = request.remote_addr
        self.redis = redis_connection(db)
        self.user = user

    def headers(self):
        """Return ratelimit headers for `self.user`.

        Format:
            X-RateLimit-Limit: The maximum amount of requests.
            X-RateLimit-Remaining: The number of requests Remaining.
            X-RateLimit-Reset: Seconds until reset of ratelimit.
        """
        token, limit = self.token, self.limit
        remaining = limit - int(self.redis.get(token) or 0)
        if remaining < 0:
            remaining = 0
        return {
            'X-RateLimit-Limit': limit,
            'X-RateLimit-Remaining': remaining,
            'X-RateLimit-Reset': self.redis.ttl(token),
        }

    def is_rate_limited(self):
        return not self.ip_is_whitelisted() and \
                self.over_limit(self.token, self.limit)

    def over_limit(self, key, limit):
        if self.redis.exists(key):
            requests = self.redis.incr(key)
        else:
            requests = self.redis.setex(
                key, 1, current_app.config['RATE_LIMIT_EXPIRATION']
            )

        if not current_app.config.get("RATE_LIMITING", True):
            return False
        return requests > limit

    def ip_is_whitelisted(self):
        whitelist = current_app.config.get('RATE_LIMIT_WHITELIST', [])
        whitelist = [ipaddress.ip_network(ip) for ip in whitelist]
        request_ip = ipaddress.IPv4Address(self.ip)
        for network in whitelist:
            if request_ip in network:
                return True
        return False

    @property
    def token(self):
        if self.user.is_authenticated:
            return self.redis_token()
        return self.ip

    @property
    def limit(self):
        val = 'REQUESTS_PER_HOUR'
        if self.user.is_authenticated:
            val = 'AUTHENTICATED_REQUESTS_PER_HOUR'
        return current_app.config[val]

    def redis_token(self):
        return "{}:{}:{}".format(
            str(self.user.__class__),
            self.user.id,
            request.remote_addr,
        )
