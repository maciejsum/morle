from algorithms.mcmc.statistics import \
    MCMCStatistic, ScalarStatistic, IterationStatistic, EdgeStatistic, \
    RuleStatistic, UnorderedWordPairStatistic
from datastruct.lexicon import LexiconEntry, Lexicon
from datastruct.graph import GraphEdge, Branching, FullGraph
from models.suite import ModelSuite
from utils.files import open_to_write, write_line
import shared

import logging
import math
import numpy as np
from operator import itemgetter
import random
import sys
import tqdm
from typing import List, Tuple


class ImpossibleMoveException(Exception):
    pass


# TODO monitor the number of moves from each variant and their acceptance rates!
class MCMCGraphSampler:
    def __init__(self, full_graph :FullGraph, 
                       model :ModelSuite,
                       warmup_iter :int = 1000,
                       sampling_iter :int = 100000,
                       iter_stat_interval :int = 1) -> None:
        self.full_graph = full_graph
        self.lexicon = full_graph.lexicon
        self.edge_set = full_graph.edge_set
        self.rule_set = model.rule_set
        self.model = model
        self.root_cost_cache = np.empty(len(self.lexicon))
        self.edge_cost_cache = np.empty(len(self.edge_set))
        self.warmup_iter = warmup_iter
        self.sampling_iter = sampling_iter
        self.iter_stat_interval = iter_stat_interval
        self.stats = {}               # type: Dict[str, MCMCStatistic]
        self.iter_num = 0
