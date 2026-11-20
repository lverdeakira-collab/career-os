from __future__ import annotations

from datetime import date
import re
from typing import Any


TYPE_MAP = {
    'object': dict,
    'array': list,
    'string': str,
    'number': (int, float),
    'integer': int,
    'boolean': bool,
    'null': type(None),
}


def _resolve_ref(root: dict, ref: str) -> dict:
    if not ref.startswith('#/'):
        raise ValueError(f'Only local JSON Schema references are supported: {ref}')
    node: Any = root
    for token in ref[2:].split('/'):
        node = node[token.replace('~1', '/').replace('~0', '~')]
    return node


def _type_matches(value: Any, expected: str) -> bool:
    if expected in {'number', 'integer'} and isinstance(value, bool):
        return False
    return isinstance(value, TYPE_MAP[expected])


def _validate(value: Any, schema: dict, root: dict, path: str, errors: list[str]) -> None:
    if '$ref' in schema:
        _validate(value, _resolve_ref(root, schema['$ref']), root, path, errors)
        return

    if 'const' in schema and value != schema['const']:
        errors.append(f'{path}: expected constant {schema["const"]!r}, got {value!r}')
    if 'enum' in schema and value not in schema['enum']:
        errors.append(f'{path}: {value!r} is not an allowed value')

    expected_types = schema.get('type')
    if expected_types:
        expected_types = [expected_types] if isinstance(expected_types, str) else expected_types
        if not any(_type_matches(value, item) for item in expected_types):
            errors.append(f'{path}: expected type {expected_types}, got {type(value).__name__}')
            return

    if isinstance(value, dict):
        required = schema.get('required', [])
        for key in required:
            if key not in value:
                errors.append(f'{path}.{key}: required property is missing')
        properties = schema.get('properties', {})
        if schema.get('additionalProperties') is False:
            for key in value:
                if key not in properties:
                    errors.append(f'{path}.{key}: additional property is not allowed')
        for key, subschema in properties.items():
            if key in value:
                _validate(value[key], subschema, root, f'{path}.{key}', errors)

    if isinstance(value, list):
        if len(value) < schema.get('minItems', 0):
            errors.append(f'{path}: fewer than {schema["minItems"]} items')
        if 'maxItems' in schema and len(value) > schema['maxItems']:
            errors.append(f'{path}: more than {schema["maxItems"]} items')
        if schema.get('uniqueItems'):
            serialized = [repr(item) for item in value]
            if len(serialized) != len(set(serialized)):
                errors.append(f'{path}: items are not unique')
        if 'items' in schema:
            for index, item in enumerate(value):
                _validate(item, schema['items'], root, f'{path}[{index}]', errors)

    if isinstance(value, str):
        if len(value) < schema.get('minLength', 0):
            errors.append(f'{path}: string is shorter than {schema["minLength"]}')
        if 'pattern' in schema and re.fullmatch(schema['pattern'], value) is None:
            errors.append(f'{path}: {value!r} does not match {schema["pattern"]}')
        if schema.get('format') == 'date':
            try:
                date.fromisoformat(value)
            except ValueError:
                errors.append(f'{path}: {value!r} is not an ISO date')

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if 'minimum' in schema and value < schema['minimum']:
            errors.append(f'{path}: {value} is below minimum {schema["minimum"]}')
        if 'maximum' in schema and value > schema['maximum']:
            errors.append(f'{path}: {value} exceeds maximum {schema["maximum"]}')


def validate_schema(instance: Any, schema: dict, label: str = '$') -> list[str]:
    """Validate the JSON Schema subset used by Career_OS without external packages."""
    errors: list[str] = []
    _validate(instance, schema, schema, label, errors)
    return errors
