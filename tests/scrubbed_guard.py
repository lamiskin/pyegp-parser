"""Hashed guard for the upstream identifiers scrubbed from the real-world fixtures.

The `.egp` fixtures under ``tests/fixtures/real_world/`` were authored by a named
individual inside a named organisation, and originally embedded both — along with
their user name, workstation, and a UNC file-redirect server. Those were rewritten
before committing, and a guard asserts they never come back, which a refresh from
upstream would otherwise reintroduce silently.

Holding that guard's list as plaintext, however, republishes in this repository
exactly the values the sanitisation removed — and worse, gathers a person, their
employer, their user name and their hosts into one convenient table. So the
identifiers are stored here as SHA-256 digests of their lowercased form, and the
guard hashes candidate windows out of the archive text to compare.

**This is disclosure control, not secrecy.** The identifiers are short and
guessable, and anyone who suspects a particular value can confirm it by hashing
it. What the digests achieve is that the values are no longer *readable* here:
not indexed by search engines, not harvestable from a clone, and not presented
as an assembled profile. That is the whole of the intent.

Regenerating: the plaintext list is not kept in this repository. To add an
identifier, hash its lowercased form with ``sha256`` and add the digest plus its
length below; see ``tests/fixtures/real_world/README.md`` for the procedure.
"""

import hashlib

# SHA-256 of each scrubbed identifier, lowercased. See the module docstring.
_DIGESTS = frozenset(
    {
        "117a9d2cc85fbf9d1e2fc53b572014b842eac10d61b41ed8447b34beaff99e36",
        "1e014526e9cb78e89365fc5072b5adc06b7cdb5b9e1290fabe6685470d54d453",
        "3e0bcf48b88bb30d47175451b07d6910ab0c8f94fe274b97a89d5143b5ad47c5",
        "6a94fd257ae53148ae1800931336e848a6c3298dd032a54220d51b9c19ba2581",
        "847a5edbfe3b92726804997edaffb29a151d3f10ee5f0f3d68e4c838ca97f70b",
        "934c598c984056038e965a2c82d9e9bed4b35a415ebd40a92142abc13268754a",
        "ddc2e0d2e9773d0648385da0cb4bd7d6701f68814c45f95550d55d3196bb0582",
        "e2813bdf6e981a34b32ddb8306a3fa50cb10f0d8f6b3efdd263b9fcbb4e462db",
    }
)

# A digest can only be checked against a window of the right size, so lengths
# outside this range are invisible to the guard by construction. An identifier
# has already slipped through this way — a real hostname the guard was never
# widened to test at its actual length — so this is a contiguous range wide
# enough for any realistic single token (username, hostname, path segment)
# rather than the exact set of lengths seen so far, which is exactly what
# proved too narrow.
_WINDOW_LENGTHS = tuple(range(3, 33))


def find_scrubbed(text: str) -> tuple[int, str] | None:
    """Return ``(offset, digest)`` of the first scrubbed identifier in *text*.

    Returns ``None`` if the text is clean. The identifier itself is deliberately
    not returned — the caller reports the offset, which is enough to find it in
    a local working copy without printing it into CI logs.

    Windows are anchored to token starts (the beginning of the text, or any
    position following a non-alphanumeric character), which is where every known
    identifier begins: the user name appears in ``c:\\users\\…`` paths and the
    UNC server after a separator, and the organisation name follows ``OneDrive -``.
    An identifier buried mid-token would be missed here; the shape patterns in
    ``test_real_world.py`` are the backstop for anything this list cannot name.
    """
    haystack = text.lower()
    limit = len(haystack)
    for index in range(limit):
        if index and haystack[index - 1].isalnum():
            continue
        for length in _WINDOW_LENGTHS:
            if index + length > limit:
                break
            window = haystack[index : index + length]
            digest = hashlib.sha256(window.encode()).hexdigest()
            if digest in _DIGESTS:
                return index, digest
    return None
