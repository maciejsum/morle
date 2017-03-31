import logging
import math
import numpy as np
import random
import sys
import time
from operator import itemgetter
import scipy.sparse
from scipy.special import beta, betaln, expit
from datastruct.lexicon import *
from datastruct.rules import *
from models.point import PointModel
from models.marginal import MarginalModel
from utils.files import *
from utils.printer import *
import shared

# TODO split into smaller modules?
# - index
# - statistics
# - samplers
# - inference

class ImpossibleMoveException(Exception):
    pass

### INDICES ###

class Index:
    def __init__(self) -> None:
        pass

    def __getitem__(self, key :Any) -> None:
        pass

class EdgeIndex:
    pass

class RuleIndex:
    pass

class WordpairIndex:
    pass

### STATISTICS ###

class MCMCStatistic:
    def __init__(self) -> None:
        self.reset()
    
    def reset(self) -> None:
        self.iter_num = 0

    def update(self) -> None:
        pass

    def edge_added(self, edge :GraphEdge) -> None:
        pass

    def edge_removed(self, edge :GraphEdge) -> None:
        pass

    def next_iter(self) -> None:
        self.iter_num += 1


class ScalarStatistic(MCMCStatistic):
    def __init__(self) -> None:
        super().__init__()
        self.reset()
    
    def reset(self) -> None:
        super().reset()
        self.val = 0                # type: float
        self.last_modified = 0      # type: int

    def update(self) -> None:
        raise NotImplementedError()

    def edge_added(self, edge :GraphEdge) -> None:
        raise NotImplementedError()

    def edge_removed(self, edge :GraphEdge) -> None:
        raise NotImplementedError()

    def value(self) -> float:
        return self.val


class ExpectedCostStatistic(ScalarStatistic):
    def __init__(self, model :Model) -> None:
        super().__init__()
        self.model = model

    def update(self) -> None:
        pass
    
    def edge_added(self, edge :GraphEdge) -> None:
        pass

    def edge_removed(self, edge :GraphEdge) -> None:
        pass
    
    def next_iter(self):
        super().next_iter()
        self.val = \
            (self.val * (self.iter_num-1) + self.model.cost()) / self.iter_num


class TimeStatistic(ScalarStatistic):
    def reset(self, sampler):
        self.started = time.time()
        self.val = 0
    
    def update(self, sampler):
        self.val = time.time() - self.started
    
    def edge_added(self, sampler, idx, edge):
        pass

    def edge_removed(self, sampler, idx, edge):
        pass


# TODO deprecated
# class GraphsWithoutRuleSetStatistic(ScalarStatistic):
#     def __init__(self, sampler, forbidden_rules):
#         self.forbidden_rules = forbidden_rules
#         self.reset(sampler)
# 
#     def reset(self, sampler):
#         self.val = 0
#         self.last_modified = 0
#         self.forbidden_edges =\
#             sum(count for rule, count in sampler.lexicon.rules_c.items()\
#                 if rule in self.forbidden_rules)
# 
#     def update(self, sampler):
#         self.val =\
#             (self.val * self.last_modified +\
#              int(self.forbidden_edges == 0) *\
#                 (sampler.num - self.last_modified)) /\
#             sampler.num
#         self.last_modified = sampler.num
# 
#     def edge_added(self, sampler, idx, edge):
#         if edge.rule in self.forbidden_rules:
#             if self.forbidden_edges == 0:
#                 self.update(sampler)
#             self.forbidden_edges += 1
# 
#     def edge_removed(self, sampler, idx, edge):
#         if edge.rule in self.forbidden_rules:
#             if self.forbidden_edges == 1:
#                 self.update(sampler)
#             self.forbidden_edges -= 1
# 
#     def next_iter(self, sampler):
#         pass


class AcceptanceRateStatistic(ScalarStatistic):
    def update(self, sampler):
        pass
    
    def edge_added(self, sampler, idx, edge):
        self.acceptance(sampler)

    def edge_removed(self, sampler, idx, edge):
        self.acceptance(sampler)

    def acceptance(self, sampler):
        if sampler.num > self.last_modified:
            self.val = (self.val * self.last_modified + 1) / sampler.num
            self.last_modified = sampler.num


class EdgeStatistic(MCMCStatistic):
    def __init__(self, sampler):
        self.reset(sampler)

    def reset(self, sampler):
        self.values = [0] * sampler.len_edges
        self.last_modified = [0] * sampler.len_edges
    
    def update(self, sampler):
        raise Exception('Not implemented!')

    def edge_added(self, sampler, idx, edge):
        raise Exception('Not implemented!')

    def edge_removed(self, sampler, idx, edge):
        raise Exception('Not implemented!')

    def next_iter(self, sampler):
        pass
    
    def value(self, idx, edge):
        return self.values[idx]