#         self.reset()

        self.unordered_word_pair_index = {}
        next_id = 0
        for e in self.edge_set:
            key = (min(e.source, e.target), max(e.source, e.target))
            if key not in self.unordered_word_pair_index:
                self.unordered_word_pair_index[key] = next_id
                next_id += 1
    
    def add_stat(self, name: str, stat :MCMCStatistic) -> None:
        if name in self.stats:
            raise Exception('Duplicate statistic name: %s' % name)
        self.stats[name] = stat

    def logl(self) -> float:
        return self._logl

    def set_initial_branching(self, branching :Branching) -> None:
        self._logl = \
            float(np.sum(self.root_cost_cache) + self.model.null_cost() +\
                  self.cost_of_change(list(branching.edges_iter()), []))
        logging.getLogger('main').debug('roots cost = {}'\
            .format(np.sum(self.root_cost_cache)))
        logging.getLogger('main').debug('null cost = {}'\
            .format(self.model.null_cost()))
        logging.getLogger('main').debug('initial branching cost = {}'\
            .format(self.cost_of_change(list(branching.edges_iter()), [])))

    def run_sampling(self) -> None:
        self.cache_costs()
        self.branching = self.full_graph.random_branching()
        self.set_initial_branching(self.branching)
        logging.getLogger('main').debug(\
            'initial log-likelihood: {}'.format(self._logl))
        logging.getLogger('main').info('Warming up the sampler...')
        self.reset()
        for i in tqdm.tqdm(range(self.warmup_iter)):
            self.next()
        logging.getLogger('main').debug(\
            'log-likelihood after warmup: {}'.format(self._logl))
        self.reset()
        logging.getLogger('main').info('Sampling...')
        for i in tqdm.tqdm(range(self.sampling_iter)):
            self.next()
        self.update_stats()

    def next(self) -> None:
        # increase the number of iterations
        self.iter_num += 1

        # select an edge randomly
        edge = self.full_graph.random_edge()

        # try the move determined by the selected edge
        try:
            edges_to_add, edges_to_remove, prop_prob_ratio =\
                self.determine_move_proposal(edge)
            acc_prob = self.compute_acc_prob(\
                edges_to_add, edges_to_remove, prop_prob_ratio)
            if acc_prob >= 1 or acc_prob >= random.random():
                self.accept_move(edges_to_add, edges_to_remove)
        # if move impossible -- propose staying in the current graph
        # (the acceptance probability for that is 1, so this move
        # is automatically accepted and nothing needs to be done
        except ImpossibleMoveException:
            pass

        # inform all the statistics that the iteration is completed
        for stat in self.stats.values():
            stat.next_iter()

    # TODO fit to the new Branching class
    # TODO a more reasonable return value?
    def determine_move_proposal(self, edge :GraphEdge) \
            -> Tuple[List[GraphEdge], List[GraphEdge], float]:
        if self.branching.has_edge(edge.source, edge.target, edge.rule):
            return self.propose_deleting_edge(edge)
        elif self.branching.has_path(edge.target, edge.source):
            return self.propose_flip(edge)
        elif self.branching.parent(edge.target) is not None:
            return self.propose_swapping_parent(edge)
        else:
            return self.propose_adding_edge(edge)

    def propose_adding_edge(self, edge :GraphEdge) \
            -> Tuple[List[GraphEdge], List[GraphEdge], float]:
        return [edge], [], 1

    def propose_deleting_edge(self, edge :GraphEdge) \
            -> Tuple[List[GraphEdge], List[GraphEdge], float]:
        return [], [edge], 1

    def propose_flip(self, edge :GraphEdge) \
            -> Tuple[List[GraphEdge], List[GraphEdge], float]:
        if random.random() < 0.5:
            return self.propose_flip_1(edge)
        else:
            return self.propose_flip_2(edge)

    def propose_flip_1(self, edge :GraphEdge) \
            -> Tuple[List[GraphEdge], List[GraphEdge], float]:
        edges_to_add, edges_to_remove = [], []
        node_1, node_2, node_3, node_4, node_5 = self.nodes_for_flip(edge)

        if not self.full_graph.has_edge(node_3, node_1):
            raise ImpossibleMoveException()

        edge_3_1 = random.choice(self.full_graph.find_edges(node_3, node_1))
        edge_3_2 = self.branching.find_edges(node_3, node_2)[0] \
                   if self.branching.has_edge(node_3, node_2) else None
        edge_4_1 = self.branching.find_edges(node_4, node_1)[0] \
                   if self.branching.has_edge(node_4, node_1) else None

        if edge_3_2 is not None: edges_to_remove.append(edge_3_2)
        if edge_4_1 is not None:
            edges_to_remove.append(edge_4_1)
        else: raise Exception('!')
        edges_to_add.append(edge_3_1)
        prop_prob_ratio = (1/len(self.full_graph.find_edges(node_3, node_1))) /\
                          (1/len(self.full_graph.find_edges(node_3, node_2)))

        return edges_to_add, edges_to_remove, prop_prob_ratio

    def propose_flip_2(self, edge :GraphEdge) \
            -> Tuple[List[GraphEdge], List[GraphEdge], float]:
        edges_to_add, edges_to_remove = [], []
        node_1, node_2, node_3, node_4, node_5 = self.nodes_for_flip(edge)

        if not self.full_graph.has_edge(node_3, node_5):
            raise ImpossibleMoveException()

        edge_2_5 = self.branching.find_edges(node_2, node_5)[0] \
                   if self.branching.has_edge(node_2, node_5) else None
        edge_3_2 = self.branching.find_edges(node_3, node_2)[0] \
                   if self.branching.has_edge(node_3, node_2) else None
        edge_3_5 = random.choice(self.full_graph.find_edges(node_3, node_5))

        if edge_2_5 is not None:
            edges_to_remove.append(edge_2_5)
        elif node_2 != node_5: raise Exception('!')     # TODO ???
        if edge_3_2 is not None: edges_to_remove.append(edge_3_2)
        edges_to_add.append(edge_3_5)
        prop_prob_ratio = (1/len(self.full_graph.find_edges(node_3, node_5))) /\
                          (1/len(self.full_graph.find_edges(node_3, node_2)))

        return edges_to_add, edges_to_remove, prop_prob_ratio

    def nodes_for_flip(self, edge :GraphEdge) -> List[LexiconEntry]:
        node_1, node_2 = edge.source, edge.target
        node_3 = self.branching.parent(node_2)
        node_4 = self.branching.parent(node_1)
        node_5 = node_4
        if node_5 != node_2:
            while self.branching.parent(node_5) != node_2: 
                node_5 = self.branching.parent(node_5)
        return [node_1, node_2, node_3, node_4, node_5]

    def find_edge_in_full_graph(self, source, target):
        edges = [e for e in source.edges if e.target == target] 
        return edges[0] if edges else None

    def propose_swapping_parent(self, edge :GraphEdge) \
                             -> Tuple[List[GraphEdge], List[GraphEdge], float]:
        edges_to_remove = self.branching.find_edges(
                              self.branching.parent(edge.target),
                              edge.target)
        return [edge], edges_to_remove, 1

    def compute_acc_prob(self, edges_to_add :List[GraphEdge], 
                         edges_to_remove :List[GraphEdge], 
                         prop_prob_ratio :float) -> float:
        cost = self.cost_of_change(edges_to_add, edges_to_remove)
        if cost < math.log(prop_prob_ratio):
            return 1.0
        else: 
            return math.exp(-cost) * prop_prob_ratio
