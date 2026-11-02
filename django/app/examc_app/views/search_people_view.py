import csv
import logging

import pandas as pd
from django.contrib import messages
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from examc_app.forms.misc import PeopleSearchForm
from examc_app.services.epfl_api.accreds.models import EpflApiAccred
from examc_app.services.epfl_api.accreds.search import accreds_search
from examc_app.services.epfl_api.people.search import get_person_by_identifier
from examc_app.services.epfl_api.utils import EpflApiException

logger = logging.getLogger(__name__)

CSV_FIELDS = ["Sciper", "First name", "Last name", "Email", "Username", "Units", "Positions"]
ACCREDS_BATCH_SIZE = 100


def upload_excel_generate_csv(request: HttpRequest):
    if request.method == "POST":
        form = PeopleSearchForm(request.POST, request.FILES)

        if form.is_valid():
            # search_key = form.cleaned_data["choice"]

            try:
                # dtype=str keeps the SCIPERs as written ("012345", not 12345.0)
                values = pd.read_excel(form.cleaned_data["file"], dtype=str).iloc[:, 0]
            except Exception:
                logger.exception("Unreadable Excel file")
                form.add_error("file", "This file can't be read as an Excel file.")
            else:
                try:
                    persons = []
                    not_found = []

                    for value in values.dropna().map(str.strip):
                        if not value:
                            continue
                        person = get_person_by_identifier(value)
                        if person:
                            persons.append(person)
                        else:
                            not_found.append(value)

                    # Accreditations of all the persons found, one API call per batch
                    scipers = [person.sciper or person.id for person in persons]
                    accreds: dict[str, list[EpflApiAccred]] = {}
                    for start in range(0, len(scipers), ACCREDS_BATCH_SIZE):
                        batch = ",".join(scipers[start : start + ACCREDS_BATCH_SIZE])
                        for accred in accreds_search(persid=batch):
                            accreds.setdefault(accred.persid, []).append(accred)
                except EpflApiException:
                    logger.exception("EPFL API search failed")
                    form.add_error(None, "The EPFL directory can't be reached. Please try again later.")
                else:
                    if not_found:
                        messages.warning(request, f"No person found for: {', '.join(not_found)}")

                    response = HttpResponse(content_type="text/csv; charset=utf-8")
                    response["Content-Disposition"] = (
                        'attachment; filename="people.csv"'
                    )
                    # BOM so that Excel opens the accents correctly
                    response.write("\ufeff")
                    writer = csv.DictWriter(response, fieldnames=CSV_FIELDS)
                    writer.writeheader()

                    for person, sciper in zip(persons, scipers):
                        person_accreds = accreds.get(sciper, [])
                        writer.writerow(
                            {
                                "Sciper": sciper,
                                "First name": person.firstname,
                                "Last name": person.lastname,
                                "Email": person.email,
                                "Username": person.username,
                                "Units": "; ".join(
                                    a.unit_name for a in person_accreds if a.unit_name
                                ),
                                "Positions": "; ".join(
                                    a.position_label
                                    for a in person_accreds
                                    if a.position_label
                                ),
                            }
                        )
                    return response
    else:
        form = PeopleSearchForm()

    return render(
        request,
        "search_people/search.html",
        {
            "form": form
        }
    )