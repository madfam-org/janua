"""Run inside an image: print what language its chooser and refusal pages speak, for the workflow.

Runs in the base image too, where the new names and parameters do not exist, so
they are looked up defensively. Importing the routers imports the application,
so this also proves the image imports cleanly. Nothing connects to a database.

Prints two lines:

- ``LOCALE=`` the properties janua#814 and janua#820 change (all true on the
  hotfix, all false on production's image);
- ``ENGLISH=`` sha256 of the English pages, which must be byte for byte the
  same in both images (English stays the default).
"""

import hashlib
import inspect
import json
from urllib.parse import urlencode

from app.routers.v1 import auth as auth_router
from app.routers.v1 import oauth_provider

ACCOUNTS = [
    ("sid-hotfix-check-1", type("U", (), {"email": "person@example.test", "username": None})()),
    ("sid-hotfix-check-2", type("U", (), {"email": None, "username": None})()),
]
NEXT = "/api/v1/oauth/authorize?response_type=code&client_id=hotfix-check&prompt=select_account"
ADD = "/api/v1/auth/login?client_id=hotfix-check"
REFUSALS = {
    # janua#820's copy key: the English sentence production printed for it.
    "switch_refused_cross_origin": "This request did not come from the account chooser.",
    "switch_refused_not_held": "That account is no longer signed in on this browser.",
}
HOSTILE = ['es-"><script>alert(1)</script>', "es-x&next=https://evil.example/&ui_locales=fr"]


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _chooser(locale=None, client_name="Hotfix Check App"):
    kwargs = {"authorize_next": NEXT, "add_account_url": ADD, "client_name": client_name}
    if locale is not None:
        kwargs["locale"] = locale
    return oauth_provider._account_chooser_html(ACCOUNTS, **kwargs)


def _refusal_english(key: str) -> str:
    # Production's page takes the English sentence; the hotfix's takes the copy key.
    params = list(inspect.signature(auth_router._switch_refused_html).parameters)
    return auth_router._switch_refused_html(REFUSALS[key] if params[0] == "message" else key)


def _chooser_speaks_spanish() -> bool:
    try:
        named, unnamed = _chooser("es"), _chooser("es", client_name="")
    except TypeError:  # production's chooser takes no locale
        return False
    spanish = ('<html lang="es-MX">', "<title>Elige una cuenta - Janua</title>",
               "<h1>Elige una cuenta</h1>", "para continuar a Hotfix Check App", ">Usar otra cuenta</a>", "Cuenta")
    english = ("Choose an account", "to continue to", "Use another account", "the application")
    return (
        all(s in named for s in spanish)
        and "para continuar a la aplicación" in unnamed
        and not any(s in named or s in unnamed for s in english)
    )


def _authorize_carries_locale() -> bool:
    # The chooser call site inside /authorize: `next` gets the normalized
    # constant and the page gets the locale (a request handler needs a database
    # to run, so its wiring is read from the code the image ships).
    source = inspect.getsource(oauth_provider.authorize_get)
    return "with_ui_locales(" in source and "locale=chooser_locale" in source


def _second_factor_branch_normalizes_locale() -> bool:
    source = inspect.getsource(oauth_provider.authorize_get)
    return (
        '"ui_locales": ui_locales or "es"' not in source
        and '"ui_locales": ui_locales,' not in source
        and "mfa_ui_locale = hosted_locale(ui_locales)" in source
    )


def _refusal_speaks_spanish() -> bool:
    locale_of = getattr(auth_router, "_switch_page_locale", None)
    if locale_of is None:
        return False
    if locale_of(NEXT + "&ui_locales=es") != "es" or locale_of(NEXT) != "en" or locale_of(None) != "en":
        return False
    # A hostile value posted in `next` only ever yields the constant.
    if any(locale_of(NEXT + "&" + urlencode({"ui_locales": value})) != "es" for value in HOSTILE):
        return False
    pages = [auth_router._switch_refused_html(key, "es") for key in REFUSALS]
    return all(
        '<html lang="es-MX">' in page
        and "<h1>Esa cuenta no se puede usar aquí</h1>" in page
        and "Regresa a la aplicación y vuelve a iniciar sesión." in page
        and "can't be used here" not in page
        for page in pages
    ) and "Esta solicitud no vino de la página para elegir una cuenta." in pages[0]


print(
    "LOCALE="
    + json.dumps(
        {
            "chooser_speaks_spanish": _chooser_speaks_spanish(),
            "authorize_carries_locale": _authorize_carries_locale(),
            "second_factor_branch_normalizes_locale": _second_factor_branch_normalizes_locale(),
            "refusal_speaks_spanish": _refusal_speaks_spanish(),
        },
        sort_keys=True,
    )
)
print(
    "ENGLISH="
    + json.dumps(
        {
            "chooser_named": _sha(_chooser()),
            "chooser_unnamed": _sha(_chooser(client_name="")),
            **{f"refusal_{key}": _sha(_refusal_english(key)) for key in REFUSALS},
        },
        sort_keys=True,
    )
)
