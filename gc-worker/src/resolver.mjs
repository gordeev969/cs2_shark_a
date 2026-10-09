import { decodeMatchShareCode } from 'csgo-sharecode';

export class ResolverError extends Error {
  constructor(status, message) { super(message); this.status = status; }
}
export function replayFromMatch(match) {
  const rounds = [...(match.roundstatsall ?? []), match.roundstats_legacy].filter(Boolean);
  const urls = rounds.map(r => r.map).filter(v => typeof v === 'string' && /^https?:\/\//.test(v));
  for (const value of urls.reverse()) {
    let url;
    try { url = new URL(value); } catch { continue; }
    if (!/^replay\d{1,5}\.valve\.net$/.test(url.hostname) || url.username || url.password || url.search || url.hash || url.port || !/^\/730\/[A-Za-z0-9_-]+\.dem(?:\.bz2)?$/.test(url.pathname)) continue;
    const result = { demo_url: url.href, match_id: String(match.matchid) };
    if (Number.isInteger(match.matchtime) && match.matchtime > 0) result.played_at = match.matchtime;
    return result;
  }
  throw new ResolverError(410, 'Replay is not available from Valve');
}
export class MatchResolver {
  constructor(gc, ready, { timeout = 30000, maxQueue = 16 } = {}) {
    this.gc = gc; this.ready = ready; this.timeout = timeout; this.maxQueue = maxQueue;
    this.queue = Promise.resolve(); this.pending = 0;
  }
  async resolve(code) {
    let expected;
    try { expected = decodeMatchShareCode(code).matchId.toString(); }
    catch { throw new ResolverError(422, 'Invalid match sharing code'); }
    if (this.pending >= this.maxQueue) throw new ResolverError(429, 'Coordinator queue is full');
    this.pending++;
    const task = this.queue.then(() => this.request(code, expected));
    this.queue = task.catch(() => undefined);
    try { return await task; } finally { this.pending--; }
  }
  request(code, expected) {
    if (!this.ready()) throw new ResolverError(503, 'Coordinator is not connected');
    return new Promise((resolve, reject) => {
      const cleanup = () => { clearTimeout(timer); this.gc.off('matchList', onMatches); this.gc.off('disconnectedFromGC', onDisconnected); };
      const onDisconnected = () => { cleanup(); reject(new ResolverError(503, 'Coordinator disconnected')); };
      const onMatches = matches => {
        const match = matches.find(m => String(m.matchid) === expected);
        if (!match) return;
        cleanup();
        try { resolve(replayFromMatch(match)); } catch(e) { reject(e); }
      };
      const timer = setTimeout(() => { cleanup(); reject(new ResolverError(503, 'Coordinator response timed out')); }, this.timeout);
      this.gc.on('matchList', onMatches); this.gc.on('disconnectedFromGC', onDisconnected);
      try { this.gc.requestGame(code); } catch { cleanup(); reject(new ResolverError(503, 'Coordinator request failed')); }
    });
  }
}
