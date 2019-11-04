#!/usr/bin/python
# -*- coding: utf-8 -*-

"""Polish rhyming dictionary."""

# Copyright 2013 Marcin Ciura
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import bisect
import fcntl
import os
import re
import struct
import subprocess
import sys
import termios


RHYMES_FILE = '/usr/local/share/dict/polish-rhymes.dic'
PAGER = ['/usr/bin/less']
RHYME_AND_LENGTH_PATTERN = '%s,%x,'


def Decode(s):
  return unicode(s, 'utf-8').encode('iso-8859-2')


def ForgivingDecode(s):
  return unicode(s, 'utf-8').encode('iso-8859-2', 'ignore')


def Encode(s):
  return unicode(s, 'iso-8859-2').encode('utf-8')


def CompileRegexp(s):
  return re.compile(Decode(s))


OPT_CONSONANTS = '[bcćçčdfghjklłmnńpqrsśštvwxzźžż]*'
OPT_NONSYLLABIC = (
    '(?:(?:(?<=l))y(?:(?=o))|(?:(?<=g))u(?:(?=[eiy]))|(?:(?<=q)u))?')
MONOSYLLABIC = (
    'ae$|[aeo]y|(?:(?<!arc|ędz|prz))y[ao]|au|eau|eu|ée|oeh|ou|'
    '(?:(?<=[dn]))ai(?:(?=s))|(?:(?<=[lw]))ai|'
    '(?:(?<=[^i]m))ai(?:(?=[lns]))|(?:(?<=[ln]t))ai|'
    '(?:(?<=[blz]))ei(?:(?=t))|(?:(?<=[mw]))ei(?:(?=n))|'
    '(?:(?<=st))ei(?:(?=n))|ei(?:(?=f))|'
    '(?:(?<=v))oi|(?:(?<=çen))oi(?:(?=s))|oi(?:(?=x))')
VOWEL = '[aąáâäeéęëiíîoóôöuúüyý]'

SUBSTITUTIONS = [
    (CompileRegexp('austria([ck])'), 'austryja\\1'),
    (CompileRegexp('^hm'), 'hym'),
    (CompileRegexp('klien([ct])'), 'klijen\\1'),
    (CompileRegexp('marz([lłn])'), 'mars\\1'),
    (CompileRegexp('^(m[iu]r)z([aąęoó]|y$|y[^nń])'), '\\1s\\2'),
    (CompileRegexp('patrio([ct])'), 'patryjo\\1'),
    (CompileRegexp('^sir$'), 'ser'),
    (CompileRegexp('żmii$'), 'żmiji'),
    (CompileRegexp('^(a+|e+|i+|o+|u+|y+)$'), lambda m: m.group(1)[0]),
]

SYLLABLE = CompileRegexp(
    "(?:e'|" + OPT_CONSONANTS + OPT_NONSYLLABIC + 'i?)?'
    '(?:' + MONOSYLLABIC + '|' + VOWEL + ')'
    '(?:' + OPT_CONSONANTS + OPT_NONSYLLABIC + ')')

MORE_SYLLABLES = CompileRegexp(
    'auł|nau(?=b[il]|cz|ga|j|k|m(?:(?!ach))|r[ąz]|w|ż)|'
    'prau|zau(?=f|ł|r[ao].|s[tz]|w)|'
    '(?:ant|w|rz)y(?=[ao])|'
    'eu(?=sz)|kreu|nieu|przeu|seu(?=l)|'
    '[dnpw]ou|długou|samou')

INITIAL_CONSONANTS = CompileRegexp(
    '^' + OPT_CONSONANTS + OPT_NONSYLLABIC +
    '(?:i?(?=' + VOWEL + '))')

INITIAL_VOWEL = CompileRegexp(
    '^' + VOWEL)

ULTIMATE = CompileRegexp(
    '[âçîô]|eu$|(?<!wi)é$|([^ir]|[^abks]r)é[^ćjmr]|'
    'voi|[çen]ois|oix')