class EdgeFrequencyStatistic(EdgeStatistic):
    def update(self, sampler):
        for i, edge in enumerate(sampler.edges):
            if edge in edge.source.edges:
                # the edge was present in the last graphs
                self.edge_removed(sampler, i, edge)
            else:
                # the edge was absent in the last graphs
                self.edge_added(sampler, i, edge)

    def edge_added(self, sampler, idx, edge):
        self.values[idx] =\
            self.values[idx] * self.last_modified[idx] / sampler.num
        self.last_modified[idx] = sampler.num

    def edge_removed(self, sampler, idx, edge):
        self.values[idx] =\
            (self.values[idx] * self.last_modified[idx] +\
             (sampler.num - self.last_modified[idx])) /\
            sampler.num
        self.last_modified[idx] = sampler.num


class WordpairStatistic(MCMCStatistic):
    def __init__(self, sampler):
        self.word_ids = {}
        self.words = []
        cur_id = 0
        for node in sampler.lexicon.iter_nodes():
            self.word_ids[node.key] = cur_id
            self.words.append(node.key)
            cur_id += 1
        self.reset(sampler)

    def reset(self, sampler):
        self.values = {}
        self.last_modified = {}
#         self.values = scipy.sparse.lil_matrix(
#                         (len(self.words), len(self.words)), dtype=np.float32)
#         self.last_modified = scipy.sparse.lil_matrix(
#                                (len(self.words), len(self.words)), 
#                                dtype=np.uint32)
        
    def update(self, sampler):
        raise NotImplementedError()

    def edge_added(self, sampler, idx, edge):
        raise NotImplementedError()

    def edge_removed(self, sampler, idx, edge):
        raise NotImplementedError()

    def next_iter(self, sampler):
        pass

    def value(self, word_1, word_2):
        key = self.key_for_wordpair(word_1, word_2)
        if key in self.values:
            return self.values[key]
        else:
            return 0.0

    def key_for_edge(self, edge):
        key_1 = self.word_ids[edge.source.key]
        key_2 = self.word_ids[edge.target.key]
        return (min(key_1, key_2), max(key_1, key_2))

    def key_for_wordpair(self, word_1, word_2):
        key_1 = self.word_ids[word_1]
        key_2 = self.word_ids[word_2]
        return (min(key_1, key_2), max(key_1, key_2))


class UndirectedEdgeFrequencyStatistic(WordpairStatistic):
    def update(self, sampler):
        # note: the relation edge <-> wordpair is one-to-one here because 
        # in well-formed graphs there can only be one edge per wordpair
        for i, edge in enumerate(sampler.edges):
            key = self.key_for_edge(edge)   # only for debug
            if edge in edge.source.edges:
                # the edge was present in the last graphs
                self.edge_removed(sampler, i, edge)
#                 logging.getLogger('main').debug('updating +: %s -> %s : %f' %\
#                     (edge.source.key, edge.target.key, self.values[key]))
        # second loop because all present edges must be processed first
        for i, edge in enumerate(sampler.edges):
            key = self.key_for_edge(edge)   # only for debug
            if edge not in edge.source.edges:
                # the edge was absent in the last graphs
                self.edge_added(sampler, i, edge)
#                 logging.getLogger('main').debug('updating -: %s -> %s : %f' %\
#                     (edge.source.key, edge.target.key, self.values[key]))

    def edge_added(self, sampler, idx, edge):
        key = self.key_for_edge(edge)
        if key not in self.values:
            self.values[key] = 0
            self.last_modified[key] = 0
        self.values[key] =\
            self.values[key] * self.last_modified[key] / sampler.num
        self.last_modified[key] = sampler.num

    def edge_removed(self, sampler, idx, edge):
        key = self.key_for_edge(edge)
        if key not in self.values:
            self.values[key] = 0
            self.last_modified[key] = 0
        self.values[key] =\
            (self.values[key] * self.last_modified[key] +\
             (sampler.num - self.last_modified[key])) /\
            sampler.num
        self.last_modified[key] = sampler.num

