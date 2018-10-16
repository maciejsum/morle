from algorithms.analyzer import Analyzer
import algorithms.fst
from datastruct.lexicon import Lexicon, LexiconEntry, unnormalize_word
from models.suite import ModelSuite
from utils.files import file_exists, full_path, open_to_write
import shared

# from operator import itemgetter
import hfst
import logging
import math
from scipy.stats import norm
import subprocess


# TODO
# - refactor edge cost computation
# - optimize edge cost computation?
# - 

def get_analyzer(filename, lexicon, model):
    if file_exists(filename):
        analyzer = Analyzer.load(filename, lexicon, model)
    else:
        analyzer = Analyzer(lexicon, model)
        analyzer.save(filename)
    return analyzer


def create_new_words_acceptor_if_not_exists(filename, analyzer, lexicon):
    if not file_exists(filename):
        new_words_acceptor = hfst.HfstTransducer(analyzer.fst)
        new_words_acceptor.convert(
            hfst.ImplementationType.TROPICAL_OPENFST_TYPE)
        new_words_acceptor.input_project()
        new_words_acceptor.minimize()
        new_words_acceptor.subtract(lexicon.to_fst())
        new_words_acceptor.minimize()
        algorithms.fst.save_transducer(new_words_acceptor, filename)


def run() -> None:
    lexicon = Lexicon.load(shared.filenames['wordlist'])
    model = ModelSuite.load()
    analyzer = get_analyzer('analyzer.fsm', lexicon, model)
    tr_file = 'wordgen.fst'
    create_new_words_acceptor_if_not_exists(tr_file, analyzer, lexicon)

    logging.getLogger('main').info('Generating...')
    cmd = ['hfst-fst2strings', full_path(tr_file)]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE,
                         stderr=subprocess.DEVNULL, 
                         universal_newlines=True, bufsize=1)
    # TODO
    log_max_freq = math.log(5)
    log_min_freq = 0
#     with open_to_write(shared.filenames['wordgen']) as fp:
    while True:
        try: 
            line = p.stdout.readline().strip()
            if line:
                word = unnormalize_word(line.rstrip())
                analyses = analyzer.analyze(LexiconEntry(word), compute_cost=False)
                if not analyses:
                    continue
                word_prob_ratio = 0
                for e in analyses:
                    r_id = model.rule_set.get_id(e.rule)
                    prob = model.edge_model.edge_prob(e)
                    mean = e.source.logfreq + \
                           model.edge_frequency_model.means[r_id]
                    sdev = model.edge_frequency_model.sdevs[r_id]
                    prob *= (norm.cdf(log_max_freq, mean, sdev) -
                             norm.cdf(log_min_freq, mean, sdev))
                    word_prob_ratio += prob / (1-prob)
                    print(str(e), prob)
                if word_prob_ratio > 0:
                    print(word, -math.log(word_prob_ratio), sep='\t')
            else:
                break
        except Exception as e:
            logging.getLogger('main').warning(str(e))

