import algorithms.branching
import algorithms.ngrams
import algorithms.optrules
import algorithms.align
from algorithms.optrules import extract_all_rules
from datastruct.lexicon import *
from datastruct.rules import *
from utils.files import *
from utils.printer import *
import settings
import re

import math

GRAPH_MDL_FILE = 'graph_mdl.txt'
GAMMA_THRESHOLD = 1e-20

# TODO:
# - integrate optrules into the module
#	- patterns, make_rule etc. -> datastruct.rules
# - settings (e.g. filenames)
#   - lexicon.training
#   - wordlist.training
#   - wordlist.testing
#   - lexicon.gs
# - switch: supervised / unsupervised
# - switch: use frequencies or not (if not -- ignore corpus probability)
# - integrate word generation (mdl-analyze) into the module

def rule_cost(f, d, prod):
	#return f*math.log(float(f)/d) + (d-f)*math.log(float(d-f)/d)
	if f > 0.9 * d:
		f = 0.9 * d
#	return (d-f)*math.log(float(d-f)/d)
	return (d-f)*math.log(1.0 - prod)

def check_rules(rules, lexicon):
	# check rules
	rsp = RuleSetPrior()
	rsp.train(lexicon.rules_c)
	gain, analyzed = {}, set([])
	edges = []
	for word_1, freq_1, word_2, freq_2, rule, weight, delta_logl, d1, d2 in\
			read_tsv_file('edges.txt',\
			(str, int, str, int, str, int, float, float, float),\
			print_progress=True, print_msg='Checking rules...'):
		edges.append((word_1, word_2, rule, delta_logl))
	edges.sort(reverse=True, key=lambda x: x[3])
	for word_1, word_2, rule, delta_logl in edges:
		if lexicon[word_2].prev == lexicon[word_1]:
			if word_2 not in gain:
				gain[word_2] = 0.0
			gain[word_2] += delta_logl
		if word_2 not in analyzed and lexicon[word_2].prev != lexicon[word_1]\
				and word_2 not in lexicon[word_1].analysis()\
				and rule not in lexicon[word_1].next:
			if word_2 not in gain:
				gain[word_2] = 0.0
			gain[word_2] -= delta_logl
			analyzed.add(word_2)
	rules_gain = {}
	for w in lexicon.values():
		for r, w2 in w.next.items():
			if r not in rules_gain:
				rules_gain[r] = 0.0
			rules_gain[r] += gain[w2.word]
	rules_score = []
	for r, g in rules_gain.items():
		cost = rule_cost(lexicon.rules_c[r], rules[r].domsize, rules[r].prod)
		if r.count('*') == 0:
			cost += math.log(rsp.rule_prob(r))
		elif r.count('*') == 2:
			meta_rule = re.sub(r'\*.*\*', '*', r)
			cost += math.log(rules[meta_rule].prod)
		rules_score.append((r, g, cost, cost+g))
		if cost+g < 0.0 and r.count('*') != 1:
			del rules[r]
	rules_score.sort(key=lambda x: x[3])
	with open_to_write('rules_gain.txt') as fp:
		for r, g, c, sc in rules_score:
			write_line(fp, (r, g, c, sc))

def build_lexicon_edmonds(unigrams, rules, lexicon):
	print('Resetting lexicon...')
	lexicon.reset()

#	rules_to_delete = []
	for r in rules.keys():
		if rules[r].weight < 0 and r.count('*') != 1:
			rules[r].weight = 0
#			rules_to_delete.append(r)
#	for r in rules_to_delete:
#		del rules[r]

	# compute the improvement for each possible edge
	vertices, edges = set(['ROOT']), []
	with open_to_write('edges.txt') as outfp:
		for word_1, word_2, rule in read_tsv_file(settings.FILES['surface.graph'],\
#			print_progress=False):
				print_progress=True, print_msg='Computing edge scores...'):
			if rule in rules:
				delta_logl = lexicon.try_edge(word_1, word_2, rules[rule])
				delta_cor_logl = math.log(rules[rule].freqprob(lexicon[word_2].freqcl - lexicon[word_1].freqcl))
				write_line(outfp, (word_1, lexicon[word_1].freqcl, word_2, lexicon[word_2].freqcl,\
					rule, int(rules[rule].weight), delta_logl, delta_logl-delta_cor_logl, delta_cor_logl))
				if delta_logl < 0:
					continue
				edges.append((word_1, word_2, rule, delta_logl))
			if not word_1 in vertices:
