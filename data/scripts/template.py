#!/usr/bin/env python3

# This file is part of the Soletta Project
#
# Copyright (C) 2015 Intel Corporation. All rights reserved.
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

import argparse
import configparser
import os
import re
import stat

class TemplateFragment:
    def __init__(self, tpl_global, context, verbatim, expr):
        self.context = context
        self.verbatim = verbatim
        self.expr = expr
        self.tpl_global = tpl_global
        self.subst = ""

    def __append_subst(self, subst):
        self.subst += "%s\n" % subst

    def value_of(self, k):
        value = self.context.get(k)
        if value:
            self.__append_subst(value)

    def on_value(self, k, v, ontrue, onfalse):
        value = self.context.get(k.lower())
        if value and value == v:
            self.__append_subst(ontrue)
        else:
            self.__append_subst(onfalse)

    def on_set(self, k, ontrue, onfalse):
        if self.context.get(k.lower()):
            self.__append_subst(ontrue)
        else:
            self.__append_subst(onfalse)

    def println(self, ln):
        self.__append_subst(ln)

    def include(self, template):
        dir_path = os.path.dirname(self.tpl_global["root_tpl"])
        path = os.path.join(dir_path, template)

        try:
            f = open(path)
        except:
            print("Could not open include file: %s" % path)
            return

        content = run_template(f.read(), self.tpl_global, self.context, self)
        self.__append_subst(content)

def parse_template(raw, tpl_global, context):
    result = []
    curr = prev = ""
    expr = False
    for ch in raw:
        if ch == "{" and prev == "{":
            if curr:
                fragment = TemplateFragment(tpl_global, context, curr, expr)
                result.append(fragment)
            curr = ""
            expr = True
        elif ch == "}" and prev == "}":
            if curr:
                fragment = TemplateFragment(tpl_global, context, curr[:len(curr) - 1], expr)
                result.append(fragment)
            curr = ""
            expr = False
        else:
            curr += ch
        prev = ch

    if curr:
        fragment = TemplateFragment(tpl_global, context, curr, expr)
        result.append(fragment)

    return result

def load_context(files):
    result = {}
    for f in files:
        lines = f.read()
        content = "[context]\n%s" % lines
        handle = configparser.ConfigParser(delimiters=('=','?=',':='))
        handle.read_string(content)
        dc = handle["context"]
        result = dict(list(result.items()) + list(dc.items()))

    # also consider env vars in the context
    for k,v in os.environ.items():
        result[k.lower()] = v

    return result

def try_subst(verbatim):
    p = re.compile("^\@.*\@$")
    m = p.match(verbatim)

    if not m:
        return None

    return verbatim.replace("@","")

def run_template(raw, tpl_global, context, nested=None):
    fragments = parse_template(raw, tpl_global, context)
    for frag in fragments:
        if frag.expr:
            subst = try_subst(frag.verbatim)
            if subst:
                subst = context.get(subst.lower(), "")
                subst = subst.replace("\"","")
                frag.subst = subst
            else:
                if nested:
                    tpl_global["st"] = nested
                else:
                    tpl_global["st"] = frag
                tpl_global["context"] = context
                exec(frag.verbatim, tpl_global)
            raw = raw.replace("{{%s}}" % frag.verbatim, frag.subst)

    return raw

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--context-files",
                        help=("The context files path. A context file"
                              "is a file containing key=value pairs, like"
                              "the kconfig's .config file"),
                        type=argparse.FileType("r"), nargs="+",
                        required=True)
    parser.add_argument("--template", help="The template file path",
                        type=argparse.FileType("r"), required=True)
    parser.add_argument("--output", help="The template file path",
                        type=argparse.FileType("w"), required=True)

    args = parser.parse_args()
    tpl_global = {"root_tpl": os.path.realpath(args.template.name)}
    context = load_context(args.context_files)
    output = run_template(args.template.read(), tpl_global, context)

    args.output.write(output)
    st = os.fstat(args.template.fileno())
    os.fchmod(args.output.fileno(), st.st_mode)
