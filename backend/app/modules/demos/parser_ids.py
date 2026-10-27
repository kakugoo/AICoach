from numbers import Integral


def steam_id(value: object) -> str | None:
    if isinstance(value, Integral):
        value = str(int(value))
    if isinstance(value, str) and value.isdigit() and len(value) == 17:
        return value
    return None
