#!/usr/bin/env python3
"""Build a dependency-free portfolio, optionally importing a published Google Sheet."""
import csv
import html
import io
import json
import os
from pathlib import Path
import re
import shutil
import urllib.parse
import urllib.request
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
FIELDS = ['type', 'title', 'category', 'date', 'description', 'url', 'image', 'featured', 'published']
TYPES = {'publication', 'news', 'course', 'project', 'education', 'award', 'service', 'photo'}
SITE = 'https://wdloe.github.io'

def esc(value):
    return html.escape(str(value), quote=True)

def safe_url(value, image=False):
    if not value:
        return ''
    if value.startswith('/') and not value.startswith('//') and not any(c in value for c in ('\\', '\n', '\r')) and '..' not in value:
        return value
    parsed = urllib.parse.urlsplit(value)
    if parsed.scheme == 'https' and parsed.hostname and not parsed.username and not parsed.password:
        return value
    raise ValueError(f'Use an HTTPS URL or /assets/ path: {value[:100]}')

def parse_content(text):
    reader = csv.DictReader(io.StringIO(text.lstrip('\ufeff')))
    if not reader.fieldnames or set(reader.fieldnames) - {'id'} != set(FIELDS) or len(reader.fieldnames) != len(set(reader.fieldnames)):
        raise ValueError('Content headers must be: ' + ','.join(FIELDS))
    rows, seen = [], set()
    for n, source in enumerate(reader, 2):
        if not any(source.values()):
            continue
        if None in source or any(v is None for v in source.values()):
            raise ValueError(f'Row {n}: incorrect number of columns')
        row = {k: v.strip() for k, v in source.items() if k != 'id'}
        if not row['published']:
            print(f'Content row {n}: skipped draft with blank published cell ({row["title"] or "untitled"}).')
            continue
        if row['published'].upper() not in ('TRUE', 'FALSE'):
            raise ValueError(f'Row {n}: published must be TRUE or FALSE')
        if row['published'].upper() == 'FALSE':
            continue
        if row['type'] not in TYPES or not row['title']:
            raise ValueError(f'Row {n}: valid type and title are required')
        identity = tuple(row[k].casefold() for k in ('type', 'title', 'category', 'date', 'description', 'url', 'image'))
        if identity in seen:
            raise ValueError(f'Row {n}: duplicate content row')
        seen.add(identity)
        if row['featured'].upper() not in ('', 'TRUE', 'FALSE'):
            raise ValueError(f'Row {n}: featured must be TRUE or FALSE')
        if row['type'] == 'publication' and (row['category'] not in ('Journal', 'Conference', 'Poster') or not re.fullmatch(r'\d{4}', row['date'])):
            raise ValueError(f'Row {n}: publication needs Journal, Conference or Poster and a YYYY date')
        if row['type'] == 'news':
            try:
                datetime.strptime(row['date'], '%Y-%m')
            except ValueError as e:
                raise ValueError(f'Row {n}: news date must be YYYY-MM') from e
        for key in ('url', 'image'):
            safe_url(row[key], image=key == 'image')
        if row['type'] == 'photo' and not row['image']:
            raise ValueError(f'Row {n}: photo needs an image')
        rows.append(row)
    if not rows:
        raise ValueError('Refusing to build an empty content feed')
    return rows

def load_content():
    if os.environ.get('CONTENT_OFFLINE') == '1':
        return parse_content((ROOT / 'data/content.csv').read_text()), 'local'
    url = os.environ.get('CONTENT_SHEET_URL', '').strip()
    config_path = ROOT / 'data/source.json'
    if not url and config_path.exists():
        url = json.loads(config_path.read_text()).get('google_sheet_csv_url', '').strip()
    if not url:
        return parse_content((ROOT / 'data/content.csv').read_text()), 'local'
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != 'https' or parsed.hostname != 'docs.google.com' or '/spreadsheets/d/e/' not in parsed.path or urllib.parse.parse_qs(parsed.query).get('output') != ['csv']:
        raise ValueError('CONTENT_SHEET_URL must be a published docs.google.com spreadsheet CSV URL')
    # Fail closed: a failed import never replaces the last successful deployment.
    request = urllib.request.Request(url, headers={'User-Agent': 'WilliamLukitoPortfolio/1.0'})
    with urllib.request.urlopen(request, timeout=30) as response:
        data = response.read(5_000_001)
    if len(data) > 5_000_000:
        raise ValueError('Content feed exceeds 5 MB')
    return parse_content(data.decode('utf-8-sig')), 'google-sheets'

