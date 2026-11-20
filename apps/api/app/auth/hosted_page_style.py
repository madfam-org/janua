"""The fixed, issuer-owned style of the strict hosted pages, and their CSP.

Shared by the hosted security pages (`hosted_security.py`) and the hosted
error page (`hosted_errors.py`) without either importing the other. The
security-headers middleware recognises `SECURITY_CSP` to keep it as sent.
"""

import base64
import hashlib

# Fixed issuer-owned CSS. Its CSP hash allows this exact style block without
# permitting arbitrary inline styles, scripts, remote fonts, or trackers.
SECURITY_CSS = """
:root{color-scheme:light;--paper:#fff;--ground:#f4f5f7;--ink:#1b1c2e;--line:#d8dbe3;--control-line:#6d7386;--accent:#4338a6}
@media(prefers-color-scheme:dark){:root{color-scheme:dark;--paper:#1e2030;--ground:#14151f;--ink:#ece6f5;--line:#53586f;--control-line:#8b92ad;--accent:#c1baff}}
*{box-sizing:border-box}
body{margin:0;min-height:100dvh;padding:1rem;background:var(--ground);color:var(--ink);font:1rem/1.6 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
main{width:100%;max-width:32rem;margin:1rem auto;padding:1.5rem;background:var(--paper);border:1px solid var(--line);border-radius:12px;overflow-wrap:anywhere}
h1{font-size:1.5rem;line-height:1.25;margin:0 0 1rem}h2{font-size:1.2rem;line-height:1.4}
img{display:block;max-width:100%;height:auto;margin:1rem auto}
form,label{display:grid;gap:.5rem}form{gap:1rem;margin-top:1.5rem}
input,button{font:inherit;min-height:44px;width:100%;padding:.65rem .8rem;border:1px solid var(--control-line);border-radius:8px}
input{background:var(--paper);color:var(--ink)}
button{cursor:pointer;font-weight:600;background:var(--paper);color:var(--ink)}
button:hover{border-color:var(--accent)}a{color:var(--accent);text-underline-offset:.2em}
:focus-visible{outline:3px solid var(--accent);outline-offset:3px}
pre{white-space:pre-wrap;overflow-wrap:anywhere}code{overflow-wrap:anywhere}
"""
SECURITY_STYLE_HASH = base64.b64encode(hashlib.sha256(SECURITY_CSS.encode()).digest()).decode()
SECURITY_CSP = (
    f"default-src 'none'; style-src 'sha256-{SECURITY_STYLE_HASH}'; "
    "img-src data:; form-action 'self'; frame-ancestors 'none'; base-uri 'none'"
)
