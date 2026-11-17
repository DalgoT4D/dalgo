"""Data region exceptions."""


class RegionServiceError(Exception):
    """Base class for data region errors"""

    def __init__(self, message: str, error_code: str = "REGION_ERROR"):
        self.message = message
        self.error_code = error_code
        super().__init__(self.message)


class RegionValidationError(RegionServiceError):
    """Bad region input from a caller (unknown/disabled region, missing country) -> 400"""

    def __init__(self, message: str):
        super().__init__(message, "VALIDATION_ERROR")


class RegionConfigError(RegionServiceError):
    """A region's configuration (its secret) cannot be read or is invalid -> 500"""

    def __init__(self, message: str):
        super().__init__(message, "REGION_CONFIG_ERROR")
