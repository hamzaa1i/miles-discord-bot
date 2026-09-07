'use client';

/** GuildIcon — avatar with veloura initial fallback. */

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
  const url = guildIconUrl(id, icon, 128);
  if (url) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={url}
        alt={`${name} server icon`}
        width={size}
        height={size}
        className={cn('rounded-[12px] object-cover', className)}
      />
    );
  }
  return (
    <div
      aria-label={`${name} — no icon`}
      style={{ width: size, height: size, fontSize: size * 0.36 }}
      className={cn(
        'flex items-center justify-center rounded-[12px] bg-veloura-card font-heading font-semibold text-veloura-lavender',
        className,
      )}
    >
      {initials(name)}
    </div>
  );
}
