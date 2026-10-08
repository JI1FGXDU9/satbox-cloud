"""Parse local 3-line TLE catalogs, with optional bulletin header/footer."""
from dataclasses import dataclass


@dataclass(frozen=True)
class TLERecord:
    name: str
    line1: str
    line2: str


def read_catalog(text):
    lines = text.splitlines()
    records = []
    for i, line in enumerate(lines):
        if not line.startswith('1 '):
            continue
        if i == 0 or i + 1 >= len(lines) or not lines[i + 1].startswith('2 '):
            raise ValueError(f'Incomplete TLE at line {i + 1}')
        name = lines[i - 1].strip()
        if name.startswith('0 '):
            name = name[2:]
        if not name or name.startswith(('1 ', '2 ')):
            raise ValueError(f'Missing satellite name at line {i + 1}')
        records.append(TLERecord(name, line, lines[i + 1]))
    if not records:
        raise ValueError('No TLE records found')
    return tuple(records)


def select_records(records, names=None):
    if names is None:
        return records
    if not names or not all(isinstance(n, str) and n.strip() for n in names):
        raise ValueError('satellites must be a nonempty list of names')
    if len({n.casefold() for n in names}) != len(names):
        raise ValueError('Duplicate selected satellite names')
    selected = []
    for name in names:
        matches = [r for r in records if r.name.casefold() == name.strip().casefold()]
        if len(matches) != 1:
            raise ValueError(f'Satellite {name}: expected one record, found {len(matches)}')
        selected.append(matches[0])
    return tuple(selected)
