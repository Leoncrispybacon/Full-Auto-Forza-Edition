# FAFE Website Handoff

Last updated: 2026-06-21

## Current website structure

- `index.html` detects the visitor's saved/browser language and routes to `/en/` or `/zh-tw/`.
- `en/index.html` and `zh-tw/index.html` are the localized homepages.
- Each language has a search-oriented overview guide plus 11 detailed guides under `<language>/guides/`.
- Shared guide presentation and behavior live in `assets/site/guide.css` and `assets/site/guide.js`.
- Guide screenshots live in `assets/site/`, primarily as resized WebP files.

## Latest completed work

- Merged the duplicated homepage Features and Guides sections into one clickable **Features & Guides** section.
- Removed decorative emoji from both homepages and replaced card icons with restrained text category labels.
- Expanded the English and Traditional Chinese overview guides with Auto Buy and Delete Used Cars sections.
- Added overview tables of contents, full-size screenshot opening, previous/next guide navigation, and visible FAFE v1.8.0 update dates.
- Standardized English product terminology around **AFK Races** and **Wheelspins**.
- Added and optimized localized tutorial screenshots.
- Kept direct downloads pointed at the latest `FAFE.zip` GitHub release asset.

## Editing conventions

- Keep English and Traditional Chinese pages structurally equivalent.
- Preserve `/en/` and `/zh-tw/` routes and their canonical/hreflang metadata.
- Reuse existing screenshots when possible. Resize large gameplay screenshots to a maximum width near 1600 px and save photographic images as WebP.
- Every screenshot needs accurate `width`, `height`, lazy loading, async decoding, descriptive alt text, and a useful caption.
- Detailed guides load `assets/site/guide.js`; it supplies image enlargement and previous/next navigation.
- Do not add query parameters, URL hashes, or additional language-routing systems.
- Keep the website deployable as static GitHub Pages files with no build step.

## Publishing workflow

1. Work only on the public website paths: `index.html`, `en/`, `zh-tw/`, `assets/site/`, `robots.txt`, `sitemap.xml`, and the Google verification file.
2. Validate local links, image paths, fragment IDs, and duplicate IDs.
3. Serve the repository locally with `python -m http.server 8000 --bind 127.0.0.1` and inspect both languages.
4. Scan the staged diff before committing; unrelated application files must not be included in a website-only change.
5. Push `main`; GitHub Pages will deploy the static files automatically.

## Suggested next checks

- Recheck mobile card spacing and long Traditional Chinese headings after future copy changes.
- Update the visible date and `article:modified_time` only when a guide receives a meaningful content update.
- After deployment, request indexing for the overview guides in Google Search Console.
