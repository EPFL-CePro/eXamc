#!/usr/bin/env python
"""
tectonic_wrapper.py: pretends to be pdflatex for AMC, which calls the engine as
    <engine> --jobname=<job> -interaction=nonstopmode <file>.tex

Installed as /usr/local/bin/tectonic_wrapper.py and as /usr/local/bin/pdflatex, so every
caller (eXamc, AMC, the options.xml of uploaded projects) compiles with Tectonic.
"""

import os
import subprocess
import sys
from pathlib import Path
from typing import NoReturn

PROG = Path(__file__).name

# AMC's LaTeX style, installed by auto-multiple-choice-common: must match the installed AMC
AMC_TEXMF = "/usr/share/texmf/tex/latex/AMC"


class WrapperError(Exception):
    """An error reported to the caller as one line, with exit code `code`."""

    def __init__(self, message: str, code: int = 2) -> None:
        super().__init__(message)
        self.code = code


def parse(args: list[str]) -> tuple[str | None, Path]:
    """The job name (if any) and the input file, from pdflatex's arguments."""
    jobname, source = None, None
    for arg in args:
        if arg.startswith(("--jobname=", "-jobname=")):
            jobname = arg.split("=", 1)[1]
        elif not arg.startswith("-"):
            source = arg  # other pdflatex options (-interaction=…) aren't needed by Tectonic

    if source is None:
        raise WrapperError("no input file")

    path = Path(source)
    if path.suffix != ".tex" and not path.exists():
        path = path.with_suffix(".tex")  # pdflatex adds .tex when missing
    return jobname, path


def compile_tex(jobname: str | None, source: Path) -> int:
    """Compile with Tectonic, the outputs named after the job (like pdflatex --jobname)."""
    # Tectonic names its outputs after the input file: compile a link named after the job
    target, link = source, None
    if jobname and f"{jobname}.tex" != source.name:
        target = link = Path(f"{jobname}.tex")
        if link.exists() and not link.is_symlink():
            raise WrapperError(f"{link} exists and isn't a link, not replacing it")
        link.unlink(missing_ok=True)
        link.symlink_to(os.path.relpath(source.resolve(), link.resolve().parent))

    command = [
        "tectonic", "-X", "compile",
        "-Z", f"search-path={AMC_TEXMF}",
        "--keep-intermediates",  # AMC reads the .xy file written next to the PDF
        "--keep-logs",
        str(target),
    ]

    try:
        return subprocess.run(command, check=False).returncode
    except FileNotFoundError:
        raise WrapperError("tectonic not found in PATH", code=127) from None
    finally:
        if link is not None:
            link.unlink(missing_ok=True)


def main(args: list[str]) -> int:
    return compile_tex(*parse(args))


def fail(err: WrapperError) -> NoReturn:
    print(f"{PROG}: {err}", file=sys.stderr)
    sys.exit(err.code)


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except WrapperError as error:
        fail(error)