# TODO deprecated
# class PathFrequencyStatistic(WordpairStatistic):
#     def reset(self, sampler):
#         WordpairStatistic.reset(self, sampler)
#         self.comp = [None] * len(sampler.lexicon)
#         for root in sampler.lexicon.roots:
#             comp = [self.word_ids[node.key] for node in root.subtree()]
#             for x in comp:
#                 self.comp[x] = comp
#             for x in comp:
#                 for y in comp:
#                     if x != y:
#                         key = (min(x, y), max(x, y))
#                         self.values[key] = 0
#                         self.last_modified[key] = 0
# 
#     def update(self, sampler):
#         for key in self.values:
#             key_1, key_2 = key
#             if self.comp[key_1] == self.comp[key_2]:
#                 self.values[key] =\
#                     (self.values[key] * self.last_modified[key] +\
#                      (sampler.num - self.last_modified[key])) /\
#                     sampler.num
#             else:
#                 self.values[key] =\
#                     self.values[key] * self.last_modified[key] / sampler.num
#             self.last_modified[key] = sampler.num
# 
#     def edge_added(self, sampler, idx, edge):
#         for key_1 in self.comp[self.word_ids[edge.source.key]]:
#             for key_2 in self.comp[self.word_ids[edge.target.key]]:
#                 key = (min(key_1, key_2), max(key_1, key_2))
#                 if key not in self.values:
#                     self.values[key] = 0
#                     self.last_modified[key] = 0
#                 self.values[key] =\
#                     self.values[key] * self.last_modified[key] / sampler.num
#                 self.last_modified[key] = sampler.num
#         # join the subtrees
#         comp_joined = self.comp[self.word_ids[edge.source.key]] +\
#                       self.comp[self.word_ids[edge.target.key]]
#         for x in comp_joined:
#             self.comp[x] = comp_joined
# 
#     def edge_removed(self, sampler, idx, edge):
#         comp_target = [self.word_ids[node.key] \
#                        for node in edge.target.subtree()]
#         comp_source = [x for x in self.comp[self.word_ids[edge.source.key]]\
#                          if x not in comp_target]
#         for key_1 in comp_source:
#             for key_2 in comp_target:
#                 key = (min(key_1, key_2), max(key_1, key_2))
#                 if key not in self.values:
#                     self.values[key] = 0
#                     self.last_modified[key] = 0
#                 self.values[key] =\
#                     (self.values[key] * self.last_modified[key] +\
#                      (sampler.num - self.last_modified[key])) /\
#                     sampler.num
#                 self.last_modified[key] = sampler.num
#         # split the component
#         for x in comp_source:
#             self.comp[x] = comp_source
#         for x in comp_target:
#             self.comp[x] = comp_target

# #     def next_iter(self, sampler):
# #         if sampler.num % 1000 == 0:
# #             logging.getLogger('main').debug('size of PathFrequencyStatistic dict: %d' %\
# #                 len(self.values))

class RuleStatistic(MCMCStatistic):
    def __init__(self, sampler):
        self.values = {}
        self.last_modified = {}
        self.reset(sampler)

    def reset(self, sampler):
#        for rule in sampler.model.rules:
        for rule in sampler.model.rule_features:
            self.values[rule] = 0.0
            self.last_modified[rule] = 0
    
    def update(self, sampler):
#        for rule in sampler.model.rules:
        for rule in sampler.model.rule_features:
            self.update_rule(rule, sampler)
    
    def update_rule(self, rule, sampler):
        raise Exception('Not implemented!')
    
    def edge_added(self, sampler, idx, edge):
        raise Exception('Not implemented!')

    def edge_removed(self, sampler, idx, edge):
        raise Exception('Not implemented!')

    def next_iter(self, sampler):
        pass
    
    def value(self, rule):
        return self.values[rule]


class RuleFrequencyStatistic(RuleStatistic):
    def update_rule(self, rule, sampler):
        self.values[rule] = \
            (self.values[rule] * self.last_modified[rule] +\
             sampler.lexicon.rules_c[rule] * (sampler.num - self.last_modified[rule])) /\
            sampler.num
        self.last_modified[rule] = sampler.num
    
    def edge_added(self, sampler, idx, edge):
        self.update_rule(edge.rule, sampler)

    def edge_removed(self, sampler, idx, edge):
        self.update_rule(edge.rule, sampler)


# TODO include rule cost
class RuleExpectedContributionStatistic(RuleStatistic):
    def update_rule(self, rule, sampler):
        if self.last_modified[rule] < sampler.num:
            edges = sampler.lexicon.edges_by_rule[rule]
            new_value = sampler.model.cost_of_change([], edges) #TODO + rule_cost
            self.values[rule] = \
                (self.values[rule] * self.last_modified[rule] +\
                 new_value * (sampler.num - self.last_modified[rule])) /\
                sampler.num
            self.last_modified[rule] = sampler.num
    
    def edge_added(self, sampler, idx, edge):
        self.update_rule(edge.rule, sampler)

    def edge_removed(self, sampler, idx, edge):
        self.update_rule(edge.rule, sampler)


