/**
 * components/site/FeatureShowcase.tsx — PHASE M PART 1 §3.
 *
 * Six feature sections, each: icon + one-line tag + description + a
 * lightweight CSS "preview". The previews are hand-built in the veloura
 * palette (chat bubbles, a welcome embed, a case card, a browser
 * frame) — they ship zero image bytes, need no lazy-loading, and can
 * later be swapped for real screenshots by replacing the mock node.
 */

import { Icon, IconName } from '@/components/icons';
import { cn } from '@/lib/format';

interface Feature {
  icon: IconName | string;
  title: string;
  tag: string;
  desc: string;
  bullets: string[];
  preview: 'chat' | 'welcome' | 'mod' | 'community' | 'dashboard' | 'privacy';
}

const FEATURES: Feature[] = [
  {
    icon: 'moon',
    title: 'ai chat & memory',
    tag: 'she remembers you',
    desc: 'talk to aurelia with @aurelia or /aurelia — she keeps the thread of your conversation and quietly learns the things worth remembering. every server can tune her personality.',
    bullets: [
      'persistent conversation memory',
      'automatic fact extraction',
      'natural-language commands ("@aurelia warn @user spam")',
      'per-server personality',
    ],
    preview: 'chat',
  },
  {
    icon: 'heart',
    title: 'aesthetic welcome cards',
    tag: 'greet every soul',
    desc: 'soft embed cards with custom colors, images and template variables — welcome, goodbye and DM modes, all previewable live before you save.',
    bullets: [
      'embed · text · hybrid · dm modes',
      '13 configurable settings',
      'live preview in the dashboard',
      'goodbye messages included',
    ],
    preview: 'welcome',
  },
  {
    icon: 'shield',
    title: 'smart moderation',
    tag: 'gentle but firm',
    desc: 'warnings with escalating thresholds, ai automod that reads context before acting, and a full audit trail — firm where it matters, soft everywhere else.',
    bullets: [
      'warnings → timeout → kick → ban ladders',
      'ai automod with severity levels',
      'searchable case history',
      'mod + server event logging',
    ],
    preview: 'mod',
  },
  {
    icon: 'sparkles',
    title: 'community engagement',
    tag: 'keep the vibes alive',
    desc: 'leveling with role rewards, daily streaks, the question of the day, giveaways with realtime entry counts, starboard, achievements — the whole engagement toolkit.',
    bullets: [
      'xp + levels + role rewards',
      'daily rewards with streak bonuses',
      'qotd with answer threads',
      'giveaways · starboard · achievements',
    ],
    preview: 'community',
  },
  {
    icon: 'settings',
    title: 'beautiful dashboard',
    tag: 'manage everything visually',
    desc: '34 module pages wrapped in veloura — live welcome previews, channel pickers straight from discord, one-click actions and a full audit log. no slash command archaeology.',
    bullets: [
      'live discord channel & role pickers',
      'test actions ("post qotd now")',
      'realtime giveaway entries',
      'full audit trail',
    ],
    preview: 'dashboard',
  },
  {
    icon: 'lock',
    title: 'privacy first',
    tag: "you're in control",
    desc: 'opt out of any ai feature per-user, export everything as json, or erase all your data everywhere with one double-confirmed command. your server, your rules.',
    bullets: [
      '/privacy set — per-feature opt-outs',
      '/privacy export — full json download',
      '/privacy delete — erase everything',
      'minimal data by design',
    ],
    preview: 'privacy',
  },
];

/* ── CSS mock previews (zero image bytes) ─────────────────────────── */

function ChatPreview() {
  return (
    <div className="space-y-2.5" aria-hidden>
      <div className="flex justify-end">
        <p className="max-w-[80%] rounded-[14px] rounded-br-[4px] bg-veloura-pink/15 px-3.5 py-2 text-xs leading-relaxed text-veloura-text">
          aurelia, remember that i love lavender?
        </p>
      </div>
      <div className="flex items-end gap-2">
        <div className="h-6 w-6 shrink-0 rounded-full bg-veloura-lavender/25" />
        <p className="max-w-[80%] rounded-[14px] rounded-bl-[4px] bg-veloura-card-hover px-3.5 py-2 text-xs leading-relaxed text-veloura-text">
          noted forever ♡ i already knew — you mention it when the server
          gets quiet ✦
        </p>
      </div>
      <div className="flex items-end gap-2">
        <div className="h-6 w-6 shrink-0 rounded-full bg-veloura-lavender/25" />
        <p className="max-w-[80%] rounded-[14px] rounded-bl-[4px] bg-veloura-card-hover px-3.5 py-2 text-xs leading-relaxed text-veloura-text">
          <span className="text-veloura-pink">memory updated</span>{' '}
          <span className="text-veloura-muted/60">— 3 facts kept about you</span>
        </p>
      </div>
    </div>
  );
}

