#!/usr/bin/python

import os
import re
import glob
import cStringIO as StringIO

string_re = re.compile('_\\(\'(.*?)\'\\)')
strings = {}

gettext_tpl = """/*
 * Script: gettext.js
 *  A script file that is run through the template renderer in order for
 *  translated strings to be used.
 *
 * Copyright:
 *  Damien Churchill (c) 2009
 */

GetText = {
    maps: {},
    add: function(string, translation) {
        this.maps[string] = translation;
    },
    get: function(string) {
        if (this.maps[string]) {
            return this.maps[string];
        } else {
            return string;
        }
    }
}

var _ = GetText.get.bind(GetText);

"""

files = glob.glob('js/deluge-*.js')
for filename in files:
    for line_num, line in enumerate(open(filename)):
        for match in string_re.finditer(line):
            string = match.group(1)
            locations = strings.get(string, [])
            locations.append((os.path.basename(filename), line_num + 1))
            strings[string] = locations
keys = strings.keys()
keys.sort()

fp = StringIO.StringIO()
fp.write(gettext_tpl)
for key in keys:
    fp.write('// %s\n' % ', '.join(map(lambda x: '%s:%s' % x, strings[key])))
    fp.write("GetText.add('%(key)s', '${_(\"%(key)s\")}');\n\n" % locals())
fp.seek(0)
print fp.read()
