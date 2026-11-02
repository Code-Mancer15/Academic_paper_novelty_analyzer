import os
os.environ['DATABASE_URL']='sqlite:///./test_novelty.db'
from fastapi.testclient import TestClient
import fitz
import pytest
from app.main import app
from app.database import Base, engine
from app.processing import pdf_extract, contributions, extract_sections
from app.analysis import similarities

@pytest.fixture
def client():
    Base.metadata.drop_all(engine); Base.metadata.create_all(engine)
    with TestClient(app) as c: yield c
    Base.metadata.drop_all(engine)

def pdf(text):
    doc=fitz.open(); page=doc.new_page(); page.insert_textbox(fitz.Rect(40,40,550,750),text,fontsize=11); b=doc.tobytes();doc.close();return b

def test_health(client): assert client.get('/api/health').json()=={'status':'ok'}
def test_upload_and_metadata(client):
    data=pdf('A Sample Research Paper\nAbstract\nWe propose a new framework for analysing energy demand in campus buildings.\nIntroduction\nThis paper presents a useful new approach for forecasting energy usage.')
    r=client.post('/api/papers/upload',files={'file':('paper.pdf',data,'application/pdf')}); assert r.status_code==201
    assert 'Sample' in r.json()['title']; assert 'propose' in r.json()['abstract']; assert client.get('/api/papers/'+str(r.json()['id'])).status_code==200

def test_bad_uploads(client):
    assert client.post('/api/papers/upload',files={'file':('x.txt',b'hello','text/plain')}).status_code==400
    assert client.post('/api/papers/upload',files={'file':('x.pdf',b'%PDF-broken','application/pdf')}).status_code==400
    assert client.post('/api/papers/upload',files={'file':('x.pdf',pdf(''),'application/pdf')}).status_code==400
    assert client.post('/api/papers/upload',files={'file':('x.pdf',b'x'*(10*1024*1024+1),'application/pdf')}).status_code==413

def test_processing():
    text='Abstract\nWe propose a novel framework for analysing campus energy usage.\nIntroduction\nBackground text.\nConclusion\nWe demonstrate improved forecasting performance with our method.'
    sections=extract_sections(text); assert 'abstract' in sections and 'conclusion' in sections
    assert len(contributions(text,sections))>=1
    assert contributions('Ordinary text without any useful sentences.',{})==[]

def test_similarity():
    vals,method=similarities('campus energy demand forecasting',['campus energy demand forecasting','marine ecology'])
    assert vals[0]>vals[1];assert method=='tf-idf'

def test_analysis_and_report(client):
    ref=client.post('/api/papers',json={'title':'Reference','abstract':'We propose a framework for campus energy forecasting.','kind':'library'}); assert ref.status_code==201
    paper=client.post('/api/papers',json={'title':'Submitted','abstract':'We propose a new framework for campus energy forecasting using graphs.','kind':'submitted'}).json()
    r=client.post('/api/analyses',json={'paper_id':paper['id']}); assert r.status_code==202
    a=client.get('/api/analyses/'+str(r.json()['id'])).json(); assert a['status']=='completed'; assert a['result']['matches'][0]['title']=='Reference'; assert a['result']['indicators']['overall'] is not None
    assert client.get('/api/analyses/'+str(a['id'])+'/report').status_code==200
    assert len(client.get('/api/analyses').json())==1
    assert client.delete('/api/papers/'+str(paper['id'])).status_code==204
    assert client.get('/api/analyses/'+str(a['id'])).json()['result']['paper']['title']=='Submitted'

def test_empty_library(client):
    p=client.post('/api/papers',json={'title':'Alone','abstract':'We propose a novel method for measuring water quality in rivers.','kind':'submitted'}).json()
    a=client.post('/api/analyses',json={'paper_id':p['id']}).json()
    result=client.get('/api/analyses/'+str(a['id'])).json()['result']; assert result['indicators']['overall'] is None; assert not result['matches']

def test_errors_duplicates_and_demo(client):
    assert client.get('/api/papers/999').status_code==404
    assert client.post('/api/analyses',json={'paper_id':999}).status_code==404
    assert client.post('/api/papers',json={'title':''}).status_code==422
    payload={'title':'Same','abstract':'Same abstract'}
    assert client.post('/api/papers',json=payload).status_code==201
    assert client.post('/api/papers',json=payload).status_code==409
    assert client.post('/api/demo').json()['added']==2
    assert client.post('/api/demo').json()['added']==0
