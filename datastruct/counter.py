from utils.files import *
import settings

class Counter:
	def __init__(self, convert=False):
		self.entries = {}
		self.total = 0
		self.convert = convert
	
	def inc(self, obj, count=1):
		self.total += count
		key = obj
		if self.convert:
			key = obj.to_string()
		try:
			self.entries[key] += count
		except KeyError:
			self.entries[key] = count
	
	def add(self, obj, count):
		key = obj
		if self.convert:
			key = obj.to_string()
		previous_count = 0
		try:
			previous_count = self.entries[key]
		except KeyError:
			pass
		self.entries[key] = count
		self.total += count - previous_count
	
	def __len__(self):
		return len(self.entries)
	
	def __contains__(self, obj):
		key = obj
		if self.convert:
			key = obj.to_string()
		return self.entries.has_key(key)
	
	def __getitem__(self, obj):
		key = obj
		if self.convert:
			key = obj.to_string()
		return self.entries[key]
	
	def __setitem__(self, key, val):
		self.entries[key] = val
	
	def has_key(self, key):
		if self.convert:
			key = obj.to_string()
		return self.entries.has_key(key)

	def iteritems(self):
		return self.entries.iteritems()
	
	def keys(self):
		return self.entries.keys()
	
	def values(self):
		return self.entries.values()
	
	def save_to_file(self, filename):
		# sort according to counts and save
		lines_written = 0
		entries_sorted = sorted([(x, y) for x, y in self.entries.iteritems()], \
			reverse = True, key = lambda x: x[1])
		with open_to_write(filename) as fp:
			for key, count in entries_sorted:
				if isinstance(key, str) or isinstance(key, unicode):
					write_line(fp, (key, count))
					lines_written += 1
				elif isinstance(key, tuple):
					write_line(fp, key + (count, ))
					lines_written += 1
		set_file_size(filename, lines_written)
	
	@staticmethod
	def load_from_file(filename, max_entries=None, convert=False):
		counter = Counter(convert)
		processed = 0
		for row in read_tsv_file(filename):
			counter.add(row[0], int(row[1]))
#			if len(row) == 2:
#				counter.add(row[0], int(row[1]))
#			elif len(row) >= 2:
#				counter.add(row[:-1], int(row[-1]))
			processed += 1
			if max_entries is not None and processed >= max_entries:
				break
		return counter

