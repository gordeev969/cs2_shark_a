import { LoginSession, EAuthTokenPlatformType } from 'steam-session';
import { resolve } from 'node:path';
import { saveToken } from './token.mjs';
process.umask(0o077);
const path = resolve(process.env.CS2_GC_TOKEN_FILE ?? '../.secrets/steam-refresh-token');
const session = new LoginSession(EAuthTokenPlatformType.SteamClient);
session.loginTimeout = 180000;
session.on('authenticated', () => {
  try { saveToken(path, session.refreshToken); console.log(`Steam session saved to ${path}. Keep this file private; do not commit it.`); }
  catch { console.error('Could not save Steam session'); process.exitCode = 1; }
});
session.on('timeout', () => { console.error('Steam login timed out'); process.exitCode = 1; });
session.on('error', () => { console.error('Steam login failed; try again'); process.exitCode = 1; });
process.on('SIGINT', () => { session.cancelLoginAttempt(); process.exit(130); });
try {
  const { qrChallengeUrl } = await session.startWithQR();
  const qrcode = (await import('qrcode-terminal')).default;
  console.log('Scan with the Steam mobile app and confirm login for this local CS2 demo service.');
  qrcode.generate(qrChallengeUrl, { small: true });
} catch { console.error('Steam QR login could not start'); process.exitCode = 1; }