# TODO
class RuleChangeCountStatistic(RuleStatistic):
    def reset(self, sampler):
        for rule in sampler.lexicon.ruleset.keys():
            self.values[rule] = 0
            self.last_modified[rule] = 0

    def update_rule(self, rule, sampler):
        pass
    
    def edge_added(self, sampler, idx, word_1, word_2, rule):
        if sampler.lexicon.rules_c[rule] == 1:
            self.values[rule] += 1

    def edge_removed(self, sampler, idx, word_1, word_2, rule):
        if sampler.lexicon.rules_c[rule] == 0:
            self.values[rule] += 1


# TODO deprecated
# class RuleGraphsWithoutStatistic(RuleStatistic):
#     def update_rule(self, rule, sampler):
#         if sampler.lexicon.rules_c[rule] > 0:
#             self.values[rule] = \
#                 self.values[rule] * self.last_modified[rule] / sampler.num
#             self.last_modified[rule] = sampler.num
#         else:
#             self.values[rule] = \
#                 (self.values[rule] * self.last_modified[rule] +\
#                  sampler.num - self.last_modified[rule]) / sampler.num
#     
#     def edge_added(self, sampler, idx, word_1, word_2, rule):
#         if sampler.lexicon.rules_c[rule] == 1:
#             self.values[rule] = \
#                 (self.values[rule] * self.last_modified[rule] +\
#                  sampler.num - self.last_modified[rule]) / sampler.num
#             self.last_modified[rule] = sampler.num
# 
#     def edge_removed(self, sampler, idx, word_1, word_2, rule):
#         if sampler.lexicon.rules_c[rule] == 0:
#             self.values[rule] = \
#                 self.values[rule] * self.last_modified[rule] / sampler.num
#             self.last_modified[rule] = sampler.num


# TODO deprecated
# class RuleIntervalsWithoutStatistic(MCMCStatistic):
#     def __init__(self, sampler):
#         self.intervals = {}
#         self.int_start = {}
#         self.reset(sampler)
# 
#     def reset(self, sampler):
#         for rule in sampler.lexicon.ruleset.keys():
#             self.intervals[rule] = []
#             if sampler.lexicon.rules_c[rule] > 0:
#                 self.int_start[rule] = None
#             else:
#                 self.int_start[rule] = 0
# 
#     def update(self, sampler):
#         for rule in sampler.lexicon.ruleset.keys():
#             if self.int_start[rule] is not None:
#                 self.intervals[rule].append((self.int_start[rule], sampler.num))
#                 self.int_start[rule] = None
#     
#     def edge_added(self, sampler, idx, word_1, word_2, rule):
#         if sampler.lexicon.rules_c[rule] == 1:
#             if self.int_start[rule] is None:
#                 raise Exception('Interval with no left end: %s' % rule)
#             self.intervals[rule].append((self.int_start[rule], sampler.num))
#             self.int_start[rule] = None
# 
#     def edge_removed(self, sampler, idx, word_1, word_2, rule):
#         if sampler.lexicon.rules_c[rule] == 0:
#             self.int_start[rule] = sampler.num
#     
#     def next_iter(self, sampler):
#         pass

### SAMPLERS ###

# TODO monitor the number of moves from each variant and their acceptance rates!
# TODO refactor
class MCMCGraphSampler:
    def __init__(self, model, lexicon, edges, warmup_iter, sampl_iter):
        self.model = model
        self.lexicon = lexicon
        self.edges = edges
        self.edges_hash = defaultdict(lambda: list())
        self.edges_idx = {}
        for idx, e in enumerate(edges):
            self.edges_idx[e] = idx
            self.edges_hash[(e.source, e.target)].append(e)
#        for idx, e in enumerate(edges):
#            self.edges_hash[(e.source, e.target)] = (idx, e)
        self.len_edges = len(edges)
        self.num = 0        # iteration number
        self.stats = {}
        self.warmup_iter = warmup_iter
        self.sampl_iter = sampl_iter
#         self.tr = tracker.SummaryTracker()
#        self.accept_all = False
    
    def add_stat(self, name, stat):
        if name in self.stats:
            raise Exception('Duplicate statistic name: %s' % name)
        self.stats[name] = stat

    def logl(self):
        return self.model.cost()

    def run_sampling(self):
        logging.getLogger('main').info('Warming up the sampler...')
        pp = progress_printer(self.warmup_iter)
        for i in pp:
            self.next()
        self.reset()
        pp = progress_printer(self.sampl_iter)
        logging.getLogger('main').info('Sampling...')
        for i in pp:
            self.next()
        self.update_stats()

    def next(self):
