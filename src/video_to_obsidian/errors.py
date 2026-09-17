"""Stable, user-facing pipeline errors."""

from __future__ import annotations

from typing import Any


class AppError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        retryable: bool = False,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable
        self.details = dict(details or {})
        self.details.setdefault("retryable", retryable)

    def payload(self) -> dict[str, Any]:
        return {
            "ok": False,
            "complete": False,
            "status": "failed",
            "error_code": self.code,
            "error": self.message,
            "retryable": self.retryable,
            "details": self.details,
        }

