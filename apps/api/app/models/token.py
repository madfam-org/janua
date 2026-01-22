"""
Token models - backward compatibility module
"""

# Import token-related models from the main models module
from . import TokenClaims

# Alias for backward compatibility
Token = TokenClaims