#         if self.num % 10000 == 0:
#             print(asizeof.asized(self, detail=2).format())
#             for stat_name, stat in self.stats.items():
#                 print(stat_name, asizeof.asized(stat, detail=2).format())
        # increase the number of iterations
        self.num += 1

        # select an edge randomly
        edge_idx = random.randrange(self.len_edges)
        edge = self.edges[edge_idx]

        # try the move determined by the selected edge
        try:
            edges_to_add, edges_to_remove, prop_prob_ratio =\
                self.determine_move_proposal(edge)
            acc_prob = self.compute_acc_prob(\
                edges_to_add, edges_to_remove, prop_prob_ratio)
            if acc_prob >= 1 or acc_prob >= random.random():
                self.accept_move(edges_to_add, edges_to_remove)
            for stat in self.stats.values():
                stat.next_iter(self)
        # if move impossible -- discard this iteration
        except ImpossibleMoveException:
            self.num -= 1

    def determine_move_proposal(self, edge):
        if edge in edge.source.edges:
            return self.propose_deleting_edge(edge)
        elif edge.source.has_ancestor(edge.target):
            return self.propose_flip(edge)
        elif edge.target.parent is not None:
            return self.propose_swapping_parent(edge)
        else:
            return self.propose_adding_edge(edge)

    def propose_adding_edge(self, edge):
        return [edge], [], 1

    def propose_deleting_edge(self, edge):
        return [], [edge], 1

    def propose_flip(self, edge):
        if random.random() < 0.5:
            return self.propose_flip_1(edge)
        else:
            return self.propose_flip_2(edge)

    def propose_flip_1(self, edge):
        edges_to_add, edges_to_remove = [], []
        node_1, node_2, node_3, node_4, node_5 = self.nodes_for_flip(edge)

        if not self.edges_hash[(node_3, node_1)]:
            raise ImpossibleMoveException()

        edge_3_1 = random.choice(self.edges_hash[(node_3, node_1)])
        edge_3_2 = self.find_edge_in_lexicon(node_3, node_2)
        edge_4_1 = self.find_edge_in_lexicon(node_4, node_1)

        if edge_3_2 is not None: edges_to_remove.append(edge_3_2)
        if edge_4_1 is not None:
            edges_to_remove.append(edge_4_1)
        else: raise Exception('!')
        edges_to_add.append(edge_3_1)
        prop_prob_ratio = (1/len(self.edges_hash[(node_3, node_1)])) /\
                          (1/len(self.edges_hash[(node_3, node_2)]))

        return edges_to_add, edges_to_remove, prop_prob_ratio

    def propose_flip_2(self, edge):
        edges_to_add, edges_to_remove = [], []
        node_1, node_2, node_3, node_4, node_5 = self.nodes_for_flip(edge)

        if not self.edges_hash[(node_3, node_5)]:
            raise ImpossibleMoveException()

        edge_2_5 = self.find_edge_in_lexicon(node_2, node_5)
        edge_3_2 = self.find_edge_in_lexicon(node_3, node_2)
        edge_3_5 = random.choice(self.edges_hash[(node_3, node_5)])

        if edge_2_5 is not None:
            edges_to_remove.append(edge_2_5)
        elif node_2 != node_5: raise Exception('!')
        if edge_3_2 is not None: edges_to_remove.append(edge_3_2)
        edges_to_add.append(edge_3_5)
        prop_prob_ratio = (1/len(self.edges_hash[(node_3, node_5)])) /\
                          (1/len(self.edges_hash[(node_3, node_2)]))

        return edges_to_add, edges_to_remove, prop_prob_ratio

    def nodes_for_flip(self, edge):
        node_1, node_2 = edge.source, edge.target
        node_3 = node_2.parent\
                              if node_2.parent is not None\
                              else None
        node_4 = node_1.parent
        node_5 = node_4
        if node_5 != node_2:
            while node_5.parent != node_2: 
                node_5 = node_5.parent
        return node_1, node_2, node_3, node_4, node_5

    def find_edge_in_lexicon(self, source, target):
        edges = [e for e in source.edges if e.target == target] 
        return edges[0] if edges else None

    def propose_swapping_parent(self, edge):
        return [edge], [e for e in edge.target.parent.edges\
                          if e.target == edge.target], 1

    def compute_acc_prob(self, edges_to_add, edges_to_remove, prop_prob_ratio):
        return math.exp(\
                -self.model.cost_of_change(edges_to_add, edges_to_remove)) *\
               prop_prob_ratio

    def accept_move(self, edges_to_add, edges_to_remove):
