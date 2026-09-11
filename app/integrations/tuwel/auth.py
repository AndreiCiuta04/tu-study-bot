"""Authentication boundary; interactive token acquisition is external."""

from typing import Protocol

from pydantic import SecretStr

from app.integrations.tuwel.errors import TuwelAuthenticationError


class TuwelAuth(Protocol):
    def token(self) -> str: ...


class TokenAuth:
    def __init__(self, token: SecretStr) -> None:
        self._token = token

    def token(self) -> str:
        value = self._token.get_secret_value().strip()
        if not value:
            raise TuwelAuthenticationError()
        return value
