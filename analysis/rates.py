"""Shared rate helpers.

Small module, but it exists so the tax-rate clamp has one definition. It was
previously written out independently in projector.py, wacc.py and fcff.py, which
meant a change to the bounds silently applied to some of the pipeline and not the
rest.
"""

from __future__ import annotations

# An effective rate outside this band means the filing's tax line is being read
# against a distorted or negative pre-tax income, not that the company genuinely
# pays that rate. Clamping keeps one odd year from swinging the whole valuation.
MIN_TAX_RATE = 0.0
MAX_TAX_RATE = 0.50


def clamp_tax_rate(tax_rate: float) -> float:
    """Constrain an effective tax rate to a plausible range."""
    return max(MIN_TAX_RATE, min(tax_rate, MAX_TAX_RATE))
