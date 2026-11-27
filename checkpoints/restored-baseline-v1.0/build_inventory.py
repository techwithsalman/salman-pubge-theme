"""Generate a read-only branding inventory from the frozen website files."""
from pathlib import Path
from html.parser import HTMLParser
from html import escape, unescape
from collections import Counter, defaultdict
from datetime import datetime, timezone
from urllib.parse import urlsplit, unquote
import json, re, csv
from PIL import Image

OUT=Path(__file__).resolve().parent
ROOT=OUT.parent.parent/'2mcrafters.com'
MAN=json.loads((OUT/'website-manifest.json').read_text(encoding='utf-8'))
FILES={x['path']:x for x in MAN['files']}
TEXT_EXT={'.html','.txt','.js','.css','.json','.webmanifest','.svg','.py','.bak'}
TEXT={p:p0.read_text(encoding='utf-8',errors='replace') for p in FILES if (p0:=ROOT/p).suffix in TEXT_EXT}

class Page(HTMLParser):
    def __init__(self):
        super().__init__(); self.hidden=0; self.intitle=False; self.title=''; self.meta=[]; self.links=[]; self.media=[]; self.text=[]; self.jsonld=[]; self.injson=False; self.jsontext=''
    def handle_starttag(self,t,attrs):
        a=dict(attrs)
        if t in ('script','style'): self.hidden+=1
        if t=='script' and a.get('type')=='application/ld+json': self.injson=True;self.jsontext=''
        if t=='title': self.intitle=True
        if t=='meta': self.meta.append(a)
        if t in ('a','link') and a.get('href'): self.links.append({'tag':t,**a})
        if t in ('img','source','video'): self.media.append({'tag':t,**a})
    def handle_endtag(self,t):
        if t=='script' and self.injson:
            self.jsonld.append(self.jsontext);self.injson=False
        if t in ('script','style'): self.hidden=max(0,self.hidden-1)
        if t=='title':self.intitle=False
    def handle_data(self,t):
        if self.intitle:self.title+=t
        if self.injson:self.jsontext+=t
        if not self.hidden and t.strip():self.text.append(t.strip())

PATTERNS={
 'Personal name / aliases':r"Mohamed\s+Andaloussi(?:\s+L['’]Khaoua)?|Andaloussi\s+Mohamed|Andalossi\s+Mohamed|M\.\s*ANDALOUSSI|L['’]Khaoua|محمد\s+الأندلسي",
 'Personal email':r'andalossi90@gmail\.com',
 'Personal phone / WhatsApp':r'\+?212[ -]?688[ -]?284[ -]?783',
 'Personal social handles':r'mhmedaloui|andaluussi|mohamed\.andalossi\.5070|(?:linkedin\.com/in/|github\.com/)mohamedandaloussi|guru_graphixx',
 'Personal marks / terminal / TV':r'MA//(?:VERSE|OS|TV)|M\.\s*ANDALOUSSI',
 'Personal route / canonical identity':r'mohamedandaloussi',
 'Location / professional biography':r'Tangier|Tanger|طنجة|Tanja Marina|ISMONTIC|Makers TEXLAB|Conceptify|Abi Abbas Sebti|Graphic Designer|Full.Stack Developer',
 'Agency identity / company credit':r'2M\s*Crafters|2mcrafters\.com',
 'Agency contacts':r'2m\.crafters@gmail\.com|\+?212[ -]?679[ -]?805[ -]?494|\+?212[ -]?5[ -]?39[ -]?42[ -]?61[ -]?05',
 'Contact / newsletter backend':r'form-handler\.php|projectType:"MA//VERSE"',
 'CV / portfolio download':r'CV\.pdf|portfolio\.pdf',
 'Profile / character media references':r'portrait-800|portrait-jacket|badge-photo|robot-body|robot-hand|Graphic_designer\.mp4|IT\.mp4|editing\.mp4|photog\.mp4|meta\.mp4',
 'Logos / favicon / social previews':r'2mcrafters-logo|apple-icon-tv2ix7|icon[12]-tv2ix7|icons/(?:icon-|maskable-)|og/mohamedandaloussi',
 'Metadata / structured data':r'og:|twitter:|application/ld\+json|rel="canonical"|"short_name"',
}
hits=[]; bycat=defaultdict(list)
for path,s in TEXT.items():
    for cat,expr in PATTERNS.items():
        matches=list(re.finditer(expr,s,re.I))
        if not matches:continue
        samples=[]
        for m in matches[:5]:
            line=s.count('\n',0,m.start())+1; line_start=s.rfind('\n',0,m.start())
            samples.append({'line':line,'column':m.start()-line_start,'value':m.group(), 'context':s[max(0,m.start()-75):m.end()+110]})
        row={'category':cat,'path':path,'absolutePath':str(ROOT/path),'occurrences':len(matches),'sampleLocations':samples,'archivalOrHelper':path.endswith(('.bak','.py')) and path!='serve.py'}
        hits.append(row);bycat[cat].append(path)

