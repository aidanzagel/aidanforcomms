// Play counters for the videos on the site.
// GET /api/plays?v=pitch returns that video's count; POST adds one play and returns the new count.
// Storage: Upstash Redis, connected through the Vercel dashboard (Storage → Upstash → Redis).
// Only these videos have counters (the pitch keeps its original key, so its count carries over).
const KEYS = { pitch: 'campaign-video:plays', film: 'oneiop-film:plays' };

module.exports = async (req, res) => {
  res.setHeader('Cache-Control', 'no-store');
  const url = process.env.KV_REST_API_URL || process.env.UPSTASH_REDIS_REST_URL;
  const token = process.env.KV_REST_API_TOKEN || process.env.UPSTASH_REDIS_REST_TOKEN;
  if (!url || !token) return res.status(503).json({ error: 'Counter storage is not connected' });
  if (req.method !== 'GET' && req.method !== 'POST') {
    res.setHeader('Allow', 'GET, POST');
    return res.status(405).json({ error: 'Method not allowed' });
  }
  const v = new URL(req.url, 'http://x').searchParams.get('v') || 'pitch';
  const KEY = KEYS[v];
  if (!KEY) return res.status(400).json({ error: 'Unknown video' });
  try {
    const cmd = req.method === 'POST' ? 'incr' : 'get';
    const r = await fetch(`${url}/${cmd}/${encodeURIComponent(KEY)}`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!r.ok) throw new Error(`Redis responded ${r.status}`);
    const { result } = await r.json();
    return res.status(200).json({ plays: Number(result) || 0 });
  } catch (err) {
    return res.status(502).json({ error: 'Counter unavailable' });
  }
};
