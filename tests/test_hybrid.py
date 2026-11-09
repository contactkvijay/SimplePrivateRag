"""Fast ranking regression checks; no Ollama or user documents needed."""
import sys
import tempfile
import unittest
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend import storage

class HybridTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.previous = storage.DATA, storage.FILES, storage.DB
        storage.DATA = Path(self.directory.name)
        storage.FILES = storage.DATA / 'files'
        storage.DB = storage.DATA / 'test.sqlite3'
        passages = [('Name: Ravi\nBank: HDFC\nAccount: TEST-RAVI', 'Line 1'),
                    ('Name: Priya\nBank: HDFC\nAccount: TEST-PRIYA', 'Line 2')]
        # Vector-only favours Ravi. Priya's exact name should correct the ranking.
        vectors = [np.array([1, 0], dtype=np.float32),
                   np.array([0.9, 0.43589], dtype=np.float32)]
        storage.save_document('test.txt', b'synthetic', passages, vectors, 'test-model')
        self.vector = np.array([1, 0], dtype=np.float32)

    def tearDown(self):
        storage.DATA, storage.FILES, storage.DB = self.previous
        self.directory.cleanup()

    def search(self, question, weight=0.35):
        return storage.find_similar_passages(self.vector, 'test-model', question, weight)

    def test_keyword_match_corrects_wrong_person(self):
        question = "What is Priya's HDFC account number?"
        self.assertIn('TEST-RAVI', self.search(question, 0)[0]['content'])
        self.assertIn('TEST-PRIYA', self.search(question)[0]['content'])

    def test_other_owner_and_case(self):
        self.assertIn('TEST-RAVI', self.search('RAVI HDFC ACCOUNT')[0]['content'])

    def test_no_keyword_overlap_keeps_semantic_order(self):
        self.assertEqual(self.search('unrelated words'), self.search('unrelated words', 0))

    def test_stopwords_do_not_change_semantic_order(self):
        self.assertEqual(self.search('what is the'), self.search('what is the', 0))

if __name__ == '__main__':
    unittest.main()
