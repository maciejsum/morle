from morle.algorithms.em import softem
from morle.datastruct.graph import FullGraph, EdgeSet
from morle.datastruct.lexicon import Lexicon
from morle.datastruct.rules import Rule, RuleSet
# from models.point import PointModel
from morle.models.suite import ModelSuite
from morle.utils.files import file_exists, read_tsv_file
import morle.shared as shared

from collections import defaultdict
import logging


def run() -> None:
    logging.getLogger('main').info('Loading lexicon...')
    lexicon = Lexicon.load(shared.filenames['wordlist'])

    logging.getLogger('main').info('Loading rules...')
    rules_file = shared.filenames['rules-modsel']
    if not file_exists(rules_file):
        rules_file = shared.filenames['rules']
    rule_set = RuleSet.load(rules_file)

    edges_file = shared.filenames['graph-modsel']
    if not file_exists(edges_file):
        edges_file = shared.filenames['graph']
    logging.getLogger('main').info('Loading the graph...')
    edge_set = EdgeSet.load(edges_file, lexicon, rule_set)
    full_graph = FullGraph(lexicon, edge_set)
    if shared.config['General'].getboolean('supervised'):
        full_graph.remove_isolated_nodes()
#     full_graph.load_edges_from_file(graph_file)

    # count rule frequencies in the full graph
#     rule_freq = defaultdict(lambda: 0)
#     for edge in full_graph.iter_edges():
#         rule_freq[edge.rule] += 1

    # initialize a PointModel
    logging.getLogger('main').info('Initializing the model...')
    model = ModelSuite(rule_set, lexicon = lexicon)
#     model = PointModel()
#     model.fit_rootdist(lexicon.entries())
#     model.fit_ruledist(rule for (rule, domsize) in rules)
#     for rule, domsize in rules:
#         model.add_rule(rule, domsize, freq=rule_freq[rule])

    softem(full_graph, model)

