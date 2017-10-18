from algorithms.negex import NegativeExampleSampler
from datastruct.graph import GraphEdge, EdgeSet
from datastruct.rules import Rule, RuleSet
from utils.files import read_tsv_file, write_tsv_file
import shared

from collections import defaultdict
from itertools import chain
from keras.models import Model
from keras.layers import concatenate, Dense, Embedding, Flatten, Input
import numpy as np
from operator import itemgetter
import os.path
from typing import Dict, Iterable, List, Tuple


class EdgeModel:
    def __init__(self, edges :List[GraphEdge], rule_domsizes :Dict[Rule, int])\
                -> None:
        raise NotImplementedError()

    def edge_cost(self, edge :GraphEdge) -> float:
        raise NotImplementedError()

    def null_cost(self) -> float:
        'Cost of a graph without any edges.'
        raise NotImplementedError()

    def rule_cost(self, rule :Rule) -> float:
        'Cost of having a rule in the model.'
        raise NotImplementedError()

    def recompute_costs(self) -> None:
        raise NotImplementedError()

    def fit_to_sample(self, root_weights :np.ndarray, 
                      edge_weights :np.ndarray) -> None:
        raise NotImplementedError()

    def save(self, filename :str) -> None:
        raise NotImplementedError()

    @staticmethod
    def load(filename :str) -> 'EdgeModel':
        raise NotImplementedError()


class SimpleEdgeModel(EdgeModel):
    def __init__(self, rule_set :RuleSet, alpha=1.1, beta=1.1) -> None:
        self.rule_set = rule_set
        self.rule_domsize = np.empty(len(rule_set))
        for i in range(len(rule_set)):
            self.rule_domsize[i] = rule_set.get_domsize(rule_set[i])
        self.alpha = alpha
        self.beta = beta

    def edge_cost(self, edge :GraphEdge) -> float:
        return self._rule_appl_cost[self.rule_set.get_id(edge.rule)]

    def edges_cost(self, edge_set :EdgeSet) -> np.ndarray:
        result = np.zeros(len(edge_set))
        for rule, edge_ids in edge_set.get_edge_ids_by_rule().items():
            result[edge_ids] = self._rule_appl_cost[self.rule_set.get_id(rule)]
        return result

    def null_cost(self) -> float:
        'Cost of a graph without any edges.'
        return self._null_cost

    def rule_cost(self, rule :Rule) -> float:
        'Cost of having a rule in the model.'
        return self._rule_cost[self.rule_set.get_id(rule)]

    def set_probs(self, probs :np.ndarray) -> None:
        self.rule_prob = probs
        self._rule_appl_cost = -np.log(probs) + np.log(1-probs)
        self._rule_cost = -np.log(1-probs) * self.rule_domsize
        self._null_cost = np.sum(self._rule_cost)

    def fit(self, edge_set :EdgeSet, weights :np.ndarray) -> None:
        # compute rule frequencies
        rule_freq = np.zeros(len(self.rule_set))
        for i in range(weights.shape[0]):
            rule_id = self.rule_set.get_id(edge_set[i].rule)
            rule_freq[rule_id] += weights[i]
        # fit
        probs = (rule_freq + np.repeat(self.alpha-1, len(self.rule_set))) /\
                 (self.rule_domsize + np.repeat(self.alpha+self.beta-2,
                                                len(self.rule_set)))
        self.set_probs(probs)

    def save(self, filename :str) -> None:
        write_tsv_file(filename, ((rule, self.rule_prob[i])\
                                  for i, rule in enumerate(self.rule_set)))

    @staticmethod
    def load(filename :str, rule_set :RuleSet) -> 'SimpleEdgeModel':
        result = SimpleEdgeModel(rule_set)
        probs = np.zeros(len(rule_set))
        for rule, prob in read_tsv_file(filename, (str, float)):
            probs[rule_set.get_id(rule_set[rule])] = prob
        result.set_probs(probs)
        return result


class NGramFeatureExtractor:
    def __init__(self) -> None:
        self.ngrams = []
        self.feature_idx = {}

    def select_features(self, edge_set :EdgeSet, max_num=1000) -> None:
        '''Count n-grams and select the most frequent ones.'''
        ngrams_freq = defaultdict(lambda: 0)
        for edge in edge_set:
            for ngram in self._extract_from_seq(edge.source.word):
                ngrams_freq[ngram] += 1
        self.ngrams = list(map(itemgetter(0),
                               sorted(ngrams_freq.items(), reverse=True,
                                      key=itemgetter(1))))[:max_num]
        self.feature_idx = { ngram: i for i, ngram in enumerate(self.ngrams) }

    def num_features(self) -> int:
        return len(self.ngrams)

    def extract(self, edge_set :EdgeSet) -> np.ndarray:
        '''Extract n-gram features from edges and return a binary matrix.'''
        result = np.zeros((len(edge_set), self.num_features()))
        for i, edge in enumerate(edge_set):
            for ngram in self._extract_from_seq(edge.source.word):
                if ngram in self.feature_idx:
                    result[i,self.feature_idx[ngram]] = 1
        return result

    def _extract_from_seq(self, seq :Iterable[str]) -> Iterable[str]:
        result = []
        my_seq = ['^'] + list(seq) + ['$']
        for n in range(1, len(my_seq)):
            for i in range(len(my_seq)-1):
                result.append(''.join(my_seq[i:i+n]))
        return result


