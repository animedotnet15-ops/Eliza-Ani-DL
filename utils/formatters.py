def format_size(num_bytes: int) -> str:
    if not num_bytes:
        return "Unknown"
    for unit in ("B", "KB", "MB", "GB"):
        if num_bytes < 1024:
            return f"{num_bytes:.1f} {unit}" if unit != "B" else f"{num_bytes} B"
        num_bytes /= 1024
    return f"{num_bytes:.1f} TB"


def paginate(items: list, page: int, per_page: int = 10) -> tuple:
    start = page * per_page
    end = start + per_page
    total_pages = max(1, (len(items) + per_page - 1) // per_page)
    return items[start:end], total_pages


def truncate(text: str, length: int = 60) -> str:
    return text if len(text) <= length else text[: length - 1] + "…"
