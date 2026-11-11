import time
from dataclasses import asdict, dataclass

EXPIRY_MARGIN = 60


@dataclass
class TokenSet:
    """One sign-in session's tokens. expires_at is in seconds since the epoch."""

    api_url: str
    access_token: str
    refresh_token: str | None
    expires_at: float
    auth_time: int | None = None
    user_unique_id: str | None = None
    grant: str = 'authorization_code'

    @classmethod
    def from_response(cls, api_url: str, body: dict, grant: str, now: float | None = None) -> 'TokenSet':
        current = time.time() if now is None else now
        return cls(
            api_url=api_url,
            access_token=body['access_token'],
            refresh_token=body.get('refresh_token'),
            expires_at=current + int(body.get('expires_in') or 0),
            auth_time=body.get('auth_time'),
            grant=grant,
        )

    def fresh(self, now: float | None = None) -> bool:
        current = time.time() if now is None else now
        return current < self.expires_at - EXPIRY_MARGIN

    def signed_in_within(self, seconds: int, now: float | None = None) -> bool:
        current = time.time() if now is None else now
        return self.auth_time is not None and current - self.auth_time <= seconds

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> 'TokenSet':
        return cls(**{key: data[key] for key in cls.__dataclass_fields__ if key in data})