#				edges.append(('ROOT', word_1, '', math.log(unigrams.word_prob(word_1))))
				vertices.add(word_1)
			if not word_2 in vertices:
#				edges.append(('ROOT', word_2, '', math.log(unigrams.word_prob(word_2))))
				vertices.add(word_2)
	edges.sort(reverse=True, key=lambda x: x[3])
	update_file_size('edges.txt')

	print('Computing maximum branching...')
	branching = algorithms.branching.branching(list(vertices), edges)
	for v1, v2, rule in branching:
		if not v1 == 'ROOT':
			lexicon.draw_edge(v1, v2, rules[rule])

	return lexicon

def build_lexicon_new(rules, lexicon):
	print('Resetting lexicon...')
	lexicon.reset()

	for r in rules.keys():
		if rules[r].weight < 0 and r.count('*') != 1:
			rules[r].weight = 0

	# compute the improvement for each possible edge
	edges = []
	with open_to_write('edges.txt') as outfp:
		for word_1, word_2, rule in read_tsv_file(settings.FILES['surface.graph'],\
#			print_progress=False):
				print_progress=True, print_msg='Computing edge scores...'):
			if rule in rules:
				delta_logl = lexicon.try_edge(word_1, word_2, rules[rule])
				delta_cor_logl = math.log(rules[rule].freqprob(lexicon[word_2].freq - lexicon[word_1].freq))
				write_line(outfp, (word_1, lexicon[word_1].freq, word_2, lexicon[word_2].freq,\
					rule, int(rules[rule].weight), delta_logl, delta_logl-delta_cor_logl, delta_cor_logl))
				if delta_logl < 0:
					continue
				edges.append((word_1, word_2, rule, delta_logl))
	edges.sort(reverse=True, key=lambda x: x[3])
	update_file_size('edges.txt')

	for (word_1, word_2, rule, delta_logl) in edges:
		if lexicon[word_2].prev is None and not word_2 in lexicon[word_1].analysis()\
				and rule not in lexicon[word_1].next:
			if word_1 in lexicon.roots and not lexicon[word_2].next:
				lexicon.draw_edge(word_1, word_2, rules[rule])
##			new_parent_stem = lcs(lexicon[word_1].stem, lcs(word_1, word_2))
##			if lcs(new_parent_stem, lexicon[word_2].stem) == new_parent_stem:
#			lexicon.draw_edge(word_1, word_2, rules[rule])
	
	return lexicon

# TODO: build_lexicon_iter
# start with the outermost "layer", then proceed to deeper layers

def build_lexicon_freq(rules, lexicon):
	print('Resetting lexicon...')
	lexicon.reset()

	for r in rules.keys():
		if rules[r].weight < 2 and r.count('*') != 1:
			rules[r].weight = 2

	# compute the improvement for each possible edge
	edges = []
	with open_to_write('edges.txt') as outfp:
		for word_1, word_2, rule in read_tsv_file(settings.FILES['surface.graph'],\
#			print_progress=False):
				print_progress=True, print_msg='Computing edge scores...'):
			if rule in rules:
#				delta_logl = lexicon.try_edge(word_1, word_2, rules[rule])
#				delta_cor_logl = math.log(rules[rule].freqprob(lexicon[word_2].freq - lexicon[word_1].freq))
#				write_line(outfp, (word_1, lexicon[word_1].freq, word_2, lexicon[word_2].freq,\
#					rule, int(rules[rule].weight), delta_logl, delta_logl-delta_cor_logl, delta_cor_logl))
#				if delta_logl < 0:
#					continue
				delta_logl = max([rules[rule].prod * rules[rule].domsize] + \
					[rules[r].prod * rules[r].domsize\
					for r in extract_all_rules(word_1, word_2) if rule in rules])
				edges.append((word_1, word_2, rule, delta_logl))
	edges.sort(reverse=True, key=lambda x: x[3])
	update_file_size('edges.txt')

	for (word_1, word_2, rule, delta_logl) in edges:
		if lexicon[word_2].prev is None and not word_2 in lexicon[word_1].analysis()\
				and not rule in lexicon[word_1].next:
			if lexicon[word_1].freq <= lexicon[word_2].freq and rules[rule].weight >= 0:
#			new_parent_stem = lcs(lexicon[word_1].stem, lcs(word_1, word_2))
#			if lcs(new_parent_stem, lexicon[word_2].stem) == new_parent_stem:
				lexicon.draw_edge(word_1, word_2, rules[rule])
	
	return lexicon

