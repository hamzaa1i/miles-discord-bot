'use client';

/**
 * components/site/AuthAwareCta.tsx — PHASE N (19.2).
 *
 * The landing hero's secondary call-to-action. Logged-out visitors see
 * "login to dashboard"; signed-in visitors see "open dashboard" pointing
 * straight at /servers. The primary "add to discord" CTA stays for
 * everyone (the spec keeps it).
 *
 * Uses the AuthProvider session (httpOnly-cookie backed) — no tokens
 * are exposed to client JS.
 */

import Link from 'next/link';
import { Icon } from '@/components/icons';
import { useAuth } from '@/lib/auth';

export function AuthAwareCta() {
  const { user, loading } = useAuth();

  if (loading) {
    // placeholder with the same footprint — no layout shift, no flash
    return (
      <span className="veloura-button-ghost px-8 text-base opacity-70">
        <Icon name="settings" size={16} />
        ✦
      </span>
    );
  }

  if (user) {
    return (
      <Link href="/servers" className="veloura-button-ghost px-8 text-base">
        <Icon name="settings" size={16} />
        open dashboard
      </Link>
    );
  }

  return (
    <Link href="/login" className="veloura-button-ghost px-8 text-base">
      <Icon name="settings" size={16} />
      login to dashboard
    </Link>
  );
}
