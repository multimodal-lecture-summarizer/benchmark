"""Regression for the exact user-reported legacy PARSeq key mismatch."""
import unittest
from collections import OrderedDict
from unittest.mock import Mock

from experiments.scripts.spotting_colab_doctr import LEGACY_UNUSED, load_parseq_checkpoint


class ParseqCompatibilityTests(unittest.TestCase):
    def test_state_dict_metadata_is_preserved(self):
        state = OrderedDict([('head.weight',object())])
        state._metadata = {'head':{'version':1}}
        model = Mock()
        model.state_dict.return_value = state
        load_parseq_checkpoint(model,state)
        loaded = model.load_state_dict.call_args.args[0]
        self.assertEqual(loaded._metadata,state._metadata)
        self.assertIs(loaded['head.weight'],state['head.weight'])

    def test_only_known_unused_keys_removed_and_remaining_load_strictly(self):
        tensor = object()
        state = {'head.weight':tensor,**{k:object() for k in LEGACY_UNUSED}}
        original = dict(state)
        model = Mock()
        model.state_dict.return_value = {'head.weight':tensor}
        receipt = load_parseq_checkpoint(model,state)
        model.load_state_dict.assert_called_once_with({'head.weight':tensor},strict=True)
        self.assertEqual(state,original)
        self.assertEqual(set(receipt['removed_unused_keys']),LEGACY_UNUSED)
        self.assertFalse(receipt['checkpoint_bytes_modified'])

    def test_unrelated_extra_key_is_rejected(self):
        model = Mock()
        model.state_dict.return_value = {'head.weight':0}
        with self.assertRaisesRegex(ValueError,'unrecognized'):
            load_parseq_checkpoint(model,{'head.weight':0,'unexpected.weight':1})
        model.load_state_dict.assert_not_called()

    def test_missing_or_shape_mismatched_weights_still_fail_strict_load(self):
        model = Mock()
        model.state_dict.return_value = {'head.weight':0}
        model.load_state_dict.side_effect = RuntimeError('strict missing/shape mismatch')
        with self.assertRaisesRegex(RuntimeError,'strict missing/shape'):
            load_parseq_checkpoint(model,{k:0 for k in LEGACY_UNUSED})
        model.load_state_dict.assert_called_once_with({},strict=True)

    def test_used_legacy_layer_is_never_discarded(self):
        model = Mock()
        model.state_dict.return_value = {next(iter(LEGACY_UNUSED)):0}
        with self.assertRaisesRegex(ValueError,'profile changed'):
            load_parseq_checkpoint(model,model.state_dict.return_value)
        model.load_state_dict.assert_not_called()


if __name__=='__main__':
    unittest.main()
