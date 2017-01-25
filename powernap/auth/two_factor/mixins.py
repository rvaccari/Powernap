from flask import current_app, request

from core.extensions import redis_connection
from core.helpers import decode_object
from core.shepherd.two_factor.models import TOTPDevice, StaticOTPDevice


class OTPMixin(object):
    """Add to model that can be :class:`flask_login.current_user`."""
    key = 'otp'

    @property
    def otp_verified(self):
        redis, auth_token = self._redis_data
        return redis.hget(auth_token, self.key) == "True"

    @otp_verified.setter
    def otp_verified(self, v):
        redis, auth_token  = self._redis_data
        redis.hset(auth_token, self.key, bool(v))

    @property
    def totp_device(self):
        return TOTPDevice.query.filter_by(client_id=self.client_id).first()

    @property
    def static_otp_device(self):
        return StaticOTPDevice.query.filter_by(client_id=self.client_id).first()

    @property
    def confirmed_totp_device(self):
        return bool(getattr(self.totp_device, 'confirmed', False))

    def activate_totp(self, static_tokens=False):
        device = self.totp_device
        device.confirmed = True
        device.save()
        self.otp_verified = True
        if static_tokens:
            return self.create_static_otp_tokens()

    def check_otp(self, token):
        for device in [self.totp_device, self.static_otp_device]:
            if device and device.verify_token(token):
                return True
        return False

    def create_static_otp_tokens(self):
        device = self.static_otp_device or StaticOTPDevice.create_for_user(self)
        return decode_object(device.new_tokens())

    def delete_otp_devices(self):
        for device in [self.totp_device, self.static_otp_device]:
            if device:
                device.delete()
        self.otp_verified = False

    @property
    def _redis_data(self):
        redis = redis_connection()
        auth_token = request.headers.get('X-Auth')
        return redis, auth_token
