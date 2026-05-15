/**
 * cursor/canvas polyfill — plain-React reimplementation of the surface
 * the .canvas.tsx files in specs/ import from. Used by the static-site
 * build so canvases render outside Cursor.
 *
 * Surface (inventoried from 5 canvases in specs/):
 *   Components: Card, CardBody, CardHeader, Stat, Pill, Callout, Table,
 *               Stack, Grid, Row, H1, H2, H3, Text, Code, Divider, Link,
 *               BarChart
 *   Helper:     computeDAGLayout
 *   Hook:       useHostTheme
 *
 * Visual style mimics Cursor's dark canvas look — tone palette + neutral
 * card chrome. Best-effort parity, not pixel-perfect.
 */

import * as React from 'react';
import dagre from 'dagre';
import { BarChart as RBarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, ResponsiveContainer } from 'recharts';

// ---------- theme ----------

export type Tone = 'primary' | 'secondary' | 'tertiary' | 'info' | 'success' | 'warning' | 'danger' | 'neutral' | 'brand';

const theme = {
  text: {
    primary:   '#e8e9ea',
    secondary: '#b6b8bc',
    tertiary:  '#7e8084',
  },
  fill: {
    primary:    '#0e0f10',
    secondary:  '#161719',
    tertiary:   '#1d1e21',
    quaternary: '#26282b',
    brand:      '#1f2735',
  },
  stroke: {
    primary:   '#3a3d42',
    secondary: '#2a2c30',
    tertiary:  '#1d1e21',
    brand:     '#5b8def',
    success:   '#56b76d',
    warning:   '#d4a83a',
    danger:    '#d96b6b',
  },
  accent: {
    primary: '#5b8def',
  },
  bg: {
    elevated: '#181a1d',
  },
  diff: {
    strip: '#2a2c30',
  },
};

export function useHostTheme() {
  return theme;
}

// ---------- tone → color ----------

const toneText: Record<string, string> = {
  primary:   theme.text.primary,
  secondary: theme.text.secondary,
  tertiary:  theme.text.tertiary,
  info:      '#7ea8ff',
  success:   '#7ed18b',
  warning:   '#f0c45a',
  danger:    '#f08585',
  neutral:   theme.text.secondary,
  brand:     '#7ea8ff',
};

const toneBorder: Record<string, string> = {
  primary:   theme.stroke.primary,
  secondary: theme.stroke.secondary,
  tertiary:  theme.stroke.tertiary,
  info:      '#3a5ea8',
  success:   '#3a7a4d',
  warning:   '#8a6e2a',
  danger:    '#8a3a3a',
  neutral:   theme.stroke.secondary,
  brand:     theme.stroke.brand,
};

const toneBg: Record<string, string> = {
  primary:   theme.fill.tertiary,
  secondary: theme.fill.secondary,
  tertiary:  theme.fill.quaternary,
  info:      'rgba(94, 138, 239, 0.10)',
  success:   'rgba(94, 195, 116, 0.10)',
  warning:   'rgba(220, 178, 78, 0.10)',
  danger:    'rgba(220, 110, 110, 0.10)',
  neutral:   theme.fill.tertiary,
  brand:     'rgba(94, 138, 239, 0.10)',
};

// ---------- primitives ----------

type Children = { children?: React.ReactNode };

export function Stack({ children, gap = 12, ...rest }: Children & { gap?: number; style?: React.CSSProperties }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap, ...rest.style }}>
      {children}
    </div>
  );
}

export function Row({ children, gap = 8, ...rest }: Children & { gap?: number; style?: React.CSSProperties }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'row', gap, alignItems: 'center', flexWrap: 'wrap', ...rest.style }}>
      {children}
    </div>
  );
}

