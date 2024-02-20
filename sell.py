#!/usr/bin/env python3

"""
======= pySELL =================================================================
        
        A Python based Simple E-Learning Language 
        for the simple creation of interactive courses

AUTHOR  Andreas Schwenk <mailto:contact@compiler-construction.com>

LICENSE GPLv3

Docs:   Refer to https://github.com/andreas-schwenk/pysell and read the
        descriptions at the end of the page

Usage:  Only file 'sell.py' is required to compile question files
        
        COMMAND    python3 [-J] sell.py PATH
        ARGUMENTS  -J is optional and generates a JSON output file for debugging        
        EXAMPLE    python3 sell.py examples/ex1.txt
        OUTPUT     examples/ex1.html, examples/ex1_DEBUG.html
"""

import json, sys, os, re
from typing import Self


class Lexer:
    """Scanner that takes a string input and returns a sequence of tokens."""

    def __init__(self, src: str):
        self.src = src
        self.token = ""
        self.pos = 0
        self.next()

    def next(self):
        """gets the next token"""
        self.token = ""
        stop = False
        while not stop and self.pos < len(self.src):
            ch = self.src[self.pos]
            if ch in "`^'\"%#*$()[]{}\\,.:;+-*/_!<>\t\n =?|&":
                if len(self.token) > 0:
                    return
                stop = True
                if ch in '"`':
                    kind = ch
                    self.token += ch
                    self.pos += 1
                    while self.pos < len(self.src):
                        if self.src[self.pos] == kind:
                            break
                        self.token += self.src[self.pos]
                        self.pos += 1
            self.token += ch
            self.pos += 1


# # lexer tests
# lex = Lexer('a"x"bc 123 *blub* $`hello, world!`123$')
# while len(lex.token) > 0:
#     print(lex.token)
#     lex.next()
# exit(0)

boolean_types = ["<class 'bool'>", "<class 'numpy.bool_'>"]
int_types = [
    "<class 'int'>",
    "<class 'numpy.int64'>",
    "<class 'sympy.core.numbers.Integer'>",
    "<class 'sage.rings.integer.Integer'>",
    "<class 'sage.rings.finite_rings.integer_mod.IntegerMod_int'>",
]
float_types = ["<class 'float'>"]

python_kws = [
    "and",
    "as",
    "assert",
    "break",
    "class",
    "continue",
    "def",
    "del",
    "elif",
    "else",
    "except",
    "False",
    "finally",
    "for",
    "from",
    "global",
    "if",
    "import",
    "in",
    "is",
    "lambda",
    "None",
    "nonlocal",
    "not",
    "or",
    "pass",
    "raise",
    "return",
    "True",
    "try",
    "while",
    "with",
    "yield",
]

# the following list of identifiers may be in locals of sympy, and must be
# skipped for the JSON export
skipVariables = [
    "acos",
    "acosh",
    "acoth",
    "asin",
    "asinh",
    "atan",
    "atan2",
    "atanh",
    "ceil",
    "ceiling",
    "cos",
    "cosh",
    "cot",
    "coth",
    "exp",
    "floor",
    "ln",
    "log",
    "pi",
    "round",
    "sin",
    "sinc",
    "sinh",
    "tan",
    "transpose",
]


rangeZ_src = """def rangeZ(*a):
    r = []
    if len(a) == 1:
        r = list(range(a[0]))
    elif len(a) == 2:
        r = list(range(a[0], a[1]))
    elif len(a) == 3:
        r = list(range(a[0], a[1], a[2]))
    if 0 in r:
        r.remove(0)
    return r
"""


class TextNode:
    """Tree structure for the question text"""

    def __init__(self, type: str, data: str = ""):
        self.type = type
        self.data = data
        self.children = []

    def parse(self):
        if self.type == "root":
            self.children = [TextNode(" ", "")]
            lines = self.data.split("\n")
            self.data = ""
            for line in lines:
                line = line.strip()
                if len(line) == 0:
                    continue
                type = line[0]  # '[' := multi-choice, '-' := itemize, ...
                if type not in "[(-":
                    type = " "
                if type != self.children[-1].type:
                    self.children.append(TextNode(type, ""))
                self.children[-1].type = type
                self.children[-1].data += line + "\n"
                if line.endswith("\\\\"):
                    # line break
                    # TODO: this is NOT allowed, if we are within math mode!!
                    self.children[-1].data = self.children[-1].data[:-3] + "\n"
                    self.children.append(TextNode(" ", ""))
            types = {
                " ": "paragraph",
                "(": "single-choice",
                "[": "multi-choice",
                "-": "itemize",
            }
            for child in self.children:
                child.type = types[child.type]
                child.parse()
        elif self.type == "multi-choice" or self.type == "single-choice":
            options = self.data.strip().split("\n")
            self.data = ""
            for option in options:
                node = TextNode("answer")
                self.children.append(node)
                text = ""
                if self.type == "multi-choice":
                    text = "]".join(option.split("]")[1:]).strip()
                else:
                    text = ")".join(option.split(")")[1:]).strip()
                if option.startswith("[!"):
                    # conditionally set option
                    # !!! TODO: check, if variable exists and is of type bool
                    var_id = option[2:].split("]")[0]
                    node.children.append(TextNode("var", var_id))
                else:
                    # statically set option
                    correct = option.startswith("[x]") or option.startswith("(x)")
                    node.children.append(
                        TextNode("bool", "true" if correct else "false")
                    )
                node.children.append(TextNode("paragraph", text))
                node.children[1].parse()
        elif self.type == "itemize":
            items = self.data.strip().split("\n")
            self.data = ""
            for child in items:
                node = TextNode("paragraph", child[1:].strip())
                self.children.append(node)
                node.parse()
        elif self.type == "paragraph":
            lex = Lexer(self.data.strip())
            self.data = ""
            self.children.append(self.parse_span(lex))
        else:
            raise Exception("unimplemented")

    def parse_span(self, lex: Lexer) -> Self:
        # grammar: span = { item };
        #          item = bold | math | text | input;
        #          bold = "*" { item } "*";
        #          math = "$" { item } "$";
        #          input = "%" ["!"] var;
        #          text = "\\" | otherwise;
        span = TextNode("span")
        while lex.token != "":
            span.children.append(self.parse_item(lex))
        return span

    def parse_item(self, lex: Lexer, math_mode=False) -> Self:
        if not math_mode and lex.token == "*":
            return self.parse_bold_italic(lex)
        elif lex.token == "$":
            return self.parse_math(lex)
        elif not math_mode and lex.token == "%":
            return self.parse_input(lex)
        elif not math_mode and lex.token == "\\":
            lex.next()
            if lex.token == "\\":
                lex.next()
            return TextNode("text", "<br/>")
        else:
            n = TextNode("text", lex.token)
            lex.next()
            return n

    def parse_bold_italic(self, lex: Lexer) -> Self:
        node = TextNode("italic")
        if lex.token == "*":
            lex.next()
        if lex.token == "*":
            node.type = "bold"
            lex.next()
        while lex.token != "" and lex.token != "*":
            node.children.append(self.parse_item(lex))
        if lex.token == "*":
            lex.next()
        if lex.token == "*":
            lex.next()
        return node

    def parse_math(self, lex: Lexer) -> Self:
        math = TextNode("math")
        if lex.token == "$":
            lex.next()
        if lex.token == "$":
            math.type = "display-math"
            lex.next()
        while lex.token != "" and lex.token != "$":
            math.children.append(self.parse_item(lex, True))
        if lex.token == "$":
            lex.next()
        if math.type == "display-math" and lex.token == "$":
            lex.next()
        return math

    def parse_input(self, lex: Lexer) -> Self:
        input = TextNode("input")
        if lex.token == "%":
            lex.next()
        if lex.token == "!":
            input.type = "input2"
            lex.next()
        input.data = lex.token.strip()
        lex.next()
        return input

    def optimize(self) -> Self:
        children_opt = []
        for c in self.children:
            opt = c.optimize()
            if (
                opt.type == "text"
                and opt.data.startswith('"') is False
                and opt.data.startswith("`") is False
                and len(children_opt) > 0
                and children_opt[-1].type == "text"
                and children_opt[-1].data.startswith('"') is False
                and children_opt[-1].data.startswith("`") is False
            ):
                children_opt[-1].data += opt.data
            else:
                children_opt.append(opt)
        self.children = children_opt
        return self

    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "data": self.data,
            "children": list(map(lambda o: o.to_dict(), self.children)),
        }


