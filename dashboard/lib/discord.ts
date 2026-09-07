/** Discord CDN helpers (display only — auth happens server-side). */

export function guildIconUrl(id: string, icon: string | null, size = 128): string | null {
  if (!icon) return null;
  return `https://cdn.discordapp.com/icons/${id}/${icon}.png?size=${size}`;
}

export function defaultAvatar(seed: string): string {
  const index = Number(BigInt(seed || '0') % 6n);
  return `https://cdn.discordapp.com/embed/avatars/${index}.png`;
}

export function channelTypeEmoji(type: number): string {
  if (type === 0) return '#'; // text
  if (type === 2) return '🔊'; // voice
  if (type === 5) return '📣'; // announcement
  if (type === 13) return '🔊'; // stage
  if (type === 15) return '🗂'; // forum
  return '#';
}

/** Thrown when /api/auth/state can't provide an authorize URL.
 *  Carries the server's actual error code + detail (never generic). */
export class LoginStartError extends Error {
  status: number;
  detail: string;

  constructor(status: number, message: string, detail = '') {
    super(message);
    this.name = 'LoginStartError';
    this.status = status;
    this.detail = detail;
  }
}

/**
 * Fetch a fresh state + fully-built Discord authorize URL.
 *
 * The server route (/api/auth/state) returns structured errors:
 *   { error: 'discord integration not configured', detail: '...' }  → 500
 *   { error: 'server configuration incomplete', detail: '...' }     → 500
 * Anything those routes say is surfaced verbatim through
 * LoginStartError so the login page can show the real reason.
 */
export async function beginLogin(): Promise<{
  url: string;
  state: string;
  origin: string;
  warnings: string[];
}> {
  let res: Response;
  try {
    res = await fetch('/api/auth/state', { cache: 'no-store' });
  } catch (e) {
    // the fetch itself failed — network, ad blocker, function cold start
    throw new LoginStartError(
      0,
      'network error',
      e instanceof Error ? e.message : 'could not reach /api/auth/state',
    );
  }

  if (!res.ok) {
    let error = '';
    let detail = '';
    try {
      const body = (await res.json()) as { error?: string; detail?: string };
      error = typeof body.error === 'string' ? body.error : '';
      detail = typeof body.detail === 'string' ? body.detail : '';
    } catch {
      // non-JSON body — fall through to the status text
    }
    throw new LoginStartError(
      res.status,
      error || `login service returned ${res.status}`,
      detail,
    );
  }

  return (await res.json()) as {
    url: string;
    state: string;
    origin: string;
    warnings: string[];
  };
}
