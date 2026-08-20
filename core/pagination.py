from flask import request, url_for
from urllib.parse import urlencode

DEFAULT_PER_PAGE = 20

def get_pagination_args(default=DEFAULT_PER_PAGE):
    """
    Extracts page and per_page arguments from request.
    Supports ?page=1&per_page=20, 50, 100, or 'all'.
    """
    page = request.args.get('page', 1, type=int)
    if page < 1:
        page = 1

    per_page_raw = request.args.get('per_page', '').strip().lower()
    if per_page_raw in ('all', 'semua', '0', '-1'):
        per_page = 100000
        per_page_str = 'all'
    elif per_page_raw:
        try:
            val = int(per_page_raw)
            per_page = max(1, min(1000, val))
            per_page_str = str(per_page)
        except ValueError:
            per_page = default
            per_page_str = str(default)
    else:
        per_page = default
        per_page_str = str(default)

    return page, per_page, per_page_str

def update_query_params(**kwargs):
    """
    Helper to create a URL for the current endpoint with updated query parameters.
    Preserves existing query parameters unless explicitly overridden or set to None.
    """
    args = dict(request.args)
    for k, v in kwargs.items():
        if v is None:
            args.pop(k, None)
        else:
            args[k] = v

    if request.endpoint:
        try:
            view_args = dict(request.view_args or {})
            view_args.update(args)
            return url_for(request.endpoint, **view_args)
        except Exception:
            pass

    query_str = urlencode(args)
    return f"{request.path}?{query_str}" if query_str else request.path