function WelcomePreview() {
  return (
    <div className="veloura-card overflow-hidden !p-0" aria-hidden>
      <div className="h-1.5 w-full bg-gradient-to-r from-veloura-pink via-veloura-lavender to-veloura-pink" />
      <div className="space-y-2.5 p-4">
        <p className="font-heading text-sm text-veloura-pink">
          ♡ welcome to veloura lounge
        </p>
        <p className="text-xs leading-relaxed text-veloura-muted">
          <span className="text-veloura-text">miyu</span> drifted in — member
          #128 ✧ may the stars be kind
        </p>
        <div className="flex items-center gap-2 pt-0.5 text-[10px] text-veloura-muted/60">
          <span className="rounded-full bg-veloura-pink/10 px-2 py-0.5">embed mode</span>
          <span className="rounded-full bg-veloura-lavender/10 px-2 py-0.5">#FFC0CB</span>
          <span>live preview</span>
        </div>
      </div>
    </div>
  );
}

function ModPreview() {
  return (
    <div className="space-y-2.5" aria-hidden>
      <div className="veloura-card flex items-start gap-3 p-3.5">
        <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-[10px] bg-veloura-danger/15 text-veloura-danger">
          <Icon name="shieldAlert" size={15} />
        </span>
        <div className="min-w-0">
          <p className="text-xs font-medium text-veloura-text">
            case #7 · warning
          </p>
          <p className="mt-0.5 truncate text-[11px] text-veloura-muted">
            reason: spam in #general · 2/3 warnings before timeout
          </p>
        </div>
      </div>
      <div className="veloura-card flex items-start gap-3 p-3.5">
        <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-[10px] bg-veloura-lavender/15 text-veloura-lavender">
          <Icon name="bot" size={15} />
        </span>
        <div className="min-w-0">
          <p className="text-xs font-medium text-veloura-text">
            ai automod · severity 2/5
          </p>
          <p className="mt-0.5 text-[11px] text-veloura-muted">
            soft nudge sent · no timeout — it was just caps lock ✧
          </p>
        </div>
      </div>
    </div>
  );
}

function CommunityPreview() {
  return (
    <div className="space-y-2.5" aria-hidden>
      <div className="veloura-card p-3.5">
        <p className="text-[10px] uppercase tracking-wider text-veloura-muted/70">
          question of the day
        </p>
        <p className="mt-1 text-xs leading-relaxed text-veloura-text">
          if your server had a smell, what would it be? 🌙
        </p>
        <p className="mt-2 text-[10px] text-veloura-pink">thread: 41 replies</p>
      </div>
      <div className="veloura-card flex items-center justify-between gap-3 p-3.5">
        <div>
          <p className="text-xs font-medium text-veloura-text">level 12 ♡</p>
          <p className="mt-0.5 text-[10px] text-veloura-muted">+45 xp · 2140 total</p>
        </div>
        <span className="rounded-full bg-veloura-pink/15 px-2.5 py-1 text-[10px] text-veloura-pink">
          streak 14 days
        </span>
      </div>
    </div>
  );
}

