from urllib.parse import urlencode

from django.templatetags.static import static
from django.urls import reverse
from jinja2 import Environment


def url_for(endpoint, **values):
    if endpoint == "static":
        return static(values.pop("filename"))
    path_values = {}
    query_values = {}
    for key, value in values.items():
        if key.endswith("_id"):
            path_values[key] = value
        else:
            query_values[key] = value
    url = reverse(endpoint, kwargs=path_values or None)
    if query_values:
        url = f"{url}?{urlencode(query_values)}"
    return url


def environment(**options):
    env = Environment(**options)
    env.globals["url_for"] = url_for
    return env