def build_lexicon(rules, lexicon):
	print('Resetting lexicon...')
	lexicon.reset()

	# compute the improvement for each possible edge
	word_best_edge = {}
	for word_1, word_2, rule in read_tsv_file(settings.FILES['surface.graph'],\
#			print_progress=False):
			print_progress=True, print_msg='Computing edge scores...'):
		if rule in rules:
			delta_logl = lexicon.try_edge(word_1, word_2, rules[rule])
			if delta_logl < 0:
				continue
			if not word_best_edge.has_key(word_2) or word_best_edge[word_2] < delta_logl:
				word_best_edge[word_2] = delta_logl

	# words should be processed in the order of the best edge score,
	#   so sort them according to this value
	word_num = dict([(word, num) for num, (word, delta_logl) in enumerate(\
		sorted(word_best_edge.iteritems(), reverse=True, key=lambda x:x[1]), 1)])
	# write the desired position for each word into the graph
	num_lines = 0
	with open_to_write(GRAPH_MDL_FILE) as outfp:
		for word_1, word_2, rule in read_tsv_file(settings.FILES['surface.graph'],\
				print_progress=False):
#				print_progress=True, print_msg='Writing edge scores...'):
			if word_num.has_key(word_2) and rules.has_key(rule):
				write_line(outfp, (word_1, word_2, rule, word_num[word_2]))
				num_lines += 1
	set_file_size(GRAPH_MDL_FILE, num_lines)
	# sort the graph according to desired positions of words
	sort_file(GRAPH_MDL_FILE, numeric=True, key=4)

	# for each word, compute once more the improvement for each possible edge
	#   and draw the best edges
	for word_2, rest in read_tsv_file_by_key(GRAPH_MDL_FILE, 2,\
				print_progress=False):
#				print_progress=True, print_msg='Building lexicon...'):
		edges = sorted([(word_1, word_2, rule,\
			lexicon.try_edge(word_1, word_2, rules[rule]))\
			for (word_1, rule, _) in rest],\
			reverse=True, key = lambda x: x[3])
		for edge in edges:
			word_1, word_2, rule, delta_logl = edge
			if delta_logl > 0 and not word_2 in lexicon[word_1].analysis()\
					and not lexicon[word_1].next.has_key(rule):
#				print word_1, word_2, rule, delta_logl, len(lexicon.roots)
				lexicon.draw_edge(word_1, word_2, rules[rule])
				break
	return lexicon

def reestimate_rule_prod(rules, lexicon):
	# count occurrences of rules in the lexicon
	rules_c = Counter()
	for word in lexicon.values():
		for r in word.next.keys():
			rules_c.inc(r)
			if r.count('*') == 2:
				r_sp = r.split('*')
				rules_c.inc(r_sp[0] + '*' + r_sp[2])
				lexicon.rules_c.inc(r_sp[0] + '*' + r_sp[2])
	# replace productivity with count / domsize
	deleted_metarules = set([])
	rules_to_delete = []
	for r in rules.keys():
		if r in rules_c:
#			rules[r].prod = float(rules_c[r]) / rules[r].domsize
			if rules[r].domsize == 0:
				print(r)
#			rules[r].prod = math.exp(round(math.log(float(rules_c[r]) / rules[r].domsize)))
			rules[r].prod = rules_c[r] / rules[r].domsize
			if rules[r].prod > 0.9:
				rules[r].prod = 0.9
		elif r == u'#':
			pass
		else:
			rules_to_delete.append(r)
			if r.count('*') == 1:
				deleted_metarules.add(r)
	for r in rules_to_delete:
		del rules[r]
#	for r in rules.keys():
#		if r.count('*') == 2:
#			r_sp = r.split('*')
#			if r_sp[0]+'*'+r_sp[2] in deleted_metarules:
#				del rules[r]

def reestimate_rule_weights(rules, lexicon):
	rules_w = {}
	for w1 in lexicon.values():
		for rule, w2 in w1.next.items():
			if w1.freqcl is None: print(w1.word, w1 == lexicon[w1.word])
			if w2.freqcl is None: print(w2.word, w2 == lexicon[w2.word])
			w3 = None
			if rule.count('*') == 2:
				r_sp = rule.split('*')
				w3 = lexicon[r_sp[1]]
				rule = r_sp[0] + '*' + r_sp[2]
			if rule not in rules_w:
				rules_w[rule] = 0
			if w3 is not None:
				rules_w[rule] += w2.freqcl - w1.freqcl - w3.freqcl
