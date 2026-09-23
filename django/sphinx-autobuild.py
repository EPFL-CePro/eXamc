"""
Run sphinx-autobuild, but always bind to 0.0.0.0 inside the container.

--host is only used for the live-reload WebSocket URL sent to the browser.
"""
import os

import uvicorn
from sphinx_autobuild.__main__ import main

ARGS = [
    "--host=localhost",
    "--port=9000",
    "docs/source/",
    "examc_app/static/docs",
]

_original_run = uvicorn.run


def _run_on_all_interfaces(app, **kwargs):
    kwargs["host"] = "0.0.0.0"
    _original_run(app, **kwargs)


uvicorn.run = _run_on_all_interfaces

if __name__ == "__main__":
    os.environ.setdefault("WEB_CONCURRENCY", "1")
    main(ARGS)