ANTEPENULTIMATE = CompileRegexp(
    '(ł[ao]?|^byle|^chociaż|^jeśli|^jeżeli)(bym|byś|by)$|'
    '[bćfhjklmńpśwzźż]że$|kądże$|'
    '(li|ły)(by|śmy|ście)$|'
    '(([afgm]|([by]|ta|cyk|ato|ncho)l|([hi]|[hmp]a|[lmrt]o)n|[eip]p)i|'
    '(([els]|[lt]o)d|ir|as|([eknpt]|[mn]a|li|[rz]o|.s|[ae]u|ry)t|'
    '(la|ab|e|f|[ft]o|p|met)r|[iuy]z)y)'
    '(ka|kiem|ku|cy|kach|kom|ce|ką|kę|ki|ko)$|'
    '^cztery.|[^lrs]set$|kroć$|imum$|bruderszaf|cyferbla|rzecz.*pospolit|'
    '(^a|^aże|^choć|^gdy|^jak|^że)(byśmy|byście)$')

PREANTEPENULTIMATE = CompileRegexp(
    '(li|ły|^byle|^chociaż|^jeśli|^jeżeli)(byśmy|byście)$')

# NOTE: ę$:e belongs to FINAL_RHYME_RULES while ą$:o belongs to
# GENERIC_RHYME_RULES. Thanks to this, "chcę go" rhymes with "ego"
# while "chcą go" rhymes with "Kongo".
FINAL_RHYME_RULES = [
    (CompileRegexp(pr.split(':')[0]), Decode(pr.split(':')[1])) for pr in """
    tz$:c trz$:cz (?<!o)ck$:k chs$:ks cks$:ks stw$:s dt$:t th$:t
    ff$:f gg$:k kk$:k ll$:l łł$:ł mm$:m ss$:s tt$:t
    bł$:b chł$:ch dł$:d gł$:g kł$:k pł$:p rł$:r sł$:s tł$:t zł$:z
    ę$:e
""".split()]

# TODO(mciura): po wielu spółgłoskach -ii można przerobić na -i.
# TODO(mciura): po wielu spółgłoskach -i[aeou] należy przerobić na -j[aeou].
GENERIC_RHYME_RULES = [
    (CompileRegexp(pr.split(':')[0]), Decode(pr.split(':')[1])) for pr in """
    dz$:c dż$:cz dź$:ć w$:f g$:k b$:p (?<![crs])z$:s rz$:sz ż$:sz ższ$:sz
    strz$:szcz zdrz$:szcz żdż$:szcz ź$:ś źć$:ść źdź$:ść d$:t
    (<=[aąáâäeéęëoóôöuúüyý])i:ji
    é:e ée?s?$:e ö:e ü:i

    ^i:y ch:h (?<=[^hkpt])rz:ż (?<=[hkpt])rz:sz ó:u
    ck(?=[^aąeęioóuylnr]):k

    b(?=[cćfhkpsśt]):p             p(?=[bdgźż]):b
    d(?=[cćfhkpsśt]):t             t(?=[bdgźż]):d
    dz(?=[cćfhkpsśt]):c            c(?=[bdgźż]):dz
    dź(?=[cćfhkpsśt]):ć            ć(?=[bdgźż]):dź
    dż(?=[cćfhkpsśt]):cz           cz(?=[bdgźż]):dż
    g(?=[cćfhkpsśt]):k             k(?=[bdgźż]):g
    w(?=[cćfhkpsśt]):f             f(?=[bdgźż]):w
    (?<![cdrs])z(?=[cćfhkpsśt]):s  s(?=[bdgźż]):z
    (?<!d)ź(?=[cćfhkpsśt]):ś       ś(?=[bdgźż]):ź
    ((?<!d)ż)(?=[cćfhkpsśt]):sz    sz(?=[bdgźż]):ż

    (?<=[śź])l(?=[cmn]): błk:pk wsk:sk
    ight:ajt ais$:e eaux?:o ault:o au(?!(cz|k|ł)):ał
    ohm:om ohn:on ou(?!ch|st):u v:w x:ks tsch:cz

    ą(?=[ćfhsśwzźż]):oł ą(?=[bp]):om ą(?=[cdgkt]):on ą(?=[lł]):o ą$:o
    ę(?=[ćfhsśwzźż]):eł ę(?=[bp]):em ę(?=[cdgkt]):en ę(?=[lł]):e
""".split()]