pages=[]
for path,s in TEXT.items():
    if not path.endswith('.html'):continue
    p=Page();p.feed(s)
    pages.append({'path':path,'absolutePath':str(ROOT/path),'title':p.title,'metadata':p.meta,'links':p.links,'media':p.media,'structuredData':p.jsonld,'visibleText':p.text})

assets=[]
for path,f in FILES.items():
    p=ROOT/path
    if p.suffix.lower() not in {'.png','.jpg','.jpeg','.webp','.avif','.svg','.mp4','.pdf','.ico','.woff','.woff2','.ttf','.otf','.glb','.gltf','.obj','.hdr','.exr','.ktx','.ktx2'}:continue
    category='Preserve: shared imagery / texture / font'
    if path.startswith('_ext/local-image-cache/'):category='Review only if a related project changes: cached stock imagery'
    if '/portfolio/' in path:category='Portfolio: client project imagery'
    if '/profile/optimized/' in path:category='Portfolio: 34 client artwork designs and responsive copies'
    if '/mohamedandaloussi/posts/' in path:category='Agency portfolio: 15 Crafters promotional designs and responsive copies'
    if '/brand/' in path or path.startswith('icons/'):category='Agency logos / PWA icons'
    if 'portrait' in p.name or 'badge-photo' in p.name:category='Personal portrait / character cutout'
    if 'robot-body' in p.name or 'robot-hand' in p.name:category='Character: robot body / separately animated hand (approval required)'
    if path.startswith('mohamedandaloussi/') and 'icon' in p.name:category='Personal portrait favicon / Apple touch icon'
    if path=='og/mohamedandaloussi.jpg':category='Personal Open Graph screenshot with portrait and name'
    if p.suffix=='.mp4':
        category='Personal portrait video' if '/profile/' in path else ('Portfolio: recorded project video' if p.name.startswith('case-') else 'Preserve: animated room background')
    if p.name=='CV.pdf':category='Personal CV document: text and embedded portrait'
    if p.name=='portfolio.pdf':category='Personal portfolio document: portrait, contact and client work'
    row={'category':category,**f}
    if p.suffix.lower() in {'.png','.jpg','.jpeg','.webp','.avif'}:
        with Image.open(p) as im:row.update(width=im.width,height=im.height,mode=im.mode)
    assets.append(row)

projects=[]
for p in sorted((ROOT/'mohamedandaloussi/work').glob('*/index.html')):
    slug=p.parent.name; page=next(x for x in pages if x['path']==p.relative_to(ROOT).as_posix())
    routefiles=[x for x in FILES if re.search(r'/work/'+re.escape(slug)+r'(?:/|\.)',x)]
    media={x['path'] for x in assets if slug.replace('-','').lower() in Path(x['path']).name.replace('-','').lower()}
    hero=set(); other_page_media=set()
    for index,element in enumerate(page['media']):
        urls=[element.get('src',''),element.get('poster','')]
        urls += [part.strip().split(' ')[0] for part in element.get('srcset','').split(',') if part.strip()]
        for url in urls:
            rel=unquote(urlsplit(url).path).lstrip('/')
            if rel in FILES:
                other_page_media.add(rel)
                if index==0:hero.add(rel)
    # Include every responsive derivative and original of the numbered hero.
    for rel in list(hero):
        m=re.search(r'_img/(.+?\.(?:jpg|png|webp))-\d+\.webp$',rel)
        if m:
            hero.update(x for x in FILES if x.startswith('_img/'+m[1]+'-') or x=='images/'+m[1])
    media.update(hero)
    references=[x for x,s in TEXT.items() if slug in s]
    projects.append({'slug':slug,'title':page['title'].split(' | ')[0],'page':str(p),'routeFiles':[str(ROOT/x) for x in routefiles],'heroAssetFiles':[str(ROOT/x) for x in sorted(hero)],'matchingAssetFiles':[str(ROOT/x) for x in sorted(media)],'pageMediaIncludingNextProject':[str(ROOT/x) for x in sorted(other_page_media)],'referenceFiles':[str(ROOT/x) for x in references], 'outboundLinks':sorted({x['href'] for x in page['links'] if x['tag']=='a' and x['href'].startswith('http')})})

