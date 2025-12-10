import json
from pathlib import Path
from urllib.parse import urlencode

from django.conf import settings
from django.core.files.storage import FileSystemStorage

from examc_app.signing import make_token_for, signer, b64url_encode
from django.utils.http import urlencode

private_storage = FileSystemStorage(
    location=str(settings.PRIVATE_MEDIA_ROOT),
    base_url=getattr(settings, "PRIVATE_MEDIA_URL", "/_protected/"),
)


class SummernoteSignedPrivateStorage(FileSystemStorage):
    """
    Stores files under PRIVATE_MEDIA_ROOT, but exposes them with
    signed URLs using signing.make_token_for.
    """

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("location", str(settings.PRIVATE_MEDIA_ROOT))
        # base_url doesn't really matter because we override url()
        kwargs.setdefault("base_url", "/_ignored/")
        super().__init__(*args, **kwargs)

    def url(self, name):
        rel_path = str(name)
        msg = b64url_encode(json.dumps({"type": "private_media", "path": rel_path}, separators=(",", ":")))
        token = signer.sign(msg)
        # 👇 no copy_page in the URL; just /protected/?token=...
        return f"{settings.SIGNED_FILES_URL}?{urlencode({'token': token})}"

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
