"""Who a URL or a path points at: the handle on a profile host, the record after a people collection, a home
directory, a referral handle. The host and the route stay; only the person's part is masked."""
from __future__ import annotations
from .common import *  # noqa: F401,F403  (Ctx, helpers, constants)
from .languages import G as _G


def G_lit(words):
    """An alternation of literal strings, for patterns."""
    return _G(*words)


def url_parts(c: Ctx):
    """Who a URL points at: the handle on a profile host, the record after a people collection in a path, a referral
    handle in a query string. The host, the route and the rest of the URL stay; only the person's part is masked."""
    n = c.n
    d = n.cls(D)
    segc = n.cls(AN + "_.-")
    seg_end_ok = n.OR(n.cls("/?#&\"' )<>,;\n"), n.cls("\x00"), force=True)
    reserved = ("login", "signup", "explore", "settings", "home", "search", "hashtag", "intent", "share", "reel", "reels", "watch", "help",
                "about", "pricing", "features", "topics", "trending", "notifications", "messages", "marketplace", "groups", "events", "pages",
                "profile.php", "sharer", "dialog", "jobs", "company", "school", "feed", "mynetwork", "results", "playlist", "shorts", "embed",
                "channel", "user", "status", "orgs", "organizations", "sponsors", "new", "join", "legal", "privacy", "terms", "policies",
                "blog", "docs", "api", "apps", "download", "stories", "direct", "accounts", "live", "video", "videos", "photos", "mobile",
                "me", "self", "current", "edit", "list", "index", "all", "public", "static", "assets", "en", "de", "fr", "es", "features",
                "enterprise", "team", "teams", "security", "customer-stories", "readme", "collections", "marketplace", "login.php")
    resv = n.OR(*[n.AND(n.lit(w), ~segc.at(-1), ~segc.at(len(w))) for w in reserved], force=True)
    def handle_after(prefix_end):
        h = n.prop_right(n.AND(segc, prefix_end.at(-1)), segc, 6)
        h = n.AND(h, n.fill(h, n.AND(h, ~h.at(1), seg_end_ok.at(1)), 6), ~n.fill(h, n.AND(h, resv), 6),
                  n.fill(h, n.AND(h, n.cls(AN)), 6), n.fill(h, n.AND(h, ~h.at(-1), n.run(segc, 2)), 6))
        return n.AND(h, ~n.AND(n.cls(".-"), ~h.at(1)))                      # "neha.k." keeps its trailing dot out
    # (1) the handle on a profile host
    hosts = ("twitter.com/", "x.com/", "instagram.com/", "facebook.com/", "tiktok.com/@", "youtube.com/@", "youtube.com/c/",
             "youtube.com/user/", "medium.com/@", "t.me/", "telegram.me/", "reddit.com/user/", "reddit.com/u/", "linkedin.com/in/",
             "calendly.com/", "pinterest.com/", "threads.net/@", "behance.net/", "dribbble.com/", "soundcloud.com/", "twitch.tv/",
             "keybase.io/", "mastodon.social/@", "about.me/", "paypal.me/", "venmo.com/u/", "venmo.com/", "patreon.com/",
             "buymeacoffee.com/", "ko-fi.com/", "linktr.ee/", "snapchat.com/add/", "vk.com/", "flickr.com/people/", "quora.com/profile/",
             "leetcode.com/u/", "codepen.io/", "npmjs.com/~", "hub.docker.com/u/", "substack.com/@", "bsky.app/profile/", "wa.me/")
    _, host_end = c.P(G_lit(hosts), pre="A-Za-z0-9-", post=None)
    social = handle_after(host_end)
    # code hosts: the owner of a repository is a person when the name looks like a personal handle
    _, code_end = c.P(G_lit(("github.com/", "gitlab.com/", "huggingface.co/", "kaggle.com/", "bitbucket.org/", "sourcehut.org/~",
                             "codeberg.org/")), pre="A-Za-z0-9-", post=None)
    code = handle_after(code_end)
    lone = n.fill(code, n.AND(code, ~code.at(1), n.OR(n.cls("?#\"' )<>,;\n"), n.cls("\x00"), force=True).at(1), ~n.lit("/").at(1)), 6)
    personal = n.fill(code, n.AND(code, n.OR(d, n.cls("_.-"), force=True)), 6)
    code = n.AND(code, n.OR(lone, personal, force=True))
    # (2) the record after a people collection in a path ("/users/42918/profile", "/patients/MRN-0045121/records", "/u/8f14e45f-...")
    coll = ("users", "user", "u", "profile", "profiles", "members", "member", "accounts", "account", "customers", "customer", "patients",
            "patient", "employees", "employee", "students", "student", "people", "person", "clients", "client", "subscribers", "players",
            "staff", "contacts", "contact", "applicants", "candidates", "learners", "guests", "drivers", "riders", "sellers", "buyers")
    _, coll_end = c.P(G_lit(tuple("/" + w + "/" for w in coll)), pre=None, post=None)
    rec = handle_after(coll_end)
    rec = n.AND(rec, ~n.fill(rec, n.AND(rec, ~rec.at(-1), c.english, ~n.fill(rec, n.AND(rec, d), 6)), 6))   # "/account/orders"
    rec_id = n.AND(rec, n.fill(rec, n.AND(rec, d), 6))
    # (3) home directories ("/home/priya.sharma/", "C:\\Users\\rahul.verma\\", "/Users/anita/")
    _, home_end = c.P(G_lit(("/home/", "/Users/", "\\Users\\")), pre=None, post=None)
    hh = n.prop_right(n.AND(segc, home_end.at(-1)), segc, 6)
    home = n.AND(hh, n.fill(hh, n.AND(hh, ~hh.at(1), n.cls("/\\").at(1)), 6), ~n.fill(hh, n.AND(hh, resv), 6))
    # (4) a referral handle in a query string ("?ref=priya_s", "&invited_by=rahul.v91")
    _, ref_end = c.P(G_lit(("ref=", "referrer=", "referral=", "invited_by=", "inviter=", "affiliate=", "aff=", "referred_by=")),
                     pre="A-Za-z0-9_", post=None)
    rv = n.prop_right(n.AND(segc, ref_end.at(-1)), segc, 5)
    ref = n.AND(rv, n.fill(rv, n.AND(rv, n.OR(d, n.cls("_."), force=True)), 5), n.fill(rv, n.AND(rv, n.cls(AL)), 5))
    users = n.OR(social, code, n.AND(rec, ~rec_id), home, ref, force=True)
    c.add("USERNAME", users, 0)
    c.add("ID", rec_id, 0)
    c.url_person = n.OR(users, rec_id, force=True)
    # (5) an encyclopedia article title is a topic, not a person ("/wiki/Alan_Turing")
    _, wiki_end = c.P(G_lit(("/wiki/",)), pre=None, post=None)
    c.url_topic = n.prop_right(n.AND(n.cls(AN + "_%(),.'-"), wiki_end.at(-1)), n.cls(AN + "_%(),.'-"), 7)
