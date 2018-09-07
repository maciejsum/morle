from datastruct.graph import GraphEdge, EdgeSet
from datastruct.lexicon import LexiconEntry, Lexicon
from datastruct.rules import RuleSet
from models.generic import Model, ModelFactory, UnknownModelTypeException
from utils.files import full_path

import numpy as np
from scipy.stats import norm


class RootFrequencyModel(Model):
    pass


class ZipfRootFrequencyModel(RootFrequencyModel):
    def __init__(self) -> None:
        pass

    def fit(self, lexicon :Lexicon, weights :np.ndarray) -> None:
        pass

#     def root_cost(self, entry :LexiconEntry) -> float:
#         return float(self.roots_cost([entry]))
# 
    def root_costs(self, lexicon :Lexicon) -> np.ndarray:
        freqs = np.array([entry.freq for entry in lexicon])
        return np.log(freqs)+np.log(freqs+1)

    def save(self, filename :str) -> None:
        pass
        
    @staticmethod
    def load(filename :str) -> 'ZipfRootFrequencyModel':
        return ZipfRootFrequencyModel()


class RootFrequencyModelFactory(ModelFactory):
    @staticmethod
    def create(model_type :str) -> RootFrequencyModel:
        if model_type == 'none':
            return None
        elif model_type == 'zipf':
            return ZipfRootFrequencyModel()
        else:
            raise UnknownModelTypeException('root frequency', model_type)

    @staticmethod
    def load(model_type :str, filename :str) -> RootFrequencyModel:
        if model_type == 'none':
            return None
        elif model_type == 'zipf':
            return ZipfRootFrequencyModel()
        else:
            raise UnknownModelTypeException('root frequency', model_type)


class EdgeFrequencyModel(Model):
    pass


class LogNormalEdgeFrequencyModel(EdgeFrequencyModel):
    def __init__(self, rule_set :RuleSet) -> None:
        self.rule_set = rule_set
        self.means = None
        self.vars = None

    def fit_rule(self, rule_id :int, freq_vector :np.ndarray,
                 weights :np.ndarray) -> None:
        if np.sum(weights > 0) <= 1:
            logging.getLogger('main').debug(
                'LogNormalEdgeFrequencyModel: rule {} cannot be fitted:'
                ' not enough edges.'.format(self.rule_set[rule_id]))
            return
        self.means[rule_id,] = np.average(freq_vector, weights=weights)
        err = freq_vector - self.means[rule_id,]
        self.vars[rule_id,] = np.average(err**2, weights=weights) + 0.001 

    def fit(self, edge_set :EdgeSet, weights :np.ndarray) -> None:
        if self.means is None:
            self.means = np.empty(len(self.rule_set))
        if self.vars is None:
            self.vars = np.empty(len(self.rule_set))
        for rule, edge_ids in edge_set.get_edge_ids_by_rule().items():
            edge_ids = tuple(edge_ids)
            freq_vector = np.array([edge_set[i].target.logfreq - \
                                    edge_set[i].source.logfreq \
                                    for i in edge_ids])
            self.fit_rule(self.rule_set.get_id(rule), freq_vector,
                          weights[edge_ids,])

    def edge_cost(self, edge :GraphEdge) -> float:
        rule_id = self.rule_set.get_id(edge.rule)
        return -norm.logpdf(edge.target.logfreq-edge.source.logfreq,
                            self.means[rule_id,],
                            self.vars[rule_id,])

    def edges_cost(self, edge_set :EdgeSet) -> np.ndarray:
        result = np.zeros(len(edge_set))
        for rule, edge_ids in edge_set.get_edge_ids_by_rule().items():
            rule_id = self.rule_set.get_id(rule)
            freq_vector = np.array([edge_set[i].target.logfreq - \
                                    edge_set[i].source.logfreq \
                                    for i in edge_ids])
            costs = -norm.logpdf(freq_vector, self.means[rule_id,],
                                 self.vars[rule_id,])
            result[tuple(edge_ids),] = costs
        return result

    def save(self, filename :str) -> None:
        np.savez(full_path(filename), means=self.means, vars=self.vars)

    @staticmethod
    def load(filename :str, rule_set :RuleSet) -> 'LogNormalEdgeFrequencyModel':
        result = LogNormalEdgeFrequencyModel(rule_set)
        with np.load(full_path(filename)) as data:
            result.means = data['means']
            result.vars = data['vars']
        return result


class EdgeFrequencyModelFactory(ModelFactory):
    @staticmethod
    def create(model_type :str, rule_set :RuleSet) -> EdgeFrequencyModel:
        if model_type == 'none':
            return None
        elif model_type == 'lognormal':
            return LogNormalEdgeFrequencyModel(rule_set)
        else:
            raise UnknownModelTypeException('edge frequency', model_type)

    @staticmethod
    def load(model_type :str, filename :str, rule_set :RuleSet) \
            -> EdgeFrequencyModel:
        if model_type == 'none':
            return None
        elif model_type == 'lognormal':
            return LogNormalEdgeFrequencyModel.load(filename, rule_set)
        else:
            raise UnknownModelTypeException('edge frequency', model_type)
