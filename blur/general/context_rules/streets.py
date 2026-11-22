"""Streets in many languages, as explicit shapes with a house number, and the city after them."""
from .words import *  # noqa: F401,F403  (word-part vocabulary and shared imports)


def streets(c, k):
    NAMES = k.NAMES
    P = k.P
    add_veto = k.add_veto
    n = k.n
    # (13) streets in many languages, as explicit shapes with a house number:
    #   street word + capitalised name (+ ", ") + number   "Via Roma, 42", "Ulitsa Tverskaya, 18", "Calle Mayor 5", "Rue de Rivoli 12"
    #   number + ", " + street word + name                  "22, Boulevard Haussmann"
    #   one or two capitalised words + Street/Road/... + number   "Bukhara Street 45", "Pyay Road 34"
    #   a compound street name + number                     "Drottninggatan 16", "Hauptstraße 3", "Nørrebrogade 21"
    from ..languages import L as _L
    NAMEC = "[A-Za-z\x80-\xbf\xc3\xc4\xc5'-]"
    pre_w = G(*[w for w in ("Via ", "Viale ", "Piazza ", "Corso ", "Calle ", "Avenida ", "Rua ", "Rue ", "Boulevard ", "Ulitsa ", "ulitsa ",
                                 "Prospekt ", "Sharia ", "Shari ", "Jalan ", "Carrera ", "Paseo ", "Praça ", "Largo ", "Strada ", "Calea ", "Ulica ",
                                 "Utca ", "Sokak ", "Caddesi ", "Rruga ", "Odos ", "Chemin ", "Allée ", "Camino ", "Avinguda ", "Carrer ")])
    st_a = n.OR(*[P(pre_w + "[A-Z]" + NAMEC + "{1,20}" + mid + sep + "[0-9]{1,4}[A-Za-z]?", pre="A-Za-z", post="0-9A-Za-z")[0]
                  for mid in ("", " [A-Z]" + NAMEC + "{1,20}", " (de|del|di|da|do|la|le|des|du|al|el) [A-Z]" + NAMEC + "{1,20}" if False else " [a-z]{1,3} [A-Z]" + NAMEC + "{1,20}")
                  for sep in (" ", ", ")], force=True)
    st_b = n.OR(*[P("[0-9]{1,4}[A-Za-z]?, " + pre_w + "[A-Z]" + NAMEC + "{1,20}" + mid, pre="0-9A-Za-z", post="A-Za-z")[0]
                  for mid in ("", " [A-Z]" + NAMEC + "{1,20}")], force=True)
    suf_w = G(" Street", " Road", " Avenue", " St", " Rd", " Ave", " Marg", " Lane", " Boulevard", " Blvd")
    st_c = n.OR(*[P(first + suf_w + G(" ", ", ") + "[0-9]{1,4}[A-Za-z]?", pre="A-Za-z", post="0-9A-Za-z")[0]
                  for first in ("[A-Z]" + NAMEC + "{1,20}", "[A-Z]" + NAMEC + "{1,20} [A-Z]" + NAMEC + "{1,20}")], force=True)
    comp_w = G(*[w for w in ("gatan", "vägen", "straße", "strasse", "gade", "vej", "katu", "weg", "laan", "straat", "gasse", "allee", "ulica")])
    st_d = P("[A-Z]" + NAMEC + "{1,24}" + comp_w + " [0-9]{1,4}[A-Za-z]?", pre="A-Za-z", post="0-9A-Za-z")[0]
    streets = n.OR(st_a, st_b, st_c, st_d, force=True)
    # the tail of a street with a house number: "[postcode] City [City]" after ", " ("Via Roma 8, Milano",
    # "Hauptstraße 12, 10115 Berlin", "Avenida de Mayo 1370, Buenos Aires")
    st_end = n.AND(streets, ~streets.at(1))
    cityw = "[A-Z]" + NAMEC + "{2,20}"
    tail = n.OR(*[c.P(pc + cityw + more, pre=None, post="A-Za-z0-9", start_terms=[st_end.at(-3), n.lit(", ").at(-2)])[0]
                  for pc in ("", "[0-9]{4,6} ") for more in ("", " " + cityw)], force=True)
    # one address owns its parts: the street, its number, its city ("Calle Mayor 5": "Mayor" is not a title here)
    region = n.OR(streets, tail, force=True)
    c.add("ADDRESS", region, 1)
    add_veto(NAMES + ("CITY", "STATE", "COUNTRY", "ORG", "TITLE", "BUILDING", "POSTCODE", "STREET", "DATE", "BOD"), region)   # "Avenida de Mayo 1370"
