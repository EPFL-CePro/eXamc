from examc_app.exceptions import UserFacingError


class ExamDateMissingError(UserFacingError):
    """Raised when a folder path is needed but the exam has no date."""
    title = "Exam date missing"
    message = "This exam has no date. Please set one in the exam information first."
    status_code = 400


class ExamFolderNameInvalidError(UserFacingError):
    """Raised when the code, year or semester of an exam can't be used as a folder name."""
    title = "Invalid exam information"
    message = (
        "The code, year or semester of this exam can't be used as a folder name. "
        "Please remove slashes and make sure none of them is empty."
    )
    status_code = 400


class ExamFolderConflictError(UserFacingError):
    """Raised when renaming the folders of an exam would overwrite an existing folder."""
    title = "Exam folder already exists"
    message = (
        "Another exam already uses the new code, year, semester and date. "
        "Nothing was moved, please choose different information."
    )
    status_code = 409
