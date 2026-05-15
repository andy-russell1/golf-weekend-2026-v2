# Golf Trip Data Package

## Purpose
This package hardens the v1 golf scrape into a Codex-ready input for a standalone Streamlit app covering St. Pierre Old Course, Clyne Golf Club, Neath Golf Club, and Rolls of Monmouth.

## Folder structure
- `courses/`: standardised hole-by-hole course files
- `metadata/`: enrichment, summaries, source traceability, image mapping, and data gaps
- `images/`: locally stored official imagery where retrieved

## Course CSV schema
`course,hole,hole_name,par,yards_white,yards_yellow,si,section`

Notes:
- `hole_name` is blank where no reliable official name was found.
- `par` is stored as a single field to match the requested schema. Where tee-specific par differs on the source site, the package preserves the single-par representation already used in the v1 package.
- `section` is `OUT` for holes 1-9 and `IN` for holes 10-18.

## Metadata CSV schemas
### `hole_enrichment.csv`
`course,hole,hole_name,pro_tip,source_type,source_url,image_path,image_caption,official_hole_url`

### `course_summary.csv`
`course,par_out,par_in,par_total,yards_white_out,yards_white_in,yards_white_total,yards_yellow_out,yards_yellow_in,yards_yellow_total`

### `source_log.csv`
`course,hole,field,value,source_url,source_type,notes`

### `data_gaps_report.csv`
`course,hole,field,issue,action_needed`

### `image_mapping.csv`
`course,hole,image_path,source_url,image_type,notes`

## Source hierarchy used
1. Official club/course scorecard pages
2. Official hole-by-hole pages / club course tours
3. Accessible third-party scorecard page only where the official site did not expose structured scorecard values
4. Existing v1 package only as a preservation baseline, then checked against accessible web sources

## Known limitations
- St. Pierre Old Course: accessible official scorecard values were available, but no official hole-by-hole guide with named holes or per-hole tips was found.
- Clyne: official scorecard and official hole-by-hole text were available, but direct image asset download returned 403 from the official site.
- Neath: official hole pages now include local hole photo galleries in `images/neath/hole_XX/`; official hole names remain numeric-only in the source.
- Rolls of Monmouth: imagery now uses the official hole planner layout images for holes 1-18, stored in `images/rolls_monmouth/` as `hole_1.jpg` through `hole_18.jpg`.

## Streamlit / Codex ingestion guidance
- Treat each course CSV as the authoritative hole table.
- Join `hole_enrichment.csv` on `course` + `hole`.
- Join `course_summary.csv` on `course`.
- Use `image_mapping.csv` as the source of truth for app image lookup, with graceful fallback to blank/missing states.
- Surface `data_gaps_report.csv` in QA/admin views so any remaining image or naming gaps remain explicit.
