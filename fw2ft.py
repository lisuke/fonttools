#!/usr/bin/python

# FontWorker-to-FontTools for OpenType Layout tables

from __future__ import print_function, division, absolute_import
from fontTools import ttLib
from fontTools.ttLib.tables import otTables as ot
import re

debug = print

def skipUntil(lines, what):
	for line in lines:
		if line[0] == what:
			return line

def readUntil(lines, what):
	for line in lines:
		if line[0] == what:
			raise StopIteration
		yield line

def parseScriptList(lines):
	skipUntil(lines, 'script table begin')
	self = ot.ScriptList()
	self.ScriptRecord = []
	for line in readUntil(lines, 'script table end'):
		scriptTag, langSysTag, defaultFeature, features = line
		debug("Adding script", scriptTag, "language-system", langSysTag)

		langSys = ot.LangSys()
		langSys.LookupOrder = None
		# TODO The following two lines should use lazy feature name-to-index mapping
		langSys.ReqFeatureIndex = int(defaultFeature) if defaultFeature else 0xFFFF
		langSys.FeatureIndex = [int(f) for f in features.split(',')]
		langSys.FeatureCount = len(langSys.FeatureIndex)

		script = [s for s in self.ScriptRecord if s.ScriptTag == scriptTag]
		if script:
			script = script[0].Script
		else:
			scriptRec = ot.ScriptRecord()
			scriptRec.ScriptTag = scriptTag
			scriptRec.Script = ot.Script()
			self.ScriptRecord.append(scriptRec)
			script = scriptRec.Script
			script.DefaultLangSys = None
			script.LangSysRecord = []
			script.LangSysCount = 0

		if langSysTag == 'default':
			script.DefaultLangSys = langSys
		else:
			langSysRec = ot.LangSysRecord()
			langSysRec.LangSysTag = langSysTag + ' '*(4 - len(langSysTag))
			langSysRec.LangSys = langSys
			script.LangSysRecord.append(langSysRec)
			script.LangSysCount = len(script.LangSysRecord)

	self.ScriptCount = len(self.ScriptRecord)
	# TODO sort scripts and langSys's?
	return self

def parseFeatureList(lines):
	skipUntil(lines, 'feature table begin')
	self = ot.FeatureList()
	self.FeatureRecord = []
	for line in readUntil(lines, 'feature table end'):
		idx, featureTag, lookups = line
		assert int(idx) == len(self.FeatureRecord), "%d %d" % (idx, len(self.FeatureRecord))
		featureRec = ot.FeatureRecord()
		featureRec.FeatureTag = featureTag
		featureRec.Feature = ot.Feature()
		self.FeatureRecord.append(featureRec)
		feature = featureRec.Feature
		feature.FeatureParams = None
		# TODO The following line should use lazy lookup name-to-index mapping
		feature.LookupListIndex = [int(l) for l in lookups.split(',')]
		feature.LookupCount = len(feature.LookupListIndex)

	self.FeatureCount = len(self.FeatureRecord)
	return self

def parseLookupList(lines, tableTag):
	self = ot.LookupList()
	self.Lookup = []
	while True:
		line = skipUntil(lines, 'lookup')
		if line is None: break
		_, idx, typ = line
		assert int(idx) == len(self.Lookup), "%d %d" % (idx, len(self.Lookup))

		lookup = ot.Lookup()
		self.Lookup.append(lookup)
		lookup.LookupFlags = 0
		lookup.LookupType = {
			'GSUB': {
				'single': 1,
				'multiple': 2,
				'alternate': 3,
				'ligature': 4,
				'context': 5,
				'chained': 6,
			},
			'GPOS': {
				'single': 1,
				'pair': 2,
				'kernset': 2,
				'cursive': 3,
				'mark to base': 4,
				'mark to ligature': 5,
				'mark to mark': 6,
				'context': 7,
				'chained': 8,
			},
		}[tableTag][typ]
		subtable = ot.lookupTypes[tableTag][lookup.LookupType]()
		for line in readUntil(lines, 'lookup end'):
			flag = {
				'RightToLeft':		0x0001,
				'IgnoreBaseGlyphs':	0x0002,
				'IgnoreLigatures':	0x0004,
				'IgnoreMarks':		0x0008,
				}.get(line[0])
			if flag:
				assert line[1] in ['yes', 'no'], line[1]
				if line[1] == 'yes':
					lookup.LookupFlags |= flag
				continue

			pass # TODO the real thing

		lookup.SubTable = [subtable]
		lookup.SubTableCount = len(lookup.SubTable)

	self.LookupCount = len(self.Lookup)
	return self

def parseGSUB(lines):
	debug("Parsing GSUB")
	self = ot.GSUB()
	self.ScriptList = parseScriptList(lines)
	self.FeatureList = parseFeatureList(lines)
	self.LookupList = parseLookupList(lines, 'GSUB')
	return self

def parseGPOS(lines):
	debug("Parsing GPOS")
	self = ot.GPOS()
	self.ScriptList = parseScriptList(lines)
	self.FeatureList = parseFeatureList(lines)
	self.LookupList = parseLookupList(lines, 'GPOS')
	return self

def parseGDEF(lines):
	debug("Parsing GDEF TODO")
	return None

def compile(s):
	lines = (line.split('\t') for line in re.split('\r?\n?', s))
	line = next(lines)
	assert line[0][:9] == 'FontDame ', line
	assert line[0][13:] == ' table', line
	tableTag = line[0][9:13]
	container = ttLib.getTableClass(tableTag)()
	table = {'GSUB': parseGSUB,
		 'GPOS': parseGPOS,
		 'GDEF': parseGDEF,
		}[tableTag](lines)
	container.table = table
	return container

if __name__ == '__main__':
	import sys
	for f in sys.argv[1:]:
		debug("Processing", f)
		compile(open(f).read())

