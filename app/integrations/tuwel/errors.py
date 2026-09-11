"""Safe errors: never retain response bodies, credentials, or HTTP requests."""


class TuwelError(Exception):
    pass


class TuwelAuthenticationError(TuwelError):
    def __init__(self) -> None:
        super().__init__("TUWEL authentication expired.")


class TuwelAccessError(TuwelError):
    def __init__(self) -> None:
        super().__init__("TUWEL web-service access is unavailable.")


class TuwelNetworkError(TuwelError):
    def __init__(self) -> None:
        super().__init__("TUWEL could not be reached.")


class TuwelResponseError(TuwelError):
    def __init__(self) -> None:
        super().__init__("TUWEL returned an invalid or incomplete response.")
