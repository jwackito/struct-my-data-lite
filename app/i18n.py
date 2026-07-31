import json
from contextvars import ContextVar
from pathlib import Path

SUPPORTED_LANGS = ("en", "es")
_DEFAULT_LANG = "en"
_DIR = Path(__file__).parent / "i18n"

DICTS = {}

for _lang in SUPPORTED_LANGS:
    with open(_DIR / f"{_lang}.json", encoding="utf-8") as _f:
        DICTS[_lang] = json.load(_f)

current_lang = ContextVar("current_lang", default=_DEFAULT_LANG)


def t(key, lang="en", **kwargs):
    text = DICTS.get(lang, {}).get(key)
    if not text:
        text = DICTS.get("en", {}).get(key)
    if not text:
        return key
    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, IndexError):
            pass
    return text


def _normalize(locale):
    if not locale:
        return None
    code = locale.split(",")[0].split(";")[0].strip().lower()
    code = code.replace("_", "-").split("-")[0]
    return code if code in SUPPORTED_LANGS else None


def resolve_lang(request):
    lang = _normalize(request.cookies.get("lang"))
    if lang:
        return lang
    lang = _normalize(request.headers.get("accept-language"))
    return lang or _DEFAULT_LANG


def t_req(key, **kwargs):
    return t(key, current_lang.get(), **kwargs)
