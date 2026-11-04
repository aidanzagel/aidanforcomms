#!/usr/bin/env python3
"""Daily OneIOP refresh: pulls upcoming events from iop.harvard.edu/events.

Writes events.json and the built-in copy in oneiop.html,
downloads each event's graphic into assets/iop/, and drops events that have
already ended. To reword an event, add it to tools/event_overrides.json (keyed
by the event's URL slug); those fields always win over the IOP's own text.
Standard library only, so it runs anywhere with Python 3.9+.

    python3 tools/update_events.py            # run from the site folder
    python3 tools/update_events.py --days 14  # how far ahead to keep events
"""
import argparse, html, json, re, sys, urllib.parse, urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

BASE = 'https://iop.harvard.edu'
UA = {'User-Agent': 'OneIOP-demo-updater/1.0 (+https://aidanforcomms.com)'}
ET = ZoneInfo('America/New_York')
ROOT = Path(__file__).resolve().parent.parent
OUT_JSON, IMG_DIR = ROOT / 'events.json', ROOT / 'assets' / 'iop'
PAGES = [ROOT / 'oneiop.html']  # keeps a built-in copy of the events
OVERRIDES = Path(__file__).resolve().parent / 'event_overrides.json'

# IOP program names, as the IOP site writes them, mapped to OneIOP program ids
PROGRAM_IDS = {
    'john f. kennedy jr. forum': 'Forum', 'fellows & study groups': 'FSG',
    'conferences committee': 'Conferences', 'harvard political union': 'HPU',
    "women's initiative in leadership": 'WIL', 'politics of race and ethnicity': 'PRE',
    'global affairs program': 'GAP', 'program for environmental politics': 'Environment',
    'the policy program': 'Policy', 'policy program': 'Policy',
    'harvard public opinion project': 'HPOP', 'research & strategy group': 'RSG',
    'governance lab': 'GovLab', 'civics': 'CIVICS', 'citizenship tutoring': 'Cit Tut',
    'harvard votes challenge': 'HVC', 'harvard political review': 'HPR',
    'campaigns and advocacy program': 'CAP', 'coalition for the arts': 'Arts',
    'conservative coalition': 'Conservative', 'gender & sexuality coalition': 'GSC',
    'service coalition': 'Service',
}


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
        return r.read()


def text(s):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', s or ''))).strip()


def field(page, name):
    m = re.search(r'field--name-%s\b.*?class="[^"]*field__item[^"]*">(.*?)</(?:div|span)>' % name, page, re.S)
    return text(m.group(1)) if m else ''


def var(page, name):
    m = re.search(r'<var class="atc_%s">(.*?)</var>' % name, page, re.S)
    return html.unescape(m.group(1)).strip() if m else ''


def listing_slugs(max_pages):
    slugs = []
    for p in range(max_pages):
        page = get(f'{BASE}/events?page={p}').decode('utf-8', 'replace')
        rows = page.split('class="views-row"')[1:]
        if not rows:
            break
        for r in rows:
            m = re.search(r'href="/events/([^"?#/]+)"', r)
            if m and m.group(1) not in slugs:
                slugs.append(m.group(1))
    return slugs


def sentence(s, limit=190):
    s = s.strip()
    if len(s) <= limit:
        return s
    cut = s[:limit]
    # Sentence ends after a lowercase letter, so "U.S." or "Amb." don't count
    ends = [m.end() for m in re.finditer(r'(?<=[a-z)][.?!])\s', cut)]
    return cut[:ends[-1]].strip() if ends and ends[-1] > 60 else cut.rsplit(' ', 1)[0] + '…'


def join_names(names):
    names = names[:3]
    return names[0] if len(names) == 1 else ', '.join(names[:-1]) + ' and ' + names[-1]