export function Grid({ children, columns = 2, gap = 12 }: Children & { columns?: number; gap?: number }) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))`, gap }}>
      {children}
    </div>
  );
}

export function Divider() {
  return <hr style={{ border: 'none', borderTop: `1px solid ${theme.stroke.secondary}`, margin: '6px 0' }} />;
}

export function H1({ children }: Children) {
  return <h1 style={{ fontSize: 28, fontWeight: 700, margin: '4px 0', color: theme.text.primary, letterSpacing: '-0.01em' }}>{children}</h1>;
}
export function H2({ children }: Children) {
  return <h2 style={{ fontSize: 20, fontWeight: 700, margin: '4px 0', color: theme.text.primary, letterSpacing: '-0.005em' }}>{children}</h2>;
}
export function H3({ children }: Children) {
  return <h3 style={{ fontSize: 15, fontWeight: 600, margin: '2px 0', color: theme.text.primary }}>{children}</h3>;
}

export function Text({
  children, tone, size, weight,
}: Children & { tone?: Tone; size?: 'small' | 'normal'; weight?: 'normal' | 'semibold' }) {
  return (
    <span style={{
      color: tone ? toneText[tone] ?? theme.text.primary : theme.text.primary,
      fontSize: size === 'small' ? 12.5 : 14,
      fontWeight: weight === 'semibold' ? 600 : 400,
      lineHeight: 1.55,
    }}>{children}</span>
  );
}

export function Code({ children, language }: Children & { language?: string }) {
  // Block vs inline detection: presence of newlines = block.
  const text = String(children ?? '');
  const isBlock = text.includes('\n');
  if (!isBlock) {
    return (
      <code style={{
        fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
        fontSize: 12.5,
        padding: '1.5px 5px',
        background: theme.fill.secondary,
        border: `1px solid ${theme.stroke.tertiary}`,
        borderRadius: 4,
        color: theme.text.primary,
      }}>{children}</code>
    );
  }
  return (
    <pre style={{
      fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
      fontSize: 12,
      padding: 12,
      background: theme.fill.secondary,
      border: `1px solid ${theme.stroke.tertiary}`,
      borderRadius: 6,
      color: theme.text.primary,
      overflowX: 'auto',
      whiteSpace: 'pre',
      lineHeight: 1.55,
    }} data-lang={language ?? ''}>{children}</pre>
  );
}

export function Link({ children, href }: Children & { href?: string }) {
  return <a href={href} style={{ color: theme.accent.primary, textDecoration: 'none' }} target="_blank" rel="noreferrer">{children}</a>;
}

// ---------- Card ----------

export function Card({ children }: Children) {
  return (
    <div style={{
      background: theme.fill.secondary,
      border: `1px solid ${theme.stroke.secondary}`,
      borderRadius: 10,
      overflow: 'hidden',
    }}>{children}</div>
  );
}

export function CardHeader({ children, trailing }: Children & { trailing?: React.ReactNode }) {
  return (
    <div style={{
      padding: '12px 14px',
      borderBottom: `1px solid ${theme.stroke.tertiary}`,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      gap: 12,
    }}>
      <div style={{ flex: 1, minWidth: 0 }}>{children}</div>
      {trailing ? <div style={{ flexShrink: 0 }}>{trailing}</div> : null}
    </div>
  );
}

export function CardBody({ children }: Children) {
  return <div style={{ padding: 14 }}>{children}</div>;
}

// ---------- Pill ----------

export function Pill({
  children, tone = 'neutral', size, active,
}: Children & { tone?: Tone; size?: 'sm' | 'small'; active?: boolean }) {
  // Treat "sm" and "small" identically per inventory.
  const isSmall = size === 'sm' || size === 'small';
  return (
    <span style={{
      display: 'inline-flex',
      alignItems: 'center',
      padding: isSmall ? '1px 7px' : '3px 9px',
      fontSize: isSmall ? 11 : 12,
      fontWeight: 600,
      lineHeight: 1.4,
      color: toneText[tone] ?? theme.text.secondary,
      background: active ? toneBg[tone] : 'transparent',
      border: `1px solid ${toneBorder[tone] ?? theme.stroke.secondary}`,
      borderRadius: 999,
      whiteSpace: 'nowrap',
    }}>{children}</span>
  );
}

// ---------- Stat ----------

export function Stat({
  value, label, tone = 'primary',
}: { value: React.ReactNode; label: string; tone?: Tone }) {
  return (
    <div style={{
      background: theme.fill.secondary,
      border: `1px solid ${theme.stroke.secondary}`,
      borderRadius: 10,
      padding: '14px 16px',
    }}>
      <div style={{ fontSize: 24, fontWeight: 700, color: toneText[tone] ?? theme.text.primary, lineHeight: 1.1 }}>{value}</div>
      <div style={{ fontSize: 12.5, color: theme.text.tertiary, marginTop: 6, lineHeight: 1.4 }}>{label}</div>
    </div>
  );
}

// ---------- Callout ----------

export function Callout({
  children, tone = 'info', title,
}: Children & { tone?: Tone; title?: string }) {
  return (
    <div style={{
      borderRadius: 8,
      padding: '10px 14px',
      background: toneBg[tone] ?? theme.fill.tertiary,
      border: `1px solid ${toneBorder[tone] ?? theme.stroke.secondary}`,
      borderLeft: `3px solid ${toneBorder[tone] ?? theme.stroke.primary}`,
    }}>
      {title ? <div style={{ fontWeight: 600, color: theme.text.primary, marginBottom: 4 }}>{title}</div> : null}
      <div style={{ color: theme.text.secondary, fontSize: 13.5, lineHeight: 1.55 }}>{children}</div>
    </div>
  );
}

// ---------- Table ----------

export function Table({
  headers, rows, striped,
}: { headers: React.ReactNode[]; rows: React.ReactNode[][]; striped?: boolean }) {
  return (
    <div style={{ overflowX: 'auto', border: `1px solid ${theme.stroke.tertiary}`, borderRadius: 8 }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12.5 }}>
        <thead>
          <tr>
            {headers.map((h, i) => (
              <th key={i} style={{
                padding: '8px 10px',
                textAlign: 'left',
                fontWeight: 600,
                color: theme.text.secondary,
                borderBottom: `1px solid ${theme.stroke.secondary}`,
                background: theme.fill.tertiary,
                whiteSpace: 'nowrap',
              }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, ri) => (
            <tr key={ri} style={{ background: striped && ri % 2 === 1 ? theme.fill.tertiary : 'transparent' }}>
              {row.map((cell, ci) => (
                <td key={ci} style={{
                  padding: '8px 10px',
                  color: theme.text.primary,
                  borderBottom: `1px solid ${theme.stroke.tertiary}`,
                  verticalAlign: 'top',
                  lineHeight: 1.5,
                }}>{cell}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ---------- BarChart ----------

export function BarChart({
  categories, series, height = 220,
}: {
  categories: string[];
  series: Array<{ name: string; data: number[]; tone?: Tone }>;
  height?: number;
}) {
  const data = categories.map((c, i) => {
    const row: any = { category: c };
    for (const s of series) row[s.name] = s.data[i] ?? 0;
    return row;
  });
  return (
    <div style={{ width: '100%', height }}>
      <ResponsiveContainer>
        <RBarChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
          <CartesianGrid stroke={theme.stroke.tertiary} strokeDasharray="2 4" />
          <XAxis dataKey="category" tick={{ fill: theme.text.tertiary, fontSize: 11 }} stroke={theme.stroke.secondary} />
          <YAxis tick={{ fill: theme.text.tertiary, fontSize: 11 }} stroke={theme.stroke.secondary} />
          <Tooltip
            contentStyle={{ background: theme.bg.elevated, border: `1px solid ${theme.stroke.primary}`, fontSize: 12, color: theme.text.primary }}
            cursor={{ fill: theme.fill.tertiary }}
          />
          {series.map((s) => (
            <Bar key={s.name} dataKey={s.name} fill={toneText[s.tone ?? 'info']} radius={[3, 3, 0, 0]} />
          ))}
        </RBarChart>
      </ResponsiveContainer>
    </div>
  );
}

// ---------- computeDAGLayout ----------

type LayoutInput = {
  nodes: Array<{ id: string }>;
  edges: Array<{ from: string; to: string }>;
  direction?: 'horizontal' | 'vertical';
  nodeWidth: number;
  nodeHeight: number;
  rankGap?: number;
  nodeGap?: number;
  padding?: number;
};

type LayoutOutput = {
  width: number;
  height: number;
  nodes: Array<{ id: string; x: number; y: number }>;
  edges: Array<{ sourceX: number; sourceY: number; targetX: number; targetY: number }>;
  ranks: Array<{ rank: number; x: number; y: number; width: number; height: number }>;
};

export function computeDAGLayout(input: LayoutInput): LayoutOutput {
  const {
    nodes, edges,
    direction = 'horizontal',
    nodeWidth, nodeHeight,
    rankGap = 60, nodeGap = 12, padding = 20,
  } = input;

  const g = new dagre.graphlib.Graph();
  g.setGraph({
    rankdir: direction === 'horizontal' ? 'LR' : 'TB',
    ranksep: rankGap,
    nodesep: nodeGap,
    marginx: padding,
    marginy: padding,
  });
  g.setDefaultEdgeLabel(() => ({}));

  for (const n of nodes) g.setNode(n.id, { width: nodeWidth, height: nodeHeight });
  for (const e of edges) g.setEdge(e.from, e.to);

  dagre.layout(g);

  const graphLabel: any = g.graph();
  const out: LayoutOutput = {
    width: graphLabel.width,
    height: graphLabel.height,
    nodes: [],
    edges: [],
    ranks: [],
  };
  // node centers
  const centers: Record<string, { x: number; y: number }> = {};
  for (const id of g.nodes()) {
    const n: any = g.node(id);
    centers[id] = { x: n.x, y: n.y };
    out.nodes.push({ id, x: n.x, y: n.y });
  }
  // edges (source/target centers)
  for (const e of edges) {
    const s = centers[e.from]; const t = centers[e.to];
    if (!s || !t) continue;
    out.edges.push({ sourceX: s.x, sourceY: s.y, targetX: t.x, targetY: t.y });
  }
  // ranks: bucket nodes by primary axis position, emit rank rectangles
  const axis = direction === 'horizontal' ? 'x' : 'y';
  const buckets = new Map<number, { ids: string[]; min: number; max: number }>();
  for (const id of g.nodes()) {
    const n: any = g.node(id);
    const key = Math.round(n[axis]);
    const b = buckets.get(key) ?? { ids: [], min: Infinity, max: -Infinity };
    b.ids.push(id);
    const cross = direction === 'horizontal' ? n.y : n.x;
    b.min = Math.min(b.min, cross - (direction === 'horizontal' ? nodeHeight : nodeWidth) / 2);
    b.max = Math.max(b.max, cross + (direction === 'horizontal' ? nodeHeight : nodeWidth) / 2);
    buckets.set(key, b);
  }
  const sortedKeys = [...buckets.keys()].sort((a, b) => a - b);
  sortedKeys.forEach((key, i) => {
    const b = buckets.get(key)!;
    if (direction === 'horizontal') {
      out.ranks.push({ rank: i, x: key - nodeWidth / 2, y: b.min, width: nodeWidth, height: b.max - b.min });
    } else {
      out.ranks.push({ rank: i, x: b.min, y: key - nodeHeight / 2, width: b.max - b.min, height: nodeHeight });
    }
  });
  return out;
}
