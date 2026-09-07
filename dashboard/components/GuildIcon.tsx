'use client';

/** GuildIcon — server avatar with veloura initial fallback.
 *
 * Accepts the RAW icon hash from the API (the backend no longer
 * pre-builds CDN urls). Animated icons (a_ prefix) load as .gif; any
 * load error (404, CDN hiccup, offline) gracefully swaps to the
 * initials tile instead of a broken-image alt text.
 */

import { useState } from 'react';
import { guildIconUrl } from '@/lib/discord';
import { initials, cn } from '@/lib/format';

export function GuildIcon({
  id,
  name,
  icon,
  size = 40,
  className,
}: {
  id: string;
  name: string;
  icon: string | null;
  size?: number;
  className?: string;
}) {
  const [failed, setFailed] = useState(false);
  const raw = icon && !icon.startsWith('http') ? icon : null;
  const url = raw ? guildIconUrl(id, raw, 128) : icon?.startsWith('http') ? icon : null;

  if (url && !failed) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={url}
        alt={`${name} server icon`}
        width={size}
        height={size}
        onError={() => setFailed(true)}
        className={cn('rounded-[12px] object-cover', className)}
      />
    );
  }
  return (
    <div
      aria-label={`${name} server icon`}
      style={{ width: size, height: size, fontSize: size * 0.36 }}
      className={cn(
        'flex items-center justify-center rounded-[12px] bg-veloura-card font-heading font-semibold text-veloura-lavender',
        className,
      )}
    >
      {initials(name) || '✦'}
    </div>
  );
}
