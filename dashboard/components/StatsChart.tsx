'use client';

/**
 * StatsChart — dependency-free SVG charts (veloura-styled):
 *  <LineChart data=[{label, value}] />  — smooth area line
 *  <BarChart data=[{label, value}] />   — rounded bars
 * Both show hover titles (native <title> tooltips) and degrade
 * gracefully to "no data yet" states.
 */

import { useMemo, useState } from 'react';
import { EmptyState } from './EmptyState';
import { shortDate, cn } from '@/lib/format';

export interface Point {
  label: string;
  value: number;
}

export function LineChart({
  data,
  height = 200,
  color = '#FFC0CB',
  valueLabel = 'commands',
}: {
  data: Point[];
  height?: number;
  color?: string;
  valueLabel?: string;
}) {
  const [hover, setHover] = useState<number | null>(null);
  const width = 640;
  const pad = { l: 34, r: 12, t: 12, b: 26 };

  const { path, area, points, max } = useMemo(() => {
    if (data.length === 0) return { path: '', area: '', points: [] as (Point & { x: number; y: number })[], max: 0 };
    const maxV = Math.max(...data.map((d) => d.value), 1);
    const innerW = width - pad.l - pad.r;
    const innerH = height - pad.t - pad.b;
    const step = data.length > 1 ? innerW / (data.length - 1) : 0;
    const pts = data.map((d, i) => ({
      ...d,
      x: pad.l + i * step,
      y: pad.t + innerH - (d.value / maxV) * innerH,
    }));
    const d = pts
      .map((p, i) => {
        if (i === 0) return `M ${p.x} ${p.y}`;
        const prev = pts[i - 1];
        const cx = (prev.x + p.x) / 2;
        return `C ${cx} ${prev.y} ${cx} ${p.y} ${p.x} ${p.y}`;
      })
      .join(' ');
    const bottom = pad.t + innerH;
    return {
      path: d,
      area: `${d} L ${pts[pts.length - 1].x} ${bottom} L ${pts[0].x} ${bottom} Z`,
      points: pts,
      max: maxV,
    };
  }, [data, height]);

  if (data.length === 0) {
    return <EmptyState icon="✦" title={`no ${valueLabel} recorded yet`} hint="data appears as the bot is used" />;
  }

  const uid = color.replace('#', '');

  return (
    <div className="w-full overflow-x-auto">
      <svg viewBox={`0 0 ${width} ${height}`} className="h-auto w-full min-w-[420px]" role="img" aria-label={`${valueLabel} chart`}>
        <defs>
          <linearGradient id={`grad-${uid}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity="0.35" />
            <stop offset="100%" stopColor={color} stopOpacity="0.02" />
          </linearGradient>
        </defs>
        {/* grid */}
        {[0, 0.25, 0.5, 0.75, 1].map((f) => {
          const y = pad.t + (height - pad.t - pad.b) * f;
          return (
            <g key={f}>
              <line x1={pad.l} x2={width - pad.r} y1={y} y2={y} stroke="#333A4E" strokeWidth="1" strokeDasharray={f === 1 ? '' : '3 5'} />
              <text x={pad.l - 6} y={y + 3} textAnchor="end" fontSize="9" fill="#9CA3AF">
                {Math.round(max * (1 - f))}
              </text>
            </g>
          );
        })}
        <path d={area} fill={`url(#grad-${uid})`} />
        <path d={path} fill="none" stroke={color} strokeWidth="2.2" strokeLinecap="round" />
        {points.map((p, i) => (
          <g key={i}>
            <circle
              cx={p.x}
              cy={p.y}
              r={hover === i ? 4.5 : 2.5}
              fill={hover === i ? color : '#1A1D29'}
              stroke={color}
              strokeWidth="1.6"
            />
            <rect
              x={p.x - 8}
              y={pad.t}
              width={16}
              height={height - pad.t - pad.b}
              fill="transparent"
              onMouseEnter={() => setHover(i)}
              onMouseLeave={() => setHover(null)}
            >
              <title>{`${p.label}: ${p.value} ${valueLabel}`}</title>
            </rect>
          </g>
        ))}
        {/* x labels (sparse) */}
        {points.map((p, i) => {
          const every = Math.ceil(points.length / 8);
          if (i % every !== 0 && i !== points.length - 1) return null;
          return (
            <text key={`l-${i}`} x={p.x} y={height - 8} textAnchor="middle" fontSize="9" fill="#9CA3AF">
              {shortDate(p.label)}
            </text>
          );
        })}
        {hover !== null && (
          <text x={points[hover].x} y={points[hover].y - 10} textAnchor="middle" fontSize="10" fill="#F5F5F5">
            {points[hover].value}
          </text>
        )}
      </svg>
    </div>
  );
}

export function BarChart({ data, max = 8, color = '#E6E6FA' }: { data: Point[]; max?: number; color?: string }) {
  if (data.length === 0) {
    return <EmptyState icon="✧" title="nothing to chart yet" />;
  }
  const top = Math.max(...data.map((d) => d.value), 1);
  const shown = data.slice(0, max);

  return (
    <div className="space-y-2.5">
      {shown.map((d, i) => (
        <div key={d.label} className="flex items-center gap-3" title={`${d.label}: ${d.value}`}>
          <span className="w-32 shrink-0 truncate text-right font-mono text-xs text-veloura-muted">
            /{d.label}
          </span>
          <div className="h-6 flex-1 overflow-hidden rounded-full bg-veloura-navy">
            <div
              className={cn('h-full rounded-full transition-all', i === 0 ? 'shadow-glow' : '')}
              style={{ width: `${Math.max((d.value / top) * 100, 3)}%`, background: i === 0 ? '#FFC0CB' : color, opacity: 1 - i * 0.08 }}
            />
          </div>
          <span className="w-10 shrink-0 text-right text-xs text-veloura-text">{d.value}</span>
        </div>
      ))}
    </div>
  );
}
