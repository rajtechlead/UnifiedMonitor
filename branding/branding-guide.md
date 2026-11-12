# UniMonitor Brand Identity Guide

## Brand Overview
UniMonitor is a unified Microsoft 365 security monitoring and GRC platform.
The brand communicates trust, precision, and comprehensive security intelligence.

## Logo
- **Primary logo**: `logo.svg` — for light backgrounds
- **Dark-mode logo**: `logo-dark.svg` — for dark backgrounds
- **Icon only**: `icon.svg` — for favicons, app tiles, compact use

### Logo Clear Space
Maintain a minimum clear space of 1× the shield height on all sides.

### Minimum Size
- Logo with text: 160px wide minimum
- Icon only: 24px minimum

### Don'ts
- Do not recolor the shield or wordmark
- Do not add drop shadows to the logo
- Do not stretch or distort proportions
- Do not place on busy photographic backgrounds

---

## Color Palette

### Primary Colors
| Token | Hex | Usage |
|-------|-----|-------|
| `--color-brand-primary` | `#1776D2` | Primary CTAs, links, active states |
| `--color-brand-dark` | `#0D47A1` | Hover states, gradients |
| `--color-brand-light` | `#42A5F5` | Dark-mode accents, highlights |

### Neutral Colors
| Token | Hex | Usage |
|-------|-----|-------|
| `--color-bg-dark` | `#0A0E1A` | Dark mode page background |
| `--color-surface-dark` | `#1A1F2E` | Dark mode card/panel background |
| `--color-surface-dark-2` | `#242A3B` | Dark mode elevated surfaces |
| `--color-text-primary` | `#E8EDF5` | Dark mode primary text |
| `--color-text-secondary` | `#8FA8C8` | Dark mode secondary text |
| `--color-bg-light` | `#F4F7FC` | Light mode page background |
| `--color-surface-light` | `#FFFFFF` | Light mode card background |
| `--color-text-dark-primary` | `#1A1F2E` | Light mode primary text |

### Severity Colors (Semantic)
| Severity | Background | Text | Border |
|----------|-----------|------|--------|
| CRITICAL | `#FEE2E2` | `#991B1B` | `#EF4444` |
| HIGH | `#FEF3C7` | `#92400E` | `#F59E0B` |
| MEDIUM | `#FEF9C3` | `#854D0E` | `#EAB308` |
| LOW | `#DBEAFE` | `#1E40AF` | `#3B82F6` |
| INFORMATIONAL | `#F1F5F9` | `#475569` | `#94A3B8` |
| PASS | `#DCFCE7` | `#166534` | `#22C55E` |

### Score Colors (Gauge)
- 90-100: `#22C55E` (Green — Excellent)
- 70-89: `#84CC16` (Lime — Good)
- 50-69: `#F59E0B` (Amber — Moderate)
- 30-49: `#EF4444` (Red — Poor)
- 0-29: `#991B1B` (Dark Red — Critical)

---

## Typography

### Typeface
- **Primary**: `'Inter', 'Segoe UI', system-ui, sans-serif`
- **Monospace**: `'JetBrains Mono', 'Cascadia Code', 'Consolas', monospace`

### Scale
| Use | Size | Weight |
|-----|------|--------|
| Page title | 28px | 700 |
| Section header | 20px | 600 |
| Card title | 16px | 600 |
| Body | 14px | 400 |
| Label/caption | 12px | 500 |
| Code/data | 13px | 400 (mono) |

---

## CSS Design Tokens (copy into your app)

```css
:root {
  /* Brand */
  --color-brand: #1776D2;
  --color-brand-dark: #0D47A1;
  --color-brand-light: #42A5F5;

  /* Light mode */
  --color-bg: #F4F7FC;
  --color-surface: #FFFFFF;
  --color-surface-2: #EEF2F8;
  --color-border: #D1DCF0;
  --color-text: #1A1F2E;
  --color-text-secondary: #4B5A7A;

  /* Severity */
  --color-critical: #EF4444;
  --color-high: #F59E0B;
  --color-medium: #EAB308;
  --color-low: #3B82F6;
  --color-info: #94A3B8;
  --color-pass: #22C55E;

  /* Spacing */
  --radius-sm: 4px;
  --radius-md: 8px;
  --radius-lg: 12px;
  --radius-xl: 16px;

  /* Shadows */
  --shadow-sm: 0 1px 3px rgba(0,0,0,0.08);
  --shadow-md: 0 4px 12px rgba(0,0,0,0.10);
  --shadow-lg: 0 8px 24px rgba(0,0,0,0.12);
}

[data-theme="dark"] {
  --color-bg: #0A0E1A;
  --color-surface: #1A1F2E;
  --color-surface-2: #242A3B;
  --color-border: #2D3A54;
  --color-text: #E8EDF5;
  --color-text-secondary: #8FA8C8;
  --color-brand: #42A5F5;
  --color-brand-dark: #1976D2;
  --color-brand-light: #90CAF9;
}
```

---

## Dashboard Layout Principles

1. **Information hierarchy**: Critical findings always top-left; score gauges top-right
2. **Card system**: 8px rounded corners, subtle shadow, 16px padding
3. **Data density**: Tables use 44px row height; compact mode: 36px
4. **Color sparingly**: Only severity chips and score gauges use full color; rest is neutral
5. **Dark mode first**: Design for dark, adapt for light