#         try:
#             return math.exp(\
#                     -self.cost_of_change(edges_to_add, edges_to_remove)) *\
#                    prop_prob_ratio
#         except OverflowError as e:
#             logging.getLogger('main').debug('OverflowError')
#             cost = -self.cost_of_change(edges_to_add, edges_to_remove)
#             if edges_to_add:
#                 logging.getLogger('main').debug('adding:')
#                 for edge in edges_to_add:
#                     logging.getLogger('main').debug(
#                         '{} {} {} {}'.format(edge.source, edge.target,
#                                              edge.rule, self.model.edge_cost(edge)))
#             if edges_to_remove:
#                 logging.getLogger('main').debug('deleting:')
#                 for edge in edges_to_remove:
#                     logging.getLogger('main').debug(
#                         '{} {} {} {}'.format(edge.source, edge.target,
#                                              edge.rule, -self.model.edge_cost(edge)))
#             logging.getLogger('main').debug('total cost: {}'.format(cost))
#             return 1.0

    def cache_costs(self) -> None:
        logging.getLogger('main').info('Computing root costs...')
        self.root_cost_cache = self.model.roots_cost(self.lexicon)
        logging.getLogger('main').info('Computing edge costs...')
        self.edge_cost_cache = self.model.edges_cost(self.edge_set)
        if (np.any(np.isnan(self.root_cost_cache))):
            logging.getLogger('main').warn('NaN in root costs!')
        if (np.any(np.isnan(self.edge_cost_cache))):
            logging.getLogger('main').warn('NaN in edge costs!')
       

    def cost_of_change(self, edges_to_add :List[GraphEdge], 
                       edges_to_remove :List[GraphEdge]) -> float:
        result = 0.0
        for e in edges_to_add:
            result += self.edge_cost_cache[self.edge_set.get_id(e)]
            result -= self.root_cost_cache[self.lexicon.get_id(e.target)]
        for e in edges_to_remove:
            result -= self.edge_cost_cache[self.edge_set.get_id(e)]
            result += self.root_cost_cache[self.lexicon.get_id(e.target)]
        return float(result)

    def accept_move(self, edges_to_add, edges_to_remove):
        self._logl += self.cost_of_change(edges_to_add, edges_to_remove)
        if np.isnan(self._logl):
            logging.getLogger('main').info('adding:')
            for e in edges_to_add:
                print(e.source, e.target, e.rule, \
                      self.edge_cost_cache[self.edge_set.get_id(edge)])
            logging.getLogger('main').info('deleting:')
            for e in edges_to_remove:
                print(e.source, e.target, e.rule, \
                      self.edge_cost_cache[self.edge_set.get_id(edge)])
            raise RuntimeError('NaN log-likelihood at iteration {}'\
                               .format(self.iter_num))
        # remove edges and update stats
        for e in edges_to_remove:
            self.branching.remove_edge(e)
#             self.model.apply_change([], [e])
            for stat in self.stats.values():
                stat.edge_removed(e)
        # add edges and update stats
        for e in edges_to_add:
            self.branching.add_edge(e)
