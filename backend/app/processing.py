import re, hashlib, json
import fitz

HEADINGS = {'abstract': r'abstract', 'introduction': r'(?:\d+[.\s]*)?introduction', 'methodology': r'(?:\d+[.\s]*)?(?:methodology|methods|materials and methods)', 'results': r'(?:\d+[.\s]*)?(?:results|experiments|experimental results)', 'conclusion': r'(?:\d+[.\s]*)?(?:conclusion|conclusions|discussion and conclusion)'}
def clean(text):
    return re.sub(r'\n{3,}', '\n\n', text.replace('\x00','')).strip()
def extract_sections(text):
    # Headings should occupy a line; inline Abstract is handled separately.
    pattern = re.compile(r'^\s*('+'|'.join('(?:'+v+')' for v in HEADINGS.values())+r')\s*[:.]?\s*$', re.I|re.M)
    matches = list(pattern.finditer(text)); out = {}
    for i,m in enumerate(matches):
        name = next((k for k,v in HEADINGS.items() if re.fullmatch(v,m.group(1).strip(),re.I)),None)
        if name and name not in out: out[name] = text[m.end():matches[i+1].start() if i+1<len(matches) else len(text)].strip()[:15000]
    if not out.get('abstract'):
        m = re.search(r'\babstract\s*[:—-]\s*(.+?)(?=\n\s*(?:keywords|\d*\.?\s*introduction)\b|\n\n|$)',text,re.I|re.S)
        if m: out['abstract'] = m.group(1).strip()[:5000]
    return out

def pdf_extract(data):
    if not data.startswith(b'%PDF-'): raise ValueError('The file is not a valid PDF.')
    try:
        doc=fitz.open(stream=data,filetype='pdf')
        if doc.is_encrypted: raise ValueError('Password-protected PDFs are not supported.')
        if len(doc)==0: raise ValueError('This PDF has no pages.')
        if len(doc)>300: raise ValueError('PDFs are limited to 300 pages.')
        text=clean('\n'.join(page.get_text() for page in doc)); metadata=doc.metadata or {}; doc.close()
    except ValueError: raise
    except Exception: raise ValueError('The PDF is malformed or could not be read.')
    if len(re.sub(r'\s','',text))<50: raise ValueError('No usable text found. This may be a scanned or image-only PDF; OCR is not available.')
    sections=extract_sections(text)
    lines=[x.strip() for x in text.splitlines() if len(x.strip())>8]
    title=(metadata.get('title') or (lines[0] if lines else 'Untitled paper'))[:500]
    kw=re.search(r'\b(?:keywords|index terms)\s*[:—-]\s*([^\n]+)',text,re.I)
    return {'title':title,'authors':(metadata.get('author') or '')[:500],'abstract':sections.get('abstract','')[:10000], 'keywords':kw.group(1)[:1000] if kw else '', 'text':text[:1000000], 'sections':sections}
def fingerprint(title, abstract): return hashlib.sha256((title.strip().lower()+'|'+abstract.strip().lower()).encode()).hexdigest()

def contributions(text, sections):
    selected='\n'.join(sections.get(x,'') for x in ('abstract','introduction','conclusion')) or text[:20000]
    sentences=re.split(r'(?<=[.!?])\s+', re.sub(r'\s+',' ', selected))
    pattern=re.compile(r'\b(propos\w*|introduc\w*|develop\w*|present\w*|contribut\w*|novel|framework|dataset|benchmark|improv\w*|achiev\w*|we (?:show|demonstrate|find))\b',re.I)
    found=[]
    for s in sentences:
        s=s.strip()
        if 35<=len(s)<=700 and pattern.search(s) and s not in found: found.append(s)
        if len(found)>=6: break
    return [{'text':s,'excerpt':s} for s in found]
