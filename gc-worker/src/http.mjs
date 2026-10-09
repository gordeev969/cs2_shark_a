import { createServer } from 'node:http';
import { timingSafeEqual } from 'node:crypto';
import { ResolverError } from './resolver.mjs';
export function createBridgeServer(resolver, secret, ready) {
  if (!secret || secret.length < 24) throw new Error('CS2_GC_SECRET must contain at least 24 characters');
  const expected = Buffer.from(`Bearer ${secret}`);
  return createServer(async (req, res) => {
    function send(status, body) {
      res.writeHead(status, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' });
      res.end(JSON.stringify(body));
    }
    if (req.method === 'GET' && req.url === '/health') return send(200, { status: 'ok', ready: ready() });
    const received = Buffer.from(req.headers.authorization ?? '');
    if (received.length !== expected.length || !timingSafeEqual(received, expected)) return send(401, { detail: 'Unauthorized' });
    if (req.method !== 'POST' || req.url !== '/resolve') return send(404, { detail: 'Not found' });
    try {
      if (Number(req.headers['content-length'] ?? 0) > 4096) throw new ResolverError(413, 'Request too large');
      const chunks = []; let size = 0;
      for await (const chunk of req) {
        size += chunk.length;
        if (size > 4096) throw new ResolverError(413, 'Request too large');
        chunks.push(chunk);
      }
      let body;
      try { body = JSON.parse(Buffer.concat(chunks).toString('utf8')); }
      catch { throw new ResolverError(422, 'Invalid JSON'); }
      if (typeof body?.sharecode !== 'string' || body.sharecode.length > 64) throw new ResolverError(422, 'Invalid sharing code');
      send(200, await resolver.resolve(body.sharecode));
    } catch(e) {
      send(e instanceof ResolverError ? e.status : 500, { detail: e instanceof ResolverError ? e.message : 'Coordinator failed' });
    }
  });
}
