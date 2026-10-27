import json
import sys

from app.modules.demos.parser import parse_demo

if __name__ == "__main__":
    result = parse_demo(sys.argv[1])
    with open(sys.argv[2], "w", encoding="utf-8") as output:
        json.dump(result, output, ensure_ascii=False, allow_nan=False)
