'use client';

/**
 * EmbedPreview — renders a message + embed exactly like Discord will:
 * text / embed / hybrid modes, configured color bar, title, footer,
 * thumbnail, image and template variables substituted.
 */

import { useMemo } from 'react';
import type { Settings } from '@/lib/types';
import { cn } from '@/lib/format';

interface PreviewCtx {
  username: string;
  serverName: string;
  membercount: number;
  avatar: string;
}

function substitute(template: string, ctx: PreviewCtx): string {
  return String(template ?? '')
    .replaceAll('{user}', `@${ctx.username}`)
    .replaceAll('{user.name}', ctx.username)
    .replaceAll('{user.id}', '123456789012345678')
    .replaceAll('{user.avatar}', ctx.avatar)
    .replaceAll('{server}', ctx.serverName)
    .replaceAll('{server.id}', '111222333444555666')
    .replaceAll('{server.icon}', ctx.avatar)
    .replaceAll('{membercount}', String(ctx.membercount))
    .replaceAll('\\n', '\n');
}

export function EmbedPreview({
  settings,
  ctx,
  isGoodbye = false,
}: {
  settings: Settings;
  ctx: PreviewCtx;
  isGoodbye?: boolean;
}) {
  const mode = (settings.embed_mode as string) || 'embed';
  const rawMessage = String(
    (isGoodbye ? settings.goodbye_message : settings.message) ?? '',
  );
  const text = useMemo(() => substitute(rawMessage, ctx), [rawMessage, ctx]);
  const color = normalizeColor(String(settings.welcome_color ?? '#FFC0CB'));
  const title = substitute(String(settings.welcome_title ?? ''), ctx);
  const footer = substitute(String(settings.welcome_footer ?? ''), ctx);
  const image = String(settings.welcome_image ?? '') || null;
  const thumbnailMode = String(settings.welcome_thumbnail ?? 'avatar');
  const body = text.replaceAll('---', '· · ·');

  return (
    <div className="rounded-[12px] bg-[#313338] p-4 font-body">
      <p className="mb-1 flex items-center gap-2 text-xs font-semibold text-lavender-900">
        <span className="text-[#949BA4]">live preview</span>
        <span aria-hidden className="text-[#949BA4]">✦</span>
        <span className="text-[#949BA4] font-normal">
          {isGoodbye ? 'goodbye' : 'welcome'} · {mode} mode
        </span>
      </p>

      {/* the fake message */}
      <div className="mt-2 flex gap-3">
        <img
          src={ctx.avatar}
          alt=""
          width={40}
          height={40}
          className="mt-0.5 h-10 w-10 rounded-full"
        />
        <div className="min-w-0 flex-1">
          <p className="flex items-baseline gap-2">
            <span className="font-medium text-[#F2F3F5]">{isGoodbye ? 'aurelia' : 'aurelia'}</span>
            <span className="rounded bg-[#5865F2] px-1 py-px text-[10px] font-semibold text-white">
              BOT
            </span>
            <span className="text-[11px] text-[#949BA4]">today at 4:20 PM</span>
          </p>

          {mode !== 'embed' && (
            <p className="mt-0.5 whitespace-pre-wrap break-words text-[15px] leading-[1.375rem] text-[#DBDEE1]">
              {body || <span className="italic text-[#949BA4]">no message set…</span>}
            </p>
          )}

          {mode !== 'text' && (
            <div
              className="mt-1.5 max-w-[440px] overflow-hidden rounded-[4px]"
              style={{ background: '#2B2D31', borderLeft: `4px solid ${color}` }}
            >
              <div className="flex gap-4 p-3">
                <div className="min-w-0 flex-1">
                  {title && (
                    <p className="mb-1.5 font-medium leading-5 text-[#F2F3F5]">{title}</p>
                  )}
                  {mode === 'hybrid' ? (
                    <p className="whitespace-pre-wrap break-words text-sm leading-[1.125rem] text-[#DBDEE1]">
                      {body}
                    </p>
                  ) : (
                    <p className="whitespace-pre-wrap break-words text-sm leading-[1.125rem] text-[#DBDEE1]">
                      {body || <span className="italic text-[#949BA4]">no message set…</span>}
                    </p>
                  )}
                  {image && (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={image} alt="welcome banner" className="mt-3 max-h-56 w-full rounded-[4px] object-cover" />
                  )}
                  {footer && (
                    <p className="mt-2 flex items-center gap-1.5 text-xs text-[#949BA4]">
                      {thumbnailMode !== 'none' && (
                        <img src={ctx.avatar} alt="" width={18} height={18} className="h-[18px] w-[18px] rounded-full" />
                      )}
                      {footer}
                    </p>
                  )}
                </div>
                {thumbnailMode === 'avatar' && (
                  <img src={ctx.avatar} alt="" width={64} height={64} className="h-16 w-16 shrink-0 rounded-[4px]" />
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function normalizeColor(raw: string): string {
  const m = /^#?([0-9a-fA-F]{6})$/.exec(raw.trim());
  return m ? `#${m[1]}` : '#FFC0CB';
}
