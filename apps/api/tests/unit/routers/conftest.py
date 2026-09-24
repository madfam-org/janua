"""Fixtures shared across the router test modules.

`test_internal_users.py` owns the SQLite-backed provisioning fixtures; re-export
them here so sibling modules (e.g. `test_internal_users_identity_pool.py`) can
request them by name without importing — an imported fixture shadowed by a test
parameter trips ruff's F811.
"""

import pytest
from test_internal_users import provisioning_client, provisioning_env  # noqa: F401


@pytest.fixture()
def cfdi_variables() -> dict:
    """A complete, synthetic ``billing/cfdi`` context (the v2 contract).

    Shaped like what nauta derives from a stamped CFDI 4.0 XML. The receptor is
    synthetic (the SAT's generic RFC): never a real client's data in the repo.
    """
    return {
        "cliente_nombre": "Cliente de Ejemplo",
        "receptor_nombre": "CLIENTE DE EJEMPLO",
        "rfc_receptor": "XAXX010101000",
        "emisor_nombre": "INNOVACIONES MADFAM",
        "rfc_emisor": "IMA2501164Y7",
        "serie_folio": "F4",
        "folio_fiscal": "11111111-2222-4333-8444-555555555555",
        "fecha_emision": "24 de septiembre de 2026",
        "periodo": "16 de septiembre de 2026 a 15 de octubre de 2026",
        "subtotal": "$16,379.31",
        "iva": "$2,620.69",
        "total": "$19,000.00 MXN",
        "forma_pago": "03 · Transferencia electrónica de fondos",
        "metodo_pago": "PUE · Pago en una sola exhibición",
        "verificacion_url": (
            "https://verificacfdi.facturaelectronica.sat.gob.mx/default.aspx"
            "?id=11111111-2222-4333-8444-555555555555&re=IMA2501164Y7"
            "&rr=XAXX010101000&tt=19000.0&fe=AbCd1234"
        ),
    }
