import os
from functools import wraps

import shopify


def session(f):
    @wraps(f)
    def dec_f(*args, **kwargs):
        with shopify.Session.temp(
            os.environ["SHOP_NAME"] + ".myshopify.com",
            os.getenv("SHOP_API_VERSION", "2021-01"),
            os.environ["SHOP_PASSWORD"],
        ):
            return f(*args, **kwargs)

    return dec_f


def paginate(type, **kwargs):
    _rsrcs = type.find(**kwargs)
    rsrcs = list(_rsrcs)

    while _rsrcs.has_next_page():
        _rsrcs = _rsrcs.next_page()
        rsrcs.extend(_rsrcs)

    return rsrcs