def scrape(slug):
    page = get(f'{BASE}/events/{slug}').decode('utf-8', 'replace')
    start, end = var(page, 'date_start'), var(page, 'date_end')
    if not start:
        return None
    s = datetime.strptime(start, '%Y-%m-%d %H:%M:%S')
    e = datetime.strptime(end, '%Y-%m-%d %H:%M:%S') if end else None
    # The IOP site fills in a junk end time when an event has none; fall back to a typical length
    if not e or e <= s or e.date() != s.date():
        e = s + timedelta(hours=1, minutes=15)
    title = text(var(page, 'title')) or text(re.search(r'<title>(.*?)</title>', page, re.S).group(1)).split('|')[0]
    host = ''
    m = re.match(r'(Study Group with [^:]+):\s*(.+)', title)
    if m:
        host, title = 'Study group with ' + m.group(1)[len('Study Group with '):], m.group(2)
    if not host:
        speakers = [text(x) for x in re.findall(r'field--name-field-speaker\b.*?<a [^>]*>(.*?)</a>', page, re.S)]
        host = join_names(speakers) if speakers else 'Institute of Politics'
    desc = ''
    m = re.search(r'<meta name="description" content="([^"]*)"', page)
    if m:
        desc = sentence(text(m.group(1)).replace('?Join', '? Join').replace('.Join', '. Join'))
    prog_name = field(page, 'field-associated-program').lower().replace('’', "'")
    img = ''
    m = re.search(r'field--name-field-image\b.*?(/sites/default/files/styles/responsive_image_1200/[^" ]+?\.(?:webp|png|jpe?g)\?itok=[\w-]+)', page, re.S)
    if m:
        img = BASE + m.group(1)
    return {
        'slug': slug, 'p': PROGRAM_IDS.get(prog_name, 'IOP'),
        'date': s.strftime('%Y-%m-%d'), 's': s.strftime('%H:%M'), 'e': e.strftime('%H:%M'),
        # "JFK Jr. Forum, 79 John F. Kennedy St., ..." -> "JFK Jr. Forum" (the page adds the address itself)
        'where': re.split(r',\s*79 J', field(page, 'field-in-person-location'))[0] or 'Institute of Politics',
        'title': title, 'host': host, 'desc': desc, 'img_url': img,
    }


def download_image(url, slug):
    ext = re.search(r'\.(webp|png|jpe?g)\?', url).group(1)
    name = re.sub(r'[^a-z0-9-]', '', slug)[:60] + '.' + ext
    path = IMG_DIR / name
    if not path.exists():
        path.write_bytes(get(url))
    return f'assets/iop/{name}'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--days', type=int, default=14)
    ap.add_argument('--pages', type=int, default=6)
    args = ap.parse_args()
    now = datetime.now(ET).replace(tzinfo=None)
    horizon = (now + timedelta(days=args.days)).strftime('%Y-%m-%d')

    old = {}
    if OUT_JSON.exists():
        old = {e['url']: e for e in json.loads(OUT_JSON.read_text())['events']}
    edits = json.loads(OVERRIDES.read_text()) if OVERRIDES.exists() else {}

    IMG_DIR.mkdir(parents=True, exist_ok=True)
    events, errors = [], []
    for slug in listing_slugs(args.pages):
        try:
            ev = scrape(slug)
        except Exception as ex:  # one broken page shouldn't stop the update
            errors.append(f'{slug}: {ex}')
            ev = None
        if not ev:
            continue
        end = datetime.strptime(f"{ev['date']} {ev['e']}", '%Y-%m-%d %H:%M')
        if end < now or ev['date'] > horizon:
            continue
        prev = old.get(slug, {})
        img = prev.get('img') if prev.get('img') and (ROOT / prev['img']).exists() else ''
        if not img and ev['img_url']:
            try:
                img = download_image(ev['img_url'], slug)
            except Exception as ex:
                errors.append(f'{slug} image: {ex}')
        events.append({
            'p': ev['p'], 'date': ev['date'], 's': ev['s'], 'e': ev['e'], 'where': ev['where'],
            'img': img, 'url': slug, 'title': ev['title'], 'host': ev['host'], 'desc': ev['desc'],
            **{k: v for k, v in edits.get(slug, {}).items() if k in ('where', 'title', 'host', 'desc', 'img', 'e')},
        })

    if not events and errors:
        sys.exit('No events scraped; leaving the old data in place.\n' + '\n'.join(errors))
    events.sort(key=lambda e: (e['date'], e['s']))
    for i, e in enumerate(events, 1):
        e['id'] = i
    data = {'updated': datetime.now(ET).isoformat(timespec='minutes'), 'source': BASE + '/events', 'events': events}
    OUT_JSON.write_text(json.dumps(data, indent=1, ensure_ascii=False) + '\n')

    # Keep the copy built into each page in sync, so the pages work even when opened as files
    block = '/*EVENTS*/' + json.dumps(data, ensure_ascii=False) + '/*END*/'
    for path in PAGES:
        if not path.exists():
            continue
        page, n = re.subn(r'/\*EVENTS\*/.*?/\*END\*/', lambda _: block, path.read_text(), flags=re.S)
        if n:
            path.write_text(page)

    # Remove graphics for events that are gone 
    keep = {Path(e['img']).name for e in events if e['img']}
    for f in IMG_DIR.glob('*'):
        if f.suffix in ('.webp', '.png', '.jpg') and f.name not in keep:
            f.unlink()

    print(f"{len(events)} upcoming events through {horizon}; updated {data['updated']}")
    for line in errors:
        print('warning:', line)


if __name__ == '__main__':
    main()
