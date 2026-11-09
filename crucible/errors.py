"""Errors the client raises."""

import requests


class RemovedError(TypeError):
    """A method, parameter, or setting that was removed; the message names its replacement."""


class CrucibleAPIError(requests.exceptions.HTTPError):
    """The API answered with an error status.

    A subclass of requests.HTTPError, so existing handlers keep working.

    Attributes:
        status: HTTP status code.
        code: The API's machine-readable error code (detail.code), if any.
        detail: The API's error detail: a message string, or the detail object.
        request_id: The API's X-Request-ID for this request; quote it when
            reporting a problem so it can be found in the server logs.
    """

    def __init__(self, message: str, response: requests.Response, status: int,
                 code: str | None = None, detail=None, request_id: str | None = None):
        super().__init__(message, response=response)
        self.status = status
        self.code = code
        self.detail = detail
        self.request_id = request_id

    @classmethod
    def from_response(cls, response: requests.Response) -> 'CrucibleAPIError':
        detail = None
        try:
            body = response.json()
        except ValueError:
            body = None
        if isinstance(body, dict):
            detail = body.get('detail') or body.get('message') or body.get('error')
        code = detail.get('code') if isinstance(detail, dict) else None
        message = f"{response.status_code} {response.reason}"
        if detail:
            message = f"{message}: {detail}"
        request_id = response.headers.get('X-Request-ID')
        return cls(message, response, response.status_code, code=code, detail=detail,
                   request_id=request_id)