def link(url, label, cls='text-link'):
    return f'<a class="{cls}" href="{esc(safe_url(url))}">{esc(label)}</a>' if url else ''

def citation_text(text):
    # Escape Sheet content before adding the one supported piece of formatting.
    return re.sub(r'\b(?:W\.\s*D\.\s*Lukito|William Damario Lukito|William D\. Lukito)\b',
                  lambda match: '<strong>' + match.group(0) + '</strong>', esc(text))

def education_text(text):
    # Support both explicit Sheet line breaks and the existing one-line entries.
    lines = re.split(r'\r?\n|\s+(?=(?:Thesis|Topic|Academic supervisor|Principal supervisor):)', text)
    return '<br>'.join(esc(line.strip()) for line in lines if line.strip())

def publication(row):
    return f'''<article class="publication" aria-label="{esc(row['title'])}" data-category="{esc(row['category'])}" data-year="{esc(row['date'])}">
      <div class="pub-meta"><strong class="publication-label">{esc(row['label'])}</strong><span>{esc(row['date'])}</span><span class="tag">{esc(row['category'])}</span></div>
      <div><p class="citation">{citation_text(row['description'] or row['title'])}</p>{link(row['url'], 'Read publication')}</div></article>'''

def cards(rows):
    return ''.join(f'''<article class="content-card"><p class="eyebrow">{esc(r['category'])}</p><h3>{esc(r['title'])}</h3><p>{esc(r['description'])}</p><p class="small">{esc(r['date'])}</p>{link(r['url'], 'Explore')}</article>''' for r in rows)

def news(rows):
    return ''.join(f'<li><time datetime="{esc(r["date"])}">{datetime.strptime(r["date"], "%Y-%m").strftime("%b %Y")}</time><div>{link(r["url"], r["title"]) if r["url"] else esc(r["title"])}</div></li>' for r in rows)

def photo(row):
    return f'''<figure><a href="{esc(row['image'])}" aria-label="View {esc(row['title'])} full size"><img src="{esc(row['image'])}" alt="{esc(row['title'])}, {esc(row['description'])}" loading="lazy" width="1200" height="800"></a><figcaption><strong>{esc(row['title'])}</strong><span>{esc(row['description'])}</span></figcaption></figure>'''

def section_heading(label, title, url='', text='View all'):
    return f'<div class="section-heading"><div><p class="eyebrow">{label}</p><h2>{title}</h2></div>{link(url,text) if url else ""}</div>'

def intro(label, title, text):
    return f'<header class="page-intro"><p class="eyebrow">{label}</p><h1>{title}</h1><p class="lede">{text}</p></header>'

