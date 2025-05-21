# examc_app/signing.py
import os
from pathlib import Path

from django.core.signing import TimestampSigner, SignatureExpired, BadSignature
from django.conf import settings

# salt isolates this signer from any others you might use
signer = TimestampSigner(salt="examc-files")

def make_token_for(rel_path: str,type_root: str) -> str:
    """
    rel_path: path under SCANS_ROOT, e.g.
      "scans/2024-2025/1/ID-1/DT/0001/copy_0001_p1.jpg"
    returns: token (no URL prefix)
    """
    type = type_root.split('/')[-1]
    token = signer.sign(rel_path)
    return f"{settings.SIGNED_FILES_URL}{token}/{type}"

def verify_and_get_path(token: str, max_age=None) -> Path:
    """
    Unsigns the token, checks age, and returns the absolute filesystem path.
    Raises BadSignature / SignatureExpired / FileNotFoundError if invalid.
    """
    rel_path = signer.unsign(token, max_age=max_age)

    if rel_path.endswith(str(settings.SCANS_ROOT).split('/')[-1]):
        full = settings.SCANS_ROOT / rel_path
    elif rel_path.endswith(str(settings.CATALOG_ROOT).split('/')[-1]):
        full = settings.CATALOG_ROOT / rel_path
    elif rel_path.endswith(str(settings.AMC_PROJECTS_ROOT).split('/')[-1]):
        full = settings.AMC_PROJECTS_ROOT / rel_path
    elif rel_path.endswith(str(settings.CATALOG_ROOT).split('/')[-1]):
        full = settings.EXPORT_TMP_ROOT / rel_path
    else:
        full = ''
    if not full.exists():
        raise FileNotFoundError(f"{full} not found")
    return full
