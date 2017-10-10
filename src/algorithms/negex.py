from datastruct.graph import EdgeSet
from datastruct.lexicon import Lexicon
from datastruct.rules import RuleSet

import hfst
import logging
import numpy as np
import tqdm
from typing import Tuple


def identity_fst() -> hfst.HfstTransducer:
    tr = hfst.HfstBasicTransducer()
    tr.add_transition(0, hfst.HfstBasicTransition(0, hfst.IDENTITY,
                                                  hfst.IDENTITY, 0.0))
    tr.set_final_weight(0, 0.0)
    return hfst.HfstTransducer(tr)


class NegativeExampleSampler:
    # TODO this is the natural place to store domsizes
    # TODO sample examples for each rule separately
    # TODO sample for each rule as many negative examples
    #      as there are edges with this rule (= potential positive examples)
    # TODO stores also weights of sample items (domsize/sample_size for each rule)

    def __init__(self, lexicon :Lexicon, lexicon_tr :hfst.HfstTransducer,
                 rule_set :RuleSet, rule_example_counts :np.ndarray,
                 rule_domsizes :np.ndarray) -> None:
        self.lexicon = lexicon
#         self.lexicon_tr = lexicon_tr
        self.rule_set = rule_set
#         self.non_lex_tr = identity_fst()
#         self.non_lex_tr.subtract(self.lexicon_tr)
        self.rule_example_counts = rule_example_counts
        self.rule_domsizes = rule_domsizes
        self.transducers = self._build_transducers(lexicon_tr)

    def sample(self) -> Tuple[EdgeSet, np.ndarray]:
        # TODO returns edges (with empty target) and weights
        # TODO automaton: Lex .o. Rules .o. (Lex^c)
        # TODO memorize automata or compute them on the fly?
        for rule in tqdm.tqdm(self.rule_set):
#             tr = hfst.HfstTransducer(self.lexicon_tr)
#             tr.compose(rule.to_fst())
#             tr.minimize()
#             tr.compose(self.non_lex_tr)
#             tr.minimize()
#             print(rule)
            for path in self.transducers[rule].extract_paths(\
                            max_number=20, random='True', output='raw'):
                source = ''.join([x for x, y in path[1]]).replace(hfst.EPSILON, '')
                target = ''.join([y for x, y in path[1]]).replace(hfst.EPSILON, '')
#                 print(source + ':' + target)
#             print()

    def _build_transducers(self, lexicon_tr :hfst.HfstTransducer):
        result = {}
        non_lex_tr = identity_fst()
        non_lex_tr.subtract(lexicon_tr)
        logging.getLogger('main').info('Building transducers for negative sampling...')
        for rule in tqdm.tqdm(self.rule_set):
            tr = hfst.HfstTransducer(lexicon_tr)
            tr.compose(rule.to_fst())
            tr.minimize()
            tr.compose(non_lex_tr)
            tr.minimize()
            result[rule] = tr
        return result