def shell(title, current, content, description):
    active = 'aria-current="page"'
    nav = ''.join(f'<a href="{url}" {active if current == name else ""}>{name}</a>' for name,url in [('About','/'),('Research','/research/'),('Projects','/projects/'),('Teaching','/teaching/'),('Photography','/gallery/')])
    path = '/' if current == 'About' else '/'+{'Research':'research','Projects':'projects','Teaching':'teaching','Photography':'gallery','Contact':'contact','Not found':'404'}.get(current, '')+'/'
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)} · William Lukito</title><meta name="description" content="{esc(description)}">
<meta name="theme-color" content="#f6f5f0"><link rel="canonical" href="{SITE}{path}">
<meta property="og:title" content="{esc(title)} · William Lukito"><meta property="og:description" content="{esc(description)}"><meta property="og:type" content="website"><meta property="og:url" content="{SITE}{path}"><meta property="og:image" content="{SITE}/assets/images/profile.png">
<link rel="icon" href="/assets/favicon.svg" type="image/svg+xml"><link rel="stylesheet" href="/assets/css/styles.css"><script src="/assets/js/site.js" defer></script></head>
<body><a class="skip-link" href="#main">Skip to content</a>
<header class="site-header"><div class="nav-wrap"><a class="wordmark" href="/" aria-label="William Lukito, home">WL</a><nav aria-label="Main navigation">{nav}</nav></div></header>
<main id="main" tabindex="-1">{content}</main>
<footer class="site-footer"><div><a class="wordmark" href="/">WL</a><p>In harmonia progressio.</p></div><p>© {datetime.now().year} William Damario Lukito</p><a href="#main">Back to top ↑</a></footer>
</body></html>'''

def number_publications(rows):
    """Newest first; Sheet row order breaks year ties. Filters never renumber."""
    publications = sorted(rows, key=lambda row: row['date'], reverse=True)
    prefixes = {'Journal': 'J', 'Conference': 'C', 'Poster': 'P'}
    counts = {kind: sum(row['category'] == kind for row in publications) for kind in prefixes}
    result = []
    for row in publications:
        kind = row['category']
        result.append(dict(row, label=f'{prefixes[kind]}{counts[kind]}'))
        counts[kind] -= 1
    return result

def build():
    rows, source = load_content()
    groups = {kind: [r for r in rows if r['type'] == kind] for kind in TYPES}
    pubs = number_publications(groups['publication'])
    updates = sorted(groups['news'], key=lambda r:r['date'], reverse=True)
    featured = [r for r in pubs if r['featured'].upper() == 'TRUE'][:3]
    home = '''<section class="hero"><div class="hero-copy"><p class="eyebrow"><span class="status-dot"></span> Researcher · Engineer</p><h1>William<br>Damario Lukito<span class="accent">.</span></h1><p class="hero-statement">Intelligence for a<br><em>more connected world.</em></p><p class="hero-description">I explore how AI, signal processing, and embedded intelligence can make wireless communication systems more efficient, reliable, and aware of the physical world.</p><div class="hero-actions"><a class="button" href="/research/">Explore my research</a><a class="text-link" href="mailto:W.Lukito@latrobe.edu.au">Get in touch</a></div><div class="social-links"><a href="https://scholar.google.com/citations?user=V7wkXKcAAAAJ">Google Scholar</a><a href="https://orcid.org/0009-0007-9940-9955">ORCID</a><a href="https://www.linkedin.com/in/williamdlukito">LinkedIn</a></div></div><div class="portrait-wrap"><img class="portrait" src="/assets/images/profile.png" alt="William Damario Lukito" width="500" height="600" fetchpriority="high"></div></section>
