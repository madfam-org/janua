# Dependency Security Exceptions

Last reviewed: 2026-05-21 UTC

The Python dependency security gate is `pip-audit` in `.github/workflows/security.yml`. It remains blocking for every non-excepted advisory. The exceptions below are explicit because the current upstream advisories have no fixed release available, or are disputed upstream. Remove an exception as soon as a fixed release exists or the dependency can be replaced.

| Ecosystem | Package | Installed version | Advisory | CVE | Status | Required follow-up |
| --- | --- | ---: | --- | --- | --- | --- |
| Python | PyJWT | 2.12.1 | PYSEC-2025-183 | CVE-2025-45768 | Disputed, no fixed version reported by pip-audit | Re-check on every weekly security scan and remove the ignore when a fixed version exists. |
| Python | Flask-Cors | 6.0.2 | PYSEC-2024-271 | CVE-2024-1681 | No fixed version reported by pip-audit | Keep CORS production allowlists restricted; remove the ignore when a fixed version exists. |
| Python | joblib | 1.5.3 | PYSEC-2024-277 | CVE-2024-34997 | Disputed, no fixed version reported by pip-audit | Do not load untrusted serialized joblib artifacts; remove the ignore when a fixed version exists. |

Local verification command:

```bash
cd apps/api
pip-audit -r requirements.txt \
  --ignore-vuln PYSEC-2025-183 \
  --ignore-vuln PYSEC-2024-271 \
  --ignore-vuln PYSEC-2024-277
```

Expected result on 2026-05-21:

```text
No known vulnerabilities found, 3 ignored
```
