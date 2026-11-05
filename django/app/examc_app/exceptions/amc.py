import logging

from examc_app.exceptions import UserFacingError


class AmcProjectPathNotFoundError(UserFacingError):
    """Raised when the AMC project path is not found."""
    title = "AMC project not found"
    message = (
        'The selected exam "{{ exam.pk|get_exam_name }}" has no AMC project yet. Please import one first '
        "<a href=\"{% url 'import' exam.pk %}?tab=amc\">in the AMC module</a>."
    )
    status_code = 404


class AmcDbManagerError(UserFacingError):
    """Raised when reading or writing an AMC database fails."""
    title = "AMC data unavailable"
    message = (
        "The AMC data for this exam couldn’t be read. Make sure you’ve imported an AMC project from the Import page "
        "in the sidebar, then try again. If the problem continues, please contact support."
    )
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
