"""Context rules: what a value is, decided from the key it sits under, the words around it and its shape.

Each module adds one family of circuits and vetoes; `run` applies them in a fixed order (the order matters: later
rules read the signals and vetoes of earlier ones). The results are left on the context `c`: c.key_veto (labels a span
may not take), c.key_trim (bytes cut from a label), c.ctx_not (not-a-name / not-a-secret / not-an-id signals exported
to the JavaScript pipeline).
"""
from types import SimpleNamespace
from .keys import read_keys
from .exceptions import documented_values, proper_nouns_and_codes
from .completion import complete_values
from .streets import streets
from .secret_cues import stated_credentials, code_and_interface_text, names_in_code, code_shapes, code_names_and_placeholders, references_and_labels
from .measurements import measurements
from .code_syntax import code_syntax


def run(c):
    k = SimpleNamespace()
    read_keys(c, k)
    documented_values(c, k)
    complete_values(c, k)
    streets(c, k)
    stated_credentials(c, k)
    code_and_interface_text(c, k)
    names_in_code(c, k)
    code_shapes(c, k)
    code_names_and_placeholders(c, k)
    references_and_labels(c, k)
    code_syntax(c, k)
    measurements(c, k)
    proper_nouns_and_codes(c, k)
