# Tactical Intelligence

Design system for CS2 Analytics Platform. Use the semantic tokens in `frontend/src/app/globals.css`; Tailwind CSS 4 receives matching utilities through `@theme inline`. Avoid hardcoded component colors. The UI is dark, restrained and oriented around real data and clear user actions.

## Color

| Token | Value | Purpose |
| --- | --- | --- |
| `--background` | `#0B0E13` | Application background |
| `--surface` | `#151A22` | Cards, sidebar and panels |
| `--surface-elevated` | `#202733` | Raised controls and active navigation |
| `--border` | `#303946` | Dividers and component boundaries |
| `--text-primary` | `#F0F3F8` | Primary text |
| `--text-secondary` | `#AAB5C5` | Supporting text |
| `--accent-primary` | `#F59E0B` | Main actions and active navigation |
| `--ai-base` | `#738BFF` | AI-related decorative borders |
| `--accent-ai` | `#A5B5FF` | Higher-contrast AI text on dark surfaces |
| `--success` | `#35C692` | Successful outcomes |
| `--danger` | `#F06B70` | Errors and warnings |

Use amber for actionable or active states; use AI blue only for AI features, and green/red only for meaningful results and errors. Do not communicate status by color alone. Verify WCAG AA contrast for text and controls against their actual surfaces.

## Type and spacing

The UI font stack prefers Inter and falls back to local system sans-serif; numeric and technical values prefer JetBrains Mono and fall back to local monospace. No build-time font downloads are required. Page headings are 30–40px in the dashboard, section headings 18–21px, body 14–15px, and secondary labels normally 12–13px. Use tabular numerals for future measured values. Spacing follows a 4px rhythm with common steps of 8, 12, 16, 24, 32 and 48px; use larger gaps between sections than within groups.

## Components and states

`frontend/src/components/ui` defines Button, Input, FormField, Card, Badge, PageHeader, EmptyState, LoadingState and ErrorState. Primary buttons use amber with dark text; secondary and ghost buttons suit lesser actions. All controls have keyboard focus, hover and disabled states. Loading disables repeated submission. Form fields use explicit labels, hints and accessible error messages. Cards use a surface and subtle border, with 12px radius; nested cards should be avoided. Use the `table-scroll` wrapper for local horizontal scrolling of future wide tables.

## Navigation and responsive behavior

`DashboardLayout` composes `Sidebar` and `Topbar`. The desktop sidebar identifies the active section; topbar contains the current section and account actions. At 800px and below, the sidebar becomes a toggleable menu, with `aria-expanded` and `aria-controls`; selecting a destination closes it. Navigation is keyboard-operable and focus remains visible. Account email remains visible in the profile area when omitted from a small topbar. Cards reflow into a single column at narrow widths; do not allow the whole page to overflow.

## Analytics rules

Never present invented match statistics, player history or AI recommendations. Unavailable capabilities use an explicit “В разработке” state rather than fake controls. Keep objective data, heuristic findings and model assumptions distinguishable, show units and provenance where appropriate, and prioritize legible tables over decorative charts. Preserve current authorization, API contracts and accessible form behavior when extending the UI.
