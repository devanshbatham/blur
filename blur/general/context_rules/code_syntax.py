"""Secret precision from syntax: declaration names are not credential values.

These circuits recognise the role of a token, not a vocabulary of identifiers.
Quoted credential values remain protected, even when their contents resemble code.
"""
from .words import G


def code_syntax(c, k):
    n, cls, P = k.n, k.cls, k.P
    ident = cls("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_$")
    first = cls("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_$")
    space = cls(" \t")
    _, decl_end = P(G("var", "let", "const", "function", "def", "class", "struct", "enum", "interface", "type", "namespace", "import")
                   + "[ \t]{1,8}", pre="A-Za-z0-9_$")
    name = n.prop_right(n.AND(first, decl_end.at(-1)), ident, 5)
    # Require syntax after the name too: "type Cedar7Lane" in prose is not a declaration.
    end = n.AND(name, ~ident.at(1))
    after = n.prop_right(end, space, 3)
    syntax = n.OR(cls("=(:{;"), n.lit("from "), n.lit("extends "), n.lit("implements "),
                  n.lit("struct "), n.lit("interface "), force=True)
    confirmed = n.fill(name, n.AND(end, n.prop_left(n.AND(syntax, after.at(-1)), space, 3).at(1)), 5)
    # In an explicitly declared JS-style assignment, an unquoted identifier on
    # the right is a reference. Shell/.env assignments have no such declaration.
    _, rhs_end = P(G("var", "let", "const") + "[ \t]{1,8}[A-Za-z_$][A-Za-z0-9_$]{0,63}[ \t]{0,8}=[ \t]{0,8}",
                   pre="A-Za-z0-9_$")
    reference = n.prop_right(n.AND(first, rhs_end.at(-1)), ident, 5)
    ref_end = n.AND(reference, ~ident.at(1))
    ref_tail = n.prop_right(ref_end, space, 3)
    terminated = n.prop_left(n.AND(cls(";,"), ref_tail.at(-1)), space, 3)
    reference = n.fill(reference, n.AND(ref_end, terminated.at(1)), 5)
    # Numeric type names in a type/list expression, e.g. XY_Float64. The token
    # shape alone is insufficient: a password may have exactly the same shape.
    numeric_type, _ = P("[A-Z]{2,8}_[A-Z][a-z]{2,16}[0-9]{1,3}", pre="A-Za-z0-9_$", post="A-Za-z0-9_$")
    type_end = n.AND(numeric_type, ~numeric_type.at(1))
    type_tail = n.prop_right(type_end, space, 3)
    type_close = n.prop_left(n.AND(cls(",]>"), type_tail.at(-1)), space, 3)
    type_open = n.prop_right(cls("[,<"), space, 3)
    numeric_type = n.AND(numeric_type,
        n.fill(numeric_type, n.AND(numeric_type, ~numeric_type.at(-1), type_open.at(-1)), 5),
        n.fill(numeric_type, n.AND(type_end, type_close.at(1)), 5))
    syntax_value = n.OR(confirmed, reference, numeric_type, force=True)
    # A quoted password may itself contain code, including a declaration.
    syntax_value = n.AND(syntax_value, ~c.literal_password)
    k.add_veto(("SECRET", "PASS"), syntax_value)
    k.ctx_not["SECRET"] = n.OR(k.ctx_not["SECRET"], syntax_value, force=True)
