import os
import re
from premailer import Premailer
from jinja2 import Environment, DictLoader

from formspree import settings

TEMPLATES_DIR = "formspree/templates/email/pre_inline_style/"


def _do_includes(source_map):
    """
    Premailer doesn't work with partial html snippets so manually substitute
    them before running premailer. Might as well just use the existing jinja
    syntax for this...
    """
    transformed = dict()
    for filename, source in source_map.items():
        transformed[filename] = re.sub(
            "\{%\s*include\s+([\"'])(.*?)\\1\s*%\}",
            lambda match: source_map[match.group(2)]
            if match.group(2) in source_map.keys()
            else "",
            source,
        )
    return transformed


def _do_premailer(source_map):
    transformed = dict()
    for filename, source in source_map.items():
        p = Premailer(source, remove_classes=True)
        transformed_template = p.transform()

        # weird issue with jinja templates beforehand so we use this hack
        # see https://github.com/peterbe/premailer/issues/72
        mapping = (("%7B%7B", "{{"), ("%7D%7D", "}}"), ("%20", " "))
        for k, v in mapping:
            transformed_template = transformed_template.replace(k, v)
        transformed[filename] = transformed_template
    return transformed


def _load_templates():
    templates = dict()
    for filename in os.listdir(TEMPLATES_DIR):
        if filename.endswith(".html") or filename.endswith(".xml"):
            with open(os.path.join(TEMPLATES_DIR, filename), "r") as html:
                templates[filename] = html.read()
    return templates


def render_email(template_name, **kwargs):
    """
    Email templates are compiled outside the normal flask environment, using
    premailer. As a result, they don't have access to the flask context.
    For consistency, we add the `config` variable to the context. However
    other flask functions, like `url_for` can't be used in an email template.     
    """
    template = _ENVIRONMENT.get_template(template_name)
    kwargs["config"] = settings
    return template.render(**kwargs)


_SOURCE_MAP = _do_premailer(_do_includes(_load_templates()))
_ENVIRONMENT = Environment(loader=DictLoader(_SOURCE_MAP))
