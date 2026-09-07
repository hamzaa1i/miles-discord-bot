'use client';

/**
 * lib/useHashTab.ts — tab state synced to the URL fragment.
 *
 * The sidebar links to pages as `route#tab` (e.g. roles#onboarding,
 * moderation#warnings). This hook makes those links work:
 *  - initial tab = the #fragment on first load (deep links open the
 *    right tab directly),
 *  - switching tabs rewrites the fragment (so the sidebar highlight
 *    follows the active tab),
 *  - hashchange events (sidebar clicks on the same page) switch tabs
 *    without a reload.
 */

import { useEffect, useState } from 'react';

export function useHashTab(validTabs: string[], fallback: string) {
  const [tab, setTab] = useState(() => {
    if (typeof window === 'undefined') return fallback;
    const h = window.location.hash.replace(/^#/, '');
    return validTabs.includes(h) ? h : fallback;
  });

  useEffect(() => {
    const onHash = () => {
      const h = window.location.hash.replace(/^#/, '');
      if (h && validTabs.includes(h)) setTab(h);
      else if (!h) setTab(fallback);
    };
    window.addEventListener('hashchange', onHash);
    return () => window.removeEventListener('hashchange', onHash);
  }, [validTabs.join(','), fallback]); // eslint-disable-line react-hooks/exhaustive-deps

  const select = (next: string) => {
    setTab(next);
    const base = window.location.pathname + window.location.search;
    window.history.replaceState(null, '', validTabs.includes(next) ? `${base}#${next}` : base);
  };

  return [tab, select] as const;
}