class Question:
    """Question of the quiz"""

    def __init__(self, src_line_no: int):
        self.src_line_no: int = src_line_no
        self.title: str = ""
        self.python_src: str = ""
        self.variables: set[str] = set()
        self.instances: list[dict] = []
        self.text_src: str = ""
        self.text: TextNode = None
        self.error: str = ""
        self.python_src_tokens: set[str] = set()

    def build(self):
        if len(self.python_src) > 0:
            self.analyze_python_code()
            instances_str = []
            for i in range(0, 5):
                # try to generate instances distinct to prior once
                # TODO: give up and keep less than 5, if applicable!
                instance = {}
                instance_str = ""
                for k in range(0, 10):
                    self.error = ""
                    instance = self.run_python_code()
                    instance_str = str(instance)
                    if instance_str not in instances_str:
                        break
                instances_str.append(instance_str)
                self.instances.append(instance)
            if "No module named" in self.error:
                print("!!! " + self.error)
        self.text = TextNode("root", self.text_src)
        self.text.parse()
        self.post_process_text(self.text)
        self.text.optimize()

    def post_process_text(self, node: TextNode, math=False):
        for c in node.children:
            self.post_process_text(
                c, math or node.type == "math" or node.type == "display-math"
            )
        if node.type == "input":
            if node.data.startswith('"'):
                # gap question
                node.type = "gap"
                node.data = node.data.replace('"', "")
            elif node.data not in self.variables:
                # ask for numerical variable
                var_id = node.data
                self.error += "Unknown input variable '" + var_id + "'. "
        elif node.type == "text":
            if (
                math
                and len(node.data) >= 2
                and node.data.startswith('"')
                and node.data.endswith('"')
            ):
                node.data = node.data[1:-1]
            elif math and (node.data in self.variables):
                node.type = "var"
            elif (
                not math
                and len(node.data) >= 2
                and node.data.startswith("`")
                and node.data.endswith("`")
            ):
                node.type = "code"
                node.data = node.data[1:-1]

    def format_float(self, v: float) -> str:
        s = str(v)
        if s.endswith(".0"):
            return s[:-2]
        return s

    def analyze_python_code(self):
        """Get all tokens from Python source code. This is required to filter
        out all locals from libraries (refer to method run_python_code)"""
        lex = Lexer(self.python_src)
        while len(lex.token) > 0:
            self.python_src_tokens.add(lex.token)
            lex.next()

    def run_python_code(self) -> dict:
        locals = {}
        res = {}
        src = self.python_src
        if "rangeZ" in self.python_src:
            src = rangeZ_src + src
        try:
            exec(src, globals(), locals)
        except Exception as e:
            # print(e)
            self.error += str(e) + ". "
            return res
        for id in locals:
            if id in skipVariables or (id not in self.python_src_tokens):
                continue
            value = locals[id]
            type_str = str(type(value))
            if type_str == "<class 'module'>" or type_str == "<class 'function'>":
                continue
            self.variables.add(id)
            if type_str in boolean_types:
                res[id] = {"type": "bool", "value": str(value).lower()}
            elif type_str in int_types:
                res[id] = {"type": "int", "value": str(value)}
            elif type_str in float_types:
                res[id] = {"type": "float", "value": self.format_float(value)}
            elif type_str == "<class 'complex'>":
                res[id] = {
                    "type": "complex",
                    "value": self.format_float(value.real)
                    + ","
                    + self.format_float(value.imag),
                }
            elif type_str == "<class 'list'>":
                res[id] = {
                    "type": "vector",
                    "value": str(value)
                    .replace("[", "")
                    .replace("]", "")
                    .replace(" ", ""),
                }
            elif type_str == "<class 'set'>":
                res[id] = {
                    "type": "set",
                    "value": str(value)
                    .replace("{", "")
                    .replace("}", "")
                    .replace(" ", ""),
                }
            elif type_str == "<class 'sympy.matrices.dense.MutableDenseMatrix'>":
                # e.g. 'Matrix([[-1, 0, -2], [-1, 5*sin(x)*cos(x)/7, 2], [-1, 2, 0]])'
                res[id] = {"type": "matrix", "value": str(value)[7:-1]}
            elif (
                type_str == "<class 'numpy.matrix'>"
                or type_str == "<class 'numpy.ndarray'>"
            ):
                # e.g. '[[ -6 -13 -12]\n [-17  -3 -20]\n [-14  -8 -16]\n [ -7 -15  -8]]'
                v = re.sub(" +", " ", str(value))  # remove double spaces
                v = re.sub("\[ ", "[", v)  # remove space(s) after "["
                v = re.sub(" \]", "]", v)  # remove space(s) before "]"
                v = v.replace(" ", ",").replace("\n", "")
                res[id] = {"type": "matrix", "value": v}
            else:
                res[id] = {"type": "term", "value": str(value).replace("**", "^")}
        if len(self.variables) > 50:
            self.error += "ERROR: Wrong usage of Python imports. Refer to pySELL docs!"
            # TODO: write the docs...
        return res

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "error": self.error,
            "variables": list(self.variables),
            "instances": self.instances,
            "text": self.text.to_dict(),
            # the following is only relevant for debugging purposes,
            # i.e. only present in _DEBUG.html
            "src_line": self.src_line_no,
            "text_src_html": self.syntax_highlight_text(self.text_src),
            "python_src_html": self.syntax_highlight_python(self.python_src),
            "python_src_tokens": list(self.python_src_tokens),
        }

    def syntax_highlight_text_line(self, src: str) -> str:
        html = ""
        math = False
        code = False
        bold = False
        italic = False
        n = len(src)
        i = 0
        while i < n:
            ch = src[i]
            if ch == " ":
                html += "&nbsp;"
            elif not math and ch == "%":
                html += '<span style="color:green; font-weight: bold;">'
                html += ch
                if i + 1 < n and src[i + 1] == "!":
                    html += src[i + 1]
                    i += 1
                html += "</span>"
            elif ch == "*" and i + 1 < n and src[i + 1] == "*":
                i += 1
                bold = not bold
                if bold:
                    html += '<span style="font-weight: bold;">'
                    html += "**"
                else:
                    html += "**"
                    html += "</span>"
            elif ch == "*":
                italic = not italic
                if italic:
                    html += '<span style="font-style: italic;">'
                    html += "*"
                else:
                    html += "*"
                    html += "</span>"
            elif ch == "$":
                display_style = False
                if i + 1 < n and src[i + 1] == "$":
                    display_style = True
                    i += 1
                math = not math
                if math:
                    html += '<span style="color:#FF5733; font-weight: bold;">'
                    html += ch
                    if display_style:
                        html += ch
                else:
                    html += ch
                    if display_style:
                        html += ch
                    html += "</span>"
            elif ch == "`":
                code = not code
                if code:
                    html += '<span style="color:#33A5FF; font-weight: bold;">'
                    html += ch
                else:
                    html += ch
                    html += "</span>"
            else:
                html += ch
            i += 1
        if math:
            html += "</span>"
        if code:
            html += "</span>"
        if italic:
            html += "</span>"
        if bold:
            html += "</bold>"
        return html

    def red_colored_span(self, innerHTML: str) -> str:
        return '<span style="color:#FF5733; font-weight:bold">' + innerHTML + "</span>"

    def syntax_highlight_text(self, src: str) -> str:
        html = ""
        lines = src.split("\n")
        for line in lines:
            if len(line.strip()) == 0:
                continue
            if line.startswith("-"):
                html += self.red_colored_span("-")
                line = line[1:].replace(" ", "&nbsp;")
            elif line.startswith("["):
                l1 = line.split("]")[0] + "]".replace(" ", "&nbsp;")
                html += self.red_colored_span(l1)
                line = "]".join(line.split("]")[1:]).replace(" ", "&nbsp;")
            elif line.startswith("("):
                l1 = line.split(")")[0] + ")".replace(" ", "&nbsp;")
                html += self.red_colored_span(l1)
                line = ")".join(line.split(")")[1:]).replace(" ", "&nbsp;")
            html += self.syntax_highlight_text_line(line)
            html += "<br/>"
        return html

    def syntax_highlight_python(self, src: str) -> str:
        lines = src.split("\n")
        html = ""
        for line in lines:
            if len(line.strip()) == 0:
                continue
            lex = Lexer(line)
            while len(lex.token) > 0:
                if len(lex.token) > 0 and lex.token[0] >= "0" and lex.token[0] <= "9":
                    html += '<span style="color:green; font-weight:bold">'
                    html += lex.token + "</span>"
                elif lex.token in python_kws:
                    html += '<span style="color:#FF5733; font-weight:bold">'
                    html += lex.token + "</span>"
                else:
                    html += lex.token.replace(" ", "&nbsp;")
                lex.next()
            html += "<br/>"
        return html


