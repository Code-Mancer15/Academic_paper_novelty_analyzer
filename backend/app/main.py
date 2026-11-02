import os, json, threading, logging, html
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy import or_
from .database import Base, engine, Session, Paper, Analysis
from .processing import pdf_extract, fingerprint, extract_sections
from .analysis import analyse, LocalLiteratureProvider

@asynccontextmanager
async def lifespan(app):
    Base.metadata.create_all(engine); yield
app=FastAPI(title='Academic Paper Novelty Analyser',lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=[os.getenv('FRONTEND_ORIGIN','http://localhost:5173')],allow_methods=['GET','POST','PUT','DELETE'],allow_headers=['Content-Type'])
class PaperIn(BaseModel):
    title: str = Field(min_length=1,max_length=500)
    authors: str = Field(default='',max_length=500)
    year: int | None = Field(default=None,ge=1000,le=2100)
    abstract: str = Field(default='',max_length=20000)
    keywords: str = Field(default='',max_length=1000)
    topic: str = Field(default='',max_length=200)
    source: str = Field(default='',max_length=1000)
    text: str = Field(default='',max_length=1000000)
    kind: str = Field(default='library',pattern='^(library|submitted)$')
class AnalysisIn(BaseModel): paper_id: int

def paper_dict(p, full=False):
    d={k:getattr(p,k) for k in ('id','title','authors','year','abstract','keywords','topic','source','kind','created_at')}
    if full: d.update(text=p.text,sections=json.loads(p.sections or '{}'))
    return d
def analysis_dict(a, full=False):
    d={k:getattr(a,k) for k in ('id','paper_id','title','status','progress','created_at')}
    if full: d['result']=json.loads(a.result or '{}')
    return d
@app.get('/api/health')
def health(): return {'status':'ok'}
@app.post('/api/papers/upload',status_code=201)
async def upload(file: UploadFile=File(...), kind: str='submitted'):
    if kind not in ('submitted','library'): raise HTTPException(422,'Invalid paper type.')
    if not file.filename or not file.filename.lower().endswith('.pdf'): raise HTTPException(400,'Please upload a PDF file.')
    data=await file.read(10*1024*1024+1)
    if len(data)>10*1024*1024: raise HTTPException(413,'PDF exceeds the 10 MB limit.')
    try: info=pdf_extract(data)
    except ValueError as e: raise HTTPException(400,str(e))
    return save_paper(PaperIn(**{**info,'kind':kind}))
def save_paper(data):
    with Session() as db:
        d=data.model_dump(); d['title']=d['title'].strip()
        if not d['title']: raise HTTPException(422,'A title is required.')
        fp=fingerprint(d['title'],d['abstract'])
        if db.query(Paper).filter_by(fingerprint=fp,kind=d['kind']).first(): raise HTTPException(409,'A paper with the same title and abstract already exists in this collection.')
        sections=extract_sections(d['text']);
        if d['abstract'] and not sections.get('abstract'): sections['abstract']=d['abstract']
        p=Paper(**d,sections=json.dumps(sections),fingerprint=fp); db.add(p); db.commit(); db.refresh(p); return paper_dict(p,True)
@app.post('/api/papers',status_code=201)
def create_paper(data: PaperIn): return save_paper(data)
@app.get('/api/papers')
def list_papers(q: str='', year: int | None=None, topic: str='', kind: str=''):
    with Session() as db:
        query=db.query(Paper)
        if q: query=query.filter(or_(Paper.title.ilike(f'%{q}%'),Paper.authors.ilike(f'%{q}%'),Paper.keywords.ilike(f'%{q}%'),Paper.abstract.ilike(f'%{q}%')))
        if year: query=query.filter(Paper.year==year)
        if topic: query=query.filter(Paper.topic.ilike(f'%{topic}%'))
        if kind: query=query.filter(Paper.kind==kind)
        return [paper_dict(p) for p in query.order_by(Paper.created_at.desc()).all()]
@app.get('/api/papers/{paper_id}')
def get_paper(paper_id:int):
    with Session() as db:
        p=db.get(Paper,paper_id)
        if not p: raise HTTPException(404,'Paper not found.')
        return paper_dict(p,True)
@app.put('/api/papers/{paper_id}')
def update_paper(paper_id:int,data:PaperIn):
    with Session() as db:
        p=db.get(Paper,paper_id)
        if not p: raise HTTPException(404,'Paper not found.')
        d=data.model_dump(); fp=fingerprint(d['title'],d['abstract'])
        if db.query(Paper).filter(Paper.id!=paper_id,Paper.fingerprint==fp,Paper.kind==d['kind']).first(): raise HTTPException(409,'This paper already exists.')
        for k,v in d.items(): setattr(p,k,v)
        sections=extract_sections(p.text); sections['abstract']=p.abstract; p.sections=json.dumps(sections); p.fingerprint=fp; db.commit(); return paper_dict(p,True)
@app.delete('/api/papers/{paper_id}',status_code=204)
def delete_paper(paper_id:int):
    with Session() as db:
        p=db.get(Paper,paper_id)
        if not p: raise HTTPException(404,'Paper not found.')
        for a in db.query(Analysis).filter_by(paper_id=paper_id): a.paper_id=None
        db.delete(p); db.commit()
