class AmcProjectPathNotFoundError(Exception):
    """Exception raised when the AMC project path is not found."""

class AmcDbManagerError(Exception):
    """Raised when reading or writing the AMC association database fails."""