def compile(src: str) -> dict:
    """compiles a SELL input file to JSON"""
    lang = "en"
    title = ""
    author = ""
    info = ""
    questions = []
    question = None
    parsing_python = False
    lines = src.split("\n")
    for line_no, line in enumerate(lines):
        line = line.split("#")[0]  # remove comments
        lineUnStripped = line
        line = line.strip()
        if len(line) == 0:
            continue
        if line.startswith("LANG"):
            lang = line[4:].strip()
        elif line.startswith("TITLE"):
            title = line[5:].strip()
        elif line.startswith("AUTHOR"):
            author = line[6:].strip()
        elif line.startswith("INFO"):
            info = line[4:].strip()
        elif line.startswith("QUESTION"):
            question = Question(line_no + 1)
            questions.append(question)
            question.title = line[8:].strip()
            parsing_python = False
        elif question != None:
            if line.startswith('"""'):
                parsing_python = not parsing_python
            else:
                if parsing_python:
                    question.python_src += lineUnStripped.replace("\t", "    ") + "\n"
                else:
                    question.text_src += line + "\n"
    for question in questions:
        question.build()
    return {
        "lang": lang,
        "title": title,
        "author": author,
        "info": info,
        "questions": list(map(lambda o: o.to_dict(), questions)),
    }


