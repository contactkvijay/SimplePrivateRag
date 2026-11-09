"""Run with: python tests/evaluate.py. Uses only synthetic data."""
import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ['RAG_DATA_DIR'] = tempfile.mkdtemp(prefix='rag-evaluation-')
from backend.ingestion import ingest, chunk, read_text
from backend.retrieval import EMBED_MODEL, answer, embedding
from backend.storage import find_similar_passages, remove_document, connect, FILES

# Question, relevant passage positions, and exact facts expected in the answer.
CASES = [
    ("Ravi's HDFC account number?", [0], ['DEMO-RAVI-HDFC']),
    ("Priya's HDFC account number?", [1], ['DEMO-PRIYA-HDFC']),
    ("Ravi's ICICI account number?", [2], ['DEMO-RAVI-ICICI']),
    ("Priya's ICICI account number?", [3], ['DEMO-PRIYA-ICICI']),
    ("What is Ravi's HDFC IFSC?", [0], ['HDFC0000001']),
    ("What is Priya's HDFC IFSC?", [1], ['HDFC0000002']),
    ("Where is Ravi's ICICI branch?", [2], ['Oak Street']),
    ("Where is Priya's ICICI branch?", [3], ['Pine Lane']),
    ("List Ravi and Priya HDFC account numbers.", [0, 1], ['DEMO-RAVI-HDFC', 'DEMO-PRIYA-HDFC']),
    ("Show Priya's HDFC account details including account number, IFSC and branch.", [1], ['DEMO-PRIYA-HDFC', 'HDFC0000002', 'Cedar Avenue']),
    ("What is Maple's moving date?", [4], ['15 December']),
    ("Who is the contact person for Cedar?", [5], ['Deepak']),
    ("How much paid time off do employees get per year?", [6], ['24']),
    ("How long do I have to claim money back for a business trip?", [7], ['30']),
    ("What should guests do when they arrive?", [8], ['reception']),
    ("Where can I leave my bike?", [9], ['basement']),
    ("On which day can employees do their jobs from home?", [10], ['Friday']),
    ("Who should I tell if my computer stops working?", [11], ['help desk']),
    ("What is Ravi's HDFC password?", [], []),
    ("What is Priya's salary?", [], []),
]

def evaluate():
    data = Path(__file__).with_name('synthetic.txt').read_bytes()
    passages = chunk(read_text(data))
    document = ingest('synthetic.txt', data)
    results = []
    try:
        for question, expected, facts in CASES:
            vector = embedding(question)
            rankings = {}
            for label, weight in [('vector', 0), ('hybrid', 0.35)]:
                sources = find_similar_passages(vector, EMBED_MODEL, question, weight)
                rankings[label] = [next(i for i, p in enumerate(passages) if p[0] == s['content']) for s in sources]
            start = time.monotonic()
            response = answer(question)
            text = response['answer'].lower()
            if facts:
                correct = all(fact.lower() in text for fact in facts)
                # An account answer must not contain an unrelated account number.
                accounts = {'DEMO-RAVI-HDFC', 'DEMO-PRIYA-HDFC', 'DEMO-RAVI-ICICI', 'DEMO-PRIYA-ICICI'}
                correct = correct and not any(n.lower() in text for n in accounts - set(facts))
            else:
                correct = bool(re.search(r'not (?:provided|available|specified|included|found|mentioned)|no information|does not|cannot|missing', text))
            cited = bool(re.search(r'\[\d+\]', text))
            results.append(dict(question=question, expected=expected, rankings=rankings,
                                answer=response['answer'], fact_check=correct, cited=cited,
                                seconds=round(time.monotonic()-start, 2)))
            print(f"{len(results)}/{len(CASES)} {'PASS' if correct else 'FAIL'}: {question}", flush=True)
        summary = {}
        positive = [r for r in results if r['expected']]
        for label in ['vector', 'hybrid']:
            recalls, reciprocal_ranks = [], []
            for r in positive:
                ranking = r['rankings'][label]
                recalls.append(len(set(r['expected']) & set(ranking)) / len(r['expected']))
                reciprocal_ranks.append(next((1/(i+1) for i, p in enumerate(ranking) if p in r['expected']), 0))
            summary[label] = dict(recall_at_5=sum(recalls)/len(positive), mrr_at_5=sum(reciprocal_ranks)/len(positive))
        summary['fact_checks_passed'] = sum(r['fact_check'] for r in results)
        summary['questions'] = len(results)
        summary['positive_answers_cited'] = sum(r['cited'] for r in positive)
        output = ROOT / '.artifacts' / 'hybrid-evaluation.json'
        output.parent.mkdir(exist_ok=True)
        output.write_text(json.dumps(dict(summary=summary, results=results), indent=2), encoding='utf-8')
        print(json.dumps(summary, indent=2))
        assert all(r['fact_check'] for r in results), 'Inspect failed cases in the report.'
    finally:
        remove_document(document['id'])
        with connect() as db:
            assert db.execute('SELECT count(*) FROM chunks').fetchone()[0] == 0
        assert not list(FILES.iterdir())

if __name__ == '__main__':
    evaluate()