#            print('Accepted')
        # remove edges and update stats
        for e in edges_to_remove:
            idx = self.edges_idx[e]
            self.lexicon.remove_edge(e)
            self.model.apply_change([], [e])
            for stat in self.stats.values():
                stat.edge_removed(self, idx, e)
        # add edges and update stats
        for e in edges_to_add:
            idx = self.edges_idx[e]
            self.lexicon.add_edge(e)
            self.model.apply_change([e], [])
            for stat in self.stats.values():
                stat.edge_added(self, idx, e)
    
    def reset(self):
        self.num = 0
        for stat in self.stats.values():
            stat.reset(self)

    def update_stats(self):
        for stat in self.stats.values():
            stat.update(self)

    def print_scalar_stats(self):
        stats, stat_names = [], []
        print()
        print()
        print('SIMULATION STATISTICS')
        print()
        spacing = max([len(stat_name)\
                       for stat_name, stat in self.stats.items() 
                           if isinstance(stat, ScalarStatistic)]) + 2
        for stat_name, stat in sorted(self.stats.items(), key = itemgetter(0)):
            if isinstance(stat, ScalarStatistic):
                print((' ' * (spacing-len(stat_name)))+stat_name, ':', stat.value())
        print()
        print()

    def log_scalar_stats(self):
        stats, stat_names = [], []
        for stat_name, stat in sorted(self.stats.items(), key = itemgetter(0)):
            if isinstance(stat, ScalarStatistic):
                logging.getLogger('main').info('%s = %f' % (stat_name, stat.value()))

    def save_edge_stats(self, filename):
        stats, stat_names = [], []
        for stat_name, stat in sorted(self.stats.items(), key = itemgetter(0)):
            if isinstance(stat, EdgeStatistic):
                stat_names.append(stat_name)
                stats.append(stat)
        with open_to_write(filename) as fp:
            write_line(fp, ('word_1', 'word_2', 'rule') + tuple(stat_names))
            for i, edge in enumerate(self.edges):
                write_line(fp, 
                           (str(edge.source), str(edge.target), 
                            str(edge.rule)) + tuple([stat.value(i, edge)\
                                                     for stat in stats]))

    def save_rule_stats(self, filename):
        stats, stat_names = [], []
        for stat_name, stat in sorted(self.stats.items(), key = itemgetter(0)):
            if isinstance(stat, RuleStatistic):
                stat_names.append(stat_name)
                stats.append(stat)
        with open_to_write(filename) as fp:
            write_line(fp, ('rule', 'domsize') + tuple(stat_names))
            for rule in self.model.rule_features:
                write_line(fp, (str(rule), self.model.rule_features[rule][0].trials) +\
                               tuple([stat.value(rule) for stat in stats]))

    def save_wordpair_stats(self, filename):
        stats, stat_names = [], []
        keys = set()
        for stat_name, stat in sorted(self.stats.items(), key = itemgetter(0)):
            if isinstance(stat, WordpairStatistic):
                stat_names.append(stat_name)
                stats.append(stat)
                for (idx_1, idx_2) in stat.values:
                    keys.add((stat.words[idx_1], stat.words[idx_2]))
        with open_to_write(filename) as fp:
            write_line(fp, ('word_1', 'word_2', 'rule') + tuple(stat_names))
            for (word_1, word_2) in sorted(list(keys)):
                write_line(fp, 
                           (word_1, word_2) + tuple([stat.value(word_1, word_2)\
                                                     for stat in stats]))
            
    def summary(self):
        self.print_scalar_stats()
        self.save_edge_stats(shared.filenames['sample-edge-stats'])
        self.save_rule_stats(shared.filenames['sample-rule-stats'])
        self.save_wordpair_stats(shared.filenames['sample-wordpair-stats'])

# TODO constructor arguments should be the same for every type
#      (pass ensured edges through the lexicon parameter?)
# TODO init_lexicon() at creation
class MCMCSemiSupervisedGraphSampler(MCMCGraphSampler):
    def __init__(self, model, lexicon, edges, ensured_conn, warmup_iter, sampl_iter):
        MCMCGraphSampler.__init__(self, model, lexicon, edges, warmup_iter, sampl_iter)
        self.ensured_conn = ensured_conn

    def determine_move_proposal(self, edge):
        edges_to_add, edges_to_remove, prop_prob_ratio =\
            MCMCGraphSampler.determine_move_proposal(self, edge)
        removed_conn = set((e.source, e.target) for e in edges_to_remove) -\
                set((e.source, e.target) for e in edges_to_add)
        if removed_conn & self.ensured_conn:
            raise ImpossibleMoveException()
        else:
            return edges_to_add, edges_to_remove, prop_prob_ratio


