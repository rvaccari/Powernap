import hmac
import time
from base64 import b32encode
from copy import deepcopy
from binascii import hexlify, unhexlify
from hashlib import sha1
from io import BytesIO
from os import urandom
from struct import pack


from flask import current_app
from flask_login import current_user
from sqlalchemy import (
    Column,
    BigInteger,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
)
from sqlalchemy.orm import relationship
import qrcode
import qrcode.image.svg

from core.extensions import db
from core.helpers import decode_object, timestamp_now, totp_auth_uri
from core.hvdb.mixins import UberUserMapperMixin
from core.hvdb.models import AuthUser
from core.mixins import CoreMixin


__all__ = ['TOTPDevice', 'StaticOTPDevice', 'StaticOTPToken']


iterbytes = lambda buf: (ord(b) for b in buf)


def default_key():
    return hexlify(urandom(20))


def hotp(key, counter, digits=6):
    """
    Implementation of the HOTP algorithm from `RFC 4226
    <http://tools.ietf.org/html/rfc4226#section-5>`_.

    :param bytes key: The shared secret. A 20-byte string is recommended.
    :param int counter: The password counter.
    :param int digits: The number of decimal digits to generate.
    """
    msg = pack('>Q', counter)
    hs = [char for char in hmac.new(key, msg, sha1).digest()]
    offset = hs[19] & 0x0f
    bin_code = (hs[offset] & 0x7f) << 24 | hs[offset + 1] << 16 | hs[offset + 2] << 8 | hs[offset + 3]
    hotp = bin_code % pow(10, digits)

    return hotp


