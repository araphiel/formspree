import glob
import hashlib

from formspree import settings
from formspree.users.models import Product
from formspree.forms.models import RoutingRule
from formspree.plugins.models import PluginKind

PUBLIC_PARAMS = {
    "SERVICE_NAME": settings.SERVICE_NAME,
    "SERVICE_URL": settings.SERVICE_URL,
    "STRIPE_PUBLISHABLE_KEY": settings.STRIPE_PUBLISHABLE_KEY,
    "AMPLITUDE_KEY": settings.AMPLITUDE_KEY,
    "CONTACT_EMAIL": settings.CONTACT_EMAIL,
    "LINKED_EMAIL_ADDRESSES_LIMIT": settings.LINKED_EMAIL_ADDRESSES_LIMIT,
    "countries": [
        cr.split("/")[-1].split(".")[0].upper()
        for cr in glob.glob("formspree/static/img/countries/*.png")
    ],
    "products": Product.product_defs,
    "coupons": {
        hashlib.md5(b"jamstack_hackathon").hexdigest(): {
            "no_card": True,
            "force_plan": "v1_platinum",
        }
    },
    "plugins": PluginKind.kinds,
    "rule_fns": [RoutingRule.serialize_function(fn) for fn in RoutingRule.functions],
}
