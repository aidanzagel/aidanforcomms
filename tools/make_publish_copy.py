"""Make the claude.ai publish copy of index.html.

The Artifact viewer wraps the page in its own <!doctype>, <html>, <head> and <body>,
so those four document tags are removed here. Only those exact tags are touched:
<header> and <headline>-style elements stay, because the pattern requires the tag
name to end right after "head" / "body" / "html".

Usage: python3 tools/make_publish_copy.py OUTPUT_PATH
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOC_TAGS = re.compile(r'(?i)<!doctype html>|</?(?:html|head|body)(?=[\s>])[^>]*>')


def main():
    if len(sys.argv) != 2:
        sys.exit('usage: python3 tools/make_publish_copy.py OUTPUT_PATH')
    src = (ROOT / 'index.html').read_text()
    out = DOC_TAGS.sub('', src)
    # Safety check: every <header> in index.html must survive
    if src.count('<header') != out.count('<header'):
        sys.exit('refusing to write: <header> tags would be lost')
    Path(sys.argv[1]).write_text(out)
    print(f'wrote {sys.argv[1]} ({len(out)} bytes, {out.count("<header")} header tags kept)')


if __name__ == '__main__':
    main()