class MCMCSupervisedGraphSampler(MCMCGraphSampler):
    def __init__(self, model, lexicon, edges, warmup_iter, sampl_iter):
        logging.getLogger('main').debug('Creating a supervised graph sampler.')
        MCMCGraphSampler.__init__(self, model, lexicon, edges, warmup_iter, sampl_iter)
        self.init_lexicon()

    def init_lexicon(self):
        edges_to_add = []
        for key, edges in self.edges_hash.items():
            edges_to_add.append(random.choice(edges))
        self.accept_move(edges_to_add, [])

    def determine_move_proposal(self, edge):
        if edge in edge.source.edges:
            edge_to_add = random.choice(self.edges_hash[(edge.source, edge.target)])
            if edge_to_add == edge:
                raise ImpossibleMoveException()
            return [edge_to_add], [edge], 1
        else:
            edge_to_remove = self.find_edge_in_lexicon(edge.source, edge.target)
            return [edge], [edge_to_remove], 1

    def run_sampling(self):
        self.reset()
        MCMCGraphSampler.run_sampling(self)


# TODO semi-supervised
class MCMCGraphSamplerFactory:
    def new(*args):
        if shared.config['General'].getboolean('supervised'):
            return MCMCSupervisedGraphSampler(*args)
        else:
            return MCMCGraphSampler(*args)


class RuleSetProposalDistribution:
    def __init__(self, rule_scores :Dict[Rule, float], 
                 temperature :float) -> None:
        self.rule_prob = {}     # type: Dict[Rule, float]
        for rule, score in rule_scores.items():
#             rule_score = -rule_costs[rule] +\
#                 (rule_contrib[rule] if rule in rule_contrib else 0)
            self.rule_prob[rule] = expit(score * temperature)

    def propose(self) -> Set[Rule]:
        next_ruleset = set()        # type: Set[Rule]
        for rule, prob in self.rule_prob.items():
            if random.random() < prob:
                next_ruleset.add(rule)
        return next_ruleset

    def proposal_logprob(self, ruleset :Set[Rule]) -> float:
        return sum((np.log(prob) if rule in ruleset else np.log(1-prob)) \
                   for rule, prob in self.rule_prob.items())


class MCMCRuleOptimizer:
    def __init__(self, model :Model, full_graph :FullGraph,
                 warmup_iter :int = 0, sampl_iter: int = 0, 
                 alpha :float = 1, beta :float = 0.01) -> None:
        self.iter_num = 0
        self.model = model
        self.full_graph = full_graph
#         self.lexicon = lexicon
#         self.edges = edges
#         self.full_ruleset = set(model.rule_features)
#         self.full_ruleset = self.model.ruleset
#         self.current_ruleset = self.full_ruleset
#         self.full_model = self.model
        self.current_ruleset = set(self.model.rule_features.keys())
        self.rule_domsize = {}      # type: Dict[Rule, int]
#         self.rule_costs = {}        # type: Dict[Rule, float]
        self.warmup_iter = warmup_iter
        self.sampl_iter = sampl_iter
        self.alpha = alpha
        self.beta = beta
        self.update_temperature()
        for rule in self.current_ruleset:
            self.rule_domsize[rule] = \
                self.model.rule_features[rule][0].trials
#             self.rule_costs[rule] = \
#                 self.model.rule_cost(rule, self.rule_domsize[rule])
        self.cost, self.proposal_dist = \
            self.evaluate_proposal(self.current_ruleset)

    def next(self):
        logging.getLogger('main').debug('temperature = %f' % self.temperature)
        next_ruleset = self.proposal_dist.propose()
#        self.print_proposal(next_ruleset)
        cost, next_proposal_dist = self.evaluate_proposal(next_ruleset)
        acc_prob = 1 if cost < self.cost else \
            math.exp((self.cost - cost) * self.temperature) *\
            math.exp(next_proposal_dist.proposal_logprob(self.ruleset) -\
                     self.proposal_dist.proposal_logprob(next_ruleset))
        logging.getLogger('main').debug('acc_prob = %f' % acc_prob)
        if random.random() < acc_prob:
            self.cost = cost
            self.proposal_dist = next_proposal_dist
            self.accept_ruleset(next_ruleset)
            logging.getLogger('main').debug('accepted')
        else:
            logging.getLogger('main').debug('rejected')
        self.iter_num += 1
        self.update_temperature()

    def evaluate_proposal(self, ruleset :Set[Rule]) \
                         -> Tuple[float, RuleSetProposalDistribution]:
