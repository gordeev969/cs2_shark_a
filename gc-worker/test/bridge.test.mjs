import test from 'node:test';
import assert from 'node:assert/strict';
import { EventEmitter } from 'node:events';
import { once } from 'node:events';
import { encodeMatch } from 'csgo-sharecode';
import { MatchResolver, replayFromMatch } from '../src/resolver.mjs';
import { createBridgeServer } from '../src/http.mjs';
import { saveToken } from '../src/token.mjs';
import { mkdtempSync, readFileSync, statSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
const matchId = 3687865087994699964n;
const code = encodeMatch({ matchId, reservationId: 3687865109469536398n, tvPort: 27015 });
const replay = { matchid: matchId.toString(), matchtime: 1700000000, roundstatsall: [{ map: 'de_mirage' }, { map: 'http://replay12.valve.net/730/123_456.dem.bz2' }] };

test('real sharing code decoding preserves uint64 and correlates GC matchList', async () => {
  const gc = new EventEmitter();
  gc.requestGame = received => {
    assert.equal(received, code);
    gc.emit('matchList', [{ ...replay, matchid: '123' }]);
    queueMicrotask(() => gc.emit('matchList', [replay]));
  };
  const resolver = new MatchResolver(gc, () => true);
  const result = await resolver.resolve(code);
  assert.equal(result.match_id, '3687865087994699964');
  assert.equal(result.played_at, 1700000000);
  assert.equal(gc.listenerCount('matchList'), 0);
});

test('queue serializes requestGame and safely ignores unrelated match lists', async () => {
  const gc = new EventEmitter(); let count = 0; let running = 0;
  gc.requestGame = () => {
    assert.equal(running++, 0); count++;
    setTimeout(() => { running--; gc.emit('matchList', [replay]); }, 10);
  };
  const resolver = new MatchResolver(gc, () => true);
  const result = await Promise.all([resolver.resolve(code), resolver.resolve(code)]);
  assert.equal(result.length, 2); assert.equal(count, 2);
});

test('unavailable coordinator and invalid codes return safe errors', async () => {
  const resolver = new MatchResolver(new EventEmitter(), () => false);
  await assert.rejects(resolver.resolve(code), e => e.status === 503);
  await assert.rejects(resolver.resolve('invalid'), e => e.status === 422);
});

test('timeouts remove listeners and allow next request', async () => {
  const gc = new EventEmitter(); gc.requestGame = () => {};
  const resolver = new MatchResolver(gc, () => true, { timeout: 10 });
  await assert.rejects(resolver.resolve(code), e => e.status === 503);
  assert.equal(gc.listenerCount('matchList'), 0);
  gc.requestGame = () => queueMicrotask(() => gc.emit('matchList', [replay]));
  assert.equal((await resolver.resolve(code)).match_id, replay.matchid);
});

test('missing or non-Valve replay URLs are not returned', () => {
  for (const map of ['de_mirage', 'http://localhost/730/x.dem', 'http://replay1.valve.net.evil/730/x.dem', 'http://replay1.valve.net/730/x.dem?key=secret']) {
    assert.throws(() => replayFromMatch({ matchid: '1', roundstatsall: [{ map }] }), e => e.status === 410);
  }
});

test('bridge authenticates bearer, validates bounded body and returns actual resolver result', async () => {
  const secret = 'a'.repeat(32);
  let called = false;
  const server = createBridgeServer({ resolve: async received => { called = true; assert.equal(received, code); return replayFromMatch(replay); } }, secret, () => true);
  server.listen(0, '127.0.0.1'); await once(server, 'listening');
  const base = `http://127.0.0.1:${server.address().port}`;
  try {
    assert.equal((await fetch(`${base}/health`)).status, 200);
    assert.equal((await fetch(`${base}/resolve`, { method: 'POST' })).status, 401);
    assert.equal(called, false);
    const headers = { Authorization: `Bearer ${secret}` };
    assert.equal((await fetch(`${base}/resolve`, { method: 'POST', headers, body: 'x'.repeat(5000) })).status, 413);
    assert.equal((await fetch(`${base}/resolve`, { method: 'POST', headers, body: 'bad json' })).status, 422);
    const response = await fetch(`${base}/resolve`, { method: 'POST', headers, body: JSON.stringify({ sharecode: code }) });
    assert.equal(response.status, 200); assert.equal((await response.json()).match_id, replay.matchid);
  } finally { server.closeAllConnections(); await new Promise(resolve => server.close(resolve)); }
});

test('Steam token file is private and atomically replaceable', () => {
  const directory = mkdtempSync(join(tmpdir(), 'cs2-token-'));
  try {
    const path = join(directory, 'session');
    saveToken(path, 'secret-one'); assert.equal(statSync(path).mode & 0o777, 0o600);
    saveToken(path, 'secret-two'); assert.equal(readFileSync(path, 'utf8'), 'secret-two\n');
  } finally { rmSync(directory, { recursive: true }); }
});
