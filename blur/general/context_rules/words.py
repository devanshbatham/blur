"""Key-aware circuits: in machine text the KEY a value belongs to says what the value is. The network reads a key the way
a person does: it splits it into its parts ("X-Request-Id" -> request + id, "appVersion" -> app + version,
"IDEMPOTENCY_KEY" -> idempotency + key, "first_name" -> first + name) and judges the value from what those parts mean,
together with the value's shape. There is no list of whole keys: a small vocabulary of word parts covers any key in any
carrier (JSON, query string, form body, cookie, header, XML, YAML / .env).

Word-part classes (see PARTS): secret parts (key, token, secret, password, signature, session ...; but a key's own
name / id / type is not the key), device parts, address parts, place parts, postcode parts, plain parts (version, type,
hash, nonce, trace, request, content, agent, region ...) and person parts (user, customer, account, owner, first, last ...).
A value under a key with a plain part and no person / secret / device part is not personal data.
Value shapes that are never identifiers or handles: product/version tokens, MIME types, booleans, UUIDs and hex hashes
(unless the key says device or secret), cloud region scopes. A label on a line of machine text is a key, not a name.
"""
from ...patterns import parse_var
from ..languages import G
from ..common import said, HI


PARTS = {
    "secret": ("key", "keys", "token", "tokens", "secret", "secrets", "password", "passwd", "pwd", "passphrase", "signature", "sig", "session",
               "sessionid", "sid", "csrf", "csrftoken", "xsrf", "credential", "credentials", "cred", "auth", "otp", "verifier", "apikey",
               "salt"),
    # keys whose values are passwords: a letters-only value counts here ("MYSQL_PASSWORD=root", "secret: averylongphrase"),
    # while a letters-only value under "key" or "token" is usually a name (measured on CredData)
    "pw": ("password", "passwd", "pwd", "passphrase", "pass", "secret", "secrets"),
    "credential_scope": ("api", "consumer", "access", "signing", "encryption", "private", "authentication", "bearer", "refresh",
                         "csrf", "xsrf", "credential"),
    "keyname": ("id", "type", "name", "alias", "ref", "hint", "url", "uri", "path", "header", "length", "expiry", "expires",
                "public", "pub",                                   # a public key is not a secret ("PublicKeyToken", "pub_key")
                # interface text about a password is not one ("passwordLabel", "password_placeholder", "PasswordHint")
                "label", "title", "placeholder", "hint", "prompt", "caption", "tooltip", "help"),
    "device": ("device", "advertising", "adid", "idfa", "idfv", "gaid", "imei", "imsi", "mac", "bssid", "ssid", "serial", "anonymous"),
    "address": ("address", "addr", "street", "line1", "line2", "line3"),
    "place": ("city", "town", "province", "country", "district", "county", "nationality"),
    "postcode": ("zip", "zipcode", "postal", "postcode", "pincode"),
    "plain": ("version", "ver", "build", "type", "kind", "status", "event", "action", "operation", "scope", "charset", "encoding", "boundary",
              "nonce", "cnonce", "realm", "qop", "nc", "algorithm", "alg", "hash", "sha", "sha1", "sha256", "md5", "digest", "checksum", "etag",
              "trace", "traceparent", "span", "request", "req", "correlation", "region", "zone", "lang", "language", "locale", "tz",
              "timezone", "theme", "currency", "consent", "variant", "experiment", "flag", "count", "size", "length", "total", "amount",
              "quantity", "max", "min", "age", "ttl", "expires", "expiry", "lifetime", "timeout", "rotation", "policy", "strength", "path", "method", "scheme", "host", "agent", "accept", "vary", "cache",
              "pragma", "server", "via", "connection", "mime", "format", "site", "same", "domain", "secure", "http", "only", "priority", "sku", "product", "item", "cart", "brand",
              "battery", "accuracy", "fingerprint", "cursor", "page", "next", "node", "hook", "delivery", "installation", "channel", "bot",
              "app", "client", "tenant", "project", "job", "run", "object", "charge", "last4", "exp",
              "month", "year", "allow", "campaign", "utm", "medium", "source", "color", "colour", "theme", "sort", "page", "headers", "methods", "expose", "control", "origin", "policy", "remember", "ab", "provider",
              "image", "state", "challenge", "dry", "synced", "opt", "marketing", "contacts", "role", "roles", "plan", "tier", "mode", "error", "err",
              "lineno", "port", "row", "col", "column", "step", "attempt", "retry", "seq", "sequence", "index", "idx", "offset", "limit", "batch"),
    "person": ("user", "customer", "member", "employee", "patient", "student", "account", "person", "owner", "holder", "subscriber", "uid",
               "contact", "recipient", "applicant", "guardian", "beneficiary", "passenger", "tenant", "driver", "first", "last", "full", "given",
               "family", "surname", "phone", "mobile", "email", "birth", "dob", "passport", "ssn", "tax", "national", "license", "licence"),
    "idempotency": ("idempotency",),
    "setting": ("ttl", "min", "max", "length", "len", "timeout", "expiry", "expires", "lifetime", "count", "size", "rotation", "policy",
                "strength", "version", "type", "format", "algorithm", "alg", "age", "interval", "limit", "retries", "attempts", "enabled",
                "required"),
    "idword": ("id", "ids", "identifier", "identifiers", "number", "no", "num", "nr", "uid", "guid"),
}
