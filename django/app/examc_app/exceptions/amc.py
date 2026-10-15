import logging

from examc_app.exceptions import UserFacingError


class AmcProjectPathNotFoundError(UserFacingError):
    """Raised when the AMC project path is not found."""
    title = "AMC project not found"
    message = (
        'The selected exam "{{ exam.pk|get_exam_name }}" has no AMC project yet. Please '
        "<a href=\"{% url 'upload_amc_project' exam.pk %}\">import</a> one first."
    )
    status_code = 404


class AmcDbManagerError(UserFacingError):
    """Raised when reading or writing an AMC database fails."""
    title = "AMC data unavailable"
    message = "The AMC data of this exam could not be read. Please contact support if this persists."
    status_code = 500
    log_level = logging.ERROR


class AmcProjectZipInvalidError(UserFacingError):
    """Raised when the uploaded AMC project is not a readable and safe zip archive."""
    title = "Invalid zip file"
    message = (
        "The uploaded file is not a valid zip archive, or it contains files that are not allowed. "
        "Please upload the .zip of your AMC project folder."
    )
    status_code = 400


class AmcProjectNotInZipError(UserFacingError):
    """Raised when the uploaded zip does not contain an AMC project."""
    title = "No AMC project in the zip file"
    message = (
        "The zip file does not contain a valid AMC project folder. "
        "Please make sure it includes the options.xml file of the project."
    )
    status_code = 400