def run_analysis(id):
    with Session() as db:
        a=db.get(Analysis,id)
        if not a: return
        try:
            a.status='processing'; a.progress='Comparing contributions with your library'; db.commit()
            p=db.get(Paper,a.paper_id)
            if not p: raise ValueError('Paper no longer exists.')
            refs=LocalLiteratureProvider(db,Paper).papers(p.id); result=analyse(p,refs)
            a=db.get(Analysis,id)
            if a: a.result=json.dumps(result); a.status='completed'; a.progress='Analysis complete'; db.commit()
        except Exception:
            logging.exception('Analysis failed')
            db.rollback(); a=db.get(Analysis,id)
            if a: a.status='failed'; a.progress='Analysis failed. Please try again.'; db.commit()
@app.post('/api/analyses',status_code=202)
def create_analysis(data:AnalysisIn,background_tasks:BackgroundTasks):
    with Session() as db:
        p=db.get(Paper,data.paper_id)
        if not p: raise HTTPException(404,'Paper not found.')
        if not (p.abstract or p.text).strip(): raise HTTPException(422,'Add an abstract or paper text before analysis.')
        a=Analysis(paper_id=p.id,title=p.title); db.add(a); db.commit(); db.refresh(a); result=analysis_dict(a)
    background_tasks.add_task(run_analysis,a.id); return result
@app.get('/api/analyses')
def list_analyses():
    with Session() as db: return [analysis_dict(a,True) for a in db.query(Analysis).order_by(Analysis.created_at.desc()).all()]
@app.get('/api/analyses/{analysis_id}')
def get_analysis(analysis_id:int):
    with Session() as db:
        a=db.get(Analysis,analysis_id)
        if not a: raise HTTPException(404,'Analysis not found.')
        return analysis_dict(a,True)
@app.delete('/api/analyses/{analysis_id}',status_code=204)
def delete_analysis(analysis_id:int):
    with Session() as db:
        a=db.get(Analysis,analysis_id)
        if not a: raise HTTPException(404,'Analysis not found.')
        db.delete(a); db.commit()
@app.get('/api/analyses/{analysis_id}/report',response_class=HTMLResponse)
def report(analysis_id:int):
    a=get_analysis(analysis_id)
    if a['status']!='completed': raise HTTPException(409,'Report is not ready.')
    r=a['result']; esc=lambda v:html.escape(str(v or 'Not available'))
    contributions_html=''.join('<li>'+esc(c['text'])+ ('<br>Closest: '+esc(c['match']['title'])+' ('+str(c['match']['score'])+'%)<br>Reference excerpt: '+esc(c['match']['excerpt']) if c['match'] else '<br>No reference available.')+'</li>' for c in r['contributions']) or '<li>No candidate contributions identified.</li>'
    matches_html=''.join('<li><b>'+esc(m['title'])+'</b> — '+esc(m['authors'])+' ('+esc(m['year'])+'), '+str(m['score'])+'% similarity<br>'+esc(m['abstract'])+'<br>Source: '+esc(m['source'])+'</li>' for m in r['matches']) or '<li>No comparable references available.</li>'
    return '<!doctype html><html><head><meta charset="utf-8"><title>Novelty report</title><style>body{font:16px Arial;max-width:850px;margin:40px auto;padding:20px;line-height:1.6;color:#16243d}li{margin-bottom:16px}@media print{button{display:none}}</style></head><body><button onclick="window.print()">Print / Save as PDF</button><h1>Preliminary novelty report</h1><h2>'+esc(r['paper']['title'])+'</h2><p>'+esc(r['paper']['authors'])+'</p><h3>Overview and research problem</h3><p>'+esc(r['problem'])+'</p><h3>Overall indicator</h3><p>'+esc(r['indicators']['overall'] if r['indicators']['overall'] is not None else 'Insufficient evidence')+'</p><p>'+esc(r['formula'])+'</p><h3>Candidate contributions and comparisons</h3><ul>'+contributions_html+'</ul><h3>Related papers</h3><ul>'+matches_html+'</ul><h3>Limitations and next steps</h3><ul>'+''.join('<li>'+esc(x)+'</li>' for x in r['limitations'])+'<li>Verify each contribution and investigate the cited references and broader literature.</li></ul></body></html>'

@app.post('/api/demo',status_code=200)
def seed_demo():
    # Fictional examples are expressly labelled, never presented as academic references.
    examples=[
        {'title':'DEMO (fictional): A graph-based approach to campus energy forecasting','authors':'Synthetic example — not a publication','year':2024,'abstract':'We propose a graph-based forecasting framework for estimating energy consumption across campus buildings. The method combines building connectivity and historical usage to improve short-term demand forecasts.','keywords':'energy forecasting, graph learning','topic':'Energy forecasting','source':'Synthetic demonstration data; not a real paper'},
        {'title':'DEMO (fictional): Evaluating temporal models for building energy demand','authors':'Synthetic example — not a publication','year':2023,'abstract':'We present a benchmark of temporal prediction methods for building energy demand. The evaluation compares forecasting accuracy under missing sensor observations.','keywords':'energy forecasting, benchmark','topic':'Energy forecasting','source':'Synthetic demonstration data; not a real paper'}]
    added=0
    for d in examples:
        try: save_paper(PaperIn(**d,kind='library')); added+=1
        except HTTPException as e:
            if e.status_code!=409: raise
    return {'added':added,'message':'Synthetic demo papers added. These are not real publications.'}
