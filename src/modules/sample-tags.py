import algorithms.align
import algorithms.fst
import algorithms.mcmc.samplers
import algorithms.mcmc.statistics as stats
from datastruct.graph import EdgeSet, GraphEdge, FullGraph
from datastruct.lexicon import Lexicon, LexiconEntry
from datastruct.rules import RuleSet
from models.suite import ModelSuite
from utils.files import file_exists, open_to_write, write_line
import shared

import hfst
import logging
import re
import subprocess
from typing import List


def extract_tag_symbols_from_rules(rule_set :RuleSet) -> List[str]:
    tags = set()
    for rule in rule_set:
        if rule.tag_subst[0]:
            tags.add(rule.tag_subst[0])
        if rule.tag_subst[1]:
            tags.add(rule.tag_subst[1])
    return sorted(list(tags))


def compute_possible_edges(lexicon :Lexicon, rule_set :RuleSet) -> EdgeSet:
    # build the transducer
    lexicon_tr = lexicon.to_fst()
    tag_seqs = extract_tag_symbols_from_rules(rule_set)
    lexicon_tr.concatenate(algorithms.fst.generator(tag_seqs))
    rules_tr = rule_set.to_fst()
    tr = hfst.HfstTransducer(lexicon_tr)
    tr.compose(rules_tr)
    tr.determinize()
    tr.minimize()
    lexicon_tr.invert()
    tr.compose(lexicon_tr)
    tr.determinize()
    tr.minimize()
    algorithms.fst.save_transducer(tr, 'tr.fsm')
    
    cmd = ['hfst-fst2strings', 'tr.fsm']
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE,
                         stderr=subprocess.DEVNULL, 
                         universal_newlines=True, bufsize=1)
    edge_set = EdgeSet(lexicon)
    while True:
        line = p.stdout.readline().strip()
        if line:
            w1, w2 = line.split(':')
            w1_without_tag = re.sub(shared.compiled_patterns['tag'], '', w1)
            w2_without_tag = re.sub(shared.compiled_patterns['tag'], '', w2)
            if w1_without_tag != w2_without_tag:
                n1 = LexiconEntry(w1)
                n2 = LexiconEntry(w2)
                rules = algorithms.align.extract_all_rules(n1, n2)
                for rule in rules:
                    if rule in rule_set:
                        n1_wt = lexicon.get_by_symstr(w1_without_tag)[0]
                        n2_wt = lexicon.get_by_symstr(w2_without_tag)[0]
                        edge_set.add(GraphEdge(n1_wt, n2_wt, rule))
        else:
            break
    return edge_set


def run() -> None:
    # load the lexicon
    logging.getLogger('main').info('Loading lexicon...')
    lexicon = Lexicon.load(shared.filenames['wordlist'])

    # load the rules
    logging.getLogger('main').info('Loading rules...')
    rules_file = shared.filenames['rules-modsel']
    if not file_exists(rules_file):
        rules_file = shared.filenames['rules']
    rule_set = RuleSet.load(rules_file)

    tagset = extract_tag_symbols_from_rules(rule_set)
    print(tagset)
    print(len(tagset))
    # TODO compute the graph of possible edges
    # TODO save the graph
    edge_set = compute_possible_edges(lexicon, rule_set)
    edge_set.save('possible-edges.txt')

    full_graph = FullGraph(lexicon, edge_set)

    model = ModelSuite.load()
    sampler = \
        algorithms.mcmc.samplers.MCMCTagSampler(\
            full_graph, model, tagset,
            warmup_iter=10000000, sampling_iter=10000000)
    sampler.add_stat('edge_freq', stats.EdgeFrequencyStatistic(sampler))
    sampler.run_sampling()

    with open_to_write('tags.txt') as outfp:
        for w_id in range(len(lexicon)):
            for t_id in range(len(tagset)):    
                write_line(outfp, (lexicon[w_id], ''.join(tagset[t_id]), sampler.tag_freq[w_id,t_id]))
    sampler.save_edge_stats(shared.filenames['sample-edge-stats'])

