class BenchmarkError(Exception):
    """Base class for expected benchmark failures."""


class ValidationError(BenchmarkError):
    """Raised when benchmark or adapter data violates its strict schema."""


class AdapterError(BenchmarkError):
    """Raised when a live adapter cannot produce a valid trace."""