function DashboardPreview() {
  return (
    <div className="veloura-card overflow-hidden !p-0" aria-hidden>
      {/* browser chrome */}
      <div className="flex items-center gap-1.5 border-b border-veloura-border/60 bg-veloura-navy-deep/60 px-3 py-2">
        <span className="h-2 w-2 rounded-full bg-veloura-danger/60" />
        <span className="h-2 w-2 rounded-full bg-veloura-lavender/50" />
        <span className="h-2 w-2 rounded-full bg-veloura-success/60" />
        <span className="ml-2 truncate rounded-full bg-veloura-card-hover px-2.5 py-0.5 text-[10px] text-veloura-muted/70">
          veloura-aurelia.vercel.app/servers
        </span>
      </div>
      <div className="flex">
        {/* mini sidebar */}
        <div className="w-16 space-y-1.5 border-r border-veloura-border/60 p-2.5 sm:w-20">
          {[0, 1, 2, 3, 4, 5].map((i) => (
            <div
              key={i}
              className={cn(
                'h-4 rounded-[6px]',
                i === 1 ? 'bg-veloura-pink/30' : 'bg-veloura-card-hover',
              )}
            />
          ))}
        </div>
        {/* mini content */}
        <div className="flex-1 space-y-2 p-3">
          <div className="h-5 w-1/2 rounded-[8px] bg-veloura-card-hover" />
          <div className="grid grid-cols-2 gap-2">
            {[0, 1, 2, 3].map((i) => (
              <div key={i} className="h-10 rounded-[10px] bg-veloura-card-hover/70" />
            ))}
          </div>
          <div className="h-12 rounded-[10px] bg-gradient-to-r from-veloura-pink/10 to-veloura-lavender/10" />
        </div>
      </div>
    </div>
  );
}

function PrivacyPreview() {
  const cmds = [
    '/privacy show',
    '/privacy set memory off',
    '/privacy export',
    '/privacy delete',
  ];
  return (
    <div className="space-y-2.5" aria-hidden>
      {cmds.map((c, i) => (
        <div
          key={c}
          className={cn(
            'flex items-center gap-2.5 rounded-[12px] border px-3.5 py-2.5 text-xs',
            i === 3
              ? 'border-veloura-danger/30 text-veloura-danger'
              : 'border-veloura-border text-veloura-text',
          )}
        >
          <Icon name={i === 3 ? 'trash2' : 'check'} size={13} />
          <span className="font-mono">{c}</span>
        </div>
      ))}
      <p className="text-[10px] text-veloura-muted/60">
        double confirmation before anything is erased ♡
      </p>
    </div>
  );
}

const PREVIEWS: Record<Feature['preview'], () => JSX.Element> = {
  chat: ChatPreview,
  welcome: WelcomePreview,
  mod: ModPreview,
  community: CommunityPreview,
  dashboard: DashboardPreview,
  privacy: PrivacyPreview,
};

/* ── section ──────────────────────────────────────────────────────── */

export function FeatureShowcase() {
  return (
    <section id="features" aria-label="feature showcase" className="scroll-mt-20">
      <div className="mx-auto max-w-6xl px-6">
        <header className="mb-12 text-center">
          <p className="text-xs uppercase tracking-[0.2em] text-veloura-pink">
            what she does
          </p>
          <h2 className="font-heading mt-2 text-3xl text-veloura-text sm:text-4xl">
            everything your server needs, softly
          </h2>
        </header>

        <div className="space-y-16">
          {FEATURES.map((f, i) => {
            const Preview = PREVIEWS[f.preview];
            const flip = i % 2 === 1;
            return (
              <article
                key={f.title}
                className={cn(
                  'grid items-center gap-8 lg:grid-cols-2 lg:gap-14',
                )}
              >
                <div className={cn(flip && 'lg:order-2')}>
                  <div className="flex items-center gap-3">
                    <span className="flex h-10 w-10 items-center justify-center rounded-[12px] bg-veloura-pink/10 text-veloura-pink">
                      <Icon name={f.icon} size={19} />
                    </span>
                    <h3 className="font-heading text-2xl text-veloura-text">
                      {f.title}
                    </h3>
                  </div>
                  <p className="mt-1.5 text-sm font-medium text-veloura-lavender">
                    “{f.tag}”
                  </p>
                  <p className="mt-3 text-sm leading-relaxed text-veloura-muted">
                    {f.desc}
                  </p>
                  <ul className="mt-4 grid gap-2 sm:grid-cols-2">
                    {f.bullets.map((b) => (
                      <li key={b} className="flex items-start gap-2 text-xs text-veloura-muted">
                        <span className="mt-1 text-veloura-pink" aria-hidden>✦</span>
                        {b}
                      </li>
                    ))}
                  </ul>
                </div>
                <div className={cn('mx-auto w-full max-w-md', flip && 'lg:order-1')}>
                  <Preview />
                </div>
              </article>
            );
          })}
        </div>
      </div>
    </section>
  );
}
