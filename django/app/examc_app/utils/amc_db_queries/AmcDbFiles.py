from enum import StrEnum


class AmcDbFile(StrEnum):
    ASSOCIATION = "association.sqlite"
    SCORING = "scoring.sqlite"
    CAPTURE = "capture.sqlite"
    LAYOUT = "layout.sqlite"