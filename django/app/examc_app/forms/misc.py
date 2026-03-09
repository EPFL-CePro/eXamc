import os

from django import forms

from examc import settings

CSV_DIR = str(settings.ROOMS_PLANS_ROOT) + "/csv/"
JPG_DIR = str(settings.ROOMS_PLANS_ROOT) + "/map/"
IMAGE_FILES = sorted([(f, f) for f in os.listdir(JPG_DIR) if f.endswith('.jpg')])

class SeatingForm(forms.Form):
    CSV_FILES = sorted([(f, f) for f in os.listdir(CSV_DIR) if f.endswith('.csv')])
    #IMAGE_FILES = sorted([(f, f) for f in os.listdir(JPG_DIR) if f.endswith('.jpg')])
    csv_file = forms.MultipleChoiceField(
        choices=CSV_FILES,
        label='Room',
        help_text="Select one or more rooms. The room order is the alphabetic one",
        widget=forms.SelectMultiple(
            attrs={
                "data-tooltip-location": "top",
                'id': 'id_csv_file',
                'class': "selectpicker form-control",
                'size': 5,
                'data-live-search': "true"
            }
        )
    )

    numbering_option = forms.ChoiceField(
        choices=[('continuous', 'Continuous'), ('special', 'Special')],
        label='Numbering Option',
        help_text="Select how seats are numbered. The special option is used for student needs. Upload a .csv with "
                  "the special numbers. Fill in the first and last number then download. The numbers will be the one "
                  "that are in the special file.",
        widget=forms.RadioSelect(attrs={'onchange': "showHideSpecialFile(this.value);"}),
        initial='continuous'
    )

    skipping_option = forms.ChoiceField(
        choices=[('noskip', 'No skip'), ('skip', 'Skip')],
        label='Skip Option',
        help_text="Choose whether to skip seats. Upload a .csv with the numbers to skip.",
        widget=forms.RadioSelect(attrs={'onchange': "showHideSpecialFile(this.value)", 'id': 'id_skipping_option'}),
        initial='noskip'
    )

    fill_all_seats = forms.BooleanField(
        required=False,
        help_text="Fill all seats of the plans from the first number to the end of the plan.",
        widget=forms.CheckboxInput(attrs={'id': 'id_fill_all_seats', 'onchange': "showHideLastNumber(this.checked)"})
    )

    first_seat_number = forms.IntegerField(
        label='First Seat Number',
        help_text="Enter the starting seat number.",
        widget=forms.NumberInput(attrs={'id': 'id_first_seat_number'}),
        required=False
    )

    last_seat_number = forms.IntegerField(
        label='Last Seat Number',
        help_text="Enter the last seat number.",
        widget=forms.NumberInput(attrs={'id': 'id_last_seat_number'}),
        required=False
    )

    special_file = forms.FileField(
        label='Special File',
        required=False,
        help_text="Upload a file for special seat numbers or skipping. A CSV file with all the numbers you want to skip or add.",
        widget=forms.ClearableFileInput(attrs={'id': 'id_special_file'})
    )

    shape_to_draw = forms.ChoiceField(
        choices=[('circle', 'Circle'), ('square', 'Square')],
        label='Shape to Draw',
        help_text="Choose the shape to numbering.",
        widget=forms.RadioSelect(attrs={'data-tooltip': "Choose the shape to draw."}),
        initial='circle'
    )

class SeatingSpecialForm(forms.Form):
    img_file = forms.ChoiceField(
        choices=IMAGE_FILES,
        label='Room',
        help_text="Select one or more rooms. The room order is the alphabetic one",
        widget=forms.Select(
            attrs={
                "data-tooltip-location": "top",
                'id': 'id_img_file',
                'class': "selectpicker form-control",
                'size': 5,
                'data-live-search': "true",
                'onchange': "onRoomChange(this.value);"
            }
        )
    )

    numbering_option = forms.ChoiceField(
        choices=[('numbers', 'Numbers'), ('letters', 'Letters'), ('prefix', 'Prefix')],
        label='Numbering Option',
        help_text="Select how seats are numbered. The `Prefix` option lets you choose the prefix before a number. Ex : `MyPrefix-13`",
        widget=forms.RadioSelect(),
        initial='numbers'
    )


class ldapForm(forms.Form):
    LDAP_SEARCH_CHOICES = [
        ('uniqueidentifier', 'Sciper'),
        ('displayName', 'Name'),
        ('mail', 'Email'),
        ('uid', 'User ID (gaspar)')
    ]

    choice = forms.ChoiceField(
        choices=LDAP_SEARCH_CHOICES,
        label='To search in LDAP',
        widget=forms.RadioSelect(attrs={'data-tooltip': "Choose LDAP search."}),
        initial='sciper'
    )