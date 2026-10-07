"""How an upstream payload is stored.

`raw_data` keeps the response verbatim **in meaning, not in bytes**: it is re-serialised with sorted
keys and no incidental whitespace. That is not cosmetic. The stored text takes part in the change
predicate that decides whether a re-ingested row is a change (ADR-008 §5's "zero changed values"), so a
serialisation whose text depends on key order makes the predicate fire when nothing happened — measured,
the same payload dumped twice differs in text while matching in length (lesson 031) — and every run
would report changes it did not make.

A payload is therefore written through exactly one function, and nothing else may reach `raw_data`.
"""

from __future__ import annotations

import json
from typing import Final

#: Compact separators: the database is storage, not a wire format, and incidental whitespace would be
#: one more way for two spellings of equal payloads to differ.
_SEPARATORS: Final = (",", ":")


def canonical_json(payload: object) -> str:
    """The one spelling of a payload that may reach `raw_data`."""
    return json.dumps(payload, sort_keys=True, separators=_SEPARATORS)