entities=defaultdict(set)
for path,s in TEXT.items():
    for expr in [r'[\w.+%-]+@[\w.-]+\.[A-Za-z]{2,}',r'\+212[\d ()-]{8,20}',r'https?://(?:www\.)?(?:linkedin\.com|instagram\.com|facebook\.com|github\.com|behance\.net|wa\.me)/[^\s"<>\\}]*']:
        for m in re.finditer(expr,s):entities[m.group().rstrip(' /,;')].add(path)
entityrows=[{'value':v,'fileCount':len(ps),'files':[str(ROOT/p) for p in sorted(ps)],'scope':('Personal' if any(x in v.lower() for x in ['andal','mhmedaloui','688284783','688 284 783']) else 'Agency / client / example; review before any replacement')} for v,ps in sorted(entities.items())]

data={'generatedUTC':datetime.now(timezone.utc).isoformat(),'root':str(ROOT),'baselineTag':'restored-baseline-v1.0','scope':'Read-only inventory; no replacements approved or applied. Exact per-file listings; hit contexts are first five per category/file, counts include every regex match. Dynamic constructions require the related compiled module to be reviewed.','counts':{'siteFiles':len(FILES),'scannedTextFiles':len(TEXT),'htmlPages':len(pages),'personalHTMLPages':sum(x['path'].startswith('mohamedandaloussi/') for x in pages),'assets':len(assets),'projectPages':len(projects),'categoryFileRecords':len(hits)},'textOccurrences':hits,'assets':assets,'projects':projects,'contactEntities':entityrows}
(OUT/'branding-inventory.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
(OUT/'page-metadata-and-content.json').write_text(json.dumps(pages,ensure_ascii=False,indent=2),encoding='utf-8')
with (OUT/'branding-file-index.tsv').open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.writer(f,delimiter='\t');w.writerow(['Category','Absolute file path','Occurrences','First line','First column','Original value / dimensions'])
    for x in hits:w.writerow([x['category'],x['absolutePath'],x['occurrences'],x['sampleLocations'][0]['line'],x['sampleLocations'][0]['column'],x['sampleLocations'][0]['value']])
    for x in assets:w.writerow([x['category'],x['absolutePath'],'','','',f"{x.get('width','')} x {x.get('height','')}"])

def e(x):return escape(str(x))
def paths(items):return '<ul class="paths">'+''.join('<li><code>'+e(ROOT/x if not Path(x).is_absolute() else x)+'</code></li>' for x in sorted(set(items)))+'</ul>'
def table(headers,rows):return '<table><thead><tr>'+''.join('<th>'+e(x)+'</th>' for x in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+str(x)+'</td>' for x in row)+'</tr>' for row in rows)+'</tbody></table>'
def section(title,body):return '<section><h2>'+e(title)+'</h2>'+body+'</section>'
body='<h1>Restored baseline — personal branding inventory</h1><p>27 November 2026 · Read-only inventory · Tag <code>restored-baseline-v1.0</code></p>'
body+='<p><strong>No website content, design, layout, animation, background, font, colour, spacing or functionality was changed during this phase.</strong> All future replacements require your supplied content and section-specific approval.</p>'
body+=section('Checkpoint scope',f'<p>Website root: <code>{e(ROOT)}</code><br>Verified restored backup: <code>{e(OUT.parent.parent/"backups/restored-baseline-v1.0/website")}</code><br>{len(FILES):,} files · {MAN["bytes"]:,} bytes · source and backup SHA-256 verified. Git stores the website and this checkpoint documentation. Prior audit/restoration evidence and backups remain outside Git, unchanged.</p><p>This is a checkpoint of the existing restored state, not a claim of 100% restoration. Prior limitations remain as described in the restoration report. The compiled Next.js runtime, route files, 14 videos, cached images, fonts, textures and routing server are included.</p>')
body+=section('Report files and how to use them','<p><a href="branding-file-index.tsv">Exact file index (TSV)</a> · <a href="branding-inventory.json">Full inventory (JSON)</a> · <a href="page-metadata-and-content.json">Every HTML page: metadata, links, image attributes and visible text</a> · <a href="website-manifest.json">All 3,359 file hashes</a> · <a href="RECOVERY.txt">Recovery instructions</a></p><p>Paths below are exact existing files, not replacement instructions. The TSV/JSON enumerate all discovered files, including translated HTML and Next.js route data. Most JavaScript is minified: use the recorded line, column, value and context rather than relying on line numbers alone. Automated text matching does not OCR every embedded image or every video frame.</p>')
identity=[('Full name',"Mohamed Andaloussi L’Khaoua / Mohamed Andaloussi L'Khaoua"),('Display and badge names','Mohamed Andaloussi; MOHAMED ANDALOUSSI; M. ANDALOUSSI; Andalossi Mohamed (PDF)'),('Personal brand marks','MA monogram; MA//VERSE; MA//OS; MA//TV; initials used by interactive UI/world'),('Roles and location','Creative Developer / Graphic Designer / Full-Stack Developer / Video Editor; Tangier, Morocco'),('Company credit','2M Crafters; 2mcrafters.com'),('Telephone and WhatsApp','+212688284783; +212 688 284 783; +212 688-284783 (PDF)'),('Email','andalossi90@gmail.com; uppercase UI variant ANDALOSSI90@GMAIL.COM'),('Website','https://2mcrafters.com/mohamedandaloussi'),('LinkedIn','https://www.linkedin.com/in/mohamedandaloussi'),('Instagram (website)','https://www.instagram.com/andaluussi/'),('Instagram (portfolio PDF)','guru_graphixx — visibly different from website handle'),('GitHub','https://github.com/mohamedandaloussi'),('Facebook','https://www.facebook.com/mohamed.andalossi.5070/'),('Behance','https://www.behance.net/mhmedaloui'),('WhatsApp greeting',"Hello Mohamed, I saw your portfolio and I'd like to discuss a project.")]
body+=section('Identity, contact details and social links',table(['Element','Existing value'],[(e(a),e(b)) for a,b in identity])+'<p>These appear in navigation, footer, mobile/contact overlays, hero badge, terminal/search/OS interfaces, dedicated pages, alt text, translated copy, metadata and route payloads. Exact locations follow in the file index.</p>')
primary=sorted({x['path'] for x in hits if x['category'] in ['Personal name / aliases','Personal marks / terminal / TV','Personal social handles'] and x['path'].endswith('.js')})
body+=section('Primary compiled identity and interaction files',paths(primary)+'<p>Identity configuration module <code>76358</code> is duplicated across several chunks. The 7552 and 5911 chunks also construct WhatsApp/mailto/tel actions. Chunk 8447 contains the laptop badge, portrait references and CV rendering. Chunk 877 contains translated biography/CV/UI dictionaries. Chunk 7431 contains world UI labels. The standalone layout chunk supplies shared portfolio navigation and identity. No editable React/TypeScript source project was found in this download.</p>')
for title,cats,description in [
 ('Profile photographs, portrait icons and character images',['Personal portrait / character cutout','Personal portrait favicon / Apple touch icon','Character: robot body / separately animated hand (approval required)'],'The badge photo, three jacket cutouts, profile portrait and its four generated image variants contain the original person. The six portfolio favicon/Apple icon files are also portraits. The robot is a separate character, with body/hand animation layers; retain it unless specifically approved. Replacement images must later retain the required dimensions, transparency and crop behaviour.'),
 ('Personal logos, favicon and social-share images',['Agency logos / PWA icons','Personal Open Graph screenshot with portrait and name'],'Personal MA marks are generated in UI/SVG/3D code, not a single downloadable logo file. The Crafters PNGs and nine generated logo variants are a separate agency identity. The personal OG image is an old website screenshot with a portrait and name. Agency OG images are listed in the complete asset inventory and remain unchanged.'),
 ('TV, cinema and other video content',['Personal portrait video','Portfolio: recorded project video','Preserve: animated room background'],'Five profile videos visibly depict the original person. Seven case videos contain project/client/agency content. Two office videos are room scenery and should remain unchanged. Three frames per video (10%, 50%, 90%) were inspected; this is not a frame-by-frame audit. See video-inventory.json for every path, duration and codec.'),
 ('CV and portfolio documents',['Personal CV document: text and embedded portrait','Personal portfolio document: portrait, contact and client work'],'Both PDFs contain one page. The CV includes a portrait, name, contact, biography, career, education, skill levels and languages. The long portfolio sheet contains portraits, name, +7 years / +221 projects / +149 clients claims, client artwork/logos, contact details and Instagram guru_graphixx. Most PDF content is raster artwork, so changing HTML will not update these documents. PDF metadata and extracted text are recorded in pdf-inventory.json; page previews were visually reviewed.'),
 ('Artwork, project imagery and agency promotional posts',['Portfolio: client project imagery','Portfolio: 34 client artwork designs and responsive copies','Agency portfolio: 15 Crafters promotional designs and responsive copies'],'The profile/optimized folder contains 34 original client artwork designs with responsive and hashed duplicate variants. The posts folder contains 15 Crafters promotional designs at two sizes; it is not a personal portrait collection. These images may contain client names, telephone numbers, logos and faces baked into pixels. Do not replace client identities globally. Each portfolio item needs a retain/replace decision and authorized replacement artwork.')]:
    items=[a for a in assets if a['category'] in cats]
    body+=section(title,'<p>'+e(description)+'</p>'+f'<details><summary>{len(items)} exact asset paths</summary>'+paths([x['path'] for x in items])+'</details>')

