import { chmodSync, mkdirSync, writeFileSync, renameSync } from 'node:fs';
import { dirname } from 'node:path';
import { randomBytes } from 'node:crypto';
export function saveToken(path, token) {
  if (typeof token !== 'string' || !token || token.length > 16384) throw new Error('Invalid Steam refresh token');
  mkdirSync(dirname(path), { recursive: true, mode: 0o700 });
  const temp = `${path}.${randomBytes(8).toString('hex')}.tmp`;
  writeFileSync(temp, `${token}\n`, { mode: 0o600, flag: 'wx' });
  renameSync(temp, path); chmodSync(path, 0o600);
}
