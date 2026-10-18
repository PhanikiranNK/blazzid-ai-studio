# BLAZZID AI Studio — Design System & Visual Specification

**Design Reference:** [Edtech SaaS Program Details Page Design | Next Step (Dribbble)](https://dribbble.com/shots/27819107-Edtech-SaaS-Program-Details-Page-Design-Next-Step)  
**Theme:** Warm Editorial Light SaaS (No Dark Theme)  
**Tone:** Modern, crisp, approachable, high-utility creative studio for gaming video intelligence.

---

## 1. Visual Architecture & Layout Hierarchy

### Overall Screen Structure
1. **Outer Canvas:**
   - Background: Soft warm sage / pistachio cream (`#E9EFEA`).
   - Outer padding: `p-4 sm:p-6 lg:p-8` creating a framing perimeter around the application.
2. **Left Icon Rail / Docked Navigation:**
   - Width: `w-16 sm:w-20` vertical floating/integrated navigation rail.
   - Circular icon action buttons (`w-10 h-10 rounded-full`) with subtle hover states (`bg-[#D8E2D9]`) and active state pill indicators.
   - Icons: Brand Emblem, Studio Workspace, Recent Edits / History, Pipeline Architecture, System Status, Settings.
3. **Primary Elevated Workspace Card:**
   - Background: Pure White (`#FFFFFF`).
   - Radius: High-curvature modern corners (`rounded-[28px]` or `rounded-[32px]`).
   - Elevation: Soft diffuse ambient drop shadow (`shadow-sm shadow-slate-900/5`), subtle hairline border (`border-[#E2E8E2]`).
   - Internal Structure:
     - **Breadcrumbs:** Small neutral tracking text (`Find Highlights > Brawl Stars Match`).
     - **Header Block:**
       - Left: Round studio avatar badge, title (`Brawl Stars Montage Engine`), pill badge (`v5.1 Distributed`), and subtitle metadata (`FastAPI • Redis Streams • FFmpeg Assembly`).
       - Right: Key metric chip (`~92x Realtime Processing`) + Primary Action Button in vibrant Coral/Orange (`#FF5722`).
     - **Segmented Horizontal Tab Navigation:**
       - Active Tab: Solid Charcoal/Jet Black pill (`bg-[#18191B] text-white font-semibold rounded-xl px-4 py-2 text-xs`).
       - Inactive Tabs: Clean text with soft icon (`text-slate-600 hover:text-slate-900 hover:bg-slate-100/70 rounded-xl px-4 py-2 text-xs`).
     - **Bento Grid Feature Cards:**
       - Soft warm tinted neutral cards (`bg-[#F6F8F6] border border-[#E7EBE7] rounded-2xl`).
       - Circular icon badges (`w-9 h-9 rounded-full bg-white shadow-xs`).
       - Explanatory title and descriptions detailing the 4 pipeline stages.
     - **Interactive Studio Workspace:**
       - Video Dropzone with drag-over state and pre-upload video preview player.
       - Output Profile selection cards (9:16 Shorts, 16:9 Landscape, Smart Adaptive).
       - Target duration slider ($5\text{s}$ to $300\text{s}$) with preset pill buttons.
     - **Recent Jobs & History:**
       - Accordion/list table with numeric prefixes (`01`, `02`, `03`), status pills, duration chips, and quick preview triggers.

---

## 2. Color Palette & Design Tokens

### Backgrounds & Surfaces
| Token | Hex | Role |
| :--- | :--- | :--- |
| `canvas-bg` | `#E9EFEA` | Outer surrounding sage/pistachio canvas |
| `card-bg` | `#FFFFFF` | Primary white workspace card |
| `surface-subtle` | `#F5F8F5` | Bento cards, secondary containers, dropzone background |
| `surface-hover` | `#EDF2ED` | Hover background for list rows and buttons |
| `border-subtle` | `#E2E8E2` | Hairline borders for cards and dividers |
| `border-focus` | `#FF5722` | Focus rings and active card borders |

### Typography & Neutrals
| Token | Hex | Role |
| :--- | :--- | :--- |
| `text-primary` | `#111827` | Headings, primary labels, bold titles |
| `text-secondary` | `#4B5563` | Subtitles, descriptions, inactive tab labels |
| `text-muted` | `#9CA3AF` | Meta information, breadcrumbs, timestamps |
| `text-inverse` | `#FFFFFF` | White text on active dark pills and CTA buttons |

### Brand & Accent Colors
| Accent | Hex | Usage |
| :--- | :--- | :--- |
| **Energetic Coral** | `#FF5722` | Primary CTA button (`Generate Highlights`), active duration indicator |
| **Coral Hover** | `#E84A1A` | Button hover and active states |
| **Charcoal Dark** | `#18191B` | Active segmented tab pill, high-contrast badges |
| **Vivid Emerald** | `#10B981` | Completed `SUCCEEDED` status badge, health online pulse |
| **Electric Amber** | `#F59E0B` | In-progress `PROCESSING` status badge |
| **Soft Rose** | `#EF4444` | Cancelled / Failed error states |

---

## 3. Typography & Hierarchy

- **Font Family:** `Geist Sans`, system fallback `-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`.
- **Numbers & Metrics:** Tabular figures font mono for durations, file sizes, and percentages.
- **Scale:**
  - Page Title: `text-2xl font-black text-slate-900 tracking-tight`
  - Section Headings: `text-base font-bold text-slate-900`
  - Body Text: `text-xs sm:text-sm text-slate-600 leading-relaxed`
  - Caption / Metadata: `text-[11px] sm:text-xs text-slate-500 font-medium`
  - Pill Badges: `text-xs font-semibold px-2.5 py-1 rounded-full`

---

## 4. Components Specification

### 1. Primary CTA Button ("Apply Now" Style)
- Background: `#FF5722`
- Text: White, bold `text-sm`, `px-5 py-2.5 rounded-xl`
- Icon: Right arrow `->` or Sparkles icon
- Shadow: `shadow-md shadow-orange-500/20 hover:shadow-orange-500/30 transition-all`

### 2. Segmented Pill Tabs
- Container: Inline row with horizontal scroll on small screens.
- Active item: `#18191B` background, white text, rounded-xl.
- Inactive items: Transparent background, `text-slate-600`, hover background `#F3F4F6`.

### 3. Bento Grid Cards
- Container: `bg-[#F6F8F6] border border-[#E7EBE7] rounded-2xl p-5`
- Icon Badge: `w-9 h-9 rounded-full bg-white shadow-xs flex items-center justify-center text-slate-800`
- Content: Bold headline + concise 2-line explanation.

### 4. Recent Jobs Accordion List
- Each row formatted as: `01` (numeric index in `text-slate-400 font-mono`), filename, duration pill, status badge, and Chevron action.

---

## 5. Verification Checklist

- [x] Completely removed dark theme overrides (`dark` class, dark backgrounds).
- [x] Outer sage/pistachio perimeter framing the main elevated card.
- [x] Left icon navigation dock with rounded action buttons.
- [x] Breadcrumbs, header block, and coral action button.
- [x] Segmented pill bar with black active pill.
- [x] Bento grid cards showcasing pipeline capabilities.
- [x] Light-themed dropzone with pre-upload preview.
- [x] Full functionality preserved (upload, real-time stage progress, results, video player, downloads).
