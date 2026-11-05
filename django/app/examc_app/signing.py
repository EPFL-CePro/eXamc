# examc_app/signing.py
import base64
import json
from pathlib import Path
from urllib.parse import unquote

from django.conf import settings
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.utils.http import urlencode

# salt isolates this signer from any others you might use
signer = TimestampSigner(salt="examc-files")


def b64url_decode(s: str) -> str:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad).decode()


def b64url_encode(s: str) -> str:
    return base64.urlsafe_b64encode(s.encode()).rstrip(b"=").decode()


def make_token_for(rel_path: str, type_root: str, token_type: str | None = None, copy_page_in_url: bool = True) -> str:
    """
    Creates a signed token holding {type, path}, and returns a URL like /protected/<copy_page>/?token=<TOKEN>.

    :param rel_path: The file's path, relative to ``type_root``.
    :param type_root: The folder the path is relative to. Its name is the token's type unless ``token_type`` is given:
        "scans", "marked_scans", "amc_projects"…
    :param token_type: Overrides the type taken from ``type_root``.
    :param copy_page_in_url: Whether to put the file's name (without extension) in the URL, e.g. "copy_0002_02".
    """
    root = Path(type_root)
    type_name = token_type or root.name

    path = rel_path
    if type_name == "extra":
        # Extra pages are served from AMC_PROJECTS_ROOT: the path starts with the project's folders.
        project_part = root.relative_to(settings.AMC_PROJECTS_ROOT).as_posix()
        path = f"{project_part}/{rel_path}"

    payload = {"type": type_name, "path": path}

    # JSON -> base64url for a compact token and no special characters
    msg = b64url_encode(json.dumps(payload, separators=(",", ":")))
    token = signer.sign(msg)  # TimestampSigner

    base_url = str(settings.SIGNED_FILES_URL).rstrip("/") + "/"
    query = urlencode({"token": token})

    if type_name == "amc_document" or not copy_page_in_url:
        return f"{base_url}?{query}"

    return f"{base_url}{Path(rel_path).stem}/?{query}"


def verify_and_get_path(token: str, max_age=None) -> Path:
    """
    Nouveau format: token = signer.sign(b64url(JSON{type,path}))
    Fallback: ancien format "<sign(rel_path)>/<type>"
    Retourne un Path absolu si OK, sinon lève BadSignature / SignatureExpired / FileNotFoundError.
    """
    # --- 1) Tentative nouveau format ---
    # Si le front a encodé le token, on le décodera ici
    if "%3A" in token or "%" in token:
        token = unquote(token)
    try:
        raw = signer.unsign(token, max_age=max_age)  # -> b64url(JSON)
        data = json.loads(b64url_decode(raw))  # -> dict
        typ = data["type"]
        rel_path = data["path"]
    except (BadSignature, SignatureExpired):
        # Re-propage, ce sont des erreurs "normales"
        raise
    except Exception:
        # --- 2) Fallback legacy: "<sign(rel_path)>/<type>"
        try:
            file_root = token.split("/").pop()
            rel_path = signer.unsign(token.rsplit("/", 1)[0], max_age=max_age)
            typ = file_root
        except Exception as e:
            # Rien ne correspond
            raise BadSignature("Malformed token") from e

    # --- 3) Résolution de la racine en fonction du type ---
    roots = {
        "scans":          Path(settings.SCANS_ROOT),
        "marked_scans":   Path(settings.MARKED_SCANS_ROOT),
        "amc_projects":   Path(settings.AMC_PROJECTS_ROOT),
        "CATALOG":        Path(settings.AMC_PROJECTS_ROOT),
        "assoc":          Path(settings.AMC_PROJECTS_ROOT),
        "extra":          Path(settings.AMC_PROJECTS_ROOT),
        "private_media":  Path(settings.PRIVATE_MEDIA_ROOT),
        "amc_document" :  Path(settings.AMC_PROJECTS_ROOT)
    }
    root = roots.get(typ)
    if root is None:
        raise BadSignature(f"Unknown root type: {typ}")

    # --- 4) Hygiène du chemin relatif ---
    # normalise en posix, refuse les traversals simples
    rel = Path(rel_path)
    if rel.is_absolute() or any(p in ("..", "") for p in rel.parts):
        raise BadSignature("Invalid relative path")

    root = root.resolve()
    fs_path = (root / rel).resolve()

    # protection anti-traversal (Python <3.9: via relative_to + try/except)
    try:
        fs_path.relative_to(root)
    except ValueError:
        raise BadSignature("Path outside of root")

    if not fs_path.exists():
        raise FileNotFoundError(f"{fs_path} not found")

    return fs_path
