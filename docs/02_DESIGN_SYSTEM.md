# 02 — Design System (Minimal, Black and White, Light/Dark Toggle)

> Every UI component must follow this file. Do not add colors, gradients, or decoration that are not defined here.

## 1. Design philosophy

- **Minimalistic and clear.** Content first, chrome last.
- **Monochrome.** Black, white and greys only. Meaning comes from typography, spacing and borders, not color.
- **Flat.** No gradients, no heavy shadows, no glow, no glassmorphism.
- **Calm.** Lots of whitespace, one primary action per screen region.
- **Consistent.** Same spacing, radius, and type scale everywhere.

## 2. Theme toggle requirement

- Two themes: **Light** (white background, black text) and **Dark** (black background, white text).
- A toggle button sits in the top-right of the app header on every page.
- Default = user's OS preference (`prefers-color-scheme`). Persist the choice in `localStorage` key `theme`.
- No flash of wrong theme on load.
- Use `next-themes` with Tailwind `darkMode: "class"`.
- Transition: `background-color` and `color` only, 150ms ease.

### Implementation sketch

```tsx
// app/providers.tsx
"use client";
import { ThemeProvider } from "next-themes";
export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider attribute="class" defaultTheme="system" enableSystem>
      {children}
    </ThemeProvider>
  );
}

// components/theme-toggle.tsx
"use client";
import { useTheme } from "next-themes";
import { Sun, Moon } from "lucide-react";
export function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();
  return (
    <button
      aria-label="Toggle theme"
      onClick={() => setTheme(resolvedTheme === "dark" ? "light" : "dark")}
      className="h-9 w-9 inline-flex items-center justify-center rounded-md border border-border hover:bg-muted"
    >
      {resolvedTheme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
    </button>
  );
}
```

## 3. Color tokens

Define as CSS variables in `globals.css`. Components use tokens only, never raw hex.

```css
:root {
  --background: #ffffff;
  --foreground: #0a0a0a;
  --muted: #f5f5f5;
  --muted-foreground: #737373;
  --border: #e5e5e5;
  --border-strong: #d4d4d4;
  --card: #ffffff;
  --primary: #0a0a0a;          /* buttons, active states */
  --primary-foreground: #ffffff;
  --ring: #0a0a0a;

  /* status: muted, used sparingly with a text label always present */
  --success: #15803d;
  --warning: #a16207;
  --danger: #b91c1c;
}

.dark {
  --background: #0a0a0a;
  --foreground: #fafafa;
  --muted: #171717;
  --muted-foreground: #a3a3a3;
  --border: #262626;
  --border-strong: #404040;
  --card: #0a0a0a;
  --primary: #fafafa;
  --primary-foreground: #0a0a0a;
  --ring: #fafafa;

  --success: #4ade80;
  --warning: #facc15;
  --danger: #f87171;
}
```

### Token usage

| Token | Use for |
|---|---|
| `background` | Page background |
| `card` | Cards, panels (distinguish with `border`, not shadow) |
| `muted` | Hover rows, subtle sections, code blocks |
| `muted-foreground` | Secondary text, captions, placeholders |
| `border` | All dividers and outlines |
| `primary` | Primary buttons, selected nav item, focus ring |
| `success / warning / danger` | Status dots and text only, never large fills |

Status must never rely on color alone. Always show a text label or icon next to the color.

## 4. Typography

- Font: **Inter** (fallback: system-ui). Mono: **JetBrains Mono** for IDs, logs and traces.
- Two weights only: 400 and 500.

| Role | Size | Weight | Line height |
|---|---|---|---|
| Page title (h1) | 24px | 500 | 32px |
| Section title (h2) | 18px | 500 | 28px |
| Card title (h3) | 15px | 500 | 24px |
| Body | 14px | 400 | 22px |
| Caption / meta | 12px | 400 | 16px |
| Mono | 13px | 400 | 20px |

Sentence case everywhere. No ALL CAPS, no Title Case in buttons or labels.

## 5. Spacing, radius, borders

- Spacing scale (px): 4, 8, 12, 16, 24, 32, 48. Use only these.
- Page padding: 24px desktop, 16px mobile. Max content width: 1200px.
- Radius: 6px controls, 10px cards. No pill shapes except status badges.
- Border: 1px solid `var(--border)`. No box shadows (only a 1px focus ring).

## 6. Components

**Button**
- Primary: `bg-primary text-primary-foreground`, 36px height, 14px text.
- Secondary: transparent, 1px border.
- Ghost: no border, hover `bg-muted`.
- Destructive: secondary style with `danger` text. Needs a confirm dialog.
- Disabled: 50% opacity, no pointer.

**Input / textarea / select**: 36px height, 1px border, focus = 2px ring in `ring`, placeholder `muted-foreground`.

**Card**: 1px border, 10px radius, 16 to 24px padding, no shadow.

**Table**: no zebra stripes. Row divider 1px `border`. Row hover `muted`. Header text 12px `muted-foreground`.

**Badge** (status): 12px text, 1px border, small dot colored by status plus a text label (Running, Waiting for approval, Completed, Failed).

**Dialog / drawer**: overlay `rgba(0,0,0,0.5)`, content uses `card` + border. Approval dialogs show action, risk reason, and Approve/Reject buttons of equal visual weight.

**Toast**: bottom-right, border, no color fill.

**Empty state**: one short sentence plus one primary action.

**Loading**: skeleton blocks in `muted`. Spinner only for buttons.

## 7. Layout

```
+-----------+----------------------------------------------+
| Sidebar   | Header: page title ............ [theme] [user]|
| 240px     +----------------------------------------------+
|           |                                              |
| Dashboard |  Page content (max 1200px, 24px padding)     |
| Employees |                                              |
| Workflows |                                              |
| Approvals |                                              |
| Knowledge |                                              |
| Analytics |                                              |
| Settings  |                                              |
+-----------+----------------------------------------------+
```

- Sidebar collapses to icons under 1024px, becomes a bottom sheet under 640px.
- Active nav item: `bg-muted` plus `text-foreground`; inactive: `muted-foreground`.

## 8. Icons and motion

- Icons: `lucide-react`, 16px in controls, 20px in nav, 1.5 stroke. No filled icons, no emoji.
- Motion: 150ms ease for hover and theme change. Respect `prefers-reduced-motion`. No decorative animation.
- Live workflow step indicators: a subtle opacity pulse on the active step only.

## 9. Charts

- Use Recharts. Monochrome: lines in `foreground`, secondary series in `muted-foreground`, dashed for comparison.
- Gridlines in `border`. No gradients or area fills heavier than 10% opacity.

## 10. Accessibility

- Contrast at least 4.5:1 for text in both themes.
- Visible focus ring on all interactive elements.
- All icon-only buttons have `aria-label`.
- Keyboard: every action reachable by Tab, dialogs trap focus, Esc closes.
- Voice interface shows live captions of what was heard and what is being spoken.

## 11. Do and don't

| Do | Don't |
|---|---|
| Use tokens | Hardcode hex values |
| Separate with whitespace and 1px borders | Use shadows or gradients |
| One primary button per area | Many competing buttons |
| Show a text label with every status color | Rely on color alone |
| Sentence case | ALL CAPS or Title Case |
