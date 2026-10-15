from pathlib import Path

from django import forms
from django.conf import settings

ROOMS_PLANS_ROOT = Path(settings.ROOMS_PLANS_ROOT)
CSV_DIR = ROOMS_PLANS_ROOT / "csv"
MAP_DIR = ROOMS_PLANS_ROOT / "map"

IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png")


# Choices are callables so new room files show up without restarting the server.

def csv_choices() -> list[tuple[str, str]]:
    return sorted((path.name, path.stem) for path in CSV_DIR.glob("*.csv"))


def image_choices() -> list[tuple[str, str]]:
    return sorted(
        (path.name, path.stem)
        for path in MAP_DIR.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    )


def room_select(**attrs: str | int) -> forms.SelectMultiple:
    """Multiple room picker; data-room-select is what the TypeScript looks for."""
    return forms.SelectMultiple(attrs={"class": "form-select", "size": 8, "data-room-select": "", **attrs})


RADIO = forms.RadioSelect(attrs={"class": "form-check-input"})

ROOM_HELP = "Select one or more rooms (Ctrl/Cmd + click). Rooms are used in alphabetical order."


class SeatingForm(forms.Form):
    csv_file = forms.MultipleChoiceField(
        choices=csv_choices,
        label="Room",
        help_text=ROOM_HELP,
        widget=room_select(),
    )

    numbering_option = forms.ChoiceField(
        choices=[("continuous", "Continuous"), ("special", "Special")],
        label="Numbering option",
        help_text="Select how seats are numbered. The special option is used for student needs: upload a .csv "
                  "with the special numbers, fill in the first and last number, then download. The numbers "
                  "will be the ones in the special file.",
        widget=RADIO,
        initial="continuous",
    )

    skipping_option = forms.ChoiceField(
        choices=[("noskip", "No skip"), ("skip", "Skip")],
        label="Skip option",
        help_text="Choose whether to skip seats. Upload a .csv with the numbers to skip.",
        widget=RADIO,
        initial="noskip",
    )

    fill_all_seats = forms.BooleanField(
        required=False,
        label="Fill all seats",
        help_text="Fill all seats of the plans from the first number to the end of the plan.",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )

    first_seat_number = forms.IntegerField(
        label="First seat number",
        help_text="Enter the starting seat number. Empty means 1.",
        required=False,
        initial=1,
        widget=forms.NumberInput(attrs={"class": "form-control"}),
    )

    last_seat_number = forms.IntegerField(
        label="Last seat number",
        help_text="Enter the last seat number.",
        required=False,
        widget=forms.NumberInput(attrs={"class": "form-control"}),
    )

    special_file = forms.FileField(
        label="Special file",
        required=False,
        help_text="A CSV file with all the numbers you want to skip or add.",
        widget=forms.FileInput(attrs={"class": "form-control", "accept": ".csv,text/csv"}),
    )

    shape_to_draw = forms.ChoiceField(
        choices=[("circle", "Circle"), ("square", "Square")],
        label="Shape to draw",
        help_text="Choose the shape drawn around each number.",
        widget=RADIO,
        initial="circle",
    )


class SeatingSpecialForm(forms.Form):
    img_file = forms.MultipleChoiceField(
        choices=image_choices,
        label="Room",
        help_text=ROOM_HELP,
        widget=room_select(),
    )

    numbering_option = forms.ChoiceField(
        choices=[("numbers", "Numbers"), ("letters", "Letters"), ("prefix", "Prefix")],
        label="Numbering option",
        help_text="Select how seats are numbered. The Prefix option lets you choose the text before each "
                  "number, e.g. MyPrefix-13.",
        widget=RADIO,
        initial="numbers",
    )


class LdapForm(forms.Form):
    LDAP_SEARCH_CHOICES = [
        ("uniqueidentifier", "Sciper"),
        ("displayName", "Name"),
        ("mail", "Email"),
        ("uid", "User ID (gaspar)"),
    ]

    choice = forms.ChoiceField(
        choices=LDAP_SEARCH_CHOICES,
        label="To search in LDAP",
        widget=RADIO,
        initial="uniqueidentifier",
    )