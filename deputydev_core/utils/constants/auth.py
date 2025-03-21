from enum import Enum


class AuthStatus(Enum):
    VERIFIED = "VERIFIED"
    NOT_VERIFIED = "NOT_VERIFIED"
    AUTHENTICATED = "AUTHENTICATED"
    PENDING = "PENDING"
    EXPIRED = "EXPIRED"
