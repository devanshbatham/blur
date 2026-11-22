"""blur: a PII and secrets masker whose network is written by this program.

    from blur import build
    model = build()          # the compiled network, for blur.engine.Engine or tools/export_model.py
"""
from .general import build

__all__ = ["build"]
