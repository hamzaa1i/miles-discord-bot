'use client';

/**
 * components/site/ShareButtons.tsx — PHASE M PART 10.
 *
 * Share row used on public pages (landing, docs, changelog):
 *   · copy link (with a pre-written share message when `shareText`
 *     is provided — paste-ready for discord)
 *   · share on twitter/x
 *   · share on reddit
 *   · qr code for mobile (rendered client-side with the `qrcode`
 *     package — no third-party api, the url never leaves the page)
 *
 * All buttons carry aria-labels; the QR toggle is keyboard accessible.
 */

import { useEffect, useRef, useState } from 'react';
import { Icon } from '@/components/icons';
import { cn } from '@/lib/format';
import {
  SHARE_MESSAGE,
  SHARE_MESSAGE_SHORT,
  redditShareUrl,
  twitterShareUrl,
} from '@/lib/marketing';

type Props = {
  /** the url being shared (defaults to the current page) */
  url?: string;
  /** page-specific share text; defaults to the pre-written message */
  text?: string;
  title?: string;
  className?: string;
  /** hide the compact "share ✦" label */
  compact?: boolean;
};

export function ShareButtons({
  url,
  text,
  title = 'aurelia — the soft, elegant discord bot',
  className,
  compact = false,
}: Props) {
  const [pageUrl, setPageUrl] = useState(url ?? '');
  const [copied, setCopied] = useState(false);
  const [qrOpen, setQrOpen] = useState(false);
  const [qrData, setQrData] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!url && typeof window !== 'undefined') {
      setPageUrl(window.location.origin + window.location.pathname);
    }
  }, [url]);

  useEffect(() => () => {
    if (timer.current) clearTimeout(timer.current);
  }, []);

  const shareText = text ?? SHARE_MESSAGE;

  async function copyLink() {
    const payload = `${shareText} ${pageUrl}`;
    try {
      await navigator.clipboard.writeText(payload);
    } catch {
      // http / older browsers — fall back to the url alone
      try {
        await navigator.clipboard.writeText(pageUrl);
      } catch {
        return;
      }
    }
    setCopied(true);
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => setCopied(false), 2200);
  }

  async function toggleQr() {
    if (qrOpen) {
      setQrOpen(false);
      return;
    }
    if (!qrData) {
      const QR = (await import('qrcode')).default;
      setQrData(
        await QR.toDataURL(pageUrl, {
          width: 240,
          margin: 2,
          color: { dark: '#1A1D29', light: '#FFC0CB' },
          errorCorrectionLevel: 'M',
        }),
      );
    }
    setQrOpen(true);
  }

  if (!pageUrl) {
    return <div className={cn('h-9', className)} aria-hidden />;
  }

  return (
    <div className={cn('flex flex-wrap items-center gap-2', className)}>
      {!compact && (
        <span className="mr-1 text-xs uppercase tracking-wider text-veloura-muted/70">
          share
        </span>
      )}

      <button
        type="button"
        onClick={copyLink}
        aria-label={`copy share link: ${shareText}`}
        className="veloura-button-ghost px-3 py-1.5 text-xs"
      >
        <Icon name={copied ? 'check' : 'key'} size={13} />
        {copied ? 'copied ♡' : 'copy link'}
      </button>

      <a
        href={twitterShareUrl(pageUrl, shareText)}
        target="_blank"
        rel="noopener noreferrer"
        aria-label="share aurelia on twitter/x (opens in a new tab)"
        className="veloura-button-ghost px-3 py-1.5 text-xs"
      >
        twitter
      </a>

      <a
        href={redditShareUrl(pageUrl, title)}
        target="_blank"
        rel="noopener noreferrer"
        aria-label="share aurelia on reddit (opens in a new tab)"
        className="veloura-button-ghost px-3 py-1.5 text-xs"
      >
        reddit
      </a>

      <button
        type="button"
        onClick={toggleQr}
        aria-expanded={qrOpen}
        aria-label="show qr code for this page (scan on mobile)"
        className="veloura-button-ghost px-3 py-1.5 text-xs"
      >
        <Icon name="zap" size={13} />
        qr
      </button>

      {qrOpen && qrData && (
        <div className="veloura-card mt-2 w-fit p-3" role="dialog" aria-label="qr code">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={qrData}
            alt={`qr code linking to ${pageUrl}`}
            width={240}
            height={240}
            className="rounded-[8px]"
          />
          <p className="mt-2 max-w-[240px] break-all text-center text-[11px] leading-relaxed text-veloura-muted">
            scan to open on mobile ✧
          </p>
        </div>
      )}
    </div>
  );
}