#             self.model.apply_change([e], [])
            for stat in self.stats.values():
                stat.edge_added(e)
    
    def reset(self):
        self.iter_num = 0
        for stat in self.stats.values():
            stat.reset()

    def update_stats(self):
        for stat in self.stats.values():
            stat.update()

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
            for idx, edge in enumerate(self.edge_set):
                write_line(fp, 
                           (str(edge.source), str(edge.target), 
                            str(edge.rule)) + tuple([stat.val[idx]\
                                                     for stat in stats]))

    def save_rule_stats(self, filename):
        stats, stat_names = [], []
        for stat_name, stat in sorted(self.stats.items(), key = itemgetter(0)):
            if isinstance(stat, RuleStatistic):
                stat_names.append(stat_name)
                stats.append(stat)
        with open_to_write(filename) as fp:
            write_line(fp, ('rule',) + tuple(stat_names))
            for idx, rule in enumerate(self.rule_set):
                write_line(fp, (str(rule),) +\
                               tuple([stat.val[idx] for stat in stats]))

    def save_wordpair_stats(self, filename):
        stats, stat_names = [], []
        for stat_name, stat in sorted(self.stats.items(), key = itemgetter(0)):
            if isinstance(stat, UnorderedWordPairStatistic):
                stat_names.append(stat_name)
                stats.append(stat)
        with open_to_write(filename) as fp:
            write_line(fp, ('word_1', 'word_2') + tuple(stat_names))
            for key in self.unordered_word_pair_index:
                write_line(fp, key +\
                               tuple([stat.value(key) for stat in stats]))

    def save_iter_stats(self, filename :str) -> None:
        stats, stat_names = [], []
        for stat_name, stat in sorted(self.stats.items(), key = itemgetter(0)):
            if isinstance(stat, IterationStatistic):
                stat_names.append(stat_name)
                stats.append(stat)
        with open_to_write(filename) as fp:
            write_line(fp, ('iter_num',) + tuple(stat_names))
            for iter_num in range(self.iter_stat_interval, 
                                  self.sampling_iter+1, 
                                  self.iter_stat_interval):
                write_line(fp, (str(iter_num),) + \
                               tuple([stat.value(iter_num) for stat in stats]))
            
    def summary(self):
        self.print_scalar_stats()
        self.save_iter_stats(shared.filenames['sample-iter-stats'])
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
    def new(*args, **kwargs):
        if shared.config['General'].getboolean('supervised'):
            return MCMCSupervisedGraphSampler(*args, **kwargs)
        else:
            return MCMCGraphSampler(*args, **kwargs)


class MCMCTagSamplerRootsOnly:

    def __init__(self, lexicon :Lexicon, 
                       model :ModelSuite,
                       tagset :List[Tuple[str]],
                       warmup_iter :int = 1000,
                       sampling_iter :int = 100000,
                       iter_stat_interval :int = 1) -> None:
        self.lexicon = lexicon
        self.model = model
        self.warmup_iter = warmup_iter
        self.sampling_iter = sampling_iter
        self.iter_stat_interval = iter_stat_interval
        self.stats = {}               # type: Dict[str, MCMCStatistic]
        # fields related to the tags
        self.tagset = tagset
#         self.tag_idx = { tag : i for i, tag in enumerate(tagset) }
        self.current_tag = \
            np.random.randint(len(self.tagset), size=len(self.lexicon))
        self.root_cost_cache = np.empty((len(self.lexicon), len(self.tagset)))
        print('Computing root costs...')
        for w_id, entry in tqdm.tqdm(enumerate(lexicon), total=len(lexicon)):
            for t_id, tag in enumerate(tagset):
                self.root_cost_cache[w_id,t_id] = \
                    self.model.root_cost(LexiconEntry(''.join(entry.word) + \
                                                      ''.join(tag)))
        self.reset()

    def run_sampling(self):
        logging.getLogger('main').info('Warming up the sampler...')
        self.reset()
        for i in tqdm.tqdm(range(self.warmup_iter)):
            self.next()
        self.reset()
        logging.getLogger('main').info('Sampling...')
        for i in tqdm.tqdm(range(self.sampling_iter)):
            self.next()
        self.finalize()

    def reset(self):
        self.iter_num = 0
        self.tag_freq = np.zeros((len(self.lexicon), len(self.tagset)))
        self.last_modified = np.zeros(len(self.lexicon))

    def next(self):
        # increase the number of iterations
        self.iter_num += 1

        # select a root and a new tag randomly
        w_id = np.random.randint(len(self.lexicon))
        tag_id = np.random.randint(len(self.tagset))

        # compute the cost of retagging