<section class="section about-grid"><div><p class="eyebrow">A little about me</p><h2>Curiosity, with <br>a purpose.</h2></div><div class="prose"><p>I’m curious about how intelligence can reshape wireless communications: how systems can learn from their environment, use limited resources efficiently, and connect people and machines reliably.</p><p>I’m a <a href="https://smartsatcrc.com/students/william-damario-lukito/">SmartSat CRC PhD Candidate</a> at <a href="https://www.latrobe.edu.au">La Trobe University</a>, under the supervision of <a href="https://scholars.latrobe.edu.au/wxiang">Professor Wei Xiang</a>. My current research applies AI techniques to efficient and reliable satellite IoT communications—one important scenario within my broader work in wireless communications.</p><p>My general research interests include wireless communications, integrated sensing and communications, machine learning, digital signal processing, and embedded systems. I’m also exploring physical AI communications: how embodied intelligent systems sense, exchange information, and act in the physical world.</p><p>I hold B.Sc. and M.Sc. degrees in <a href="https://stei.itb.ac.id/en/kk/telekomunikasi/">Telecommunications Engineering</a> from the <a href="https://itb.ac.id/en">Bandung Institute of Technology</a>, completed in 2021 and 2022.</p><p>Away from research, I enjoy travelling, photography, and aviation through flight simulation. I hold the SPP rating on IVAO and regularly fly the Boeing 737 and Airbus A330 in the simulator.</p><a class="text-link" href="/gallery/">A different perspective</a></div></section>'''
    home += '<section class="section news-section">'+section_heading('Along the way','Latest news')+'<ol class="news-list">'+news(updates[:4])+'</ol>'
    if len(updates)>4:
        home += '<details><summary>Earlier updates</summary><ol class="news-list">'+news(updates[4:])+'</ol></details>'
    home += '</section>'
    home += '<section class="section">'+section_heading('Research', 'Selected publications', '/research/', 'All publications')+''.join(map(publication,featured or pubs[:3]))+'</section>'
    home += '<section class="section">'+section_heading('The journey','Education')+'<div class="education-list">'+''.join(f'<article><p class="eyebrow">{esc(r["date"])}</p><div><h3>{esc(r["title"])}</h3><p class="institution">{esc(r["category"])}</p><p>{education_text(r["description"])}</p>{link(r["url"],"Learn more")}</div></article>' for r in groups['education'])+'</div></section>'
    home += '<section class="section two-column"><div><p class="eyebrow">Recognition</p><h2>Awards &amp; support</h2><ul class="simple-list">'+''.join(f'<li><strong>{esc(r["title"])}</strong><span>{esc(r["date"])}</span></li>' for r in groups['award'])+'</ul></div><div><p class="eyebrow">Academic community</p><h2>Service &amp; reviewing</h2><p>Member of IEEE, IEEE Communications Society, and IEEE Vehicular Technology Society.</p><details><summary>Journals I review for</summary><ul>'+''.join(f'<li>{esc(r["title"])}</li>' for r in groups['service'])+'</ul></details><a class="text-link" href="https://www.webofscience.com/wos/author/record/JXO-0029-2024">Web of Science profile</a></div></section>'
    home += '<section class="contact-panel"><p class="eyebrow">Let’s connect</p><h2>Good ideas begin<br>with a conversation.</h2><p>Open to connecting, sharing ideas, and collaborating.</p><a href="mailto:W.Lukito@latrobe.edu.au">Send me an email</a></section>'

    research = intro('Research & publications','Connecting intelligence.<br>Expanding possibility.','Wireless communications is the foundation of my research. I study how learning, sensing, signal processing, and embedded intelligence can shape more capable communication systems.')
    research += '<div class="focus-grid">'+''.join(f'<article><span class="focus-number">0{i}</span><h2>{title}</h2><p>{desc}</p></article>' for i,(title,desc) in enumerate([('Wireless communications','The broad foundation of my work, spanning reliable connectivity, resource efficiency, signal processing, and emerging communication systems.'),('AI, sensing & physical systems','Machine learning, integrated sensing and communications, digital signal processing, embedded systems, and a growing interest in communications for physical AI.'),('Current focus: satellite IoT','Applying AI techniques to make satellite IoT communications more efficient and reliable—one current scenario within my wider wireless communications research.')],1))+'</div>'
    research += '<section class="research-background"><h2>Earlier research interests</h2><p>Before my PhD, I worked on radar signal processing, software-defined radios, and UAV communication systems, including antenna design, impedance matching, and datalink integration. I also explored biomedical image processing.</p></section>'
    years=sorted({r['date'] for r in pubs},reverse=True)
    research += '<section class="section" id="publications">'+section_heading('The work','Publications')+f'''<form class="filters" role="search" hidden><label class="search-label">Search publications<input type="search" id="publication-search" placeholder="Title, author, keyword…" autocomplete="off"></label><label>Type<select id="publication-type"><option value="">All types</option><option>Journal</option><option>Conference</option><option>Poster</option></select></label><label>Year<select id="publication-year"><option value="">All years</option>{''.join(f'<option>{year}</option>' for year in years)}</select></label><button type="reset" class="reset-button">Reset</button></form><p id="result-count" class="small" aria-live="polite">{len(pubs)} publications</p>'''+''.join(map(publication,pubs))+'<p id="empty-results" class="empty-state" hidden>No publications match. Try another keyword or reset the filters.</p></section>'
    projects = intro('Ideas into practice','Projects & explorations.','A place for research tools, experiments, and work beyond the publication.')
    projects += '<section class="card-grid">'+cards(groups['project'])+'</section>' if groups['project'] else '<div class="empty-state"><span class="eyebrow">More to come</span><h2>Work takes many forms.</h2><p>Project write-ups will appear here as they are shared. In the meantime, explore my published research.</p><a class="button" href="/research/">Explore research</a></div>'
    teaching = intro('Teaching & learning','Making complex ideas<br>feel approachable.','Teaching experience across telecommunications, computing, robotics, and embedded systems.')
    for institution in ['La Trobe University, Australia','Bandung Institute of Technology, Indonesia']:
        teaching += '<section class="section">'+section_heading('Courses taught',esc(institution))+'<div class="card-grid">'+cards([r for r in groups['course'] if r['category']=='Teaching' and r['description']==institution])+'</div></section>'
    other=[r for r in groups['course'] if r['category']!='Course development' and not (r['category']=='Teaching' and r['description'] in ['La Trobe University, Australia','Bandung Institute of Technology, Indonesia'])]
    if other: teaching += '<section class="section">'+section_heading('Teaching','Other courses')+'<div class="card-grid">'+cards(other)+'</div></section>'
    teaching += '<section class="section">'+section_heading('Beyond the classroom','Course development & materials')+'<p>I have developed course materials for the following subjects.</p><div class="card-grid">'+cards([r for r in groups['course'] if r['category']=='Course development'])+'</div></section>'
    gallery = intro('Through the lens','A different perspective.','Places, passing moments, and the details that make me stop and look.')+'<div class="photo-grid">'+''.join(map(photo,groups['photo']))+'</div><section class="section gallery-outro"><h2>More stories, elsewhere.</h2><p>I also share travel stories on YouTube and photographs on my private Instagram account.</p><div class="social-links"><a href="https://www.youtube.com/@WDLukito">YouTube</a><a href="https://www.instagram.com/WilliamDLukito">Instagram</a></div></section>'
    contact = intro('Get in touch','Let’s start a conversation.','For research, collaboration, or simply to say hello.')+'<section class="contact-panel"><a href="mailto:W.Lukito@latrobe.edu.au">Send me an email</a><p><a href="https://www.linkedin.com/in/williamdlukito">Connect on LinkedIn</a></p></section>'
    pages=[('', 'About',home,'William Damario Lukito — wireless communications researcher working across AI, sensing, signal processing, embedded systems, satellite IoT, and physical AI communications.'),('research','Research',research,'Research and publications in wireless communications, AI, integrated sensing and communications, signal processing, satellite IoT, and physical AI communications.'),('projects','Projects',projects,'Projects and explorations by William Damario Lukito.'),('teaching','Teaching',teaching,'Teaching and course development at La Trobe University and Bandung Institute of Technology.'),('gallery','Photography',gallery,'Travel photography by William Damario Lukito.'),('contact','Contact',contact,'Contact William Damario Lukito for research and collaboration.')]
    out=ROOT/'_site'
    if out.exists(): shutil.rmtree(out)
    out.mkdir()
    shutil.copytree(ROOT/'assets',out/'assets')
    for slug,title,body,description in pages:
        target=out/slug/'index.html'; target.parent.mkdir(exist_ok=True)
        target.write_text(shell(title,title,body,description))
        if slug: # preserve legacy Jekyll .html links
            (out/(slug+'.html')).write_text(f'<!doctype html><html lang="en"><meta charset="utf-8"><title>Redirecting</title><meta http-equiv="refresh" content="0;url=/{slug}/"><link rel="canonical" href="{SITE}/{slug}/"><a href="/{slug}/">Continue</a></html>')
    (out/'404.html').write_text(shell('Page not found','Not found',intro('404','A little off course.','This page could not be found.')+'<a class="button" href="/">Back to home</a>','Page not found'))
    (out/'.nojekyll').touch()
    (out/'robots.txt').write_text(f'User-agent: *\nAllow: /\nSitemap: {SITE}/sitemap.xml\n')
    (out/'sitemap.xml').write_text('<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'+''.join(f'<url><loc>{SITE}/{slug+"/" if slug else ""}</loc></url>' for slug,*_ in pages)+'</urlset>')
    (out/'build-info.json').write_text(json.dumps({'built_at':datetime.now(timezone.utc).isoformat(),'content_source':source,'records':len(rows)}))
    print(f'Built {len(pages)} pages with {len(rows)} records ({source}) → {out}')

if __name__ == '__main__':
    build()
