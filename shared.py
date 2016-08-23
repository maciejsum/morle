import re

# shared
# .config -- saved in a configuration file in the working dir
# .working_dir -- working directory
# .filenames
# .patterns
# ...

# configuration and working directory -- set at runtime by the 'main' module

config = None

options = {\
    'quiet' : False,
    'verbose' : False,
    'working_dir' : ''
}

# filenames and patterns -- not changed at runtime

filenames = {\
    'config' : 'config.ini',
    'config-default' : 'config-default.ini',
    'graph' : 'graph.txt',
    'index' : 'index.txt',
    'log'   : 'log.txt',
    'rules' : 'rules.txt',
    'rules-modsel' : 'rules-modsel.txt',
    'rules-fit' : 'rules-fit.txt',
    'sample-edge-stats' : 'sample-edge-stats.txt',
    'sample-rule-stats' : 'sample-rule-stats.txt',
    'wordlist' : 'input.training'
}

format = {\
    'vector_sep' : ' ',
    'rule_subst_sep' : ':',
    'rule_part_sep' : '/',
    'rule_tag_sep' : '___'
}

patterns = {}
patterns['symbol'] = '(?:[\w-]|\{[A-Z0-9]+\})'
patterns['tag'] = '(?:<[A-Z0-9]+>)'
patterns['word'] = '^(?P<word>%s+)(?P<tag>%s*)$' %\
                          (patterns['symbol'], patterns['tag'])

patterns['rule_subst'] = '%s*%s%s*' %\
                              (patterns['symbol'], format['rule_subst_sep'], patterns['symbol'])
patterns['rule_named_subst'] = '(?P<x>%s*)%s(?P<y>%s*)' %\
                              (patterns['symbol'], format['rule_subst_sep'], patterns['symbol'])
patterns['rule_tag_subst'] = '%s*%s%s*' %\
                              (patterns['tag'], format['rule_subst_sep'], patterns['tag'])
patterns['rule'] = '^(?P<subst>%s(%s)*)(?:%s(?P<tag_subst>%s))?$' %\
                              (patterns['rule_subst'],
                               format['rule_part_sep']+patterns['rule_subst'],
                               format['rule_tag_sep'],
                               patterns['rule_tag_subst'])
patterns['rule_named_tag_subst'] = '(?P<x>%s*)%s(?P<y>%s*)' %\
                               (patterns['tag'], format['rule_subst_sep'], patterns['tag'])

compiled_patterns = {}
for key, val in patterns.items():
    compiled_patterns[key] = re.compile(val)

