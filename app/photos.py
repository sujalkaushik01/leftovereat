"""Validation helpers for listing photos. Images are stored in the database."""

MAX_PHOTO_BYTES = 3 * 1024 * 1024  # 3 MB


def sniff_image_type(data: bytes) -> str | None:
    """Return a content type from the file's real bytes, not the client-supplied name."""
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None
