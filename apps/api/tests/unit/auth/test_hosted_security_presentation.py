"""Hosted enrollment must style its responsive view without loosening CSP."""

import base64
import hashlib
import re

import pytest
from fastapi import FastAPI, Response
from httpx import ASGITransport, AsyncClient

from app.auth.hosted_security import _page
from app.middleware.security_headers import SecurityHeadersMiddleware


def test_only_the_exact_responsive_style_is_allowed_by_csp():
    response = _page('<img alt="Synthetic QR" src="data:image/png;base64,AA==">')
    styles = re.findall(r"<style>(.*?)</style>", response.body.decode(), re.S)
    assert len(styles) == 1
    digest = base64.b64encode(hashlib.sha256(styles[0].encode()).digest()).decode()
    csp = response.headers["content-security-policy"]
    assert f"style-src 'sha256-{digest}'" in csp
    assert "unsafe-inline" not in csp and "unsafe-eval" not in csp
    assert "default-src 'none'" in csp
    assert "form-action 'self'" in csp and "frame-ancestors 'none'" in csp
    assert "base-uri 'none'" in csp
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["referrer-policy"] == "no-referrer"


def test_error_and_recovery_pages_keep_the_same_style_and_security_policy():
    normal = _page("<p>Continue</p>")
    error = _page('<p role="alert">Synthetic invalid code</p>', 401)
    recovery = _page("<pre>SYNTHETIC-CODE</pre>")
    assert error.status_code == 401
    for response in (error, recovery):
        assert (
            response.headers["content-security-policy"] == normal.headers["content-security-policy"]
        )
        assert response.headers["cache-control"] == "no-store"


def test_empty_input_boundaries_have_three_to_one_contrast_in_each_palette():
    style = re.search(r"<style>(.*?)</style>", _page("").body.decode(), re.S).group(1)
    boundaries = re.findall(r"--control-line:(#[0-9a-f]+)", style)
    papers = re.findall(r"--paper:(#[0-9a-f]+)", style)
    assert len(boundaries) == len(papers) == 2

    def luminance(value):
        digits = value.lstrip("#")
        if len(digits) == 3:
            digits = "".join(c * 2 for c in digits)
        channels = [int(digits[i : i + 2], 16) / 255 for i in (0, 2, 4)]
        linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
        return sum(c * weight for c, weight in zip(linear, (0.2126, 0.7152, 0.0722)))

    for boundary, paper in zip(boundaries, papers):
        light, dark = sorted((luminance(boundary), luminance(paper)), reverse=True)
        assert (light + 0.05) / (dark + 0.05) >= 3


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [200, 401])
async def test_actual_middleware_preserves_hashed_styles_and_allows_trusted_redirect_chain(status):
    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware)

    @app.get("/factor-view")
    async def view():
        return _page("<form method='post'><button>Continue</button></form>", status)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="https://issuer.example.invalid"
    ) as client:
        response = await client.get("/factor-view")
    style = re.search(r"<style>(.*?)</style>", response.text, re.S).group(1)
    digest = base64.b64encode(hashlib.sha256(style.encode()).digest()).decode()
    csp = response.headers["content-security-policy"]
    assert response.status_code == status
    assert f"style-src 'sha256-{digest}'" in csp
    assert "default-src 'none'" in csp and "unsafe-inline" not in csp
    assert "img-src data:" in csp and "frame-ancestors 'none'" in csp
    assert "form-action 'self'" in csp and "https://*.creatumundo.mx" in csp
    assert csp.count("form-action ") == 1 and "base-uri 'none'" in csp
    assert response.headers["referrer-policy"] == "no-referrer"


@pytest.mark.asyncio
async def test_other_responses_keep_existing_global_policy():
    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware)

    @app.get("/ordinary")
    async def ordinary():
        return {"ok": True}

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="https://issuer.example.invalid"
    ) as client:
        response = await client.get("/ordinary")
    assert "default-src 'self'" in response.headers["content-security-policy"]
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"


@pytest.mark.asyncio
async def test_similar_response_policy_and_client_headers_cannot_select_security_profile():
    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware)

    @app.get("/unrecognized")
    async def unrecognized():
        return Response(
            headers={
                "Content-Security-Policy": "default-src 'none'; style-src 'sha256-FAKE'; script-src 'unsafe-eval'"
            }
        )

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="https://issuer.example.invalid"
    ) as client:
        response = await client.get(
            "/unrecognized",
            headers={"Content-Security-Policy": _page("").headers["content-security-policy"]},
        )
    csp = response.headers["content-security-policy"]
    assert csp.startswith("default-src 'self'")
    assert "FAKE" not in csp and "unsafe-eval" not in csp
