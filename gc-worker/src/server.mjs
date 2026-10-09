import SteamUser from 'steam-user';
import GlobalOffensive from 'globaloffensive';
import { readFileSync, mkdirSync } from 'node:fs';
import { MatchResolver } from './resolver.mjs';
import { createBridgeServer } from './http.mjs';
import { saveToken } from './token.mjs';
process.umask(0o077);
const secret = process.env.CS2_GC_SECRET ?? '';
const tokenFile = process.env.CS2_GC_TOKEN_FILE ?? '../.secrets/steam-refresh-token';
let token = process.env.STEAM_GC_REFRESH_TOKEN;
if (!token) { try { token = readFileSync(tokenFile, 'utf8').trim(); } catch {} }
if (!token) throw new Error('Steam GC session missing. Run npm run login first.');
const dataDirectory = process.env.STEAM_GC_DATA_DIR ?? '../.secrets/steam-client';
mkdirSync(dataDirectory, { recursive: true, mode: 0o700 });
const steam = new SteamUser({ protocol: SteamUser.EConnectionProtocol.WebSocket, dataDirectory, renewRefreshTokens: true });
const gc = new GlobalOffensive(steam);
let connected = false;
gc.on('connectedToGC', () => { connected = true; console.log('CS2 Game Coordinator connected'); });
gc.on('disconnectedFromGC', () => { connected = false; });
steam.on('loggedOn', () => { steam.gamesPlayed([730]); });
steam.on('disconnected', () => { connected = false; });
steam.on('error', () => { connected = false; console.error('Steam connection failed. Check session or network; no credentials logged.'); });
steam.on('refreshToken', refreshed => {
  try { saveToken(tokenFile, refreshed); } catch { console.error('Could not persist renewed Steam session'); }
});
const resolver = new MatchResolver(gc, () => connected);
const server = createBridgeServer(resolver, secret, () => connected);
server.requestTimeout = 45000;
server.listen(Number(process.env.CS2_GC_PORT ?? 8001), process.env.CS2_GC_BIND ?? '127.0.0.1', () => console.log('Private GC bridge listening'));
steam.logOn({ refreshToken: token });
for (const signal of ['SIGTERM', 'SIGINT']) process.on(signal, () => { connected = false; steam.logOff(); server.close(() => process.exit(0)); });
