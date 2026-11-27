"""Read-only previews of existing branding assets; never writes to the website."""
from pathlib import Path
import json, subprocess
from PIL import Image, ImageDraw, ImageOps
import pypdfium2 as pdfium
from pypdf import PdfReader

OUT = Path(__file__).resolve().parent
ROOT = OUT.parent.parent / '2mcrafters.com'
PRE = OUT / 'previews'
PRE.mkdir(exist_ok=True)

def sheet(items, name, cell=(320, 290), columns=3):
    canvas = Image.new('RGB', (cell[0]*columns, cell[1]*((len(items)+columns-1)//columns)), '#e7e7e7')
    d = ImageDraw.Draw(canvas)
    for i,(p,label) in enumerate(items):
        im=Image.open(p).convert('RGBA')
        bg=Image.new('RGBA', im.size, '#a8b0b8'); bg.alpha_composite(im)
        im=ImageOps.contain(bg.convert('RGB'), (cell[0]-16,cell[1]-55))
        x=(i%columns)*cell[0]; y=(i//columns)*cell[1]
        canvas.paste(im,(x+(cell[0]-im.width)//2,y+5))
        for j in range(0,len(label),43): d.text((x+7,y+cell[1]-48+(j//43)*13),label[j:j+43],fill='black')
    canvas.save(PRE/name,quality=88)

selected = [p for p in ROOT.rglob('*') if p.is_file() and p.suffix in ('.png','.webp','.jpg') and (
    any(k in p.name for k in ('portrait','badge-photo','robot-','logo')) or
    p.parent.name=='icons' or (p.parent.name=='mohamedandaloussi' and 'icon' in p.name) or
    p.relative_to(ROOT).as_posix()=='og/mohamedandaloussi.jpg')]
for i in range(0,len(selected),15):
    sheet([(p,p.relative_to(ROOT).as_posix()) for p in selected[i:i+15]],f'identity-assets-{i//15+1}.jpg')

docs=[]
for p in ROOT.rglob('*.pdf'):
    pdf=pdfium.PdfDocument(str(p)); reader=PdfReader(p)
    record={'path':str(p),'pages':len(pdf),'metadata':{str(k):str(v) for k,v in (reader.metadata or {}).items()},'pageText':[],'links':[]}
    for i,page in enumerate(pdf):
        w,h=page.get_size(); scale=min(1600/w,3500/h)
        page.render(scale=scale).to_pil().save(PRE/f'{p.stem}-page-{i+1}.png')
        record['pageText'].append(reader.pages[i].extract_text() or '')
        record['links'] += [str(a.get_object().get('/A','')) for a in reader.pages[i].get('/Annots',[])]
    docs.append(record)
(OUT/'pdf-inventory.json').write_text(json.dumps(docs,ensure_ascii=False,indent=2),encoding='utf-8')

videos=[]; frames=[]
for p in sorted(ROOT.rglob('*.mp4')):
    info=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration:stream=width,height,codec_name','-of','json',str(p)],text=True))
    duration=float(info.get('format',{}).get('duration',0))
    videos.append({'path':str(p),'relativePath':p.relative_to(ROOT).as_posix(),'durationSeconds':duration,'streams':info.get('streams',[])})
    for j,fraction in enumerate((0.1,0.5,0.9)):
        dst=PRE/f'video-{len(videos):02d}-{j}.jpg'
        subprocess.run(['ffmpeg','-v','error','-ss',str(duration*fraction),'-i',str(p),'-frames:v','1','-vf','scale=360:-1','-y',str(dst)],check=True,capture_output=True)
        frames.append((dst,p.name+f' ({fraction*100:.0f}%)'))
for i in range(0,len(frames),15): sheet(frames[i:i+15],f'video-review-{i//15+1}.jpg',cell=(360,275))
(OUT/'video-inventory.json').write_text(json.dumps(videos,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'identityImages':len(selected),'pdfDocuments':len(docs),'videos':len(videos),'previewSheets':[p.name for p in PRE.glob('*review*.jpg')]}))
