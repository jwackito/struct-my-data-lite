(function () {
  var LANGS = ["en", "es"];
  var DEFAULT_LANG = "en";
  var currentLang = DEFAULT_LANG;
  var dicts = {};
  var enDict = {};

  function normalize(code) {
    if (!code) return null;
    code = code.toLowerCase().replace("_", "-").split("-")[0];
    return LANGS.indexOf(code) !== -1 ? code : null;
  }

  function t(key) {
    var d = dicts[currentLang] || {};
    return d[key] || enDict[key] || key;
  }

  function translateElement(el) {
    var key = el.getAttribute("data-i18n");
    if (key) {
      var text = t(key);
      var hasElementChildren = false;
      el.childNodes.forEach(function (node) {
        if (node.nodeType === Node.ELEMENT_NODE) hasElementChildren = true;
      });
      if (hasElementChildren) {
        el.childNodes.forEach(function (node) {
          if (node.nodeType === Node.TEXT_NODE) node.textContent = text;
        });
      } else {
        el.textContent = text;
      }
    }
    var ph = el.getAttribute("data-i18n-ph");
    if (ph) el.placeholder = t(ph);
    var title = el.getAttribute("data-i18n-title");
    if (title) el.title = t(title);
  }

  function translateTree(root) {
    root.querySelectorAll("[data-i18n],[data-i18n-ph],[data-i18n-title]").forEach(translateElement);
    var self = root.getAttribute ? root.getAttribute("data-i18n") : null;
    var selfPh = root.getAttribute ? root.getAttribute("data-i18n-ph") : null;
    var selfTitle = root.getAttribute ? root.getAttribute("data-i18n-title") : null;
    if (self || selfPh || selfTitle) translateElement(root);
  }

  function renderSwitcher() {
    var host = document.getElementById("lang-switcher");
    if (!host) return;
    host.innerHTML = "";
    LANGS.forEach(function (lang) {
      var a = document.createElement("a");
      a.href = "#";
      a.textContent = lang.toUpperCase();
      a.title = lang;
      a.style.cssText =
        "margin:0 4px;text-decoration:none;font-weight:bold;font-size:0.8rem;color:#2563eb;";
      if (lang === currentLang) {
        a.style.textDecoration = "underline";
      } else {
        a.onclick = function (e) {
          e.preventDefault();
          setLang(lang);
        };
      }
      host.appendChild(a);
    });
  }

  function setLang(lang) {
    document.cookie = "lang=" + lang + "; path=/; max-age=31536000";
    currentLang = lang;
    if (!dicts[lang]) {
      fetchDict(lang).then(function (data) {
        dicts[lang] = data;
        applyLang();
      });
    } else {
      applyLang();
    }
  }

  function applyLang() {
    document.documentElement.lang = currentLang;
    translateTree(document);
    renderSwitcher();
  }

  function fetchDict(lang) {
    return fetch("/i18n/" + lang + ".json").then(function (r) {
      if (!r.ok) return {};
      return r.json();
    });
  }

  function getCookieLang() {
    var found = null;
    document.cookie.split(";").forEach(function (c) {
      var p = c.trim().split("=");
      if (p[0] === "lang") found = normalize(p[1]);
    });
    return found;
  }

  window.t = t;
  window.i18nSetLang = setLang;

  document.addEventListener("DOMContentLoaded", function () {
    var initial = getCookieLang() || normalize(navigator.language) || DEFAULT_LANG;
    fetchDict(DEFAULT_LANG).then(function (en) {
      enDict = en;
      dicts[DEFAULT_LANG] = en;
      if (initial === DEFAULT_LANG) {
        currentLang = initial;
        applyLang();
      } else {
        fetchDict(initial).then(function (data) {
          dicts[initial] = data;
          currentLang = initial;
          applyLang();
        });
      }
    });
  });

  document.body.addEventListener("htmx:afterSwap", function (e) {
    if (e.detail && e.detail.target) translateTree(e.detail.target);
  });
})();
