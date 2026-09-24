# William Damario Lukito — personal website

A responsive academic portfolio with searchable publications, projects, teaching, photography, news, education, awards, and professional service. Content is maintained in Google Sheets; GitHub Pages serves complete static HTML, including when JavaScript is disabled.

## Preview locally

Requires Python 3.9 or newer, with no third-party packages:

```sh
python3 scripts/build.py
python3 -m http.server 4173 --directory _site
```

Open http://localhost:4173. The build reads the published Google Sheet configured in `data/source.json`. For an offline preview, run `CONTENT_OFFLINE=1 python3 scripts/build.py` to use the migrated `data/content.csv` snapshot. Do not edit `_site`: it is generated.

## Connect Google Sheets (one-time setup)

1. Create a Google Sheet and import `data/content.csv` using **File → Import → Upload**. Keep the header row. Choose **No** for automatic conversion of text to numbers/dates if offered, or format the `date` column as plain text. News dates must remain `YYYY-MM`.
2. Choose **File → Share → Publish to web**. Select the content tab (not the entire workbook), select **Comma-separated values (.csv)**, and publish. Leave **Automatically republish when changes are made** enabled.
3. Copy the published URL. It should resemble `https://docs.google.com/spreadsheets/d/e/…/pub?gid=0&single=true&output=csv`. This is different from the editing/share URL.
4. The supplied published URL is already saved in `data/source.json`. To change Sheets later, update that URL, or override it with the optional GitHub Actions repository variable `CONTENT_SHEET_URL`. No variable is needed for the current Sheet.
5. Set **Settings → Pages → Build and deployment → Source** to **GitHub Actions**.
6. Push this redesign to `main`, or run **Actions → Build and deploy portfolio → Run workflow** after pushing.

The published Google Sheet has been verified: 57 public records successfully generate all six pages. The local implementation is not yet a production deployment.

## Everyday updates

Edit or add rows in Sheets. No HTML changes, numbered IDs, or git commits are needed for content updates. The workflow imports the Sheet on an hourly schedule, on pushes, or on manual runs. Google's published feed can take a few minutes to refresh, and GitHub's scheduled jobs can be delayed, so this is not an instant-update guarantee.

GitHub disables scheduled workflows in public repositories after 60 days without repository activity. If this happens, re-enable the workflow in Actions. An immediate update can always be requested with **Run workflow**. For long periods without repository activity, a separate authenticated scheduler can send the supported `content-updated` repository-dispatch event; that scheduler is not configured by this project.

Only put public portfolio information in the published tab. `published=FALSE` hides a row on the website, but that row remains readable in the published CSV. Keep private notes in a different, unpublished tab.

If a configured Google feed fails or has invalid data, the build fails before deployment. The already deployed site stays online with its last successful content. It never silently replaces newer content with the older local starter file. An empty `CONTENT_SHEET_URL` uses the saved Sheet URL. Local CSV mode requires `CONTENT_OFFLINE=1`, or no saved URL and no environment override.

## Content columns

Headers can be reordered, but their names must stay the same. An old `id` column is accepted and ignored for compatibility; it can be deleted.

| Column | What to enter |
| --- | --- |
| `type` | `publication`, `news`, `course`, `project`, `education`, `award`, `service`, or `photo` |
| `title` | Main heading; required for a published row |
| `category` | Publication: `Journal`, `Conference`, or `Poster`. Course: `Teaching` or `Course development`. Other types: an optional label/institution. |
| `date` | Publication: `YYYY`. News: `YYYY-MM`. Other types: a human-readable period such as `2026 – present`. |
| `description` | Plain text. Publications: full citation. Teaching: institution. Course development: institution. Projects: summary. Photos: location. |
| `url` | Optional HTTPS link (DOI, repository, demo, etc.) |
| `image` | For photos, an HTTPS image URL or existing `/assets/images/…` path |
| `featured` | `TRUE` to feature a publication on the homepage; otherwise `FALSE` |
| `published` | `TRUE` to show the row, `FALSE` to leave it out of the website |

The `description` column accepts line breaks and commas; use Sheets to handle CSV quoting automatically. HTML is rendered as text rather than executed. Sheets checkboxes work for the boolean columns.

### Automatic publication numbering

The website generates independent `J1…`, `C1…`, and `P1…` sequences. Years sort newest first. Within a year, the Sheet's row order is used, so put newer publications above older publications from the same year. The top publication receives the largest number in its category.

Adding a new newest journal paper gives it `J5` when four journal papers already exist. Homepage selections and research filters use the same labels and do not renumber the results. Removing a publication or inserting an older one can change the sequence; these are display labels, not permanent record IDs.

### Examples

- New journal article: `type=publication`, `category=Journal`, `date=2026`, title, full citation in description, DOI URL, `published=TRUE`.
- Project: `type=project`, title, optional category, description, link, `published=TRUE`. No template changes are needed.
- Course: `type=course`, `category=Teaching`, course title, institution in description, teaching semesters in date, `published=TRUE`.
- News: `type=news`, short update in title, `date=2026-09`, optional URL, `published=TRUE`.
- Photo: `type=photo`, title, location in description, direct image URL/path in image, `published=TRUE`. An image must be hosted before linking it; Sheets does not upload images to the repository.

Select up to three featured papers for the homepage. If none are featured, the newest three are used. Empty projects show a deliberate introductory state, without fabricated entries.

## Development and checks

```sh
python3 -m unittest discover -s tests -v
python3 scripts/build.py
```

For a live feed preview:

```sh
CONTENT_SHEET_URL='https://docs.google.com/spreadsheets/d/e/YOUR_PUBLISHED_ID/pub?gid=0&single=true&output=csv' python3 scripts/build.py
```

- `scripts/build.py`: CSV validation, numbering, and static page rendering.
- `data/content.csv`: migrated starting content and explicit offline snapshot.
- `data/source.json`: saved public Google Sheets CSV URL (no credentials).
- `assets/css/styles.css`: responsive visual design.
- `assets/js/site.js`: progressive-enhancement publication filters.
- `.github/workflows/pages.yml`: validation, import, build, and deployment.
- `tests/test_build.py`: validation, numbering, escaping, content updates, and failed-import preservation tests.

The obsolete Jekyll pages, layouts, includes, Ruby dependencies, unused icons/logos, and Finder metadata have been removed. Their original versions remain recoverable from Git history. The site builds from the Python renderer and CSV; the former third-party visitor tracker is not included.

The biography, contact details, and research introduction currently live in the renderer. Recurring portfolio entries use the Sheet. Changing styling or page structure still requires a code change.

## Reference documentation

- [Publish a Google Sheet](https://support.google.com/docs/answer/183965)
- [GitHub Pages custom workflows](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)
- [GitHub schedule timing and inactivity limits](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)
