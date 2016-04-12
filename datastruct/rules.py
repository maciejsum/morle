import algorithms.align
from utils.files import *
import libhfst
import re
#from scipy.stats import norm
#from algorithms.ngrams import *
#import math

class Rule:
	def __init__(self, subst, tag_subst=None):
		self.subst = subst
		self.tag_subst = tag_subst
	
	def __eq__(self, other):
		return self.subst == other.subst and self.tag_subst == other.tag_subst
	
	def copy(self):
		return Rule(self.subst, self.tag_subst)
	
#	def apply(self, word):
#		if not self.lmatch(word):
#			return []
#		if self.tag:
#			word = word[:-len(self.tag[0])-1]
#		i, j = len(self.prefix[0]), len(self.suffix[0])
#		word = word[i:-j] if j > 0 else word[i:]
#		if self.alternations:
#			results = []
#			alt_pat = re.compile(u'(.*?)'.join([x for x, y in self.alternations]))
#			m = alt_pat.search(word, 1)
#			while m is not None:
#				if m.end() == len(word):
#					break
#				w = word[:m.start()] + self.alternations[0][1]
#				for i in range(1, len(self.alternations)):
#					w += m.group(i) + self.alternations[i][1]
#				w += word[m.end():]
#				results.append(self.prefix[1] + w + self.suffix[1] +\
#					(u'_' + self.tag[1] if self.tag else u''))
#				m = alt_pat.search(word, m.start()+1) if m.start()+1 < len(word) else None
#			return results
#		else:
#			return [self.prefix[1] + word + self.suffix[1] +\
#				(u'_' + self.tag[1] if self.tag else u'')]
#	
#	def get_affixes(self):
#		affixes = []
#		affixes.append(self.prefix[0])
#		affixes.append(self.prefix[1])
#		affixes.append(self.suffix[0])
#		affixes.append(self.suffix[1])
#		return [x for x in affixes if x]
#
#	def get_trigrams(self):
#		trigrams = []
#		for tr in generate_n_grams('^'+self.prefix[0]+'*', 3):
#			if len(tr) == 3:
#				trigrams.append(tr)
#		for alt in self.alternations:
#			for tr in generate_n_grams('*'+alt[0]+'*', 3):
#				if len(tr) == 3:
#					trigrams.append(tr)
#		for tr in generate_n_grams('*'+self.suffix[0]+'$', 3):
#			if len(tr) == 3:
#				trigrams.append(tr)
#		return trigrams
#	
#	def make_left_pattern(self):
#		pref = re.escape(self.prefix[0])
#		alt = [re.escape(x) for x, y in self.alternations]
#		suf = re.escape(self.suffix[0])
#		pattern = '^' +\
#			pref +\
#			('(.*)' if alt else '') + \
#			'(.*)'.join(alt) +\
#			'(.*)' + suf +\
#			('_' + self.tag[0] if self.tag else '') + '$'
#		self.left_pattern = re.compile(pattern)
#	
#	def make_right_pattern(self):
#		pref = re.escape(self.prefix[1])
#		alt = [re.escape(y) for x, y in self.alternations]
#		suf = re.escape(self.suffix[1])
#		pattern = '^' +\
#			pref +\
#			('(.*)' if alt else '') + \
#			'(.*)'.join(alt) +\
#			'(.*)' + suf +\
#			('_' + self.tag[1] if self.tag else '') + '$'
#		self.right_pattern = re.compile(pattern)
#	
#	def lmatch(self, word):
#		if self.left_pattern is None:
#			self.make_left_pattern()
#		return True if word and self.left_pattern.match(word) else False
#	
#	def rmatch(self, word):
#		if self.right_pattern is None:
#			self.make_right_pattern()
#		return True if word and self.right_pattern.match(word) else False

	def seq(self):	# TODO no identity symbols between subst and tag_subst!
		x_seq, y_seq = [], []
		subst_seq = self.subst +\
			(self.tag_subst,) if self.tag_subst is not None else ()
		for x, y in subst_seq:
			x_seq.extend(x + (libhfst.EPSILON,)*(len(y)-len(x)))
			x_seq.append(libhfst.IDENTITY)
			y_seq.extend((libhfst.EPSILON,)*(len(x)-len(y)) + y)
			y_seq.append(libhfst.IDENTITY)
		return tuple(zip(x_seq, y_seq))
	
	# TODO
	def reverse(self):
		prefix_r = (self.prefix[1], self.prefix[0])
		alternations_r = [(y, x) for (x, y) in self.alternations]
		suffix_r = (self.suffix[1], self.suffix[0])
		tag_r = None
		if self.tag:
			tag_r = (self.tag[1], self.tag[0])
		return Rule(prefix_r, alternations_r, suffix_r, tag_r)

	def to_string(self):
		return settings.RULE_PART_SEP.join(
			''.join(x)+settings.RULE_SUBST_SEP+''.join(y)
				for (x, y) in self.subst
			) +\
			(settings.RULE_TAG_SEP +\
			 ''.join(self.tag_subst[0]) +\
			 settings.RULE_SUBST_SEP +\
			 ''.join(self.tag_subst[1]) if self.tag_subst else '')
	
	def build_transducer(self):
		pass
	
	def compute_domsize(self, lexicon):
		if lexicon.transducer is None:
			lexicon.build_transducer()
		if self.transducer is None:
			self.build_transducer()
		t = libhfst.HfstTransducer(lexicon.transducer)
		t.compose(self.transducer)
		t.input_project()
		return sum(1 for p in t.extract_paths())
	