#         cost = self.model.root_cost(new_root) - self.model.root_cost(old_root)
        cost = self.root_cost_cache[w_id,tag_id] - \
               self.root_cost_cache[w_id,self.current_tag[w_id]]
        acc_prob = 1.0 if cost < 0 else math.exp(-cost)
        if random.random() < acc_prob:
            # accept move
            last_tag_one_hot = np.zeros(len(self.tagset))
            last_tag_one_hot[self.current_tag[w_id]] = 1
            self.tag_freq[w_id,:] = \
                self.tag_freq[w_id,:] * \
                    (self.last_modified[w_id] / self.iter_num) + \
                last_tag_one_hot * \
                    ((self.iter_num-self.last_modified[w_id]) / self.iter_num)
            self.current_tag[w_id] = tag_id
            self.last_modified[w_id] = self.iter_num

    def finalize(self):
        self.last_tag = np.zeros((len(self.lexicon), len(self.tagset)))
        for i in range(len(self.lexicon)):
            self.last_tag[i, self.current_tag[i]] = 1
        T = len(self.tagset)
        self.tag_freq = \
            self.tag_freq * \
            np.tile(self.last_modified / self.iter_num, (T, 1)).T + \
            self.last_tag * \
                np.tile((self.iter_num-self.last_modified) / self.iter_num,
                        (T, 1)).T


class MCMCTagSamplerMove:
    def __init__(self):
        self.nodes_to_retag = set()
        self.edges_to_add = set()
        self.edges_to_remove = set()
        self.roots_to_add = set()
        self.roots_to_remove = set()

    def __bool__(self):
        return bool(self.nodes_to_retag) or bool(self.edges_to_add) or \
               bool(self.edges_to_remove)

    def join(self, other :'MCMCSamplerMove') -> None:
        self.nodes_to_retag |= other.nodes_to_retag
        self.roots_to_add |= other.roots_to_add
        self.roots_to_remove |= other.roots_to_remove
        self.edges_to_add |= other.edges_to_add
        self.edges_to_remove |= other.edges_to_remove


class MCMCTagSampler:

    # TODO
    # a sampler with edges, but only adding/deleting an edge when possible
    # NEXT: support statistics (esp. edge frequency)
    # THEN: additional moves to make adding an edge possible

    # TODO proposals: use edge IDs instead of concrete edges!!!
    # TODO tagset as parameter

    def __init__(self, full_graph :FullGraph,
                       model :ModelSuite,
                       tagset :List[Tuple[str]],
                       warmup_iter :int = 1000,
                       sampling_iter :int = 100000,
                       iter_stat_interval :int = 1) -> None:
        self.full_graph = full_graph
        self.lexicon = full_graph.lexicon
        self.edge_set = full_graph.edge_set
        self.model = model
        self.warmup_iter = warmup_iter
        self.sampling_iter = sampling_iter
        self.iter_stat_interval = iter_stat_interval
        self.stats = {}               # type: Dict[str, MCMCStatistic]
        self.branching = self.full_graph.empty_branching()
        # fields related to the tags
        self.tagset = tagset
        self.tag_idx = { tag : i for i, tag in enumerate(tagset) }
        self.current_tag = \
            np.random.randint(len(self.tagset), size=len(self.lexicon))
        self.root_cost_cache = np.empty((len(self.lexicon), len(self.tagset)))
        # TODO move to a separate method: cache_costs()
        print('Computing root costs...')
        for w_id, entry in tqdm.tqdm(enumerate(self.lexicon), total=len(self.lexicon)):
            for t_id, tag in enumerate(tagset):
                self.root_cost_cache[w_id,t_id] = \
                    self.model.root_cost(LexiconEntry(''.join(entry.word) + \
                                                      ''.join(tag)))
        print('Computing edge costs...')
        self.edge_cost_cache = self.model.edges_cost(self.edge_set)
        self.reset()

    def add_stat(self, name: str, stat :MCMCStatistic) -> None:
        if name in self.stats:
            raise Exception('Duplicate statistic name: %s' % name)
        self.stats[name] = stat

    def run_sampling(self):
        logging.getLogger('main').info('Warming up the sampler...')
        self.reset()
        for i in tqdm.tqdm(range(self.warmup_iter)):
            self.next()
        self.reset()
        logging.getLogger('main').info('Sampling...')
        for i in tqdm.tqdm(range(self.sampling_iter)):
            self.next()
        print('Impossible moves: {} ({:.2} %)'\
                  .format(self.impossible_moves,
                          self.impossible_moves / self.sampling_iter * 100))
        self.finalize()

    def reset(self):
        '''Reset all statistics.'''
        self.iter_num = 0
        self.impossible_moves = 0
        self.tag_freq = np.zeros((len(self.lexicon), len(self.tagset)))
        self.last_modified = np.zeros(len(self.lexicon))
        for stat in self.stats.values():
            stat.reset()

    def next(self):
        # increase the number of iterations
        self.iter_num += 1

        # TODO
        # - choose whether we are changing a node or an edge
        # - if changing a node:
        #   - choose new tag
        #   - propose_retagging_node(node, new_tag)
        # - if changing an edge:
        #   - if the edge is present -> propose deleting
        #   - the node has an ingoing edge -> break
        #   - the edge would create a cycle -> break
        #   - else: propose adding the edge
        #   - propose retagging the source and the target node

        try:
            move = self.choose_and_change_a_node() \
                   if random.random() < 0.1 \
                   else self.choose_and_change_an_edge()
            cost = self.move_cost(move)
            acc_prob = 1.0 if cost < 0 else math.exp(-cost)
            if move and random.random() < acc_prob:
                self.accept_move(move)

        except ImpossibleMoveException:
            self.impossible_moves += 1
