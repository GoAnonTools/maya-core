"""Contracts for model-execution workers.

Workers execute an already-selected request. They do not decide where a
request should go; that remains outside this boundary.
"""

from abc import ABC, abstractmethod
from collections.abc import Iterator
from typing import Any


class Worker(ABC):
    """Base contract for synchronous and streaming worker execution."""

    @abstractmethod
    def execute(
        self,
        context: dict[str, Any],
        route: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute a request and return the existing model result envelope."""

    @abstractmethod
    def stream(
        self,
        context: dict[str, Any],
        route: dict[str, Any],
    ) -> Iterator[str]:
        """Yield response chunks using the existing streaming contract."""
