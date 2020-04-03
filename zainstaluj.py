#!/usr/bin/python
# -*- coding: utf-8 -*-

"""Installs the Polish rhyming dictionary on Unix systems."""

# Copyright 2013-2020 Marcin Ciura
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

import cStringIO
import os
import re
import shutil
import string
import sys
import urllib2
import zipfile

import rym

COLLATE = {
    u'ą': 'a~',
    u'ć': 'c~',
    u'é': 'e',
    u'ę': 'e~',
    u'ł': 'l~',
    u'ń': 'n~',
    u'ö': 'oe',
    u'ó': 'o~',
    u'ś': 's~',
    u'ü': 'ue',
    u'ź': 'z}',
    u'ż': 'z~',
    u'-': '-',
    u"'": '',
}

LATIN = frozenset(string.lowercase)
REMOVE = frozenset(string.uppercase + u'ÉŠÜàâäçčêñôōšúùûūĄĆĘŁŃÓŚŹŻ.;0123456789')

WORD_LIST_REFERRER_URL = 'https://sjp.pl/slownik/odmiany'
WORD_LIST_URL_RE = re.compile(r'"[^.]+\.zip"')
WORD_LIST_FILENAME = 'odm.txt'

PROGRAM_DESTINATION = '/usr/local/bin/rym'

RESULT = []


def Convert(word):
  uword = unicode(word, 'utf-8')
  if u' ' in uword:
    return
  collate = []
  for char in uword:
    if char in REMOVE:
      return
    elif char in LATIN:
      collate.append(unicode(char))
    elif char in COLLATE:
      collate.append(COLLATE[char])
    else:
      sys.exit(u'Nieznany znak w wyrazie %s' % uword)
  length, rhyme = rym.GetLengthAndRhyme(word)
  if rhyme:
    RESULT.append(
        (rym.RHYME_AND_LENGTH_PATTERN % (rhyme, length),
         ''.join(collate), word))


def main():
  if os.geteuid() != 0:
    sys.exit(u'Instalator musi zostać uruchomiony w trybie superużytkownika.')
  sys.stderr.write(u'Pobieranie listy wyrazów z %s\n' % WORD_LIST_REFERRER_URL)
  page = urllib2.urlopen(WORD_LIST_REFERRER_URL).read()
  url = os.path.join(
      WORD_LIST_REFERRER_URL,
      WORD_LIST_URL_RE.search(page).group(0).strip('"'))
  zip_file = zipfile.ZipFile(cStringIO.StringIO(urllib2.urlopen(url).read()))
  word_list = zip_file.open(WORD_LIST_FILENAME)
  sys.stderr.write(u'Tworzenie słownika. To potrwa parę minut.\n')
  for line in word_list:
    for word in line.rstrip().split(', '):
      Convert(word)
  word_list.close()
  zip_file.close()
  sys.stderr.write(u'Zapisywanie słownika do %s\n' % rym.RHYMES_FILE)
  RESULT.sort()
  os.makedirs(os.path.dirname(rym.RHYMES_FILE))
  f = open(rym.RHYMES_FILE, 'w')
  prev = ''
  for prefix, _, word in RESULT:
    if word != prev:
      prev = word
      f.write(prefix)
      f.write(word)
      f.write('\n')
  f.close()
  sys.stderr.write(u'Kopiowanie programu do %s\n' % PROGRAM_DESTINATION)
  try:
    os.makedirs(os.path.dirname(PROGRAM_DESTINATION))
  except OSError:
    pass
  shutil.copy('rym.py', PROGRAM_DESTINATION)


if __name__ == '__main__':
  main()
