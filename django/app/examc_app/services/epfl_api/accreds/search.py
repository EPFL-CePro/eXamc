from examc_app.services.epfl_api.accreds.models import EpflApiAccred
from examc_app.services.epfl_api.utils import epfl_api_get

ACCREDS_API_BASE_URL = "/accreds"
ACCREDS_PAGE_SIZE = 100

# Safety net against a wrong "count": 100 pages of 100 accreds
ACCREDS_MAX_PAGES = 100


def accreds_search(**search_params) -> list[EpflApiAccred]:
    """
    Search the accreditations, following the pages of the API.
    Ex: accreds_search(persid='123456,234567'), accreds_search(unitid='13030', state='active')
    """
    accreds: list[EpflApiAccred] = []
    for page_index in range(ACCREDS_MAX_PAGES):
        data = epfl_api_get(
            path=ACCREDS_API_BASE_URL,
            params={**search_params, "pageindex": page_index, "pagesize": ACCREDS_PAGE_SIZE},
        )
        if not isinstance(data, dict):
            break

        page = data.get("accreds")
        if not isinstance(page, list) or not page:
            break
        accreds.extend(EpflApiAccred.from_api(a) for a in page if isinstance(a, dict))

        count = data.get("count")
        if len(page) < ACCREDS_PAGE_SIZE or (isinstance(count, int) and len(accreds) >= count):
            break
    return accreds