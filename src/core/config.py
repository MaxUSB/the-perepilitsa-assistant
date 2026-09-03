from collections.abc import Iterable


def parse_int_set(value: object, *, variable_name: str) -> frozenset[int]:
    if value is None:
        return frozenset()
    if isinstance(value, int):
        return frozenset({value})
    if isinstance(value, str):
        return frozenset(int(item.strip()) for item in value.split(",") if item.strip())
    if isinstance(value, Iterable):
        return frozenset(int(str(item).strip()) for item in value)

    msg = f"{variable_name} must be a CSV string or an iterable of integers"
    raise TypeError(msg)