#def tokenize_word(string):
#	'''Separate a string into a word and a POS-tag,
#	   both expressed as sequences of symbols.'''
#	m = re.match(settings.WORD_PATTERN_CMP, string)
#	if m is None:
#		raise Exception('Error while tokenizing word: %s' % string)
#	return tuple(re.findall(settings.SYMBOL_PATTERN_CMP, m.group('word'))),\
#		   tuple(re.findall(settings.TAG_PATTERN_CMP, m.group('tag')))

	@staticmethod
	def from_string(string):
		r_subst, r_tag_subst = [], None
		m = re.match(settings.RULE_PATTERN_CMP, string)
		if m is None:
			raise Exception('Error while parsing rule: %s' % string)
		subst, tag_subst = m.group('subst'), m.group('tag_subst')
#		m_subst = re.match(settings.RULE_NAMED_SUBST_PATTERN_CMP, subst)
		for ms in re.finditer(settings.RULE_NAMED_SUBST_PATTERN_CMP, subst):
			x = tuple(re.findall(settings.SYMBOL_PATTERN_CMP, ms.group('x')))
			y = tuple(re.findall(settings.SYMBOL_PATTERN_CMP, ms.group('y')))
			r_subst.append((x, y))
		if tag_subst:
			mt = re.match(settings.RULE_NAMED_TAG_SUBST_PATTERN_CMP, tag_subst)
			if mt is not None:
				x = tuple(re.findall(settings.TAG_PATTERN_CMP, mt.group('x')))
				y = tuple(re.findall(settings.TAG_PATTERN_CMP, mt.group('y')))
				r_tag_subst = (x, y)
		return Rule(tuple(r_subst), r_tag_subst)
#		mt = re.match(settings.

#		p = string.find('___')
#		tag = None
#		if p > -1:
#			tag_sp = string[p+3:].split(':')
#			tag = (tag_sp[0], tag_sp[1])
#			string = string[:p]
#		split = string.split('/')
#		prefix_sp = split[0].split(':')
#		prefix = (prefix_sp[0], prefix_sp[1])
#		suffix_sp = split[-1].split(':')
#		suffix = (suffix_sp[0], suffix_sp[1])
#		alternations = []
#		for alt_str in split[1:-1]:
#			alt_sp = alt_str.split(':')
#			alternations.append((alt_sp[0], alt_sp[1]))
#		return Rule(prefix, alternations, suffix, tag)


class RuleSetItem:
#	def __init__(self, rule, prod, freqcl, domsize, vec_mean, vec_sd):
	def __init__(self, rule, prod, freqcl, domsize):
		self.rule = rule
		self.rule_obj = Rule.from_string(rule)
		self.prod = prod
		self.freqcl = freqcl
		self.domsize = domsize
#		self.vec_mean = vec_mean
#		self.vec_sd = vec_sd
	
	def __lt__(self, other):
		return self.rule < other.rule
	
	def freqprob(self, f):
		p = 2 * norm.pdf(f-self.freqcl) * norm.cdf(f-self.freqcl)
		return p if p > 0 else 1e-100
#		return norm.pdf(f, self.freqcl, 1)
	
class RuleSet:
	def __init__(self):
		self.rsp = RuleSetPrior()
		self.rules = {}
	
	def __len__(self):
		return len(self.rules)
	
	def __delitem__(self, key):
		del self.rules[key]
	
	def keys(self):
		return self.rules.keys()

	def values(self):
		return self.rules.values()
	
	def items(self):
		return self.rules.items()
	
	def __contains__(self, key):
		return self.rules.__contains__(key)
	
	def __getitem__(self, key):
		return self.rules[key]

	def __setitem__(self, key, val):
		self.rules[key] = val
	
	def rule_cost(self, rule, freq):
		result = math.log(self.rsp.rule_prob(rule))
		r = self.rules[rule]
		result += freq * math.log(r.prod)
		result += (r.domsize-freq) * math.log(1-r.prod)
		return result

	def filter(self, condition):
		keys_to_delete = []
		for key, val in self.rules.items():
			if not condition(val):
				keys_to_delete.append(key)
		for key in keys_to_delete:
			del self.rules[key]
	
	def save_to_file(self, filename):
		with open_to_write(filename) as fp:
			for r_str, r in self.rules.items():
				write_line(fp, (r_str, r.prod, r.freqcl, r.domsize))
	
	@staticmethod
	def load_from_file(filename):
		rs = RuleSet()
		for rule, prod, freqcl, domsize in read_tsv_file(filename,\
				types=(str, float, int, int)):
			rs[rule] = RuleData(rule, prod, freqcl, domsize)
		return rs
	

