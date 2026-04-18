# AI Agent Platform Brand Assets

## Brand Identity

**Name:** AI Agent Platform  
**Tagline:** Intelligent Automation  
**Positioning:** Deploy intelligent AI agents that understand your codebase and automate development tasks with automated infrastructure provisioning

## Color System

### Primary Colors
| Color | Hex | Usage |
|-------|-----|-------|
| Carbon Void | `#0A0A0F` | Primary background |
| Carbon Deep | `#111118` | Secondary background |
| Carbon Surface | `#1A1A24` | Cards, containers |
| Carbon Elevated | `#22222E` | Hover states, elevated surfaces |

### Accent Colors
| Color | Hex | Usage |
|-------|-----|-------|
| Electric Teal | `#00D4AA` | Primary accent, CTAs |
| Teal Dim | `rgba(0, 212, 170, 0.1)` | Subtle backgrounds |
| Teal Glow | `rgba(0, 212, 170, 0.3)` | Glow effects |
| Teal Secondary | `#00B894` | Hover states |

### Semantic Colors
| Color | Hex | Usage |
|-------|-----|-------|
| Success | `#22C55E` | Positive states |
| Warning | `#F59E0B` | Caution states |
| Error | `#EF4444` | Error states |
| Info | `#3B82F6` | Informational |

### Text Colors
| Color | Hex | Usage |
|-------|-----|-------|
| Primary | `#FAFAFA` | Headlines, primary text |
| Secondary | `#A1A1AA` | Body text |
| Tertiary | `#71717A` | Subtle text |
| Muted | `#52525B` | Disabled, placeholders |

## Typography

### Font Stack
```css
font-family: 'Geist', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
```

### Type Scale
| Element | Size | Weight | Tracking |
|---------|------|--------|----------|
| H1 | 32-48px | 600 | -0.02em |
| H2 | 24-32px | 600 | -0.02em |
| H3 | 18-24px | 600 | -0.01em |
| Body | 14-16px | 400 | normal |
| Caption | 12-13px | 500 | 0.03em |
| Label | 11-12px | 600 | 0.05em |

## Spacing System

| Token | Value |
|-------|-------|
| xs | 0.25rem (4px) |
| sm | 0.5rem (8px) |
| md | 1rem (16px) |
| lg | 1.5rem (24px) |
| xl | 2rem (32px) |
| 2xl | 3rem (48px) |
| 3xl | 4rem (64px) |

## Border Radius

| Token | Value |
|-------|-------|
| sm | 6px |
| md | 8px |
| lg | 12px |
| xl | 16px |
| 2xl | 24px |

## Shadows

```css
--shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.3);
--shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.4);
--shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.5);
--shadow-glow: 0 0 20px rgba(0, 212, 170, 0.3);
--shadow-inset: inset 0 1px 0 rgba(255, 255, 255, 0.05);
```

## Animation

### Easing
```css
--ease-out-expo: cubic-bezier(0.16, 1, 0.3, 1);
--ease-spring: cubic-bezier(0.34, 1.56, 0.64, 1);
```

### Duration
```css
--duration-fast: 150ms;
--duration-normal: 250ms;
--duration-slow: 400ms;
```

## Logo

The Carbon Agent logo consists of:
1. A geometric diamond shape with gradient fill (Electric Teal to Teal Secondary)
2. The wordmark "Carbon Agent" in Geist font, weight 600
3. Optional tagline "Intelligence Hub" in lighter weight

### Logo Construction
- Primary shape: 32x32px diamond with gradient
- Glow effect: 20px blur with 30% opacity teal
- Wordmark spacing: -0.02em tracking

## Component Patterns

### Buttons
- Primary: Electric Teal background, dark text, glow on hover
- Secondary: Elevated background, border, light text
- Danger: Error color with 10% opacity background

### Cards
- Background: Carbon Surface
- Border: 1px solid Carbon Border (8% white)
- Border Radius: 12px
- Shadow: shadow-sm
- Hover: Border strongens, shadow increases

### Inputs
- Background: Carbon Deep
- Border: 1px solid Carbon Border
- Focus: Accent color border with 3px glow ring

## Usage Guidelines

1. **Always use dark mode first** - The brand is built around the Carbon Void background
2. **Accent sparingly** - Electric Teal should be used for CTAs and key actions only
3. **Maintain contrast** - Text should always be readable against backgrounds
4. **Animate smoothly** - Use the expo easing curve for all transitions
5. **No emojis** - Use Lucide or Phosphor icons only
