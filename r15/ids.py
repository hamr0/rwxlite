"""Shared identity helpers for r15 (registrable domain, name normalisation).  Not run directly."""
import re
from urllib.parse import urlparse

MULTI = {"co.uk", "org.uk", "ac.uk", "gov.uk", "com.au", "net.au", "org.au", "co.jp", "co.nz", "co.in", "co.kr",
         "co.za", "com.br", "com.cn", "com.mx", "com.tr", "com.sg", "com.hk", "com.tw", "com.ar", "com.ua"}
# hosting / generic / example hosts: not a vendor identity
GENERIC_HOSTS = {"localhost", "example.com", "example.org", "example.net", "swagger.io", "openapis.org",
                 "herokuapp.com", "github.io", "githubusercontent.com", "github.com", "gitlab.io", "gitlab.com",
                 "azurewebsites.net", "cloudfront.net", "vercel.app", "netlify.app", "onrender.com", "ngrok.io",
                 "ngrok-free.app", "execute-api.amazonaws.com", "run.app", "appspot.com", "pages.dev", "workers.dev",
                 "fly.dev", "railway.app", "glitch.me", "repl.co", "stoplight.io", "mockapi.io", "apiary.io",
                 "apiary-mock.com", "postman.com", "getpostman.com", "mocklab.io", "wiremock.io", "test.com",
                 "domain.com", "yourdomain.com", "company.com", "mycompany.com", "yourcompany.com", "foo.com",
                 "bar.com", "acme.com", "sample.com", "api.com", "host.com", "server.com", "localdomain",
                 "gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "protonmail.com", "qq.com", "163.com",
                 "icloud.com", "live.com", "users.noreply.github.com", "sourceforge.net", "bitbucket.org",
                 "smartbear.com", "readme.io", "redocly.com", "apimatic.io", "swaggerhub.com", "openapi-generator.tech"}
GENERIC_TITLES = {"", "api", "openapi", "swagger", "openapidefinition", "swaggerapi", "myapi", "restapi", "apidocs",
                  "apidocumentation", "apidefinition", "untitled", "title", "default", "swaggerdefinition", "openapispec",
                  "openapispecification", "swaggerspecification", "apispecification", "service", "backend", "app",
                  "server", "swaggerui", "apiswagger", "docs", "documentation", "yourapi", "testapi", "demo", "test"}


def norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def host_of(url):
    if not url or not isinstance(url, str):
        return None
    u = url.strip()
    if "@" in u and "://" not in u and "/" not in u:  # email
        u = u.split("@", 1)[1]
    if "://" not in u:
        u = "//" + u
    try:
        h = urlparse(u).hostname
    except Exception:
        return None
    return h.lower().strip(".") if h else None


def registrable(host):
    """Registrable domain of a hostname (heuristic public-suffix handling); None for IPs/locals."""
    if not host or "{" in host or "}" in host or "." not in host:
        return None
    if re.fullmatch(r"[\d.]+", host) or ":" in host:
        return None
    parts = host.split(".")
    last2 = ".".join(parts[-2:])
    if last2 in MULTI and len(parts) >= 3:
        return ".".join(parts[-3:])
    # hosting-style suffixes that are really 3-label (x.execute-api.amazonaws.com etc.)
    return last2


def domain(url):
    d = registrable(host_of(url))
    if d is None:
        return None
    return d


def is_generic_domain(d):
    if d is None:
        return True
    return d in GENERIC_HOSTS or d.endswith(".local") or d.endswith(".internal") or d.endswith(".test") or d.endswith(".example")


def norm_title(t):
    t = re.sub(r"\b(api|apis|rest|restful|swagger|openapi|open api|specification|spec|documentation|docs|v\d+(\.\d+)*|version)\b", " ", (t or "").lower())
    return norm(t)


def op_path_norm(p):
    p = re.sub(r"\{[^}]*\}", "{}", p or "")
    p = re.sub(r":[A-Za-z_]\w*", "{}", p)
    return p.rstrip("/").lower() or "/"
