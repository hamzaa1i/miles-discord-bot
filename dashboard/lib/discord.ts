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

/** Fetch a fresh state + fully-built Discord authorize URL. */
export async function beginLogin(): Promise<{ url: string }> {
  const res = await fetch('/api/auth/state', { cache: 'no-store' });
  if (!res.ok) throw new Error('could not start login');
  return res.json() as Promise<{ url: string }>;
}
