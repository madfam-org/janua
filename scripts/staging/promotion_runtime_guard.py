"""Fail closed while Janua has no qualified isolated staging runtime adapter.

Pin age, a source manifest and public HTTP success do not prove which image is
running, native isolation, fresh custody, or a continuous healthy runtime soak.
There is deliberately no environment/input/JSON bypass. Replace this hold only
in a reviewed change that supplies and independently validates native evidence.
"""

import sys

REFUSAL = (
    "JANUA_STAGING_RUNTIME_NOT_QUALIFIED: production promotion is held until "
    "Enclii proves the isolated staging workload/image, dedicated database and "
    "custody, distinct issuer/JWKS, synthetic auth smoke and 30-minute healthy "
    "runtime soak. See docs/runbooks/isolated-staging-activation.md."
)


def main():
    print(REFUSAL, file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
