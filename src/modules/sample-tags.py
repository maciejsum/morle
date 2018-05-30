import algorithms.align
import algorithms.fst
from datastruct.graph import EdgeSet, GraphEdge
from datastruct.lexicon import Lexicon, LexiconEntry
from datastruct.rules import RuleSet
from models.suite import ModelSuite
from utils.files import file_exists
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
    # TODO compute the graph of possible edges
    # TODO save the graph
#     edges = compute_possible_edges(lexicon, rule_set)
#     edges.save('possible-edges.txt')

    model = ModelSuite.load()
    sampler = \
        algorithms.mcmc.samplers.MCMCTagSamplerRootsOnly(\
            lexicon, model, tagset,
            warmup_iter=100000, sampling_iter=1000000)
    sampler.run_sampling()

    # TODO save results