cvpages=[p['path'] for p in pages if re.search(r'/(?:cv|experience|education|about|lab)/index\.html$',p['path']) and p['path'].startswith('mohamedandaloussi/')]
body+=section('CV information and translated biography', '<p>Review all biography, job titles, employers, dates, responsibilities, education, qualifications, technical skills, proficiency levels, language levels, soft skills, city/country and download labels. The digital CV currently lists five career entries and four education entries. Its languages include Arabic, French, English and Spanish; the PDF visibly lists French and English. Preserve each existing version until replacement wording is approved.</p><p>Education dates in the digital CV: Digital Marketing &amp; AI 2025–2026; ISMONTIC 2023–2025; Udemy 2022–2023; baccalaureate 2021–2022. These are recorded values, not independently validated credentials.</p>'+paths(cvpages)+'<p>Related route .txt files and dictionaries are included in the full text index. Download files are listed above.</p>')
body+=section('Business cards, badge and contact overlays','<p>The hero badge is rendered from HTML/CSS and badge-photo.webp. Its fields include M. ANDALOUSSI, DESIGN × CODE and the Instagram handle. The contact card/phone interface is generated from the shared identity object, including name, role, city, phone, WhatsApp, email, website and social actions. These need coordinated text and photo updates after approval; they are not replaceable as one flat screenshot. No dedicated .vcf/vCard or standalone business-card image was found in the file/extension scan.</p>'+paths(['_next/static/chunks/8447-c2247280dfd2b6a2.js','_next/static/chunks/7552-e6e362ff53e10644.js','_next/static/chunks/5911-58f891d622708b1e.js','_next/static/chunks/559-06d0d4e9a619d081.js','images/mohamedandaloussi/laptop/badge-photo.webp']))
body+=section('All 15 dedicated portfolio projects',table(['Project','Main page','Hero assets / responsive copies','Route/data files'],[(e(x['title']),'<code>'+e(x['page'])+'</code>',paths(x['heroAssetFiles']),str(len(x['routeFiles']))) for x in projects])+'<p>Each project inventory record lists all EN/FR/AR/ES page and route data paths, title, outbound links, numbered hero assets, matching videos and code/data references. Media for the next-project preview and phone frame is recorded separately to avoid confusing it with the current project. Review titles, descriptions, sector, studio credit, live URL, thumbnail/hero imagery and next-project links. The seven laptop case videos include additional project/demo content and are listed separately above. Agency demo pages and stock-image caches are also retained in the full page and asset indexes.</p>')
body+=section('Website metadata and route identity','<p>Review HTML title/description, canonical and hreflang URLs, Open Graph and Twitter text/images, Person/Organization structured data, name, jobTitle, sameAs, social/contact URLs, author/copyright credits, icon references and localized head data. The full page-metadata-and-content.json file records every HTML page and exact path. Matching .txt payloads (including __next._head.txt) must stay consistent with HTML.</p><p>The /mohamedandaloussi/ slug appears in navigation, prefetch/router payloads, assets, canonical URLs and serialized Next.js data. A future rename needs a separate routing migration. Do not perform a blind global replacement: compiled Flight text lengths and chunk consistency must be preserved. The previous initialization defect was caused by an inconsistent serialized text length.</p>'+paths(['manifest.webmanifest','mohamedandaloussi/index.html','mohamedandaloussi/cv/index.html','og/mohamedandaloussi.jpg'])+'<p>The manifest contains the separate 2M Crafters agency name, short_name, French description and PWA icon paths. Existing display mode, scope, theme/background colours and start_url remain unchanged. No favicon.ico or external 3D model file was found; portrait PNG icons and generated geometry are used.</p>')
formfiles=bycat['Contact / newsletter backend']
body+=section('Contact form and genuinely external delivery configuration','<p>Personal form: POST /form-handler.php with JSON fields type=contact, fullName, email, message, projectType=MA//VERSE, the website honeypot, current page URL and document locale. The same compiled helper supports agency contact/newsletter flows. The local serve.py forwards explicit submissions to https://2mcrafters.com/form-handler.php; it preserves the browser origin and does not implement mail delivery locally.</p><p><strong>The recipient mailbox and server-side PHP/mail configuration are not present in the download and cannot be inferred from the displayed email address.</strong> A future branding phase must supply an approved form destination/backend before changing delivery. No form was submitted during this checkpoint. Existing functionality remains intact.</p>'+paths(formfiles))
body+=section('Separate agency contacts and embedded client information','<p>Agency records include 2m.crafters@gmail.com, +212539426105 and +212679805494. They are distinct from Mohamed’s personal details. Demo pages also contain .example email addresses and demonstration phone numbers. Client posters and recorded project pages contain additional baked-in client information. These are review-only entries, not automatic replacement targets.</p>'+table(['Value','Files','Scope'],[(e(x['value']),str(x['fileCount']),e(x['scope'])) for x in entityrows])+'<p>The JSON contactEntities array gives every exact source path for each detected value.</p>')
body+=section('Exhaustive text-file index', ''.join('<details><summary>'+e(cat)+f' — {len(set(paths0))} files</summary>'+paths(paths0)+'</details>' for cat,paths0 in bycat.items())+'<p>Some references exist in archived .httrack.bak files or download helper scripts. These are identified as archival/helper records in JSON and should remain historical evidence rather than being edited as live UI.</p>')
body+=section('Preservation and approval boundaries','<p>Keep all CSS, fonts, responsive sizes, layout/spacing, colours, motion timing, camera paths, interactions, generic room/TV backgrounds, flora/ground textures and 3D rendering code unchanged. The inventory identifies content dependencies; it does not authorize replacing them. Cached stock imagery is fully enumerated in the asset index and mapped by local-image-cache.json. Generic scenery and client/agency content must not be mistaken for the original person’s portrait.</p><p>Future approval groups: (1) name/contact/social; (2) portraits and portrait icons; (3) character imagery; (4) personal marks and badge; (5) profile videos; (6) CV/PDF and biography; (7) individual projects/artworks; (8) metadata and routing; (9) contact delivery; (10) separate agency identity, if requested. No replacement content has been applied.</p><p>Inspection limits: text/code, file metadata, both PDF pages, identity assets, 34 artwork thumbnails, 15 agency posters and three sample frames of each of 14 videos were reviewed. Not every cached stock image or every video frame was OCR-reviewed. Dynamic labels and embedded raster text require a final section-specific review before future changes.</p>')
body+=section('Visual inventory evidence',''.join(f'<p><a href="previews/{e(p.name)}">{e(p.name)}</a></p>' for p in sorted((OUT/'previews').glob('*')) if p.name.startswith(('identity-assets','video-review','CV-page','portfolio-page','portfolio-posts','profile-scenes'))))
style='body{font:16px/1.55 system-ui,sans-serif;max-width:1200px;margin:40px auto;padding:0 24px;color:#172335;background:#fff}h1{font-size:32px}h2{font-size:23px;margin-top:38px}table{border-collapse:collapse;width:100%;font-size:14px}th,td{border:1px solid #ccd4dc;padding:10px;vertical-align:top;text-align:left}th{background:#eff3f7}code{overflow-wrap:anywhere;font-size:12px}.paths{font-size:13px;padding-left:22px}details{border:1px solid #ccd4dc;margin:12px 0;padding:12px}summary{cursor:pointer;font-weight:600}a{color:#145dad}section{break-inside:avoid}p{max-width:1050px}'
(OUT/'branding-inventory.html').write_text('<!doctype html><html lang="en"><meta charset="utf-8"><title>Restored baseline branding inventory</title><style>'+style+'</style><body>'+body+'</body></html>',encoding='utf-8')
parser=Page();parser.feed(body)
(OUT/'branding-inventory.txt').write_text('\n'.join(parser.text)+'\n',encoding='utf-8')
print(json.dumps(data['counts']))
