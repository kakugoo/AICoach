"""Bounded single-frame Zstandard decode into an isolated temporary file."""
from pathlib import Path

import zstandard


class InvalidDemoArchive(ValueError):
    pass


def decompress_demo(source: Path, target: Path, max_bytes: int) -> int:
    decoder = zstandard.ZstdDecompressor(max_window_size=128 * 1024 * 1024).decompressobj()
    written = 0
    prefix = b""
    try:
        with source.open("rb") as src, target.open("xb") as out:
            while chunk := src.read(256):
                if decoder.eof:
                    raise InvalidDemoArchive("Extra data after Zstandard frame")
                data = decoder.decompress(chunk)
                if decoder.unused_data:
                    raise InvalidDemoArchive("Extra data after Zstandard frame")
                written += len(data)
                if written > max_bytes:
                    raise InvalidDemoArchive("Decompressed file exceeds limit")
                if len(prefix) < 8:
                    prefix += data[:8-len(prefix)]
                out.write(data)
            if not decoder.eof or prefix != b"PBDEMS2\x00":
                raise InvalidDemoArchive("Truncated archive or not a CS2 demo")
        return written
    except BaseException:
        target.unlink(missing_ok=True)
        raise
