import os, json, re
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from .processing import contributions

# Optional model is only downloaded when explicitly enabled. TF-IDF works entirely offline.
_model = None
def similarities(query, docs):
    if not docs: return [], 'none'
    if os.getenv('EMBEDDING_BACKEND','tfidf') == 'sentence-transformers':
        global _model
        try:
            if _model is None:
                from sentence_transformers import SentenceTransformer
                _model=SentenceTransformer(os.getenv('EMBEDDING_MODEL','all-MiniLM-L6-v2'))
            vec=_model.encode([query]+docs, normalize_embeddings=True)
            return cosine_similarity([vec[0]],vec[1:])[0].clip(0,1).tolist(), 'sentence-transformers'
        except Exception:
            pass
    try:
        vec=TfidfVectorizer(stop_words='english',ngram_range=(1,2)).fit_transform([query]+docs)
        return cosine_similarity(vec[0],vec[1:])[0].clip(0,1).tolist(), 'tf-idf'
    except ValueError: return [0.0]*len(docs), 'tf-idf'

class LocalLiteratureProvider:
    def __init__(self, session, paper_model): self.session,self.paper_model=session,paper_model
    def papers(self, exclude_id): return self.session.query(self.paper_model).filter(self.paper_model.kind=='library',self.paper_model.id != exclude_id).all()

def analyse(paper, refs):
    sections=json.loads(paper.sections or '{}'); cs=contributions(paper.text or paper.abstract,sections)
    query=paper.abstract or sections.get('introduction','') or paper.text[:4000]
    refs=[p for p in refs if (p.abstract or p.text).strip()]
    docs=[p.abstract or p.text[:4000] for p in refs]
    scores,method=similarities(query,docs) if query.strip() else ([], 'none')
    matches=[]
    for i in sorted(range(len(scores)),key=lambda i:scores[i],reverse=True)[:5]:
        p=refs[i]; matches.append({'paper_id':p.id,'title':p.title,'authors':p.authors,'year':p.year,'abstract':p.abstract,'source':p.source,'score':round(scores[i]*100,1),'excerpt':(p.abstract or p.text)[:500]})
    comparisons=[]
    for c in cs:
        vals,_=similarities(c['text'],docs)
        idx=max(range(len(vals)),key=lambda i:vals[i]) if vals else None
        comparisons.append({**c,'match':{'paper_id':refs[idx].id,'title':refs[idx].title,'score':round(vals[idx]*100,1),'excerpt':docs[idx][:500]} if idx is not None else None})
    has_evidence=bool(query.strip() and matches and cs)
    maxsim=matches[0]['score'] if matches else None
    distinct=round(100-sum(c['match']['score'] for c in comparisons)/len(comparisons),1) if has_evidence else None
    indicator=round(.5*(100-maxsim)+.5*distinct,1) if has_evidence else None
    return {'paper':{'id':paper.id,'title':paper.title,'authors':paper.authors,'year':paper.year,'abstract':paper.abstract,'keywords':paper.keywords,'source':paper.source},'problem':(sections.get('introduction') or paper.abstract or '')[:500], 'contributions':comparisons,'matches':matches,'indicators':{'overall':indicator,'distinctiveness':distinct,'similarity':maxsim,'coverage':None,'evidence':None},'reference_count':len(refs),'method':method,'limitations':['Results are preliminary research assistance, not proof of novelty or plagiarism detection.','Coverage cannot be quantified without a comprehensive external literature search.','Similarity measures wording and semantic proximity, not the originality of an idea.','Candidate contributions are extracted heuristically and may require correction.'] + (['No comparable local references are available; the assessment is incomplete.'] if not matches else []) + (['TF-IDF is a lexical offline fallback, not a semantic embedding model.'] if method=='tf-idf' else []), 'formula':'Overall = 0.5 × (100 − highest paper similarity) + 0.5 × contribution distinctiveness. Distinctiveness = 100 − mean best contribution similarity. This is an unvalidated heuristic, not a scientific measurement.'}
