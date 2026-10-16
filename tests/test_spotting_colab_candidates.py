import hashlib
import io
import json
import tempfile
from pathlib import Path
import unittest
import zipfile

from experiments.scripts.spotting_colab_artifacts import acquire, digest, extract, verify_files
from experiments.scripts.spotting_colab_candidates import load_registry, prepare_candidate, lock_testr_checkpoint
from experiments.scripts.spotting_colab_adapters import tsv_regions


class CandidateContracts(unittest.TestCase):
    def test_registry_retains_six_selections_but_does_not_claim_testr_ready(self):
        registry = load_registry()
        self.assertEqual(len(registry['candidates']),6)
        conditional = [c for c in registry['candidates'] if c['conditional']]
        self.assertEqual(len(conditional),1)
        self.assertFalse(conditional[0]['locked'])
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaisesRegex(ValueError,'403'):
                prepare_candidate(conditional[0],root)
        for candidate in registry['candidates'][:-1]:
            self.assertTrue(candidate['locked'])
            self.assertTrue(candidate['model_sha256'])
            self.assertEqual(candidate['configuration_sha256'],digest(candidate['configuration']))

    def test_tsv_keeps_empty_and_low_confidence_words(self):
        header='level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n'
        text=header+'1\t1\t0\t0\t0\t0\t0\t0\t100\t100\t-1\t\n'
        text+='5\t1\t1\t1\t1\t1\t2\t3\t4\t5\t0\t\n'
        text+='5\t1\t1\t1\t1\t2\t6\t7\t8\t9\t12\tA*\n'
        rows=tsv_regions(text)
        self.assertEqual([r['text'] for r in rows],['','A*'])
        self.assertEqual(rows[0]['polygon'],[[2.,3.],[6.,3.],[6.,8.],[2.,8.]])

    def test_artifact_requires_expected_digest_and_rejects_changed_bytes(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'weight';path.write_bytes(b'wrong')
            with self.assertRaisesRegex(ValueError,'not locked'):
                acquire(dict(path='weight',url='unreachable',sha256=None),root)
            with self.assertRaisesRegex(ValueError,'digest mismatch'):
                acquire(dict(path='weight',url='unreachable',sha256='0'*64),root)

    def test_unsafe_archive_rejected_before_extract(self):
        with tempfile.TemporaryDirectory() as root:
            archive=Path(root)/'bad.zip'
            with zipfile.ZipFile(archive,'w') as bundle:
                bundle.writestr('valid','ok');bundle.writestr('../outside','unsafe')
            with self.assertRaisesRegex(ValueError,'unsafe'):
                extract(archive,Path(root)/'out')
            self.assertFalse((Path(root)/'out/valid').exists())

    def test_recovered_testr_checkpoint_creates_new_bound_registry_only(self):
        with tempfile.TemporaryDirectory() as root:
            checkpoint=Path(root)/'recovered.pth';checkpoint.write_bytes(b'recovered-checkpoint-test-data')
            candidate=load_registry()['candidates'][-1]
            with self.assertRaisesRegex(ValueError,'provenance'):
                lock_testr_checkpoint(checkpoint,Path(root)/'new.json','untrusted')
            path=lock_testr_checkpoint(checkpoint,Path(root)/'new.json',candidate['checkpoint_url'])
            new=json.loads(path.read_text())['candidates'][-1]
            self.assertTrue(new['locked'])
            self.assertEqual(new['model_sha256']['testr/model.pth'],hashlib.sha256(checkpoint.read_bytes()).hexdigest())
            self.assertFalse(load_registry()['candidates'][-1]['locked'])


if __name__=='__main__':
    unittest.main()
