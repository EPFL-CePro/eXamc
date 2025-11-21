from pathlib import Path
from django.conf import settings
from django.core.files.storage import FileSystemStorage

private_storage = FileSystemStorage(
    location=str(settings.PRIVATE_MEDIA_ROOT),
    base_url=getattr(settings, "PRIVATE_MEDIA_URL", "/_protected/"),
)

def to_private_name(p: str) -> str:
    """
    Convert absolute /private_media/... to a storage-relative name.
    If already relative, return as-is.
    """
    path = Path(p)
    base = Path(settings.PRIVATE_MEDIA_ROOT)
    try:
        # If p is absolute under /private_media, strip the prefix
        return str(path.relative_to(base))
    except Exception:
        # Already relative (or elsewhere) – return as str
        return str(path)