class TOTP(object):
    """
    :param bytes key: The shared secret. A 20-byte string is recommended.
    :param int step: The time step in seconds. The time-based code changes
        every ``step`` seconds.
    :param int t0: The Unix time at which to start counting time steps.
    :param int digits: The number of decimal digits to generate.
    :param int drift: The number of time steps to add or remove. Delays and
        clock differences might mean that you have to look back or forward a
        step or two in order to match a token.
    """
    def __init__(self, key, step=30, t0=0, digits=6, drift=0):
        self.key = key
        self.step = step
        self.t0 = t0
        self.digits = digits
        self.drift = drift
        self._time = None

    def token(self):
        """ The computed TOTP token. """
        return hotp(self.key, self.t(), digits=self.digits)

    def t(self):
        """ The computed time step. """
        return ((int(self.time) - self.t0) // self.step) + self.drift

    @property
    def time(self):
        """
        The current time.

        By default, this returns time.time() each time it is accessed. If you
        want to generate a token at a specific time, you can set this property
        to a fixed value instead. Deleting the value returns it to its 'live'
        state.

        """
        return self._time if (self._time is not None) else time.time()

    @time.setter
    def time(self, value):
        self._time = value

    @time.deleter
    def time(self):
        self._time = None


class _BaseOTPDevice(object):
    def save(self, *args, **kwargs):
        # Ensure only one OTP Device of a type exists for a client.
        self.delete_all_except(self.id)
        super(_BaseOTPDevice, self).save(*args, **kwargs)

    def delete_all_except(self, id=0):
        cls = self.__class__
        cls.query.filter(
            cls.id != id, cls.client_id == self.client_id
        ).delete(synchronize_session=False)

    @classmethod
    def create_for_user(cls, user, **kwargs):
        data = deepcopy(cls.defaults)
        data.update(kwargs)
        device = cls(**data)
        device.client_id = user.client_id
        device.save()
        return device


class TOTPDevice(_BaseOTPDevice, UberUserMapperMixin, CoreMixin, db.Model):
    __tablename__ = 'otp_totp_totpdevice'
    __bind_key__ = 'hvdb'

    id = Column(Integer, primary_key=True)
    _user_id = Column('user_id', ForeignKey(AuthUser.id), nullable=False, index=True)
    name = Column(String(64, 'utf8_bin'), nullable=False)
    confirmed = Column(Integer, nullable=False)
    key = Column(String(80, 'utf8_bin'), nullable=False)
    step = Column(SmallInteger, nullable=False)
    t0 = Column(BigInteger, nullable=False)
    digits = Column(SmallInteger, nullable=False)
    tolerance = Column(SmallInteger, nullable=False)
    drift = Column(SmallInteger, nullable=False)
    last_t = Column(BigInteger, nullable=False)

    defaults = {
        'name': '',
        'confirmed': False,
        'step': 30,
        't0': 0,
        'digits': 6,
        'tolerance': 1,
        'drift': 0,
        'last_t': timestamp_now(),
    }

    def __init__(self, *args, **kwargs):
        super(TOTPDevice, self).__init__(*args, **kwargs)
        if not self.key:
            self.key = default_key()

    @property
    def bin_key(self):
        """The secret key as a binary string."""
        return unhexlify(decode_object(self.key).encode())

    @property
    def public_key(self):
        """The secret key decoded for use with an authenticator."""
        return b32encode(self.bin_key)

    @property
    def valid_token(self):
        """A valid OTP token."""
        totp = TOTP(self.bin_key, self.step, self.t0, self.digits)
        totp.time = time.time()
        return decode_object(totp.token())

    @property
    def qr_code(self):
        f = BytesIO()
        image_factory = qrcode.image.svg.SvgImage
        uri = totp_auth_uri(current_user.login, self.public_key,
                            current_app.config["PROJECT"])
        qr = qrcode.make(uri, image_factory=image_factory)
        qr.save(decode_object(f))
        return f.getvalue().decode()

    def verify_token(self, token):
        return token == self.valid_token or self.verify_token_with_offset(token)

    def verify_token_with_offset(self, token):
        totp = TOTP(self.bin_key, self.step, self.t0, self.digits)
        totp.time = time.time()
        for offset in range(-self.tolerance, self.tolerance + 1):
            totp.drift = self.drift + offset
            if (totp.t() > self.last_t) and (totp.token() == token):
                self.last_t = totp.t()
                if (offset != 0):
                    self.drift += offset
                self.save()
                return True
        return False


class StaticOTPDevice(_BaseOTPDevice, UberUserMapperMixin, CoreMixin, db.Model):
    __tablename__ = 'otp_static_staticdevice'
    __bind_key__ = 'hvdb'

    id = Column(Integer, primary_key=True)
    _user_id = Column('user_id', ForeignKey(AuthUser.id), nullable=False, index=True)
    name = Column(String(64, 'utf8_bin'), nullable=False)
    confirmed = Column(Integer, nullable=False)

    tokens = relationship('StaticOTPToken', backref="device",
                          cascade="all, delete, delete-orphan")

    defaults = {
        'name': 'backups',
        'confirmed': True,
    }

    def new_tokens(self):
        self.delete_tokens()
        return self.create_tokens()

    def create_tokens(self):
        for _ in range(0, 10):
            token = StaticOTPToken(token=StaticOTPToken.random_token(),
                                   device_id=self.id)
            token.save()
        return self.tokens

    def delete_tokens(self):
        StaticOTPToken.query.filter_by(device_id=self.id).delete(
            synchronize_session=False
        )

    def verify_token(self, token):
        return token in [decode_object(t.token) for t in self.tokens]


class StaticOTPToken(CoreMixin, db.Model):
    __tablename__ = 'otp_static_statictoken'
    __bind_key__ = 'hvdb'

    id = Column(Integer, primary_key=True)
    device_id = Column(Integer, ForeignKey(StaticOTPDevice.id), nullable=False, index=True)
    token = Column(String(16, 'utf8_bin'), nullable=False, index=True)

    def api_response(self):
        return {'id': self.id, 'token': self.token}

    @staticmethod
    def random_token():
        return b32encode(urandom(5)).lower()
