"""(c) All rights reserved. ECOLE POLYTECHNIQUE FEDERALE DE LAUSANNE, Switzerland, VPSI, 2017"""
import os
from typing import Any

import requests
from django.conf import settings

from .settings import CONSTANTS


class EpflApiException(Exception):
    pass


def _get_optional_env(key):
    """
    Return the value of an optional environment variable, and use
    the provided default if it's not set.
    """
    environment_variable_value = os.environ.get(key)

    if environment_variable_value:
        return environment_variable_value
    elif key in CONSTANTS:
        return CONSTANTS[key]
    else:
        raise EpflApiException(f"The variable {key} is not set")



def _get_api_session() -> tuple[requests.Session, str]:
    """
    Return an authenticated HTTP session and the API base URL
    """
    if not settings.EPFL_API_USERNAME or not settings.EPFL_API_PASSWORD:
        raise EpflApiException("EPFL_API_USERNAME and EPFL_API_PASSWORD must be set.")

    session = requests.Session()
    session.auth = (
        settings.EPFL_API_USERNAME,
        settings.EPFL_API_PASSWORD,
    )
    session.headers.update({'Accept': 'application/json'})

    return session, _get_optional_env('EPFL_API_URL').rstrip('/')


def epfl_api_get(path: str, params: dict | None = None) -> Any | None:
    """
    GET a resource of the API. Return None on 404, raise on other errors.
    """
    session, base_url = _get_api_session()
    try:
        response = session.get(
            f'{base_url}{path}',
            params=params,
            timeout=float(_get_optional_env('EPFL_API_TIMEOUT')),
        )
    except requests.RequestException as e:
        raise EpflApiException(f'Unable to reach the EPFL API: {e}') from e
    finally:
        session.close()

    if response.status_code == 404: return None

    if not response.ok:
        raise EpflApiException(
            f'EPFL API error {response.status_code} on {path}: {response.text}'
        )

    return response.json()