#             pass

    def move_cost(self, move :MCMCTagSamplerMove) -> float:
        cost = 0.0
#         for (w_id, tag_id) in move.nodes_to_retag:
#             # TODO ONLY if a word is a root
#             cost += self.root_cost_cache[w_id, tag_id] \
#                     - self.root_cost_cache[w_id, self.current_tag[w_id]]
#         for (w_id, tag_id) in move.roots_to_delete:
#             cost -= self.root_cost_cache[w_id, tag_id]
        for e_id in move.edges_to_add:
            cost += self.edge_cost_cache[e_id]
        for e_id in move.edges_to_remove:
            cost -= self.edge_cost_cache[e_id]
        for (r_id, t_id) in move.roots_to_add:
            cost += self.root_cost_cache[r_id,t_id]
        for (r_id, t_id) in move.roots_to_remove:
            cost -= self.root_cost_cache[r_id,t_id]
        return cost

    def accept_move(self, move :MCMCTagSamplerMove) -> None:
        for (w_id, tag_id) in move.nodes_to_retag:
            last_tag_one_hot = np.zeros(len(self.tagset))
            last_tag_one_hot[self.current_tag[w_id]] = 1
            self.tag_freq[w_id,:] = \
                self.tag_freq[w_id,:] * \
                    (self.last_modified[w_id] / self.iter_num) + \
                last_tag_one_hot * \
                    ((self.iter_num-self.last_modified[w_id]) / self.iter_num)
            self.current_tag[w_id] = tag_id
            self.last_modified[w_id] = self.iter_num
        for e_id in move.edges_to_add:
#             edge = self.edge_set[e_id]
#             print('Adding edge: {} {} {}'.format(edge.source, edge.target, str(edge.rule)))
            self.branching.add_edge(self.edge_set[e_id])
            edge = self.edge_set[e_id]
            for stat in self.stats.values():
                stat.edge_added(edge)
        for e_id in move.edges_to_remove:
#             edge = self.edge_set[e_id]
#             print('Deleting edge: {} {} {}'.format(edge.source, edge.target, str(edge.rule)))
            self.branching.remove_edge(self.edge_set[e_id])
            edge = self.edge_set[e_id]
            for stat in self.stats.values():
                stat.edge_removed(edge)

    def choose_and_change_a_node(self) -> MCMCTagSamplerMove:
        # select a root and a new tag randomly
        w_id = np.random.randint(len(self.lexicon))
        tag_id = np.random.randint(len(self.tagset))
        return self.propose_retagging_node(self.lexicon[w_id], self.tagset[tag_id])

    def choose_and_change_an_edge(self) -> MCMCTagSamplerMove:
        edge = self.full_graph.random_edge()

        # TODO check whether the edge is already present
        if self.branching.has_edge(edge.source, edge.target, edge.rule):
            return self.propose_deleting_edge(edge)
        elif self.branching.has_path(edge.target, edge.source):
            raise ImpossibleMoveException()
