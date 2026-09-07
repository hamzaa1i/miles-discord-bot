import type { MetadataRoute } from 'next';

/**
 * app/manifest.ts — PHASE M PART 9.
 *
 * PWA manifest: installable on mobile, veloura-styled (navy bg, pink
 * accents). Icons reuse the existing public/ assets.
 */

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: 'aurelia — the soft, elegant discord bot',
    short_name: 'aurelia',
    description:
      'ai chat, aesthetic moderation, community engagement. free forever. built with love.',
    start_url: '/',
    display: 'standalone',
    background_color: '#1A1D29',
    theme_color: '#1A1D29',
    icons: [
      {
        src: '/aurelia-logo.png',
        sizes: '512x512',
        type: 'image/png',
        purpose: 'any',
      },
      {
        src: '/aurelia-logo.svg',
        sizes: 'any',
        type: 'image/svg+xml',
        purpose: 'any',
      },
    ],
  };
}
