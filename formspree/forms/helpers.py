import werkzeug.datastructures
import datetime
import hashlib
import hashids
import uuid
import json
from functools import wraps, partial

from flask import request, jsonify
from flask_login import current_user
from werkzeug.datastructures import ImmutableMultiDict, ImmutableOrderedMultiDict

from formspree import settings
from formspree.app_globals import redis_store
from formspree.utils import (
    CAPTCHA_VAL,
    referrer_to_path,
    unix_time_for_12_months_from_now,
)

HASH = lambda x, y: hashlib.md5(
    x.encode("utf-8") + y.encode("utf-8") + settings.NONCE_SECRET
).hexdigest()

KEYS_NOT_STORED = {"_gotcha", "_language", CAPTCHA_VAL, "_host_nonce", "_next"}
KEYS_EXCLUDED_FROM_EMAIL = KEYS_NOT_STORED.union({"_subject", "_cc", "_format"})

REDIS_COUNTER_KEY = "monthly_{form_id}_{month}".format
REDIS_HOSTNAME_KEY = "hostname_{nonce}".format
REDIS_FIRSTSUBMISSION_KEY = "first_{nonce}".format
HASHIDS_CODEC = hashids.Hashids(
    alphabet="abcdefghijklmnopqrstuvwxyz", min_length=8, salt=settings.HASHIDS_SALT
)


def ordered_storage(f):
    """
    By default Flask doesn't maintain order of form arguments, pretty crazy
    From: https://gist.github.com/cbsmith/5069769
    """

    def decorator(*args, **kwargs):
        request.parameter_storage_class = (
            werkzeug.datastructures.ImmutableOrderedMultiDict
        )
        return f(*args, **kwargs)

    return decorator


def http_form_to_dict(data):
    """
    Forms are ImmutableMultiDicts,
    convert to json-serializable version
    """

    ret = {}
    ordered_keys = []

    for elem in data.items(multi=True):
        if not elem[0] in ret.keys():
            ret[elem[0]] = []
            ordered_keys.append(elem[0])

        ret[elem[0]].append(elem[1])

    for k, v in ret.items():
        ret[k] = ", ".join(v)

    return ret, ordered_keys


def remove_www(host):
    if host.startswith("www."):
        return host[4:]
    return host


def temp_store_hostname(hostname, referrer):
    nonce = uuid.uuid4()
    key = REDIS_HOSTNAME_KEY(nonce=nonce)
    redis_store.set(key, "{},{}".format(hostname or "--NONE--", referrer or ""))
    redis_store.expire(key, 300000)
    return nonce


def get_temp_hostname(nonce):
    key = REDIS_HOSTNAME_KEY(nonce=nonce)
    value = redis_store.get(key)
    if value is None:
        raise KeyError("no temp_hostname stored.")
    redis_store.delete(key)
    values = value.decode("utf-8").split(",")
    if len(values) != 2:
        raise ValueError("temp_hostname value is invalid: {}".format(value))
    else:
        if values[0] == "--NONE--":
            return referrer_to_path(values[1]), values[1]
        else:
            return values


def store_first_submission(nonce, store_data, sorted_keys=[]):
    if type(store_data) in (ImmutableMultiDict, ImmutableOrderedMultiDict):
        data, _ = http_form_to_dict(store_data)
    else:
        data = store_data

    data["_sorted_keys"] = sorted_keys

    key = REDIS_FIRSTSUBMISSION_KEY(nonce=nonce)
    redis_store.set(key, json.dumps(data))
    redis_store.expire(key, 300000)


def fetch_first_submission(nonce):
    key = REDIS_FIRSTSUBMISSION_KEY(nonce=nonce)
    jsondata = redis_store.get(key)
    try:
        data = json.loads(jsondata.decode("utf-8"))
        keys = data.keys()
        if "_sorted_keys" in data:
            keys = data.pop("_sorted_keys")
        return data, keys
    except:
        return None, []


def increase_monthly_counter(form_id, basedate=None):
    basedate = basedate or datetime.datetime.now()
    month = basedate.month
    key = REDIS_COUNTER_KEY(form_id=form_id, month=month)
    counter = redis_store.incr(key)
    redis_store.expireat(key, unix_time_for_12_months_from_now(basedate))
    return int(counter)


def get_monthly_counter(form_id, basedate=None):
    basedate = basedate or datetime.datetime.now()
    month = basedate.month
    key = REDIS_COUNTER_KEY(form_id=form_id, month=month)
    counter = redis_store.get(key) or 0
    return int(counter)


def form_control(func=None, api_type="internal", allow_readonly=False):
    from .models import Form

    if not func:
        return partial(form_control, api_type=api_type, allow_readonly=allow_readonly)

    @wraps(func)
    def decorated_view(*args, **kwargs):
        hashid = kwargs["hashid"]

        if api_type == "internal":
            hashid = kwargs["hashid"]
            form = Form.get_with(hashid=hashid)
            if not form:
                return jsonify({"ok": False, "error": "Form not found."}), 404

            if not form.controlled_by(current_user):
                return (
                    jsonify({"ok": False, "error": "You do not control this form."}),
                    401,
                )

            kwargs["form"] = form
            return func(*args, **kwargs)

        elif api_type == "public":
            auth = request.authorization
            bearer = request.headers.get("Authorization", "").lower()
            key = (
                auth.password
                if auth
                else bearer.split("bearer ")[1]
                if bearer and "bearer " in bearer
                else None
            )

            if key:
                form = Form.get_with(hashid=hashid)
                if (form.apikey == key) or (
                    allow_readonly and form.apikey_readonly == key
                ):
                    kwargs["form"] = form
                    return func(*args, **kwargs)

            return (
                jsonify(
                    {"ok": False, "error": "Authorization not provided or invalid."}
                ),
                401,
            )

    return decorated_view


def get_replyto(data):
    return data.get("_replyto", data.get("email", data.get("Email", ""))).strip()
