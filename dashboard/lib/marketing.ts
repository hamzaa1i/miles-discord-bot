/**
 * lib/marketing.ts — PHASE M shared marketing/site constants
 * (maintained through Phase N).
 *
 * Everything public-facing (landing, docs, stats, changelog, share
 * buttons, SEO) pulls from here so URLs live in exactly one place:
 *
 *   - bot invite link (built from NEXT_PUBLIC_DISCORD_CLIENT_ID with a
 *     curated, least-privilege-but-complete permission set)
 *   - support server (NEXT_PUBLIC_SUPPORT_SERVER_URL — optional; all
 *     support links simply hide when unset)
 *   - creator attribution + share intents
 *   - canonical site metadata used by every public page's `metadata`
 *
 * PHASE N (20.3): the source repository is going private, so public
 * pages no longer link to the repo (a private repo link 404s for
 * strangers). CREATOR_GITHUB_URL points at the creator's GitHub
 * PROFILE — attribution stays, dead links go. Nothing here links to
 * hamzaa1i/miles-discord-bot anymore.
 *
 * Nothing here is hardcoded to a domain — the canonical dashboard URL
 * comes from NEXT_PUBLIC_SITE_URL (Vercel sets it automatically for
 * production deployments; falls back to NEXTAUTH_URL).
 */

export const SITE_NAME = 'aurelia';

export const SITE_TAGLINE = 'the soft, elegant discord bot ✦';

export const SITE_DESCRIPTION =
  'ai chat, aesthetic moderation, community engagement. free forever. built with love.';

export const SITE_KEYWORDS = [
  'discord bot',
  'aesthetic',
  'veloura',
  'community',
  'ai chatbot',
  'moderation',
  'welcome cards',
  'leveling',
  'qotd',
  'giveaways',
];

export const CREATOR_GITHUB_URL = 'https://github.com/hamzaa1i';

export const SUPPORT_SERVER_URL = (
  process.env.NEXT_PUBLIC_SUPPORT_SERVER_URL || ''
).trim();

/** Discord bot invite — 15 curated flags, NOT administrator. */
export const INVITE_PERMISSIONS = '1152073985110';

/**
 * Why these flags (documented for reviewers):
 *   kick · ban · moderate members      → /mod suite + timeouts
 *   manage channels · manage messages  → /mod nuke, purge, slowmode, lock
 *   manage roles · manage nicknames    → level rewards, autorole, colors,
 *                                         nick requests
 *   manage webhooks                    → hybrid welcome mode
 *   view · send · embed · attach ·
 *   read history · add reactions ·
 *   external emojis · threads          → chat, starboard, polls, qotd
 *   connect · speak · mute · move      → voice channel management
 */
export function botInviteUrl(clientId?: string): string | null {
  const id = clientId || process.env.NEXT_PUBLIC_DISCORD_CLIENT_ID || '';
  if (!id) return null;
  return (
    'https://discord.com/oauth2/authorize?client_id=' +
    encodeURIComponent(id) +
    '&scope=bot%20applications.commands' +
    `&permissions=${INVITE_PERMISSIONS}`
  );
}

/** Canonical public site URL (for SEO/sitemap/OG absolute links). */
export function siteUrl(): string {
  const raw =
    process.env.NEXT_PUBLIC_SITE_URL ||
    process.env.NEXTAUTH_URL ||
    (process.env.VERCEL_PROJECT_PRODUCTION_URL
      ? `https://${process.env.VERCEL_PROJECT_PRODUCTION_URL}`
      : 'http://localhost:3000');
  return raw.replace(/\/$/, '');
}

/** Pre-written share messages (PHASE M PART 10). */
export const SHARE_MESSAGE =
  "i just discovered aurelia — the softest discord bot ✦ ai chat, aesthetic moderation and a beautiful dashboard. add it to your server:";

export const SHARE_MESSAGE_SHORT =
  'the softest discord bot ✦ free forever:';

export function twitterShareUrl(url: string, text: string): string {
  return (
    'https://twitter.com/intent/tweet' +
    `?text=${encodeURIComponent(text)}` +
    `&url=${encodeURIComponent(url)}`
  );
}

export function redditShareUrl(url: string, title: string): string {
  return (
    'https://www.reddit.com/submit' +
    `?url=${encodeURIComponent(url)}` +
    `&title=${encodeURIComponent(title)}`
  );
}

/** Numeric command count shown across marketing copy. */
export const COMMAND_COUNT = 173;  // PHASE O: canonical (utils/command_counts.py) — 74 top-level roots + subcommands

export const FEATURES_OVERVIEW = [
  { title: 'ai chat & memory', tag: 'she remembers you' },
  { title: 'aesthetic welcome cards', tag: 'greet every soul' },
  { title: 'smart moderation', tag: 'gentle but firm' },
  { title: 'community engagement', tag: 'keep the vibes alive' },
  { title: 'beautiful dashboard', tag: 'manage everything visually' },
  { title: 'privacy first', tag: "you're in control" },
];