#				rules_w[rule] += w2.freq - w1.freq
			else:
				rules_w[rule] += w2.freqcl - w1.freqcl
	rules_to_delete = []
	for r in rules_w.keys():
		if r in lexicon.rules_c and r in rules:
			rules[r].weight = int(round(float(rules_w[r]) / lexicon.rules_c[r]))
		elif r in rules:
			rules_to_delete.append(r)
	for r in rules_to_delete:
		del rules[r]
	for r in rules.keys():
		if r.count('*') == 2:
			r_sp = r.split('*')
			rules[r].weight = lexicon[r_sp[1]].freqcl + rules[r_sp[0] + '*' + r_sp[2]].weight
#			rules[r].weight = rules[r_sp[0] + '*' + r_sp[2]].weight

#def reestimate_rule_weights(rules, lexicon):
#	# gradient descent
#	rules_w = dict([(r.rule, r.weight) for r in rules.values()])
#	old_logl = lexicon.corpus_logl(rules)
#	while True:
#		d = lexicon.logl_gradient(rules)
#		new_rules_w = {}
#		gamma = 1000.0
#		while gamma >= GAMMA_THRESHOLD:
##			print 'gamma = ', gamma
#			gamma_too_big = False
#			for r in rules_w.keys():
#				new_rules_w[r] = rules_w[r] + gamma * d[r]
#				if new_rules_w[r] <= 0.0:
#					gamma_too_big = True
##					print r, d[r]
#					break
#			if gamma_too_big:
#				gamma /= 10
#				continue
##			else:
##				print 'ok'
#			new_logl = lexicon.try_weights(new_rules_w)
#			if new_logl > old_logl + 100.0:
#				print 'improvement', new_logl, 'over', old_logl, 'with gamma =', gamma
#				rules_w = new_rules_w
#				old_logl = new_logl
#				# TODO update weights here!
#				break
#			else:
##				print 'no improvement', new_logl, old_logl
#				gamma /= 10
#		if gamma < GAMMA_THRESHOLD:
#			break
#	print lexicon.corpus_logl(rules)
#	# normalize the rule weight
#	print rules_w[u'#']
#	for r in rules.values():
#		r.weight = rules_w[r.rule] / rules_w[u'#']
#	# update weight sums in lexicon nodes
#	for n in lexicon.values():
#		n.sum_weights = 1.0 + sum([rules[r].weight for r in n.next.keys()])
#	print lexicon.corpus_logl(rules)

def find_new_ancestor(lexicon, rules, root, depth=0):
	node = lexicon[root]
	max_depth = 0
	for i in range(depth):
		if i in node.structure:
			max_depth += 1
		else:
			break
	if node.prev and max_depth < depth:
		if max_depth > 0:
			new_ancestor = node.prev
			for i in range(depth-max_depth):
				new_ancestor = new_ancestor.prev
			lexicon.remove_edge(node.prev.word, node.word)
			if new_ancestor is not None:
				max_prod, rule = 0.0, None
				for r in algorithms.optrules.extract_all_rules(new_ancestor.word, node.word):
					if rules.has_key(r) and rules[r].prod > max_prod:
						rule = r
						max_prod = rules[r].prod
				if rule is not None:
					lexicon.draw_edge(new_ancestor.word, node.word, rules[rule])
				else:
					rule = algorithms.align.align(new_ancestor.word, node.word)
					r = rule.to_string()
					domsize = 0
					for word in lexicon.keys():
						if rule.lmatch(word):
							domsize += 1
					rules[r] = RuleData(r, 1.0 / domsize, node.freq - new_ancestor.freq, domsize)
#					print 'Added rule:', r, node.freq - new_ancestor.freq, domsize
					lexicon.draw_edge(new_ancestor.word, node.word, rules[r])
			node.annotate_word_structure(max_depth)
	for child in node.next.values():
		find_new_ancestor(lexicon, rules, child.word, max_depth+1)

def rebuild_lexicon(lexicon, rules):
	print('Rebuilding lexicon...')
	pp = progress_printer(len(lexicon.roots))
	for root in list(lexicon.roots):
		rebuild_tree(lexicon, rules, root)
		pp.next()

