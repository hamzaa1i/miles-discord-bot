'use client';

/**
 * components/icons.tsx — central Lucide icon registry.
 *
 * UI chrome (sidebar, module headers, buttons, statuses) uses these
 * professional SVG icons instead of emoji. Brand personality stays in
 * prose text ("welcome ♡", "settings saved ✦" toasts, welcome-message
 * templates) — only the chrome is iconized.
 *
 * Usage:  <Icon name="sparkles" size={16} className="text-veloura-pink" />
 * Or the per-name components:  <StarIcon size={16} />
 */

import {
  Activity,
  Award,
  BarChart3,
  Bell,
  Bot,
  Cake,
  CalendarHeart,
  Check,
  ChevronLeft,
  ChevronRight,
  Circle,
  Crown,
  Gift,
  Hash,
  Heart,
  HelpCircle,
  KeyRound,
  Lock,
  LogOut,
  type LucideIcon,
  Megaphone,
  MessageSquare,
  Moon,
  Pencil,
  Plus,
  RefreshCw,
  ScrollText,
  Settings,
  Shield,
  ShieldAlert,
  Sparkles,
  Star,
  Swords,
  Timer,
  Trash2,
  Trophy,
  Users,
  Wand2,
  X,
  Zap,
} from 'lucide-react';

export const ICONS = {
  activity: Activity,
  award: Award,
  barChart: BarChart3,
  bell: Bell,
  bot: Bot,
  cake: Cake,
  calendarHeart: CalendarHeart,
  check: Check,
  chevronLeft: ChevronLeft,
  chevronRight: ChevronRight,
  circle: Circle,
  crown: Crown,
  gift: Gift,
  hash: Hash,
  heart: Heart,
  helpCircle: HelpCircle,
  key: KeyRound,
  lock: Lock,
  logout: LogOut,
  megaphone: Megaphone,
  messageSquare: MessageSquare,
  moon: Moon,
  pencil: Pencil,
  plus: Plus,
  refresh: RefreshCw,
  scroll: ScrollText,
  settings: Settings,
  shield: Shield,
  shieldAlert: ShieldAlert,
  sparkles: Sparkles,
  star: Star,
  swords: Swords,
  timer: Timer,
  trash: Trash2,
  trophy: Trophy,
  users: Users,
  wand: Wand2,
  x: X,
  zap: Zap,
} satisfies Record<string, LucideIcon>;

export type IconName = keyof typeof ICONS;

export function isIconName(v: string | undefined): v is IconName {
  return !!v && v in ICONS;
}

/** Render a registry icon by name (falls back to a soft spark). */
export function Icon({
  name,
  size = 16,
  className,
  strokeWidth = 1.8,
}: {
  name: string;
  size?: number;
  className?: string;
  strokeWidth?: number;
}) {
  const Cmp = ICONS[name as IconName] ?? Sparkles;
  return <Cmp size={size} className={className} strokeWidth={strokeWidth} aria-hidden />;
}

/**
 * Render either a registry icon (when the value is a registry key) or
 * the raw string as text — lets callers pass an icon name OR an emoji
 * (prose/brand marks like "🌙" on the fun page) without branching.
 */
export function MaybeIcon({
  value,
  size = 16,
  className,
}: {
  value?: string;
  size?: number;
  className?: string;
}) {
  if (!value) return null;
  if (isIconName(value)) return <Icon name={value} size={size} className={className} />;
  return (
    <span aria-hidden className={className} style={{ fontSize: size, lineHeight: 1 }}>
      {value}
    </span>
  );
}