#        self.model.reset()
        new_model = MarginalModel()
        new_model.rootdist = self.model.rootdist
        new_model.ruledist = self.model.ruledist
#        new_model.roots_cost = self.model.roots_cost
        for rule in ruleset:
            new_model.add_rule(rule, self.rule_domsize[rule])
#         self.lexicon.reset()
#         new_model.reset()
#         new_model.add_lexicon(self.lexicon)
#        print(new_model.roots_cost, new_model.rules_cost, new_model.edges_cost, new_model.cost())

#         graph_sampler = MCMCGraphSamplerFactory.new(new_model, self.lexicon,\
#             [edge for edge in self.edges if edge.rule in ruleset],\
#             self.warmup_iter, self.sampl_iter)
        graph_sampler = MCMCGraphSamplerFactory.new(
                            new_model, 
                            self.full_graph.restriction_to_ruleset(ruleset),
                            warmup_iter=self.warmup_iter,
                            sampling_iter=self.sampling_iter)
        graph_sampler.add_stat('cost', ExpectedCostStatistic(graph_sampler))
        graph_sampler.add_stat('acc_rate', AcceptanceRateStatistic(graph_sampler))
        graph_sampler.add_stat('contrib', RuleExpectedContributionStatistic(graph_sampler))
        graph_sampler.run_sampling()
        graph_sampler.log_scalar_stats()

        return graph_sampler.stats['cost'].val,\
            RuleSetProposalDistribution(
                graph_sampler.stats['contrib'].values,
                self.rule_costs, self.temperature)

    def accept_ruleset(self, new_ruleset):
        for rule in self.ruleset - new_ruleset:
            self.model.remove_rule(rule)
        for rule in new_ruleset - self.ruleset:
            self.model.add_rule(rule, self.rule_domsize[rule])
        self.current_ruleset = new_ruleset

    def print_proposal(self, new_ruleset):
        for rule in self.ruleset - new_ruleset:
            print('delete: %s' % str(rule))
        for rule in new_ruleset - self.ruleset:
            print('restore: %s' % str(rule))

    def update_temperature(self):
        self.temperature = (self.iter_num + self.alpha) * self.beta

    def save_rules(self, filename):
        self.model.save_rules_to_file(filename)
#         with open_to_write(filename) as outfp:
#             for rule, freq, domsize in read_tsv_file(shared.filenames['rules']):
#                 if Rule.from_string(rule) in self.model.rule_features:
#                     write_line(outfp, (rule, freq, domsize))

    def save_graph(self, filename):
        raise NotImplementedError()
#         with open_to_write(filename) as outfp:
#             for w1, w2, rule in read_tsv_file(shared.filenames['graph']):
#                 if Rule.from_string(rule) in self.model.rule_features:
#                     write_line(outfp, (w1, w2, rule))


#### AUXILIARY FUNCTIONS ###


def load_edges(filename):
    return list(read_tsv_file(filename, (str, str, str)))


# TODO deprecated
# def save_intervals(intervals, filename):
#     with open_to_write(filename) as fp:
#         for rule, ints in intervals.items():
#             write_line(fp, (rule, len(ints), ' '.join([str(i) for i in ints])))


def mcmc_inference(model :Model, full_graph :FullGraph) -> None:
    # initialize the rule sampler
    warmup_iter = shared.config['modsel'].getint('warmup_iterations')
    sampling_iter = shared.config['modsel'].getint('sampling_iterations')
    alpha = shared.config['modsel'].getfloat('annealing_alpha')
    beta = shared.config['modsel'].getfloat('annealing_beta')
    rule_sampler = MCMCAnnealingRuleSampler(
                       model, full_graph, warmup_iter=warmup_iter,
                       sampling_iter=sampling_iter, alpha=alpha, beta=beta)
    # main loop -- perfom the inference
    iter_num = 0
    while iter_num < shared.config['modsel'].getint('iterations'):
        iter_num += 1
        logging.getLogger('main').info('Iteration %d' % iter_num)
        logging.getLogger('main').info(\
            'num_rules = %d' % rule_sampler.model.num_rules())
        logging.getLogger('main').info('cost = %f' % rule_sampler.cost)
#         rule_sampler.next()
        rule_sampler.save_rules(shared.filenames['rules-modsel'])
        rule_sampler.save_graph(shared.filenames['graph-modsel'])
