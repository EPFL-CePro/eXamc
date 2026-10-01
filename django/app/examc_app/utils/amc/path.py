from pathlib import Path

from examc import settings


def resolve_amc_path(raw: str, project_path: str) -> Path:
    """
    Turn a file path stored in an AMC database into an absolute filesystem path.

    AMC stores paths with placeholders: ``%PROJET`` stands for the project
    directory, and older records may start with ``%HOME/html/eXamc``, the
    app's previous install location, which now lives under PRIVATE_MEDIA_ROOT.

    Args:
        raw: The path as stored by AMC, e.g. ``%PROJET/scans/copy_0001.jpg``.
        project_path: Absolute path of the exam's AMC project directory.

    Returns:
        The resolved absolute path. The file is not checked for existence.
    """
    path = raw.replace('%PROJET', str(project_path))
    path = path.replace('%HOME/html/eXamc', str(settings.PRIVATE_MEDIA_ROOT))  # legacy location
    return Path(path).resolve()