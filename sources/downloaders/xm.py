#!/usr/bin/env python3
"""
xm - site profile for the Other Downloader (URL matching).
"""
import re

KEY = "xm"

_PATTERN = re.compile(
    r"xhamster(\.[a-z]{2,})?\.com|xhamster\.(desi|one|cc|xxx)",
    re.IGNORECASE,
)


def matches(url: str) -> bool:
    return bool(_PATTERN.search(url))
