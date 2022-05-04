#!/usr/bin/env python3

from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

import sys
import os
import json
from munch import Munch
from types import SimpleNamespace

from subprocess import call

#import subprocess
import argparse
#import shlex
#import sys
from github import Github
#import os
#import re
#from pathlib import Path
import shutil
#import string

from pygit2 import Repository
from gherkin.parser import Parser
from pathvalidate import sanitize_filename

root = os.path.join(os.path.dirname(__file__), '..')
try:
  branch = Repository(root).head.shorthand
  issue = int(branch.replace('gh-', ''))
except ValueError:
  issue = None

# get arguments
parser = argparse.ArgumentParser()
parser.add_argument('--translator', '-t', dest='translator', default='biblatex')
parser.add_argument('--data',       '-d', dest='data', required=True)
parser.add_argument('--feature',    '-f', dest='feature')
parser.add_argument('--issue',      '-i', dest='issue', default=issue and str(issue))
parser.add_argument('--export',     '-e', dest='mode', action='store_const', const='export')
parser.add_argument('--import'          , dest='mode', action='store_const', const='import')
args, unknownargs = parser.parse_known_args()
sys.argv = sys.argv[:1] + unknownargs

if not args.mode:
  args.mode = 'export'

if not args.feature:
  args.feature = os.path.join(root, 'test', 'features', f'{args.mode}.feature')
assert os.path.exists(args.feature),  f'{args.feature} does not exist'

args.translator = {
  'biblatex': 'BibLaTeX',
  'bibtex': 'BibTeX',
  'csl': 'CSL-JSON',
  'csl-json': 'CSL-JSON',
  'yml': 'CSL-YAML',
  'csl-yaml': 'CSL-YAML',
}[args.translator.lower()]

assert args.issue, 'no issue'
args.data = os.path.join(root, 'logs', f'{args.data}/items.json')
assert os.path.exists(args.data),  f'{args.data} does not exist'

# get title

g = Github(os.environ['GITHUB_TOKEN'])
repo = g.get_repo('retorquere/zotero-better-bibtex')
issue = repo.get_issue(int(args.issue))
args.title = sanitize_filename(f'{issue.title} #{issue.number}'.strip())

# clean lib before putting it in place
assert call(["./util/clean-lib.ts", args.data, '--save'], cwd=root) == 0, 'clean failed'
with open(args.data) as f:
  args.n = len(json.load(f)['items'])

# insert example
parser = Parser()
doc = Munch.fromDict(parser.parse(args.feature))

outlines = [child for child in doc.feature.children if child.type == 'ScenarioOutline' and (args.translator in child.name or args.mode == 'import')]
assert len(outlines) == 1, f'{len(outlines)} outlines found containing {args.translator}'

with open(args.feature) as f:
  contents = f.readlines()
  example = [f'| {args.title} | {args.n} |\n']

examples = [example for example in outlines[0].examples[0].tableBody if example.cells[0].value == args.title]
match len(examples):
  case 0:
    # insert as first
    line = outlines[0].examples[0].tableHeader.location.line
    contents = contents[:line] + example + contents[line:]

  case 1:
    if examples[0].cells[1].value == str(args.n):
      contents = None
    else:
      # replace
      line = examples[0].location.line
      contents = contents[:line - 1] + example + contents[line:]
  case _:
    assert False, f'{len(examples)} examples found with title {json.dumps(args.title)}'

if contents:
  with open(args.feature, 'w') as f:
    f.write(''.join(contents))

# copy/create test fixtures
fixture = os.path.join(root, f'test/fixtures/{args.mode}', args.title)
shutil.copyfile(args.data, fixture + '.json')
if args.mode == 'import':
  ext = 'bib'
else:
  ext = args.translator.lower().replace('-', '.').replace('yaml', 'yml')
with open(fixture + '.' + ext, 'w') as f:
  if args.translator == 'CSL-JSON':
    f.write('{}')

# reformat
sys.argv.append(args.feature)
from reformat_gherkin.cli import main
main()