#             return self.propose_flip(edge)
        elif self.branching.parent(edge.target) is not None:
            raise ImpossibleMoveException()
#             return self.propose_swapping_parent(edge)
        else:
            return self.propose_adding_edge(edge)
        # TODO check whether the target node already has an ingoing node
        # TODO check whether the edge would create a cycle
        # TODO propose adding edge and perform the required retaggings
        

    def finalize(self):
        '''Update the statistic values after the last iteration.'''
        self.last_tag = np.zeros((len(self.lexicon), len(self.tagset)))
        for i in range(len(self.lexicon)):
            self.last_tag[i, self.current_tag[i]] = 1
        T = len(self.tagset)
        self.tag_freq = \
            self.tag_freq * \
            np.tile(self.last_modified / self.iter_num, (T, 1)).T + \
            self.last_tag * \
                np.tile((self.iter_num-self.last_modified) / self.iter_num,
                        (T, 1)).T
        for stat in self.stats.values():
            stat.update()

    # TODO change the methods below to include retagging

    def propose_retagging_edge(self, old_edge, new_source_tag, new_target_tag) \
                              -> MCMCTagSamplerMove:
        '''Change the edge rule to fit the prescribed tags. If no suitable
           edge is found, just remove the current edge.'''
        move = MCMCTagSamplerMove()
        move.edges_to_remove.add(self.edge_set.get_id(old_edge))
        new_edges = []
        for e in self.full_graph.edges_between(old_edge.source, old_edge.target):
            if e.rule.tag_subst[0] == new_source_tag and \
                    e.rule.tag_subst[1] == new_target_tag:
                new_edges.append(e)
        if not new_edges:
            move.roots_to_add.add((self.lexicon.get_id(old_edge.target), self.tag_idx[new_target_tag]))
        else:
            move.edges_to_add.add(self.edge_set.get_id(random.choice(new_edges)))
        return move

    def propose_retagging_node(self, node :LexiconEntry, tag :Tuple[str]) \
                              -> MCMCTagSamplerMove:
        move = MCMCTagSamplerMove()
        w_id = self.lexicon.get_id(node)
        tag_id = self.tag_idx[tag]
        if tag_id != self.current_tag[w_id]:
            node = self.lexicon[w_id]
            move.nodes_to_retag.add((w_id, tag_id))
            if self.branching.parent(node) is None:
                # retag as root
                move.roots_to_remove.add((w_id, self.current_tag[w_id]))
                move.roots_to_add.add((w_id, tag_id))
            else:
                ingoing_edge = list(self.branching.ingoing_edges(node))[0]
                move.join(\
                    self.propose_retagging_edge(\
                        ingoing_edge,
                        ingoing_edge.rule.tag_subst[0],
                        self.tagset[tag_id]))
            for edge in self.branching.outgoing_edges(node):
                move.join(\
                    self.propose_retagging_edge(\
                        edge,
                        self.tagset[tag_id],
                        edge.rule.tag_subst[1]))
        return move

    def propose_deleting_edge(self, edge :GraphEdge) -> MCMCTagSamplerMove:
        move = MCMCTagSamplerMove()
        move.edges_to_remove.add(self.edge_set.get_id(edge))
        return move

    def propose_adding_edge(self, edge :GraphEdge) -> MCMCTagSamplerMove:
        cur_source_tag = \
            self.tagset[self.current_tag[self.lexicon.get_id(edge.source)]]
        cur_target_tag = \
            self.tagset[self.current_tag[self.lexicon.get_id(edge.target)]]
        move = MCMCTagSamplerMove()
        move.edges_to_add.add(self.edge_set.get_id(edge))
        move.join(self.propose_retagging_node(edge.source, edge.rule.tag_subst[0]))
        move.join(self.propose_retagging_node(edge.target, edge.rule.tag_subst[1]))
        return move

    def save_edge_stats(self, filename):
        stats, stat_names = [], []
        for stat_name, stat in sorted(self.stats.items(), key = itemgetter(0)):
            if isinstance(stat, EdgeStatistic):
                stat_names.append(stat_name)
                stats.append(stat)
        with open_to_write(filename) as fp:
            write_line(fp, ('word_1', 'word_2', 'rule') + tuple(stat_names))
            for idx, edge in enumerate(self.edge_set):
                write_line(fp, 
                           (str(edge.source), str(edge.target), 
                            str(edge.rule)) + tuple([stat.val[idx]\
                                                     for stat in stats]))

