def split_by_commata(string: str) -> list[str]:
    if not string:
        return []
    return string.split(",")
