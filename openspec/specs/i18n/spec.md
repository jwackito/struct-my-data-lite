# i18n Specification

## Purpose
English and Spanish localization for the server-rendered UI, client-side HTMX fragments, API error messages and the language switcher.

## Requirements

### Requirement: Supported languages and selection

The system SHALL support exactly `en` and `es`, defaulting to `en`. Server-side selection MUST prefer the `lang` cookie, then `Accept-Language`, then English. It SHALL normalise case and region tags such as `ES` or `es-AR` to their primary language and ignore unsupported values.

#### Scenario: Cookie wins
- **WHEN** a request has a `lang=es` cookie and an English `Accept-Language`
- **THEN** the response is rendered in Spanish

#### Scenario: Header fallback
- **WHEN** no language cookie is present and the header requests `es-AR`
- **THEN** the response is rendered in Spanish

#### Scenario: Unsupported language
- **WHEN** the cookie or header names a language outside `en` and `es`
- **THEN** the response falls back to English

### Requirement: Translation lookup and fallback

Translation keys SHALL be the English strings. A lookup MUST return the requested-language value, then the English value, then the key itself. Empty values SHALL count as missing. Interpolation SHALL use named placeholders and MUST return the unformatted text when a placeholder is missing.

#### Scenario: Missing Spanish value
- **WHEN** a key has no Spanish value
- **THEN** the English value is returned

#### Scenario: Unknown key
- **WHEN** a key is absent from both dictionaries
- **THEN** the key itself is returned

#### Scenario: Interpolation
- **WHEN** a translated string contains `{name}` and a name is supplied
- **THEN** the placeholder is replaced

### Requirement: Dictionary integrity

The English and Spanish dictionaries SHALL have identical key sets, and every value MUST be non-empty after trimming. Every literal backend translation key MUST exist in both dictionaries.

#### Scenario: Key parity
- **WHEN** a translation is added to one dictionary
- **THEN** the parity test fails until the other dictionary has the same key

#### Scenario: Empty translation
- **WHEN** a dictionary value is empty or whitespace
- **THEN** the integrity test fails

### Requirement: Server-side localization

The system SHALL determine a language for each request and use it for HTTP error details, the 500 response detail and request id, server-rendered HTMX fragments such as job statistics, history and batch notices, and page templates. Templates SHALL receive the active language and a translation helper.

#### Scenario: Localized API error
- **WHEN** a request with `lang=es` triggers a handled error
- **THEN** the error detail is in Spanish

#### Scenario: Localized fragment
- **WHEN** an HTMX fragment is rendered for a Spanish request
- **THEN** its labels and notices are in Spanish

### Requirement: Client-side localization

The browser script SHALL translate `data-i18n` text, `data-i18n-ph` placeholders and `data-i18n-title` titles, preserve element children, set the document language, and re-translate after every HTMX swap. It SHALL expose translation and language-setting functions to inline scripts.

#### Scenario: HTMX swap
- **WHEN** new content is inserted by HTMX
- **THEN** its `data-i18n` elements are translated without a page reload

#### Scenario: Placeholder
- **WHEN** an input has `data-i18n-ph`
- **THEN** its placeholder is translated

### Requirement: Language switcher

The system SHALL show an `EN`/`ES` switcher in the navigation and on logged-out pages, underline the active language, and set `lang=<code>; path=/; max-age=31536000` when a language is chosen. Switching SHALL update the page without a reload.

#### Scenario: Choose Spanish
- **WHEN** a visitor clicks the Spanish switcher
- **THEN** the `lang` cookie is set and the visible text switches to Spanish

#### Scenario: Active language
- **WHEN** the page is rendered in English
- **THEN** the English switcher entry is marked active

### Requirement: Dictionary endpoints

`GET /i18n/{lang}.json` SHALL return the dictionary for `en` or `es`, and `GET /i18n.js` SHALL return the client script as JavaScript. An unsupported language code MUST return `404` with a localized error.

#### Scenario: Dictionary download
- **WHEN** a client requests `/i18n/es.json`
- **THEN** the Spanish dictionary is returned as JSON

#### Scenario: Unknown language
- **WHEN** a client requests an unsupported dictionary
- **THEN** the response is `404`