# the following code is automatically generated and updated by file "build.js"
# @begin(html)
html = """<!DOCTYPE html> <html> <head> <meta charset="UTF-8" /> <title>pySELL</title> <meta name="viewport" content="width=device-width, initial-scale=1.0" /> <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css" integrity="sha384-n8MVd4RsNIU0tAv4ct0nTaAbDJwPJzDEaqSD1odI+WdtXRGWt2kTvGFasHpSy3SV" crossorigin="anonymous" /> <script src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js" integrity="sha384-XjKyOOlGwcjNTAIQHIpgOno0Hl1YQqzUOEleOLALmuqehneUG+vnGctmUb0ZY0l8" crossorigin="anonymous" ></script> <style> html { font-family: Arial, Helvetica, sans-serif; } body { max-width: 1024px; margin-left: auto; margin-right: auto; padding-left: 5px; padding-right: 5px; } h1 { text-align: center; font-size: 28pt; } .author { text-align: center; font-size: 18pt; } .courseInfo { font-size: 14pt; font-style: italic; /*margin-bottom: 24px;*/ text-align: center; } .question { position: relative; /* required for feedback overlays */ color: black; background-color: white; border-style: solid; border-radius: 5px; border-width: 3px; border-color: black; padding: 8px; margin-top: 20px; margin-bottom: 20px; -webkit-box-shadow: 4px 6px 8px -1px rgba(0, 0, 0, 0.93); box-shadow: 4px 6px 8px -1px rgba(0, 0, 0, 0.1); } .questionFeedback { z-index: 10; display: none; position: absolute; pointer-events: none; left: 0; top: 33%; width: 100%; height: 100%; text-align: center; font-size: 8vw; text-shadow: 0px 0px 18px rgba(0, 0, 0, 0.7); } .questionTitle { font-size: 24pt; } .code { font-family: "Courier New", Courier, monospace; color: black; background-color: rgb(235, 235, 235); padding: 2px 5px; border-radius: 5px; margin: 1px 2px; } .debugCode { font-family: "Courier New", Courier, monospace; padding: 4px; margin-bottom: 5px; background-color: black; color: white; border-radius: 5px; opacity: 0.85; overflow-x: scroll; } .debugInfo { text-align: end; font-size: 10pt; margin-top: 2px; color: rgb(64, 64, 64); } ul { margin-top: 0; margin-left: 0px; padding-left: 20px; } .inputField { position: relative; width: 32px; height: 24px; font-size: 14pt; border-style: solid; border-color: black; border-radius: 5px; border-width: 0.2; padding-left: 5px; padding-right: 5px; outline-color: black; background-color: transparent; margin: 1px; } .inputField:focus { outline-color: maroon; } .equationPreview { position: absolute; top: 120%; left: 0%; padding-left: 8px; padding-right: 8px; padding-top: 4px; padding-bottom: 4px; background-color: rgb(128, 0, 0); border-radius: 5px; font-size: 12pt; color: white; text-align: start; z-index: 20; opacity: 0.95; } .button { padding-left: 8px; padding-right: 8px; padding-top: 5px; padding-bottom: 5px; font-size: 12pt; background-color: rgb(0, 150, 0); color: white; border-style: none; border-radius: 4px; height: 36px; cursor: pointer; } .buttonRow { display: flex; align-items: baseline; margin-top: 12px; } .matrixResizeButton { width: 20px; background-color: black; color: #fff; text-align: center; border-radius: 3px; position: absolute; z-index: 1; height: 20px; cursor: pointer; margin-bottom: 3px; } a { color: black; text-decoration: underline; } </style> </head> <body> <h1 id="title"></h1> <div class="author" id="author"></div> <p id="courseInfo1" class="courseInfo"></p> <p id="courseInfo2" class="courseInfo"></p> <h1 id="debug" class="debugCode" style="display: none">DEBUG VERSION</h1> <div id="questions"></div> <p style="font-size: 8pt; font-style: italic; text-align: center"> This quiz was created using <a href="https://github.com/andreas-schwenk/pysell">pySELL</a>, the <i>Python-based Simple E-Learning Language</i>, written by Andreas Schwenk, GPLv3<br /> last update on <span id="date"></span> </p> <script>let debug = false; let quizSrc = {};var sell=(()=>{var P=Object.defineProperty;var $=Object.getOwnPropertyDescriptor;var ee=Object.getOwnPropertyNames;var te=Object.prototype.hasOwnProperty;var ie=(r,e)=>{for(var t in e)P(r,t,{get:e[t],enumerable:!0})},se=(r,e,t,s)=>{if(e&&typeof e=="object"||typeof e=="function")for(let i of ee(e))!te.call(r,i)&&i!==t&&P(r,i,{get:()=>e[i],enumerable:!(s=$(e,i))||s.enumerable});return r};var ne=r=>se(P({},"__esModule",{value:!0}),r);var le={};ie(le,{init:()=>ae});function v(r=[]){let e=document.createElement("div");return e.append(...r),e}function Q(r=[]){let e=document.createElement("ul");return e.append(...r),e}function N(r){let e=document.createElement("li");return e.appendChild(r),e}function L(r){let e=document.createElement("input");return e.spellcheck=!1,e.type="text",e.classList.add("inputField"),e.style.width=r+"px",e}function U(){let r=document.createElement("button");return r.type="button",r.classList.add("button"),r}function f(r,e=[]){let t=document.createElement("span");return e.length>0?t.append(...e):t.innerHTML=r,t}function B(r,e,t=!1){katex.render(e,r,{throwOnError:!1,displayMode:t,macros:{"\\RR":"\\mathbb{R}","\\NN":"\\mathbb{N}","\\QQ":"\\mathbb{Q}","\\ZZ":"\\mathbb{Z}"}})}function M(r,e=!1){let t=document.createElement("span");return B(t,r,e),t}var W={en:"This page runs in your browser and does not store any data on servers.",de:"Diese Seite wird in Ihrem Browser ausgef\xFChrt und speichert keine Daten auf Servern.",es:"Esta p\xE1gina se ejecuta en su navegador y no almacena ning\xFAn dato en los servidores.",it:"Questa pagina viene eseguita nel browser e non memorizza alcun dato sui server.",fr:"Cette page fonctionne dans votre navigateur et ne stocke aucune donn\xE9e sur des serveurs."},F={en:"You can * this page in order to get new randomized tasks.",de:"Sie k\xF6nnen diese Seite *, um neue randomisierte Aufgaben zu erhalten.",es:"Puedes * esta p\xE1gina para obtener nuevas tareas aleatorias.",it:"\xC8 possibile * questa pagina per ottenere nuovi compiti randomizzati",fr:"Vous pouvez * cette page pour obtenir de nouvelles t\xE2ches al\xE9atoires"},O={en:"reload",de:"aktualisieren",es:"recargar",it:"ricaricare",fr:"recharger"},j={en:["awesome","great","correct","well done"],de:["super","gut gemacht","weiter so","richtig"],es:["impresionante","genial","correcto","bien hecho"],it:["fantastico","grande","corretto","ben fatto"],fr:["g\xE9nial","super","correct","bien fait"]},_={en:["try again","still some mistakes","wrong answer"],de:["leider falsch","nicht richtig","versuch's nochmal"],es:["int\xE9ntalo de nuevo","todav\xEDa algunos errores","respuesta incorrecta"],it:["riprova","ancora qualche errore","risposta sbagliata"],fr:["r\xE9essayer","encore des erreurs","mauvaise r\xE9ponse"]};function Z(r,e){let t=Array(e.length+1).fill(null).map(()=>Array(r.length+1).fill(null));for(let s=0;s<=r.length;s+=1)t[0][s]=s;for(let s=0;s<=e.length;s+=1)t[s][0]=s;for(let s=1;s<=e.length;s+=1)for(let i=1;i<=r.length;i+=1){let a=r[i-1]===e[s-1]?0:1;t[s][i]=Math.min(t[s][i-1]+1,t[s-1][i]+1,t[s-1][i-1]+a)}return t[e.length][r.length]}var K='<svg xmlns="http://www.w3.org/2000/svg" height="28" viewBox="0 0 448 512"><path d="M384 80c8.8 0 16 7.2 16 16V416c0 8.8-7.2 16-16 16H64c-8.8 0-16-7.2-16-16V96c0-8.8 7.2-16 16-16H384zM64 32C28.7 32 0 60.7 0 96V416c0 35.3 28.7 64 64 64H384c35.3 0 64-28.7 64-64V96c0-35.3-28.7-64-64-64H64z"/></svg>',q='<svg xmlns="http://www.w3.org/2000/svg" height="28" viewBox="0 0 448 512"><path d="M64 80c-8.8 0-16 7.2-16 16V416c0 8.8 7.2 16 16 16H384c8.8 0 16-7.2 16-16V96c0-8.8-7.2-16-16-16H64zM0 96C0 60.7 28.7 32 64 32H384c35.3 0 64 28.7 64 64V416c0 35.3-28.7 64-64 64H64c-35.3 0-64-28.7-64-64V96zM337 209L209 337c-9.4 9.4-24.6 9.4-33.9 0l-64-64c-9.4-9.4-9.4-24.6 0-33.9s24.6-9.4 33.9 0l47 47L303 175c9.4-9.4 24.6-9.4 33.9 0s9.4 24.6 0 33.9z"/>',X='<svg xmlns="http://www.w3.org/2000/svg" height="28" viewBox="0 0 512 512"><path d="M464 256A208 208 0 1 0 48 256a208 208 0 1 0 416 0zM0 256a256 256 0 1 1 512 0A256 256 0 1 1 0 256z"/></svg>',Y='<svg xmlns="http://www.w3.org/2000/svg" height="28" viewBox="0 0 512 512"><path d="M256 48a208 208 0 1 1 0 416 208 208 0 1 1 0-416zm0 464A256 256 0 1 0 256 0a256 256 0 1 0 0 512zM369 209c9.4-9.4 9.4-24.6 0-33.9s-24.6-9.4-33.9 0l-111 111-47-47c-9.4-9.4-24.6-9.4-33.9 0s-9.4 24.6 0 33.9l64 64c9.4 9.4 24.6 9.4 33.9 0L369 209z"/></svg>',D='<svg xmlns="http://www.w3.org/2000/svg" height="25" viewBox="0 0 384 512" fill="white"><path d="M73 39c-14.8-9.1-33.4-9.4-48.5-.9S0 62.6 0 80V432c0 17.4 9.4 33.4 24.5 41.9s33.7 8.1 48.5-.9L361 297c14.3-8.7 23-24.2 23-41s-8.7-32.2-23-41L73 39z"/></svg>',G='<svg xmlns="http://www.w3.org/2000/svg" height="25" viewBox="0 0 512 512" fill="white"><path d="M0 224c0 17.7 14.3 32 32 32s32-14.3 32-32c0-53 43-96 96-96H320v32c0 12.9 7.8 24.6 19.8 29.6s25.7 2.2 34.9-6.9l64-64c12.5-12.5 12.5-32.8 0-45.3l-64-64c-9.2-9.2-22.9-11.9-34.9-6.9S320 19.1 320 32V64H160C71.6 64 0 135.6 0 224zm512 64c0-17.7-14.3-32-32-32s-32 14.3-32 32c0 53-43 96-96 96H192V352c0-12.9-7.8-24.6-19.8-29.6s-25.7-2.2-34.9 6.9l-64 64c-12.5 12.5-12.5 32.8 0 45.3l64 64c9.2 9.2 22.9 11.9 34.9 6.9s19.8-16.6 19.8-29.6V448H352c88.4 0 160-71.6 160-160z"/></svg>';function R(r,e=!1){let t=new Array(r);for(let s=0;s<r;s++)t[s]=s;if(e)for(let s=0;s<r;s++){let i=Math.floor(Math.random()*r),a=Math.floor(Math.random()*r),h=t[i];t[i]=t[a],t[a]=h}return t}var b=class r{constructor(e,t){this.m=e,this.n=t,this.v=new Array(e*t).fill("0")}getElement(e,t){return e<0||e>=this.m||t<0||t>=this.n?"0":this.v[e*this.n+t]}resize(e,t,s){if(e<1||e>50||t<1||t>50)return!1;let i=new r(e,t);i.v.fill(s);for(let a=0;a<i.m;a++)for(let h=0;h<i.n;h++)i.v[a*i.n+h]=this.getElement(a,h);return this.fromMatrix(i),!0}fromMatrix(e){this.m=e.m,this.n=e.n,this.v=[...e.v]}fromString(e){this.m=e.split("],").length,this.v=e.replaceAll("[","").replaceAll("]","").split(",").map(t=>t.trim()),this.n=this.v.length/this.m}getMaxCellStrlen(){let e=0;for(let t of this.v)t.length>e&&(e=t.length);return e}toTeXString(e=!1){let t=e?"\\left[\\begin{array}":"\\begin{bmatrix}";e&&(t+="{"+"c".repeat(this.n-1)+"|c}");for(let s=0;s<this.m;s++){for(let i=0;i<this.n;i++){i>0&&(t+="&");let a=this.getElement(s,i);try{a=g.parse(a).toTexString()}catch{}t+=a}t+="\\\\"}return t+=e?"\\end{array}\\right]":"\\end{bmatrix}",t}};function re(r){return parseFloat(r)}var u=class r{constructor(e,t,s=0,i=0){this.op=e,this.c=t,this.re=s,this.im=i,this.explicitParentheses=!1}static const(e=0,t=0){return new r("const",[],e,t)}compare(e,t=0,s=1e-9){let i=this.re-e,a=this.im-t;return Math.sqrt(i*i+a*a)<s}toString(){let e="";if(this.op==="const"){let t=Math.abs(this.re)>1e-14,s=Math.abs(this.im)>1e-14;t&&s&&this.im>=0?e="("+this.re+"+"+this.im+"i)":t&&s&&this.im<0?e="("+this.re+"-"+-this.im+"i)":t?e=""+this.re:s&&(e="("+this.im+"i)")}else this.op.startsWith("var")?e=this.op.split(":")[1]:this.c.length==1?e=(this.op===".-"?"-":this.op)+"("+this.c.toString()+")":e="("+this.c.map(t=>t.toString()).join(this.op)+")";return e}toTexString(e=!1){let s="";switch(this.op){case"const":{let i=Math.abs(this.re)>1e-9,a=Math.abs(this.im)>1e-9,h=i?""+this.re:"",l=a?""+this.im+"i":"";l==="1i"?l="i":l==="-1i"&&(l="-i"),a&&this.im>=0&&i&&(l="+"+l),!i&&!a?s="0":s=h+l;break}case".-":s="-"+this.c[0].toTexString();break;case"+":case"-":case"*":case"^":{let i=this.op==="*"?"\\cdot ":this.op;s="{"+this.c[0].toTexString()+"}"+i+"{"+this.c[1].toTexString()+"}";break}case"/":s="\\frac{"+this.c[0].toTexString(!0)+"}{"+this.c[1].toTexString(!0)+"}";break;case"sin":case"sinc":case"cos":case"tan":case"cot":case"exp":case"ln":s+="\\"+this.op+"\\left("+this.c[0].toTexString(!0)+"\\right)";break;case"sqrt":s+="\\"+this.op+"{"+this.c[0].toTexString(!0)+"}";break;case"abs":s+="\\left|"+this.c[0].toTexString(!0)+"\\right|";break;default:if(this.op.startsWith("var:")){let i=this.op.substring(4);switch(i){case"pi":i="\\pi";break}s=" "+i+" "}else{let i="warning: Node.toString(..):";i+=" unimplemented operator '"+this.op+"'",console.log(i),s=this.op,this.c.length>0&&(s+="\\left({"+this.c.map(a=>a.toTexString(!0)).join(",")+"}\\right)")}}return!e&&this.explicitParentheses&&(s="\\left({"+s+"}\\right)"),s}},g=class r{constructor(){this.root=null,this.src="",this.token="",this.skippedWhiteSpace=!1,this.pos=0}getVars(e,t=null){t==null&&(t=this.root),t.op.startsWith("var:")&&e.add(t.op.substring(4));for(let s of t.c)this.getVars(e,s)}eval(e,t=null){let i=u.const(),a=0,h=0,l=null;switch(t==null&&(t=this.root),t.op){case"const":i=t;break;case"+":case"-":case"*":case"/":case"^":case"==":{let n=this.eval(e,t.c[0]),o=this.eval(e,t.c[1]);switch(t.op){case"+":i.re=n.re+o.re,i.im=n.im+o.im;break;case"-":i.re=n.re-o.re,i.im=n.im-o.im;break;case"*":i.re=n.re*o.re-n.im*o.im,i.im=n.re*o.im+n.im*o.re;break;case"/":a=o.re*o.re+o.im*o.im,i.re=(n.re*o.re+n.im*o.im)/a,i.im=(n.im*o.re-n.re*o.im)/a;break;case"^":l=new u("exp",[new u("*",[o,new u("ln",[n])])]),i=this.eval(e,l);break;case"==":a=n.re-o.re,h=n.im-o.im,i.re=Math.sqrt(a*a+h*h)<1e-9?1:0,i.im=0;break}break}case".-":case"abs":case"sin":case"sinc":case"cos":case"tan":case"cot":case"exp":case"ln":case"log":case"sqrt":{let n=this.eval(e,t.c[0]);switch(t.op){case".-":i.re=-n.re,i.im=-n.im;break;case"abs":i.re=Math.sqrt(n.re*n.re+n.im*n.im),i.im=0;break;case"sin":i.re=Math.sin(n.re)*Math.cosh(n.im),i.im=Math.cos(n.re)*Math.sinh(n.im);break;case"sinc":l=new u("/",[new u("sin",[n]),n]),i=this.eval(e,l);break;case"cos":i.re=Math.cos(n.re)*Math.cosh(n.im),i.im=-Math.sin(n.re)*Math.sinh(n.im);break;case"tan":a=Math.cos(n.re)*Math.cos(n.re)+Math.sinh(n.im)*Math.sinh(n.im),i.re=Math.sin(n.re)*Math.cos(n.re)/a,i.im=Math.sinh(n.im)*Math.cosh(n.im)/a;break;case"cot":a=Math.sin(n.re)*Math.sin(n.re)+Math.sinh(n.im)*Math.sinh(n.im),i.re=Math.sin(n.re)*Math.cos(n.re)/a,i.im=-(Math.sinh(n.im)*Math.cosh(n.im))/a;break;case"exp":i.re=Math.exp(n.re)*Math.cos(n.im),i.im=Math.exp(n.re)*Math.sin(n.im);break;case"ln":case"log":i.re=Math.log(Math.sqrt(n.re*n.re+n.im*n.im)),a=Math.abs(n.im)<1e-9?0:n.im,i.im=Math.atan2(a,n.re);break;case"sqrt":l=new u("^",[n,u.const(.5)]),i=this.eval(e,l);break}break}default:if(t.op.startsWith("var:")){let n=t.op.substring(4);if(n==="pi")return u.const(Math.PI);if(n==="e")return u.const(Math.E);if(n==="i")return u.const(0,1);if(n in e)return e[n];throw new Error("eval-error: unknown variable '"+n+"'")}else throw new Error("UNIMPLEMENTED eval '"+t.op+"'")}return i}static parse(e){let t=new r;if(t.src=e,t.token="",t.skippedWhiteSpace=!1,t.pos=0,t.next(),t.root=t.parseExpr(!1),t.token!=="")throw new Error("remaining tokens: "+t.token+"...");return t}parseExpr(e){return this.parseAdd(e)}parseAdd(e){let t=this.parseMul(e);for(;["+","-"].includes(this.token)&&!(e&&this.skippedWhiteSpace);){let s=this.token;this.next(),t=new u(s,[t,this.parseMul(e)])}return t}parseMul(e){let t=this.parsePow(e);for(;!(e&&this.skippedWhiteSpace);){let s="*";if(["*","/"].includes(this.token))s=this.token,this.next();else if(!e&&this.token==="(")s="*";else if(this.token.length>0&&(this.isAlpha(this.token[0])||this.isNum(this.token[0])))s="*";else break;t=new u(s,[t,this.parsePow(e)])}return t}parsePow(e){let t=this.parseUnary(e);for(;["^"].includes(this.token)&&!(e&&this.skippedWhiteSpace);){let s=this.token;this.next(),t=new u(s,[t,this.parseUnary(e)])}return t}parseUnary(e){return this.token==="-"?(this.next(),new u(".-",[this.parseMul(e)])):this.parseInfix(e)}parseInfix(e){if(this.token.length==0)throw new Error("expected unary");if(this.isNum(this.token[0])){let t=this.token;return this.next(),this.token==="."&&(t+=".",this.next(),this.token.length>0&&(t+=this.token,this.next())),new u("const",[],re(t))}else if(this.fun1().length>0){let t=this.fun1();this.next(t.length);let s=null;if(this.token==="(")if(this.next(),s=this.parseExpr(e),this.token+="",this.token===")")this.next();else throw Error("expected ')'");else s=this.parseMul(!0);return new u(t,[s])}else if(this.token==="("){this.next();let t=this.parseExpr(e);if(this.token+="",this.token===")")this.next();else throw Error("expected ')'");return t.explicitParentheses=!0,t}else if(this.token==="|"){this.next();let t=this.parseExpr(e);if(this.token+="",this.token==="|")this.next();else throw Error("expected '|'");return new u("abs",[t])}else if(this.isAlpha(this.token[0])){let t="";return this.token.startsWith("pi")?t="pi":t=this.token[0],this.next(t.length),new u("var:"+t,[])}else throw new Error("expected unary")}compare(e){let i=new Set;this.getVars(i),e.getVars(i);for(let a=0;a<10;a++){let h={};for(let o of i)h[o]=u.const(Math.random(),Math.random());let l=new u("==",[this.root,e.root]),n=this.eval(h,l);if(Math.abs(n.re)<1e-9)return!1}return!0}fun1(){let e=["abs","sinc","sin","cos","tan","cot","exp","ln","sqrt"];for(let t of e)if(this.token.startsWith(t))return t;return""}next(e=-1){if(e>0&&this.token.length>e){this.token=this.token.substring(e),this.skippedWhiteSpace=!1;return}this.token="";let t=!1,s=this.src.length;for(this.skippedWhiteSpace=!1;this.pos<s&&`	
 `.includes(this.src[this.pos]);)this.skippedWhiteSpace=!0,this.pos++;for(;!t&&this.pos<s;){let i=this.src[this.pos];if(this.token.length>0&&(this.isNum(this.token[0])&&this.isAlpha(i)||this.isAlpha(this.token[0])&&this.isNum(i)))return;if(`^%#*$()[]{},.:;+-*/_!<>=?|	
 `.includes(i)){if(this.token.length>0)return;t=!0}`	
 `.includes(i)==!1&&(this.token+=i),this.pos++}}isNum(e){return e.charCodeAt(0)>=48&&e.charCodeAt(0)<=57}isAlpha(e){return e.charCodeAt(0)>=65&&e.charCodeAt(0)<=90||e.charCodeAt(0)>=97&&e.charCodeAt(0)<=122||e==="_"}toString(){return this.root==null?"":this.root.toString()}toTexString(){return this.root==null?"":this.root.toTexString()}};function J(r){r.feedbackSpan.innerHTML="",r.numChecked=0,r.numCorrect=0;for(let s in r.expected){let i=r.types[s],a=r.student[s],h=r.expected[s];switch(i){case"bool":a===h&&r.numCorrect++;break;case"string":{let l=r.gapInputs[s],n=a.trim().toUpperCase(),o=h.trim().toUpperCase(),p=Z(n,o)<=1;p&&(r.gapInputs[s].value=o,r.student[s]=o),p&&r.numCorrect++,l.style.color=p?"black":"white",l.style.backgroundColor=p?"transparent":"maroon";break}case"int":Math.abs(parseFloat(a)-parseFloat(h))<1e-9&&r.numCorrect++;break;case"float":case"term":{try{let l=g.parse(h),n=g.parse(a);l.compare(n)&&r.numCorrect++}catch(l){r.debug&&(console.log("term invalid"),console.log(l))}break}case"vector":case"complex":case"set":{let l=h.split(",");r.numChecked+=l.length-1;let n=[];for(let o=0;o<l.length;o++)n.push(r.student[s+"-"+o]);if(i==="set")for(let o=0;o<l.length;o++)try{let m=g.parse(l[o]);for(let p=0;p<n.length;p++){let c=g.parse(n[p]);if(m.compare(c)){r.numCorrect++;break}}}catch(m){r.debug&&console.log(m)}else for(let o=0;o<l.length;o++)try{let m=g.parse(n[o]),p=g.parse(l[o]);m.compare(p)&&r.numCorrect++}catch(m){r.debug&&console.log(m)}break}case"matrix":{let l=new b(0,0);l.fromString(h),r.numChecked+=l.m*l.n-1;for(let n=0;n<l.m;n++)for(let o=0;o<l.n;o++){let m=n*l.n+o;a=r.student[s+"-"+m];let p=l.v[m];try{let c=g.parse(p),d=g.parse(a);c.compare(d)&&r.numCorrect++}catch(c){r.debug&&console.log(c)}}break}default:r.feedbackSpan.innerHTML="UNIMPLEMENTED EVAL OF TYPE "+i}r.numChecked++}r.state=r.numCorrect==r.numChecked?k.passed:k.errors,r.updateVisualQuestionState();let e=r.state===k.passed?j[r.language]:_[r.language],t=e[Math.floor(Math.random()*e.length)];r.feedbackDiv.innerHTML=t,r.feedbackDiv.style.color=r.state===k.passed?"green":"maroon",r.feedbackDiv.style.display="block",setTimeout(()=>{r.feedbackDiv.style.display="none"},500),r.state===k.passed?r.src.instances.length>0?(r.checkAndRepeatBtnState="repeat",r.checkAndRepeatBtn.innerHTML=G):r.checkAndRepeatBtn.style.display="none":(r.checkAndRepeatBtnState="check",r.checkAndRepeatBtn.innerHTML=D)}var y=class{constructor(e,t,s,i,a,h){t.student[s]="",this.question=t,this.inputId=s,this.outerSpan=f(""),this.outerSpan.style.position="relative",e.appendChild(this.outerSpan),this.inputElement=L(Math.max(i*10,48)),this.outerSpan.appendChild(this.inputElement),this.equationPreviewDiv=v(),this.equationPreviewDiv.classList.add("equationPreview"),this.equationPreviewDiv.style.display="none",this.outerSpan.appendChild(this.equationPreviewDiv),this.inputElement.addEventListener("click",()=>{this.edited()}),this.inputElement.addEventListener("focusout",()=>{this.equationPreviewDiv.innerHTML="",this.equationPreviewDiv.style.display="none"}),this.inputElement.addEventListener("keydown",l=>{let n="abcdefghijklmnopqrstuvwxyz";n+="ABCDEFGHIJKLMNOPQRSTUVWXYZ",n+="0123456789",n+="+-*/^(). <>=|",h&&(n="-0123456789"),l.key.length<3&&n.includes(l.key)==!1&&l.preventDefault()}),this.inputElement.addEventListener("keyup",()=>{this.question.editedQuestion(),this.edited()}),this.question.showSolution&&(t.student[s]=this.inputElement.value=a)}edited(){let e=this.inputElement.value.trim(),t="",s=!1;try{let i=g.parse(e);s=i.root.op==="const",t=i.toTexString(),this.equationPreviewDiv.style.backgroundColor="green"}catch{t=e.replaceAll("^","\\hat{~}").replaceAll("_","\\_"),this.equationPreviewDiv.style.backgroundColor="maroon"}B(this.equationPreviewDiv,t,!0),this.equationPreviewDiv.style.display=e.length>0&&!s?"block":"none",this.question.student[this.inputId]=e,this.validateTermInput()}validateTermInput(){let e=!0,t=this.inputElement.value.trim();if(t.length>0)try{g.parse(t)}catch{e=!1}this.inputElement.style.color=e?"black":"maroon"}},I=class{constructor(e,t,s,i){this.parent=e,this.question=t,this.inputId=s,this.matExpected=new b(0,0),this.matExpected.fromString(i),this.matStudent=new b(this.matExpected.m==1?1:3,this.matExpected.n==1?1:3),t.showSolution&&this.matStudent.fromMatrix(this.matExpected),this.genMatrixDom()}genMatrixDom(){let e=v();this.parent.innerHTML="",this.parent.appendChild(e),e.style.position="relative",e.style.display="inline-block";let t=document.createElement("table");e.appendChild(t);let s=this.matExpected.getMaxCellStrlen();for(let c=0;c<this.matStudent.m;c++){let d=document.createElement("tr");t.appendChild(d),c==0&&d.appendChild(this.generateMatrixParenthesis(!0,this.matStudent.m));for(let w=0;w<this.matStudent.n;w++){let x=c*this.matStudent.n+w,C=document.createElement("td");d.appendChild(C);let H=this.inputId+"-"+x;new y(C,this.question,H,s,this.matStudent.v[x],!1)}c==0&&d.appendChild(this.generateMatrixParenthesis(!1,this.matStudent.m))}let i=["+","-","+","-"],a=[0,0,1,-1],h=[1,-1,0,0],l=[0,22,888,888],n=[888,888,-22,-22],o=[-22,-22,0,22],m=[this.matExpected.n!=1,this.matExpected.n!=1,this.matExpected.m!=1,this.matExpected.m!=1],p=[this.matStudent.n>=10,this.matStudent.n<=1,this.matStudent.m>=10,this.matStudent.m<=1];for(let c=0;c<4;c++){if(m[c]==!1)continue;let d=f(i[c]);l[c]!=888&&(d.style.top=""+l[c]+"px"),n[c]!=888&&(d.style.bottom=""+n[c]+"px"),o[c]!=888&&(d.style.right=""+o[c]+"px"),d.classList.add("matrixResizeButton"),e.appendChild(d),p[c]?d.style.opacity="0.5":d.addEventListener("click",()=>{this.matStudent.resize(this.matStudent.m+a[c],this.matStudent.n+h[c],"0"),this.genMatrixDom()})}}generateMatrixParenthesis(e,t){let s=document.createElement("td");s.style.width="3px";for(let i of["Top",e?"Left":"Right","Bottom"])s.style["border"+i+"Width"]="2px",s.style["border"+i+"Style"]="solid";return s.rowSpan=t,s}};var k={init:0,errors:1,passed:2},A=class{constructor(e,t,s,i){this.state=k.init,this.language=s,this.src=t,this.debug=i,this.instanceOrder=R(t.instances.length,!0),this.instanceIdx=0,this.choiceIdx=0,this.gapIdx=0,this.expected={},this.types={},this.student={},this.gapInputs={},this.parentDiv=e,this.questionDiv=null,this.feedbackDiv=null,this.titleDiv=null,this.checkAndRepeatBtn=null,this.checkAndRepeatBtnState="check",this.showSolution=!1,this.feedbackSpan=null,this.numCorrect=0,this.numChecked=0}reset(){this.instanceIdx=(this.instanceIdx+1)%this.src.instances.length}getCurrentInstance(){return this.src.instances[this.instanceOrder[this.instanceIdx]]}editedQuestion(){this.state=k.init,this.updateVisualQuestionState(),this.questionDiv.style.color="black",this.checkAndRepeatBtn.innerHTML=D,this.checkAndRepeatBtn.style.display="block",this.checkAndRepeatBtn.style.color="black",this.checkAndRepeatBtnState="check"}updateVisualQuestionState(){let e="black",t="transparent";switch(this.state){case k.init:e="rgb(0,0,0)",t="transparent";break;case k.passed:e="rgb(0,150,0)",t="rgba(0,150,0, 0.025)";break;case k.errors:e="rgb(150,0,0)",t="rgba(150,0,0, 0.025)",this.numChecked>=5&&(this.feedbackSpan.innerHTML=""+this.numCorrect+" / "+this.numChecked);break}this.questionDiv.style.color=this.feedbackSpan.style.color=this.titleDiv.style.color=this.checkAndRepeatBtn.style.backgroundColor=this.questionDiv.style.borderColor=e,this.questionDiv.style.backgroundColor=t}populateDom(){if(this.parentDiv.innerHTML="",this.questionDiv=v(),this.parentDiv.appendChild(this.questionDiv),this.questionDiv.classList.add("question"),this.feedbackDiv=v(),this.feedbackDiv.classList.add("questionFeedback"),this.questionDiv.appendChild(this.feedbackDiv),this.feedbackDiv.innerHTML="awesome",this.debug&&"src_line"in this.src){let i=v();i.classList.add("debugInfo"),i.innerHTML="Source code: lines "+this.src.src_line+"..",this.questionDiv.appendChild(i)}if(this.titleDiv=v(),this.questionDiv.appendChild(this.titleDiv),this.titleDiv.classList.add("questionTitle"),this.titleDiv.innerHTML=this.src.title,this.src.error.length>0){let i=f(this.src.error);this.questionDiv.appendChild(i),i.style.color="red";return}for(let i of this.src.text.children)this.questionDiv.appendChild(this.generateText(i));let e=v();this.questionDiv.appendChild(e),e.classList.add("buttonRow");let t=Object.keys(this.expected).length>0;t&&(this.checkAndRepeatBtn=U(),e.appendChild(this.checkAndRepeatBtn),this.checkAndRepeatBtn.innerHTML=D);let s=f("&nbsp;&nbsp;&nbsp;");if(e.appendChild(s),this.feedbackSpan=f(""),e.appendChild(this.feedbackSpan),this.debug){if(this.src.variables.length>0){let h=v();h.classList.add("debugInfo"),h.innerHTML="Variables generated by Python Code",this.questionDiv.appendChild(h);let l=v();l.classList.add("debugCode"),this.questionDiv.appendChild(l);let n=this.getCurrentInstance(),o="",m=[...this.src.variables];m.sort();for(let p of m){let c=n[p].type,d=n[p].value;switch(c){case"vector":d="["+d+"]";break;case"set":d="{"+d+"}";break}o+=c+" "+p+" = "+d+"<br/>"}l.innerHTML=o}let i=["python_src_html","text_src_html"],a=["Python Source Code","Text Source Code"];for(let h=0;h<i.length;h++){let l=i[h];if(l in this.src&&this.src[l].length>0){let n=v();n.classList.add("debugInfo"),n.innerHTML=a[h],this.questionDiv.appendChild(n);let o=v();o.classList.add("debugCode"),this.questionDiv.append(o),o.innerHTML=this.src[l]}}}t&&this.checkAndRepeatBtn.addEventListener("click",()=>{this.state==k.passed?(this.state=k.init,this.reset(),this.populateDom()):J(this)})}generateMathString(e){let t="";switch(e.type){case"math":case"display-math":for(let s of e.children)t+=this.generateMathString(s);break;case"text":return e.data;case"var":{let s=this.getCurrentInstance(),i=s[e.data].type,a=s[e.data].value;switch(i){case"vector":return"\\left["+a+"\\right]";case"set":return"\\left\\{"+a+"\\right\\}";case"complex":{let h=a.split(","),l=parseFloat(h[0]),n=parseFloat(h[1]),o="";return Math.abs(l)>1e-9&&(o+=l),Math.abs(n)>1e-9&&(o+=(n<0?"-":"+")+n+"i"),o}case"matrix":{let h=new b(0,0);return h.fromString(a),t=h.toTeXString(e.data.includes("augmented")),t}case"term":{try{t=g.parse(a).toTexString()}catch{}break}default:t=a}}}return t}validateTermInput(e){let t=!0,s=e.value;if(s.length>0)try{g.parse(s)}catch{t=!1}e.style.color=t?"black":"maroon"}generateText(e,t=!1){switch(e.type){case"paragraph":case"span":{let s=document.createElement(e.type=="span"||t?"span":"p");for(let i of e.children)s.appendChild(this.generateText(i));return s}case"text":return f(e.data);case"code":{let s=f(e.data);return s.classList.add("code"),s}case"italic":case"bold":{let s=f("");return s.append(...e.children.map(i=>this.generateText(i))),e.type==="bold"?s.style.fontWeight="bold":s.style.fontStyle="italic",s}case"math":case"display-math":{let s=this.generateMathString(e);return M(s,e.type==="display-math")}case"gap":{let s=f(""),i=Math.max(e.data.length*14,24),a=L(i),h="gap-"+this.gapIdx;return this.gapInputs[h]=a,this.expected[h]=e.data,this.types[h]="string",a.addEventListener("keyup",()=>{this.editedQuestion(),a.value=a.value.toUpperCase(),this.student[h]=a.value.trim()}),this.showSolution&&(this.student[h]=a.value=this.expected[h]),this.gapIdx++,s.appendChild(a),s}case"input":case"input2":{let s=e.type==="input2",i=f("");i.style.verticalAlign="text-bottom";let a=e.data,h=this.getCurrentInstance()[a];if(this.expected[a]=h.value,this.types[a]=h.type,!s)switch(h.type){case"set":i.append(M("\\{"),f(" "));break;case"vector":i.append(M("["),f(" "));break}if(h.type==="vector"||h.type==="set"){let l=h.value.split(","),n=l.length;for(let o=0;o<n;o++){o>0&&i.appendChild(f(" , "));let m=a+"-"+o;new y(i,this,m,l[o].length,l[o],!1)}}else if(h.type==="matrix"){let l=v();i.appendChild(l),new I(l,this,a,h.value)}else if(h.type==="complex"){let l=h.value.split(",");new y(i,this,a+"-0",l[0].length,l[0],!1),i.append(f(" "),M("+"),f(" ")),new y(i,this,a+"-1",l[1].length,l[1],!1),i.append(f(" "),M("i"))}else{let l=h.type==="int";new y(i,this,a,h.value.length,h.value,l)}if(!s)switch(h.type){case"set":i.append(f(" "),M("\\}"));break;case"vector":i.append(f(" "),M("]"));break}return i}case"itemize":return Q(e.children.map(s=>N(this.generateText(s))));case"single-choice":case"multi-choice":{let s=e.type=="multi-choice",i=document.createElement("table"),a=e.children.length,h=this.debug==!1,l=R(a,h),n=s?q:Y,o=s?K:X,m=[],p=[];for(let c=0;c<a;c++){let d=l[c],w=e.children[d],x="mc-"+this.choiceIdx+"-"+d;p.push(x);let C=w.children[0].type=="bool"?w.children[0].data:this.getCurrentInstance()[w.children[0].data].value;this.expected[x]=C,this.types[x]="bool",this.student[x]=this.showSolution?C:"false";let H=this.generateText(w.children[1],!0),S=document.createElement("tr");i.appendChild(S),S.style.cursor="pointer";let E=document.createElement("td");m.push(E),S.appendChild(E),E.innerHTML=this.student[x]=="true"?n:o;let V=document.createElement("td");S.appendChild(V),V.appendChild(H),s?S.addEventListener("click",()=>{this.editedQuestion(),this.student[x]=this.student[x]==="true"?"false":"true",this.student[x]==="true"?E.innerHTML=n:E.innerHTML=o}):S.addEventListener("click",()=>{this.editedQuestion();for(let T of p)this.student[T]="false";this.student[x]="true";for(let T=0;T<p.length;T++){let z=l[T];m[z].innerHTML=this.student[p[z]]=="true"?n:o}})}return this.choiceIdx++,i}default:{let s=f("UNIMPLEMENTED("+e.type+")");return s.style.color="red",s}}}};function ae(r,e){["en","de","es","it","fr"].includes(r.lang)==!1&&(r.lang="en"),e&&(document.getElementById("debug").style.display="block"),document.getElementById("date").innerHTML=new Date().toISOString().split("T")[0],document.getElementById("title").innerHTML=r.title,document.getElementById("author").innerHTML=r.author,document.getElementById("courseInfo1").innerHTML=W[r.lang];let t='<span onclick="location.reload()" style="text-decoration: underline; font-weight: bold; cursor: pointer">'+O[r.lang]+"</span>";document.getElementById("courseInfo2").innerHTML=F[r.lang].replace("*",t);let s=[],i=document.getElementById("questions"),a=1;for(let h of r.questions){h.title=""+a+". "+h.title;let l=v();i.appendChild(l);let n=new A(l,h,r.lang,e);n.showSolution=e,s.push(n),n.populateDom(),e&&h.error.length==0&&n.checkAndRepeatBtn.click(),a++}}return ne(le);})();sell.init(quizSrc,debug);</script></body> </html>
"""
# @end(html)
html = html.replace("\\", "\\\\")


