"""Strict candidate parsing with an explicit, narrow LaTeX transport fallback."""

import json
import re

STRING = re.compile(r'"(?:[^"\\]|\\.)*"', re.DOTALL)
MATH = re.compile(r'(?<!\\)\\\(.*?(?<!\\)\\\)|(?<!\\)\\\[.*?(?<!\\)\\\]', re.DOTALL)


def _escape_math(match):
    # Preserve already escaped slash/quote pairs. Encode literal LaTeX slashes,
    # including commands such as \frac whose \f would otherwise become form feed.
    return re.sub(r'\\(?:\\|"|.)',
                  lambda m: m[0] if m[0][1] in '\\"' else '\\' + m[0], match[0])


def _repair_text(raw):
    """Walk one top-level object; modify only its text string, never answer."""
    decoder = json.JSONDecoder()
    pos = 0
    seen = set()
    replacement = None

    def whitespace(i):
        while i < len(raw) and raw[i] in ' \r\n\t':
            i += 1
        return i

    pos = whitespace(pos)
    if pos >= len(raw) or raw[pos] != '{':
        raise ValueError('Expected an object')
    pos = whitespace(pos + 1)
    while pos < len(raw) and raw[pos] != '}':
        key, pos = decoder.raw_decode(raw, pos)
        if not isinstance(key, str) or key in seen:
            raise ValueError('Invalid or duplicate key')
        seen.add(key)
        pos = whitespace(pos)
        if pos >= len(raw) or raw[pos] != ':':
            raise ValueError('Expected colon')
        pos = whitespace(pos + 1)
        if key == 'text':
            token = STRING.match(raw, pos)
            if token is None:
                raise ValueError('Expected text string')
            changed = MATH.sub(_escape_math, token[0])
            if changed != token[0]:
                replacement = (pos, token.end(), changed)
            pos = token.end()
        else:
            _, pos = decoder.raw_decode(raw, pos)
        pos = whitespace(pos)
        if pos < len(raw) and raw[pos] == ',':
            pos = whitespace(pos + 1)
            if pos >= len(raw) or raw[pos] == '}':
                raise ValueError('Trailing comma')
        else:
            break
    if pos >= len(raw) or raw[pos] != '}' or whitespace(pos + 1) != len(raw):
        raise ValueError('Invalid object ending')
    if replacement is None:
        raise ValueError('No supported text repair')
    start, end, text = replacement
    return raw[:start] + text + raw[end:]


def parse_candidate(raw, schema):
    try:
        candidate = schema.model_validate_json(raw)
        return candidate, {'mode': 'strict', 'raw_schema_valid': True}
    except ValueError:
        # Valid JSON with incorrect field types is NOT a transport error.
        try:
            json.loads(raw)
        except json.JSONDecodeError:
            repaired = _repair_text(raw)
            candidate = schema.model_validate_json(repaired)
            return candidate, {'mode': 'latex_text_escape', 'raw_schema_valid': False}
        raise
