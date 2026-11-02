"""(c) All rights reserved. ECOLE POLYTECHNIQUE FEDERALE DE LAUSANNE, Switzerland, VPSI, 2017"""
from .utils import epfl_api_get


def persons_search(**search_params) -> list[dict]:
    """
    Search the persons directory.
    Ex: persons_search(query='kermit'), persons_search(email='x@epfl.ch'),
        persons_search(firstname='Kermit', lastname='Frog')
    """
    data = epfl_api_get("/persons", params=search_params)
    if not isinstance(data, dict): return []
    return data.get("persons", [])


def get_person_by_sciper(sciper: str) -> dict | None:
    """
    Return the person with this sciper, or None if it does not exist
    """
    return epfl_api_get(f'/persons/{sciper}')


def get_entry(search_key: str, search_value: str) -> dict | None:
    """
    Return the first person matching search_key=search_value, or None
    """
    if search_key in ('sciper', 'id', 'uniqueidentifier'):
        return get_person_by_sciper(search_value)

    persons = persons_search(**{search_key: search_value})
    return persons[0] if persons else None
