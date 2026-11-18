class KeitaroError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class KeitaroAuthError(KeitaroError):
    pass


class KeitaroTimeoutError(KeitaroError):
    pass


class KeitaroValidationError(KeitaroError):
    pass


class WriteGuardError(KeitaroValidationError):
    """Refused because of a live-QA write allowlist or delete forbid."""


class PartialCreateError(KeitaroError):
    """Campaign or streams were partially created; do not retry or auto-delete."""
