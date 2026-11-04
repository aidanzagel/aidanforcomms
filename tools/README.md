# Daily OneIOP event refresh

`update_events.py` reads iop.harvard.edu/events, keeps the next 14 days of events,
downloads each event's graphic into `assets/iop/`, and writes `events.json` plus the
copy built into `oneiop.html`. Past events and their graphics are removed.

Run it by hand from the site folder:

    python3 tools/update_events.py

Once a day, automatically:
- On a host that deploys from GitHub (Pages, Netlify, Vercel, Cloudflare Pages), push this
  folder to a repo. `.github/workflows/update-events.yml` runs the script every morning and
  commits any changes, which redeploys the site.
- The claude.ai preview is refreshed by a scheduled task in the Claude app.

To reword an event, add its URL slug to `event_overrides.json` with any of `title`, `host`,
`desc`, `where` or `e` (end time, "HH:MM"). If the IOP lists no end time, the script assumes
75 minutes.
