import json
import sys
from pathlib import Path

import zstandard

from app.modules.demos.decompress import InvalidDemoArchive, decompress_demo
from app.modules.demos.parser import parse_demo

if __name__ == "__main__":
    if len(sys.argv) == 5:
        try:
            decompress_demo(Path(sys.argv[1]), Path(sys.argv[3]), int(sys.argv[4]))
        except InvalidDemoArchive as exc:
            sys.exit(22 if str(exc) == "Decompressed file exceeds limit" else 21)
        except zstandard.ZstdError:
            sys.exit(21)
        result = parse_demo(sys.argv[3])
    else:
        result = parse_demo(sys.argv[1])
    with open(sys.argv[2], "w", encoding="utf-8") as output:
        json.dump(result, output, ensure_ascii=False, allow_nan=False)