class NeuralEdgeModel(EdgeModel):
    def __init__(self, rule_set :RuleSet, edge_set :EdgeSet,
                       negex_sampler :NegativeExampleSampler) -> None:
        self.rule_set = rule_set
        self.negex_sampler = negex_sampler
        self.ngram_extractor = NGramFeatureExtractor()
        self.ngram_extractor.select_features(edge_set)
        self._compile_network()

    def edge_cost(self, edge :GraphEdge) -> float:
        raise NotImplementedError()

    def edges_cost(self, edge_set :EdgeSet) -> np.ndarray:
        X_attr, X_rule = self._prepare_data(edge_set)
        probs = self.nn.predict([X_attr, X_rule])
        return np.log(probs / (1-probs))

    def null_cost(self) -> float:
        'Cost of a graph without any edges.'
        return self._null_cost

    def rule_cost(self, rule :Rule) -> float:
        'Cost of having a rule in the model.'
        return self._rule_cost[self.rule_set.get_id(rule)]

    def fit(self, edge_set :EdgeSet, weights :np.ndarray) -> None:
        negex, weights_neg = self.negex_sampler.sample(len(edge_set))
#         for i, edge in enumerate(negex):
#             print(edge.source, edge.target, edge.rule, weights_neg[i])
        X_attr_neg, X_rule_neg = self._prepare_data(negex)
        X_attr_pos, X_rule_pos = self._prepare_data(edge_set)
        X_attr = np.vstack([X_attr_pos, X_attr_neg])
        X_rule = np.hstack([X_rule_pos, X_rule_neg])
        y = np.hstack([weights, np.zeros(len(negex))])
        weights = np.hstack([np.ones(len(edge_set)), weights_neg])
        self.nn.fit([X_attr, X_rule], y, sample_weight=weights, epochs=5,
                    batch_size=64, verbose=1)
        # set null_cost and rule_cost
        self._rule_cost = np.zeros(len(self.rule_set))
        # TODO the strange constants are to eliminate zeros and ones
        # TODO a better approach is needed!!!
#         probs = self.nn.predict([X_attr, X_rule]) * 0.9998 + 0.0001
        probs = self.nn.predict([X_attr, X_rule])
        if np.any(probs == 0):
            logging.getLogger('main').warning('zeros in predicted costs!!!')
        if np.any(probs == 1):
            logging.getLogger('main').warning('ones in predicted costs!!!')
        costs = -np.log(1-probs)
        for i, edge in chain(enumerate(edge_set),
                             enumerate(negex, len(edge_set))):
            rule_id = self.rule_set.get_id(edge.rule)
            self._rule_cost[rule_id] += costs[i] * weights[i]
        self._null_cost = np.sum(self._rule_cost)

    def save(self, filename :str) -> None:
        file_full_path = os.path.join(shared.options['working_dir'], filename)
        self.nn.save_weights(file_full_path)
        # TODO save NGramFeatureExtractor

    @staticmethod
    def load(filename :str, rule_set :RuleSet, edge_set :EdgeSet,
             negex_sampler :NegativeExampleSampler) -> 'NeuralEdgeModel':
        raise NotImplementedError()

    def _compile_network(self):
        num_ngr = self.ngram_extractor.num_features()
        num_rules = len(self.rule_set)
        input_attr = Input(shape=(num_ngr,), name='input_attr')
        input_rule = Input(shape=(1,), name='input_rule')
        rule_emb = Embedding(input_dim=num_rules, output_dim=30,\
                             input_length=1)(input_rule)
        rule_emb_fl = Flatten(name='rule_emb_fl')(rule_emb)
        attr_dr = Dense(30, name='attr_dr')(input_attr)
        concat = concatenate([attr_dr, rule_emb_fl])
        internal = Dense(30, activation='relu', name='internal')(concat)
        output = Dense(1, activation='sigmoid', name='dense')(internal)
        self.nn = Model(inputs=[input_attr, input_rule], outputs=[output])
        self.nn.compile(optimizer='adam', loss='binary_crossentropy')

    def _prepare_data(self, edge_set :EdgeSet) -> \
                     Tuple[np.ndarray, np.ndarray, np.ndarray]:
        X_attr = self.ngram_extractor.extract(edge_set)
        X_rule = np.array([self.rule_set.get_id(edge.rule) \
                           for edge in edge_set])
        return X_attr, X_rule


# TODO also using sampling of negative examples
class LogisticEdgeModel(EdgeModel):
    pass


# TODO pass alignments on character level to an RNN instead of rule embedding
class AlignmentRNNEdgeModel(EdgeModel):
    pass