# 
#     def propose_flip(self, edge :GraphEdge) \
#             -> Tuple[List[GraphEdge], List[GraphEdge], float]:
#         if random.random() < 0.5:
#             return self.propose_flip_1(edge)
#         else:
#             return self.propose_flip_2(edge)

#     def propose_flip_1(self, edge :GraphEdge) \
#             -> Tuple[List[GraphEdge], List[GraphEdge], float]:
#         edges_to_add, edges_to_remove = [], []
#         node_1, node_2, node_3, node_4, node_5 = self.nodes_for_flip(edge)
# 
#         if not self.full_graph.has_edge(node_3, node_1):
#             raise ImpossibleMoveException()
# 
#         edge_3_1 = random.choice(self.full_graph.find_edges(node_3, node_1))
#         edge_3_2 = self.branching.find_edges(node_3, node_2)[0] \
#                    if self.branching.has_edge(node_3, node_2) else None
#         edge_4_1 = self.branching.find_edges(node_4, node_1)[0] \
#                    if self.branching.has_edge(node_4, node_1) else None
# 
#         if edge_3_2 is not None: edges_to_remove.append(edge_3_2)
#         if edge_4_1 is not None:
#             edges_to_remove.append(edge_4_1)
#         else: raise Exception('!')
#         edges_to_add.append(edge_3_1)
#         prop_prob_ratio = (1/len(self.full_graph.find_edges(node_3, node_1))) /\
#                           (1/len(self.full_graph.find_edges(node_3, node_2)))
# 
#         return edges_to_add, edges_to_remove, prop_prob_ratio
# 
#     def propose_flip_2(self, edge :GraphEdge) \
#             -> Tuple[List[GraphEdge], List[GraphEdge], float]:
#         edges_to_add, edges_to_remove = [], []
#         node_1, node_2, node_3, node_4, node_5 = self.nodes_for_flip(edge)
# 
#         if not self.full_graph.has_edge(node_3, node_5):
#             raise ImpossibleMoveException()
# 
#         edge_2_5 = self.branching.find_edges(node_2, node_5)[0] \
#                    if self.branching.has_edge(node_2, node_5) else None
#         edge_3_2 = self.branching.find_edges(node_3, node_2)[0] \
#                    if self.branching.has_edge(node_3, node_2) else None
#         edge_3_5 = random.choice(self.full_graph.find_edges(node_3, node_5))
# 
#         if edge_2_5 is not None:
#             edges_to_remove.append(edge_2_5)
#         elif node_2 != node_5: raise Exception('!')     # TODO ???
#         if edge_3_2 is not None: edges_to_remove.append(edge_3_2)
#         edges_to_add.append(edge_3_5)
#         prop_prob_ratio = (1/len(self.full_graph.find_edges(node_3, node_5))) /\
#                           (1/len(self.full_graph.find_edges(node_3, node_2)))
# 
#         return edges_to_add, edges_to_remove, prop_prob_ratio
#         # propose the next move:
#         # - an edge randomly from the full graph
#         # - if the edge is already present in the graph -> try to remove it
#         # - otherwise -> try to add it:
#         #   - same cases as in the normal sampler (swap parent, flip etc.)
#         #   - then: additional edge changes needed because of retagging
#         #     (ingoing edge of w_1, all outgoing edges of w_1 and w_2)
#         pass
# 
#         def retag_ingoing_edge(self, node, new_tag) ->
#             -> Tuple[List[GraphEdge], List[GraphEdge], float]:
#             pass
# 
#         def retag_outgoing_edge(self, node, new_tag) ->
#             -> Tuple[List[GraphEdge], List[GraphEdge], float]:
#             pass