def rebuild_tree(lexicon, rules, root):
	# for each node:
	#   annotate word structure (1=root etc.)
	#     for each letter at each position: look for it by ancestors
	lexicon[root].annotate_word_structure()
	find_new_ancestor(lexicon, rules, root)
	#   determine possible ancestors
	#   hang the word over and extract all rules possible for this edge
	#   if some rules in the rule set -> choose the best, else add the most general one

#def rebuild_tree(lexicon, rules, root):
#	words = lexicon[root].words_in_tree()
#	substrings = {}
#	for w1, w2, r in read_tsv_file(settings.FILES['surface.graph']):
#		if w1 in words and w2 in words:
#			if not substrings.has_key(w1):
#				substrings[w1] = []
#			if not substrings.has_key(w2):
#				substrings[w2] = []
#			substrings[w2].append((w1, r, len(algorithms.align.lcs(w1, w2)), lexicon[w1].depth()))
#	words.sort(reverse=True, key=lambda x: lexicon[x].depth())
#	for w in words:
#		lexicon[w].prev = None
#		lexicon[w].next = {}
#		lexicon.roots.add(w)
#	for w in words:
#		max_wp, max_r, max_lcs, min_dep = None, None, 0, 0
#		for wp, r, lcs, dep in substrings[w]:
#			if not w in lexicon[wp].analysis() and not lexicon[wp].next.has_key(r) and rules.has_key(r):
#				if lcs > max_lcs:
#					max_wp = wp
#					max_r = r
#					max_lcs = lcs
#					min_dep = dep
#				elif lcs == max_lcs and dep < min_dep:
#					max_wp = wp
#					max_r = r
#					min_dep = dep
#		if max_wp is not None:
#			lexicon.draw_edge(max_wp, w, rules[max_r])

def load_training_file_with_freq(filename):
	rules, lexicon = RuleSet(), Lexicon()
	unigrams = algorithms.ngrams.NGramModel(1)
	words, total = [], 0
	for word, freq in read_tsv_file(filename, (unicode, int)):
		words.append((word, freq))
		lexicon[word] = LexiconNode(word, freq, 0.0)
		lexicon.roots.add(word)
		lexicon.total += freq
		if freq > lexicon.max_freq:
			lexicon.max_freq = freq
	lexicon.recalculate_freqcl()
	unigrams.train(words)
	for word_2, freq, word_1 in read_tsv_file(filename, (unicode, int, unicode),\
			print_progress=True, print_msg='Building lexicon from training data...'):
		lexicon[word_2].ngram_prob = unigrams.word_prob(word_2)
		if word_1 != u'-' and word_1 != word_2 and word_2 in lexicon.roots:
			if not lexicon.has_key(word_1):
				lexicon.add_word(word_1, 1, unigrams.word_prob(word_1))
			rule = algorithms.align.align(word_1, word_2).to_string()
			if not rules.has_key(rule):
				rules[rule] = RuleData(rule, 1.0, 1.0, 0)
			lexicon.draw_edge(word_1, word_2, rules[rule])
	return unigrams, rules, lexicon

def load_training_file_without_freq(filename):
	rules, lexicon = RuleSet(), Lexicon()
	unigrams = algorithms.ngrams.NGramModel(1)
	words, total = [], 0
	for word in read_tsv_file(filename, (unicode)):
		words.append((word, 1))
		lexicon[word] = LexiconNode(word, 0, 0, 0.0, 0.0, 1.0)
		lexicon.roots.add(word)
	unigrams.train(words)
	for word_2, word_1 in read_tsv_file(filename, (unicode, unicode),\
			print_progress=True, print_msg='Building lexicon from training data...'):
		lexicon[word_2].ngram_prob = unigrams.word_prob(word_2)
		if word_1 != u'-' and word_1 != word_2:
			if not lexicon.has_key(word_1):
				lexicon[word_1] = LexiconNode(word_1, 0, 0, unigrams.word_prob(word_1), 0.0, 1.0)
				lexicon.roots.add(word_1)
			rule = algorithms.align.align(word_1, word_2).to_string()
			if not rules.has_key(rule):
				rules[rule] = RuleData(rule, 1.0, 1.0, 0)
			lexicon.draw_edge(word_1, word_2, rules[rule], corpus_prob=False)
	return unigrams, rules, lexicon

def load_training_file(filename):
	if settings.USE_WORD_FREQ:
		return load_training_file_with_freq(filename)
	else:
		return load_training_file_without_freq(filename)
	
