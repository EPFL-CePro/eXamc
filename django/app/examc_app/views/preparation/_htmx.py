"""Helpers of the htmx responses of the preparation views."""

import json


def with_save_feedback(request, response, saved):
    """Tell the page (htmx "prepSaveFeedback" event) whether a Save succeeded, to notify the user."""
    if request.method == "POST":
        response["HX-Trigger"] = json.dumps({"prepSaveFeedback": {"saved": bool(saved)}})
    return response
