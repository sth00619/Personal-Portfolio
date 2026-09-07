# The SONG Files

A case-file styled portfolio + study tracker for the 2026 summer intensive.
Inspired by [kdfiles.com](https://www.kdfiles.com/).

**Live**: https://sth00619.github.io/Personal-Portfolio/

## What this is

A single-page portfolio where HR managers open the site and see a dossier — case subject, summary, focus areas, and pinned cases (featured projects). Every project is a "case file" with a number, classification, and full implementation notes.

## Sections

### Home · FILE No. 000
The landing page. Designed so a recruiter gets a clear, structured first impression within 10 seconds.
- **Case Subject** — name (EN/KR), title, status (open / exploring / closed), location, languages
- **Case Summary** — Korean + English self-introduction
- **Focus Areas** — domain chips (Finance, Transport, Tourism, BI, AI Eng)
- **Quick Actions** — counts of case files (37), active investigations, hours logged, field notes
- **Featured Cases · Sec. 01** — up to 4 pinned projects with status stamps + GitHub links
- **Evidence Log · Sec. 02** — cumulative hours by topic
- **Education · Sec. 03** — academic timeline, editable
- **Experience · Sec. 04** — work / internship timeline, editable
- **Contact · Sec. 05** — Email, GitHub, LinkedIn, Blog
- **Edit Subject Profile** button opens a full edit modal

### Files (Project Library)
37 verified projects across 8 categories: Finance, Transport, Tourism, DA/BI, Growth, ML/DS, AI Eng, MCP. Filter by category × difficulty. Click any file to open the full case dossier — implementation steps, datasets, references, fit roles. "Add to my cases" copies it into Active.

### Active (My Projects · Kanban)
Pending / In progress / Shipped columns. Click any card to edit: title, category, status, started/target/completed dates, GitHub URL, Demo URL, notes. Click the ★ to pin to Home (max 4). Status auto-fills started/completed dates when changed.

### Log (Dashboard)
Daily activity heatmap (12 weeks), session logging (date + topic + hours + note), cumulative hours by topic, recent sessions list.

### Refs (Resources)
38 learning resources extracted from 56 source images, filtered by domain.

### Journal
Field notes with date, title, body, tag (TIL / Breakthrough / Struggle / Idea / Review), and optional project link.

### Links
Quick bookmarks (study, tool, repo, article, video).

## Design

**Concept**: case file / dossier — every section feels like opening a physical folder.

**Palette** (manila + ink)
- `#0d0b08` warm dark base
- `#c9b287` manila tan (primary accent)
- `#b73e2f` stamp red (used sparingly, for classification labels only)
- `#e6dcc6` cream text
- `#7fa370` shipped green · `#d4a45c` progress yellow

**Type**
- Display: **Fraunces** (with optical / wonky variants) + Noto Serif KR
- Body: Inter + Noto Sans KR
- Utility: JetBrains Mono — for file numbers, dates, classifications

**Signature element**: "FILE No. NNN" + red CLASSIFICATION stamps on every section and project card.

## Stack
- Pure HTML / CSS / JS — no build step
- localStorage for all state (profile, projects, sessions, journal, links, education, experience)
- GitHub Pages via GitHub Actions
- External deps: Google Fonts only

## File structure
```
.
├── index.html            # Page structure — 7 sections, Home is default
├── styles.css            # Case-file aesthetic, all visual tokens
├── app.js                # All logic, modals, state, renderers
├── data.js               # PROFILE defaults + 38 RESOURCES + DEFAULT_LINKS
├── projects-library.js   # 37 case files with implementation guides
├── .github/workflows/
│   └── deploy.yml        # Auto-deploy to GitHub Pages
└── README.md
```

## Data structures (localStorage)

- `sh_profile` — subject profile (name, title, status, summary, contact)
- `sh_projects` — user's Kanban cards with featured flag
- `sh_education` — academic timeline
- `sh_experience` — work / internship timeline
- `sh_sessions` — daily learning logs (date / topic / hours / note)
- `sh_journal` — field notes
- `sh_links` — bookmarks

## First-time setup

1. Open the site → default profile shows SONG case subject placeholder
2. Click **Edit Subject Profile** on Home → fill in your details
3. **+ Add education** / **+ Add experience** → fill in timeline
4. Go to **Files** → click a case → "Add to my cases"
5. Go to **Active** → click ★ on 3-4 cards to feature them on Home
6. Click any active card → edit status, add GitHub URL when shipped

## Next pass (not yet done)

Visual refinement is mid-quality — the structure and signature elements are in place, but a future iteration can push the typography, motion, and density further if needed.

---
Built with care · 2026