def GetLengthAndRhyme2(word):
  nword = word
  for pattern, replacement in SUBSTITUTIONS:
    nword = pattern.sub(replacement, nword)
  syllables = SYLLABLE.findall(nword)
  coda = [''.join(syllables[-i:]) for i in xrange(5)]
  length = len(syllables)
  m = MORE_SYLLABLES.search(nword)
  if m and length > 1:
    for i in xrange(len(coda)):
      if m.end() > len(word) - len(coda[i]):
        coda[i] = INITIAL_CONSONANTS.sub('', coda[i])
        coda[i] = INITIAL_VOWEL.sub('', coda[i])
    # TODO(mciura): increment length by the number of occurrences
    # of MORE_SYLLABLES.
    length += 1
  if length == 0:
    accent = 1
  elif ULTIMATE.search(word) or length == 1:
    accent = 1
  elif ANTEPENULTIMATE.search(word) and length >= 3:
    accent = 3
  elif PREANTEPENULTIMATE.search(word) and length >= 4:
    accent = 4
  else:
    accent = 2
  rhyme = INITIAL_CONSONANTS.sub('', coda[accent])
  for pattern, replacement in FINAL_RHYME_RULES:
    rhyme = pattern.sub(replacement, rhyme)
  return length, rhyme


def GetLengthAndRhyme1(word):
  chunks = word.split('-')
  result = [GetLengthAndRhyme2(x) for x in chunks]
  if len(chunks) == 1 or result[-1][1]:
    return sum(x[0] for x in result), result[-1][1]
  else:
    return sum(x[0] for x in result), GetLengthAndRhyme2(''.join(chunks))[1]


def GetLengthAndRhyme(word):
  length, rhyme = GetLengthAndRhyme1(Decode(word))
  for pattern, replacement in GENERIC_RHYME_RULES:
    rhyme = pattern.sub(replacement, rhyme)
  return length, Encode(rhyme)


def GetSearchPhrase(argv):
  if 2 <= len(argv) <= 3:
    _, rhyme = GetLengthAndRhyme(argv[1])
    if len(argv) == 3:
      try:
        length = int(argv[2])
        return RHYME_AND_LENGTH_PATTERN % (rhyme, length)
      except ValueError:
        pass
    else:
      return '%s,' % (rhyme,)
  sys.exit('Usage: %s <word> [<syllable count>]\n' % argv)


def GetTerminalHeight():
  return struct.unpack('hh', fcntl.ioctl(1, termios.TIOCGWINSZ, '1234'))[0]


def main():
  search_phrase = GetSearchPhrase(sys.argv)
  try:
    f = open(RHYMES_FILE, 'r')
    rhymes = f.readlines()
    f.close()
  except IOError as error:
    sys.exit(error)
  left = bisect.bisect(rhymes, search_phrase)
  right = bisect.bisect(rhymes, search_phrase + '\xFF\xFF')
  if os.isatty(1) and right - left >= GetTerminalHeight() - 1:
    try:
      output = subprocess.Popen(PAGER, stdin=subprocess.PIPE).communicate
    except OSError as error:
      sys.exit('Cannot execute %s: %s' % (PAGER, error))
  else:
    output = sys.stdout.write
  words = []
  for i in xrange(left, right):
    words.append(rhymes[i].split(',')[-1])
  output(''.join(words))


if __name__ == '__main__':
  main()
