/**
 * lib/docs-modules.ts — PHASE M PART 2 — per-module deep dives.
 *
 * One curated entry per dashboard module route (the /docs/modules/[slug]
 * pages). Each entry: what it is, why you'd want it, the slash commands
 * that drive it, and where it lives in the dashboard. Written to read
 * like Mimu/Dyno module docs, in the veloura voice.
 *
 * NOTE: keep in sync with dashboard/lib/modules.ts (the sidebar registry
 * is the source of truth for routes; this file only documents them).
 */

export interface ModuleDoc {
  slug: string;
  title: string;
  tagline: string;
  description: string;
  commands: string[];
  notes?: string[];
}

export const MODULE_DOCS: ModuleDoc[] = [
  {
    slug: 'welcome',
    title: 'welcome & goodbye',
    tagline: 'greet every soul that drifts in',
    description:
      'aesthetic embed cards (or plain text, or both) whenever someone joins or leaves. supports custom colors, images, 13 settings and template variables like {user}, {server} and {membercount}. the dashboard shows a live preview so you see the card before anyone else does.',
    commands: ['/welcome config', '/welcome test', '/welcome show', '/welcome tags', '/welcome reset'],
    notes: [
      'hybrid mode posts a compact text line AND the embed — great for ping visibility.',
      'test with /welcome test before enabling to avoid surprising your members.',
    ],
  },
  {
    slug: 'leveling',
    title: 'leveling',
    tagline: 'xp, levels & role rewards',
    description:
      'members earn xp by chatting (with anti-spam pacing), climb levels and unlock role rewards. tune the xp rate, the level-up channel and custom level-up messages from the dashboard; rewards are managed on the dedicated level rewards page.',
    commands: ['/level', '/leaderboard', '/rewards', '/leveling config'],
    notes: ['xp is per-server and respects anti-farm cooldowns.', 'pair with the achievements module for badges.'],
  },
  {
    slug: 'level-rewards',
    title: 'level rewards',
    tagline: 'roles earned at a level',
    description:
      'the reward ladder for the leveling system — pick a level, pick a role, and aurelia hands it out automatically when someone reaches it. the dashboard lists the whole ladder with live role pickers straight from your server.',
    commands: ['/rewards', '/leveling config'],
    notes: ['rewards apply retroactively on the next message after a change.'],
  },
  {
    slug: 'qotd',
    title: 'qotd',
    tagline: 'a question every day',
    description:
      'the question of the day: one curated question posted to your channel each day (default 14:00 utc), optionally opening a public thread for answers. add your own questions to the queue or lean on the built-in pool of 40.',
    commands: ['/qotd config', '/qotd add', '/qotd list', '/qotd toggle', '/qotd post', '/qotd show'],
    notes: ['the queue is consumed before the fallback pool — curate freely.'],
  },
  {
    slug: 'automod',
    title: 'ai automod',
    tagline: 'the watchful gaze',
    description:
      'context-aware moderation: aurelia reads messages that look risky and scores severity 1-5. low severities get soft nudges, high severities escalate to timeouts. alerts land in a channel you choose, so your team stays in the loop.',
    commands: ['/aiautomod toggle', '/aiautomod channel', '/aiautomod timeout', '/aiautomod status'],
    notes: ['classic automod (antispam/antilink) lives under /mod antispam and /mod antilink.'],
  },
  {
    slug: 'warnings',
    title: 'warnings',
    tagline: 'the case history, searchable',
    description:
      'every warning is a numbered case with reason, moderator and timestamp. thresholds escalate automatically (timeout → kick → ban — configurable), and the dashboard lets you search, filter and clear the whole history.',
    commands: ['/mod warnings', '/mod config', '/mod unban'],
    notes: ['clearing warnings for a user resets their escalation position.'],
  },
  {
    slug: 'logging',
    title: 'logging',
    tagline: 'server event log',
    description:
      'a quiet channel where aurelia notes message deletions, edits, joins, leaves, bans, role changes, nickname changes and voice movement. toggle each event family individually — keep the signal, drop the noise.',
    commands: ['/log setup', '/log toggle', '/log show', '/log disable'],
  },
  {
    slug: 'ai',
    title: 'chat, memory & vibe',
    tagline: "aurelia's mind",
    description:
      'the ai module: @aurelia conversation with persistent memory, per-server personality, and optional proactive chatter where she joins conversations on her own in watched channels. vibe checks (/vibe) read the room, /recap summarizes what you missed.',
    commands: ['/aurelia', '/memory show', '/memory clear', '/proactive toggle', '/proactive channel', '/vibe', '/recap'],
    notes: ['users can opt out of any ai feature with /privacy set.'],
  },
  {
    slug: 'vibe',
    title: 'vibe & fortune',
    tagline: 'channel moods, daily cards, small decisions',
    description:
      'the soft side of the ai: /vibe reads the last few hours of a channel and describes the mood, daily fortune cards, and /pick when the server can\'t decide between two things.',
    commands: ['/vibe', '/fortune', '/pick'],
  },
  {
    slug: 'recap',
    title: 'recap',
    tagline: 'what did i miss?',
    description:
      'an ai digest of a channel\'s recent history — who said what, which threads took off, links worth opening. perfect after a busy day or a slow weekend.',
    commands: ['/recap [channel] [hours]'],
  },
  {
    slug: 'onboarding',
    title: 'onboarding',
    tagline: 'a soft first message with role buttons',
    description:
      'new members get a friendly DM with role buttons, so they self-select into the right corners of your server before their first message. fully configurable message text and role set.',
    commands: ['/onboarding toggle', '/onboarding addrole', '/onboarding removerole', '/onboarding message', '/onboarding test'],
  },
  {
    slug: 'anniversary',
    title: 'anniversaries',
    tagline: 'celebrate the stayers',
    description:
      'a celebration card on join-day milestones — 30 days, 6 months, 1 year and every full year after. one scan per day, restart-safe, no double celebrations.',
    commands: ['/anniversary config', '/anniversary show'],
  },
  {
    slug: 'nick',
    title: 'nickname requests',
    tagline: 'gentle name changes',
    description:
      'members request nickname changes and your staff approve or reject them from discord or the dashboard. cooldown and auto-approve options included — no more @everyone ping floods.',
    commands: ['/nick config', '/nick request', '/nick pending', '/nick my'],
  },
  {
    slug: 'autorole',
    title: 'autorole',
    tagline: 'the role given on join',
    description:
      'one role, handed to every new member the moment they join. pairs naturally with onboarding and the rules agreement role.',
    commands: ['/autorole set', '/autorole remove', '/autorole show'],
  },
  {
    slug: 'self-roles',
    title: 'self-roles',
    tagline: 'members pick their own roles',
    description:
      'button panels where members grant or remove roles themselves — pronouns, interests, pings. panels are created in discord with /selfroles setup and managed from there.',
    commands: ['/selfroles setup'],
    notes: ['self-roles are managed in discord, not the dashboard — the panel buttons are the interface.'],
  },
  {
    slug: 'color-roles',
    title: 'color roles',
    tagline: 'personal colors from /color set',
    description:
      'members set their own name color with /color set — a personal role, created and positioned automatically. 24-hour cooldown keeps the role list from churning.',
    commands: ['/color set', '/color remove', '/color show'],
  },
  {
    slug: 'achievements',
    title: 'achievements',
    tagline: 'badges & leaderboard',
    description:
      'earned badges for milestones — first words, streaks, ships, confessions and more. locked ones show as ??? until unlocked; a global leaderboard tracks who collects them all.',
    commands: ['/achievements show', '/achievements list'],
  },
  {
    slug: 'confessions',
    title: 'confessions',
    tagline: 'anonymous whispers',
    description:
      'members submit confessions via /confess and aurelia posts them anonymously to the channel you choose. the submission identity is never revealed — not even in logs.',
    commands: ['/confess text', '/confess setup'],
    notes: ['privacy by design: user ids are stripped before posting and logging.'],
  },
  {
    slug: 'polls',
    title: 'polls',
    tagline: 'reaction polls with /poll',
    description:
      'quick reaction polls: up to four options, optional duration, results tallied when the poll ends. the dashboard shows your server\'s active and past polls live.',
    commands: ['/poll create', '/poll end'],
  },
  {
    slug: 'giveaways',
    title: 'giveaways',
    tagline: 'gifts from the void',
    description:
      'start a giveaway, watch entries arrive in realtime on the dashboard, end early or reroll winners when someone turns out to be a bot. winners are drawn with a fair shuffle.',
    commands: ['/giveaway start', '/giveaway end', '/giveaway reroll', '/giveaway list'],
  },
  {
    slug: 'starboard',
    title: 'starboard',
    tagline: 'preserve the best moments',
    description:
      'messages that earn enough reactions (emoji configurable — ⭐ by default) get immortalized on the starboard channel with a link back to the original.',
    commands: ['/starboard channel', '/starboard threshold', '/starboard emoji', '/starboard toggle'],
  },
  {
    slug: 'custom-commands',
    title: 'custom commands',
    tagline: 'your own little spells',
    description:
      'short triggers with canned responses — rules, links, memes, whatever your server types a hundred times a week. managed from discord or the dashboard with a live editor.',
    commands: ['/custom add', '/custom remove', '/custom list'],
  },
  {
    slug: 'fun',
    title: 'fun & games',
    tagline: 'vibe checks, fortunes and time capsules',
    description:
      'the toybox: dice, coins, jokes, memes, truth or dare, ships, and time capsules — messages that unlock days or weeks later.',
    commands: ['/roll', '/flip', '/joke', '/meme', '/ship match', '/capsule create'],
  },
  {
    slug: 'reminders',
    title: 'reminders',
    tagline: 'your own /remind list — view & cancel',
    description:
      'personal reminders that follow you across servers, created by asking aurelia naturally ("@aurelia remind me in 10m to check the oven") or with /remind. the dashboard lists and cancels them.',
    commands: ['/remind create', '/remind list', '/remind delete', '/reminders'],
    notes: ['recurring reminders (daily/weekly/monthly) re-arm automatically.'],
  },
  {
    slug: 'birthdays',
    title: 'birthdays',
    tagline: 'cakes on the right day',
    description:
      'members set their birthday once and get celebrated every year — the dashboard shows whose cake day is next.',
    commands: ['/birthday set', '/birthday upcoming'],
  },
  {
    slug: 'bump-reminder',
    title: 'bump reminder',
    tagline: 'keep the server afloat',
    description:
      'aurelia notices your disboard bumps and nudges the channel exactly when the next one is ready — two hours, every two hours.',
    commands: ['/bump remind'],
  },
  {
    slug: 'rules',
    title: 'rules',
    tagline: 'rules & agreement role',
    description:
      'your server rules in a /rules command with an agree button — agreeing members get the agreement role automatically. commonly paired with gated channels.',
    commands: ['/rules set', '/rules show', '/rules agree', '/rules agree_role'],
  },
  {
    slug: 'prefix',
    title: 'prefix',
    tagline: 'the legacy prefix command',
    description:
      'for the old souls: a custom prefix for text commands (a! by default). slash commands remain the main interface; the prefix is a comfort feature.',
    commands: ['/prefix set', '/prefix list', '/prefix remove'],
  },
  {
    slug: 'privacy',
    title: 'privacy',
    tagline: 'data controls and opt-outs',
    description:
      'per-user controls: view your opt-outs, disable any ai feature (memory, vibe, recap, ship, facts), export everything as json, or erase your data everywhere with double confirmation.',
    commands: ['/privacy show', '/privacy set', '/privacy export', '/privacy delete'],
    notes: ['aurelia is privacy-first: minimal data by design, no third-party analytics.'],
  },
  {
    slug: 'danger',
    title: 'danger zone',
    tagline: 'careful destructive actions & audit',
    description:
      'the red buttons: reset a module to defaults, purge data. everything is double-confirmed and recorded in the audit log, and the audit tab shows every dashboard action with who/when/what.',
    commands: ['/owner reload', '/owner sync'],
  },
  {
    slug: 'stats',
    title: 'statistics',
    tagline: 'the shape of your server',
    description:
      'commands per day, top commands, active users and leaderboard — the dashboard charts render from real usage data with a 7-day window.',
    commands: ['/owner status'],
  },
];

/** find one module doc by slug. */
export function moduleDoc(slug: string): ModuleDoc | undefined {
  return MODULE_DOCS.find((m) => m.slug === slug);
}