if __name__ == "__main__":

    # get input and output path
    if len(sys.argv) < 2:
        print("usage: python sell.py [-J] INPUT_PATH.txt")
        print("   option -J enables to output a JSON file for debugging purposes")
        exit(-1)
    debug = "-J" in sys.argv
    input_path = sys.argv[-1]
    output_path = input_path.replace(".txt", ".html")
    output_debug_path = input_path.replace(".txt", "_DEBUG.html")
    output_json_path = input_path.replace(".txt", ".json")
    if os.path.isfile(input_path) == False:
        print("error: input file path does not exist")
        exit(-1)

    # read input
    f = open(input_path)
    src = f.read()
    f.close()

    # compile
    out = compile(src)
    output_debug_json = json.dumps(out)
    output_debug_json_formatted = json.dumps(out, indent=2)
    for question in out["questions"]:
        del question["src_line"]
        del question["text_src_html"]
        del question["python_src_html"]
        del question["python_src_tokens"]
    output_json = json.dumps(out)

    # write test output
    if debug:
        f = open(output_json_path, "w")
        f.write(output_debug_json_formatted)
        f.close()

    # write html
    # (a) debug version (*_DEBUG.html)
    f = open(output_debug_path, "w")
    f.write(
        html.replace(
            "let quizSrc = {};", "let quizSrc = " + output_debug_json + ";"
        ).replace("let debug = false;", "let debug = true;")
    )
    f.close()
    # (b) release version (*.html)
    f = open(output_path, "w")
    f.write(html.replace("let quizSrc = {};", "let quizSrc = " + output_json + ";"))
    f.close()

    # exit normally
    sys.exit(0)
