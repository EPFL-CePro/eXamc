import logging

from examc_app.exceptions import UserFacingError


class AmcProjectPathNotFoundError(UserFacingError):
    """Raised when the AMC project path is not found."""
    title = "AMC project not found"
    message = (
        "This exam has no AMC project yet. Please "
        "<a href=\"{% url 'upload_amc_project' exam.pk %}\">import</a> one first."
    )
    status_code = 404


class AmcDbManagerError(UserFacingError):
    """Raised when reading or writing an AMC database fails."""
    title = "AMC data unavailable"
    message = "The AMC data of this exam could not be read. Please contact support if this persists."
    status_code = 500
    log_level = logging.ERROR