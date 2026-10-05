"""No HTML comment ships inside an email.

An HTML comment in an email template is sent to every recipient, and anyone
who opens the message source can read it. Notes for maintainers belong in
Jinja comments ({# ... #}), which the renderer drops. This pins that for every
HTML email template's source, and for the rendered frame as a recipient gets it.
"""

from pathlib import Path

import pytest

from app.services import email_service
from app.services.email_service import EmailService

TEMPLATES = Path(email_service.__file__).parent.parent / "templates"
HTML_TEMPLATES = sorted(
    p for folder in ("email", "emails") for p in (TEMPLATES / folder).glob("*.html")
)


def test_the_templates_are_found():
    """Guards the guard: an empty glob would make every check below pass."""
    names = {f"{p.parent.name}/{p.name}" for p in HTML_TEMPLATES}
    assert {"email/base.html", "emails/base.html", "email/magic_link.html"} <= names


@pytest.mark.parametrize("path", HTML_TEMPLATES, ids=lambda p: f"{p.parent.name}/{p.name}")
def test_template_source_has_no_html_comment(path):
    assert "<!--" not in path.read_text(encoding="utf-8")


@pytest.mark.parametrize("template", ["magic_link.html", "verification.html", "welcome.html"])
@pytest.mark.parametrize("locale", ["es", "en"])
def test_rendered_email_has_no_html_comment(template, locale):
    data = {
        "magic_link": "https://x.test/a",
        "magic_url": "https://x.test/a",
        "verification_link": "https://x.test/v",
        "user_name": "persona",
        "current_year": 2026,
    }
    html = EmailService()._render_template(template, data, locale=locale)
    assert "<!--" not in html