def align_parts(left, right):
	lcs = algorithms.align.lcs(left, right)
	pattern = re.compile('(.*)' + '(.*?)'.join([\
		letter for letter in lcs]) + '(.*)')
	m1 = pattern.search(left)
	m2 = pattern.search(right)
	alignment = []
	for i, (x, y) in enumerate(zip(m1.groups(), m2.groups())):
		if x or y:
			alignment.append((x, y))
		if i < len(lcs):
			alignment.append((lcs[i], lcs[i]))
	return alignment


class RuleSetPrior:
	def __init__(self):
		self.ngr_add = None
		self.ngr_remove = None
		self.unigrams = NGramModel(1)
		filename = settings.FILES['training.lexicon'] if settings.SUPERVISED \
			else settings.FILES['training.wordlist']
		if settings.USE_WORD_FREQ:
			self.unigrams.train_from_file(filename)
		else:
			self.unigrams.train([(word, 1) for (word, ) in read_tsv_file(
				filename, (str, ))])

	def train(self, rules_c):
		self.ngr_add = NGramModel(1)
		self.ngr_remove = NGramModel(1)
		ngram_training_pairs_add = []
		ngram_training_pairs_remove = []
		for rule_str, count in rules_c.items():
			if rule_str.count('*') > 0:
				continue
			rule = Rule.from_string(rule_str)
#			ngram_training_pairs.extend([\
#				(rule.prefix[0], count), (rule.suffix[0], count),\
#				(rule.suffix[0], count), (rule.suffix[1], count)
#			])
			ngram_training_pairs_remove.extend([\
				(rule.prefix[0], count), (rule.suffix[0], count)])
			ngram_training_pairs_add.extend([\
				(rule.prefix[1], count), (rule.suffix[1], count)])
			for x, y in rule.alternations:
				ngram_training_pairs_remove.append((x, count))
				ngram_training_pairs_add.append((y, count))
			# an 'empty alternation' finishes the sequence of alternations
			ngram_training_pairs_remove.append((u'', count))
			ngram_training_pairs_add.append((u'', count))
		self.ngr_add.train(ngram_training_pairs_add)
		self.ngr_remove.train(ngram_training_pairs_remove)
	
	def rule_prob(self, rule_str):
		rule = Rule.from_string(rule_str)
		al = align_parts(rule.prefix[0], rule.prefix[1])
		if rule.alternations:
			al.append(('.', '.'))
			for x, y in rule.alternations:
				al.extend(align_parts(x, y) + [('.', '.')])
		al.extend(align_parts(rule.suffix[0], rule.suffix[1]))
		p = 1
#		print(al)
		for x, y in al:
			if x == '.' and y == '.':	# PASS
				p *= 0.5
			elif x == y:	# CHECK
				p *= 0.4**len(x) * self.unigrams.ngram_prob(x)
			elif not x and y:	# INSERT
				p *= 0.09999**len(y) * self.unigrams.ngram_prob(y)
			elif x and not y:
				p *= 0.00001**len(x) * self.unigrams.ngram_prob(x)
			else:
				p *= 0.00001**len(x) * self.unigrams.ngram_prob(x)
				p *= 0.09999**len(y) * self.unigrams.ngram_prob(y)
		# TODO parameters probability
#		p *= 
		return p
	
	def rule_prob_old(self, rule_str):
		if rule_str == u':/:':
			return 0.0
		rule = Rule.from_string(rule_str)
		prob = self.ngr_remove.word_prob(rule.prefix[0]) *\
			self.ngr_add.word_prob(rule.prefix[1]) *\
			self.ngr_remove.word_prob(rule.suffix[0]) *\
			self.ngr_add.word_prob(rule.suffix[1]) *\
			self.ngr_remove.word_prob(u'') * self.ngr_add.word_prob(u'')
		for x, y in rule.alternations:
			prob *= self.ngr_remove.word_prob(x) * self.ngr_add.word_prob(y)
		prob /= 1.0 - self.ngr_add.word_prob(u'') ** 3 * self.ngr_remove.word_prob(u'') ** 3		# empty rule not included
		return prob
	
	def param_cost(self, prod, weight):
		result = 0.0
#		print prod, math.log(prod), round(math.log(prod))
		result -= math.log(0.5) * round(math.log(prod))
#		print result
		result += math.log(2 * norm.pdf(weight, 2, 1))
#		print result
		return result

