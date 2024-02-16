#!/usr/bin/env python3

"""SELL - Simple E-Learning Language
AUTHOR:  Andreas Schwenk <mailto:contact@compiler-construction.com>
LICENSE: GPLv3
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

    def __init__(self):
        self.title = ""
        self.python_src = ""
        self.variables = set()
        self.instances = []
        self.text_src = ""
        self.text = None
        self.error = ""
        self.python_src_tokens = set()

    def build(self):
        if len(self.python_src) > 0:
            self.analyze_python_code()
            instances_str = []
            for i in range(0, 5):
                # try to generate instances distinct to prior once
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
                html += self.red_colored_span("-") + line[1:].replace(" ", "&nbsp;")
            elif line.startswith("["):
                l1 = line.split("]")[0] + "]".replace(" ", "&nbsp;")
                l2 = "]".join(line.split("]")[1:]).replace(" ", "&nbsp;")
                html += self.red_colored_span(l1) + l2
            elif line.startswith("("):
                l1 = line.split(")")[0] + ")".replace(" ", "&nbsp;")
                l2 = ")".join(line.split(")")[1:]).replace(" ", "&nbsp;")
                html += self.red_colored_span(l1) + l2
            else:
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
                    html += lex.token
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
    for line in lines:
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
            question = Question()
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
html = """<!DOCTYPE html> <html> <head> <meta charset="UTF-8" /> <title>pySELL</title> <meta name="viewport" content="width=device-width, initial-scale=1.0" /> <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css" integrity="sha384-n8MVd4RsNIU0tAv4ct0nTaAbDJwPJzDEaqSD1odI+WdtXRGWt2kTvGFasHpSy3SV" crossorigin="anonymous" /> <script src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js" integrity="sha384-XjKyOOlGwcjNTAIQHIpgOno0Hl1YQqzUOEleOLALmuqehneUG+vnGctmUb0ZY0l8" crossorigin="anonymous" ></script> <style> html { font-family: Arial, Helvetica, sans-serif; } body { max-width: 1024px; margin-left: auto; margin-right: auto; padding-left: 5px; padding-right: 5px; } h1 { text-align: center; font-size: 28pt; } .author { text-align: center; font-size: 18pt; } .courseInfo { font-size: 14pt; font-style: italic; /*margin-bottom: 24px;*/ text-align: center; } .question { color: black; background-color: white; border-style: solid; border-radius: 5px; border-width: 3px; border-color: black; padding: 8px; margin-top: 20px; margin-bottom: 20px; -webkit-box-shadow: 4px 6px 8px -1px rgba(0, 0, 0, 0.93); box-shadow: 4px 6px 8px -1px rgba(0, 0, 0, 0.1); } .questionTitle { font-size: 24pt; } .code { font-family: "Courier New", Courier, monospace; color: black; background-color: rgb(235, 235, 235); padding: 2px 5px; border-radius: 5px; margin: 1px 2px; } .debugCode { font-family: "Courier New", Courier, monospace; padding: 4px; margin-bottom: 5px; background-color: black; color: white; border-radius: 5px; opacity: 0.85; overflow-x: scroll; } .debugInfo { text-align: center; font-size: 8pt; margin-top: 2px; } ul { margin-top: 0; margin-left: 0px; padding-left: 20px; } .inputField { width: 32px; height: 24px; font-size: 14pt; border-style: solid; border-color: black; border-radius: 5px; border-width: 0.2; padding-left: 5px; padding-right: 5px; outline-color: black; background-color: transparent; margin: 1px; } .inputField:focus { outline-color: maroon; } .button { padding-left: 8px; padding-right: 8px; padding-top: 5px; padding-bottom: 5px; font-size: 12pt; /*background-color: rgba(62, 146, 3, 0.767);*/ background-color: green; color: white; border-style: none; border-radius: 4px; height: 36px; cursor: pointer; } .buttonRow { display: flex; align-items: baseline; margin-top: 12px; } .matrixResizeButton { width: 20px; background-color: black; color: #fff; text-align: center; border-radius: 3px; position: absolute; z-index: 1; height: 20px; cursor: pointer; margin-bottom: 3px; } a { color: black; text-decoration: underline; } </style> </head> <body> <h1 id="title"></h1> <div class="author" id="author"></div> <p id="courseInfo1" class="courseInfo"></p> <p id="courseInfo2" class="courseInfo"></p> <h1 id="debug" class="debugCode" style="display: none">DEBUG VERSION</h1> <div id="questions"></div> <p style="font-size: 8pt; font-style: italic; text-align: center"> This quiz was created using <a href="https://github.com/andreas-schwenk/pysell">pySELL</a>, the <i>Python-based Simple E-Learning Language</i>, written by Andreas Schwenk, GPLv3<br /> last update on <span id="date"></span> </p> <script>let debug = false; let quizSrc = {};var sell=(()=>{var P=Object.defineProperty;var ee=Object.getOwnPropertyDescriptor;var te=Object.getOwnPropertyNames;var se=Object.prototype.hasOwnProperty;var ie=(l,e)=>{for(var t in e)P(l,t,{get:e[t],enumerable:!0})},ne=(l,e,t,i)=>{if(e&&typeof e=="object"||typeof e=="function")for(let s of te(e))!se.call(l,s)&&s!==t&&P(l,s,{get:()=>e[s],enumerable:!(i=ee(e,s))||i.enumerable});return l};var re=l=>ne(P({},"__esModule",{value:!0}),l);var ae={};ie(ae,{init:()=>le});var V={de:"Diese Seite wird in Ihrem Browser ausgef\xFChrt und speichert keine Daten auf Servern.",en:"This page runs in your browser and does not store any data on servers."},N={de:"Sie k\xF6nnen diese Seite *, um neue randomisierte Aufgaben zu erhalten.",en:"You can * this page in order to get new randomized tasks."},_={de:"aktualisieren",en:"reload"};function M(l=[]){let e=document.createElement("div");return e.append(...l),e}function R(l=[]){let e=document.createElement("ul");return e.append(...l),e}function W(l){let e=document.createElement("li");return e.appendChild(l),e}function D(l){let e=document.createElement("input");return e.spellcheck=!1,e.type="text",e.classList.add("inputField"),e.style.width=l+"px",e}function j(){let l=document.createElement("button");return l.type="button",l.classList.add("button"),l}function v(l,e=[]){let t=document.createElement("span");return e.length>0?t.append(...e):t.innerHTML=l,t}function E(l,e=!1){let t=document.createElement("span");return katex.render(l,t,{throwOnError:!1,displayMode:e,macros:{"\\RR":"\\mathbb{R}","\\NN":"\\mathbb{N}","\\QQ":"\\mathbb{Q}","\\ZZ":"\\mathbb{Z}"}}),t}var O='<svg xmlns="http://www.w3.org/2000/svg" height="28" viewBox="0 0 448 512"><path d="M384 80c8.8 0 16 7.2 16 16V416c0 8.8-7.2 16-16 16H64c-8.8 0-16-7.2-16-16V96c0-8.8 7.2-16 16-16H384zM64 32C28.7 32 0 60.7 0 96V416c0 35.3 28.7 64 64 64H384c35.3 0 64-28.7 64-64V96c0-35.3-28.7-64-64-64H64z"/></svg>',Z='<svg xmlns="http://www.w3.org/2000/svg" height="28" viewBox="0 0 448 512"><path d="M64 80c-8.8 0-16 7.2-16 16V416c0 8.8 7.2 16 16 16H384c8.8 0 16-7.2 16-16V96c0-8.8-7.2-16-16-16H64zM0 96C0 60.7 28.7 32 64 32H384c35.3 0 64 28.7 64 64V416c0 35.3-28.7 64-64 64H64c-35.3 0-64-28.7-64-64V96zM337 209L209 337c-9.4 9.4-24.6 9.4-33.9 0l-64-64c-9.4-9.4-9.4-24.6 0-33.9s24.6-9.4 33.9 0l47 47L303 175c9.4-9.4 24.6-9.4 33.9 0s9.4 24.6 0 33.9z"/>',Q='<svg xmlns="http://www.w3.org/2000/svg" height="28" viewBox="0 0 512 512"><path d="M464 256A208 208 0 1 0 48 256a208 208 0 1 0 416 0zM0 256a256 256 0 1 1 512 0A256 256 0 1 1 0 256z"/></svg>',X='<svg xmlns="http://www.w3.org/2000/svg" height="28" viewBox="0 0 512 512"><path d="M256 48a208 208 0 1 1 0 416 208 208 0 1 1 0-416zm0 464A256 256 0 1 0 256 0a256 256 0 1 0 0 512zM369 209c9.4-9.4 9.4-24.6 0-33.9s-24.6-9.4-33.9 0l-111 111-47-47c-9.4-9.4-24.6-9.4-33.9 0s-9.4 24.6 0 33.9l64 64c9.4 9.4 24.6 9.4 33.9 0L369 209z"/></svg>',Y='<svg xmlns="http://www.w3.org/2000/svg" height="25" viewBox="0 0 384 512" fill="white"><path d="M73 39c-14.8-9.1-33.4-9.4-48.5-.9S0 62.6 0 80V432c0 17.4 9.4 33.4 24.5 41.9s33.7 8.1 48.5-.9L361 297c14.3-8.7 23-24.2 23-41s-8.7-32.2-23-41L73 39z"/></svg>';function K(l){let e=new Array(l);for(let t=0;t<l;t++)e[t]=t;return e}function $(l){let e=new Array(l);for(let t=0;t<l;t++)e[t]=t;for(let t=0;t<l;t++){let i=Math.floor(Math.random()*l),s=Math.floor(Math.random()*l),n=e[i];e[i]=e[s],e[s]=n}return e}var T=class l{constructor(e,t){this.m=e,this.n=t,this.v=new Array(e*t).fill("0")}getElement(e,t){return e<0||e>=this.m||t<0||t>=this.n?"0":this.v[e*this.n+t]}resize(e,t,i){if(e<1||e>50||t<1||t>50)return!1;let s=new l(e,t);s.v.fill(i);for(let n=0;n<s.m;n++)for(let r=0;r<s.n;r++)s.v[n*s.n+r]=this.getElement(n,r);return this.fromMatrix(s),!0}fromMatrix(e){this.m=e.m,this.n=e.n,this.v=[...e.v]}fromString(e){this.m=e.split("],").length,this.v=e.replaceAll("[","").replaceAll("]","").split(",").map(t=>t.trim()),this.n=this.v.length/this.m}getMaxCellStrlen(){let e=0;for(let t of this.v)t.length>e&&(e=t.length);return e}toTeX(e=!1){let t=e?"\\left[\\begin{array}":"\\begin{bmatrix}";e&&(t+="{"+"c".repeat(this.n-1)+"|c}");for(let i=0;i<this.m;i++){for(let s=0;s<this.n;s++){s>0&&(t+="&");let n=this.getElement(i,s);t+=n}t+="\\\\"}return t+=e?"\\end{array}\\right]":"\\end{bmatrix}",t}},b=class{constructor(e,t){this.op=e,this.c=t}};function x(l){return parseFloat(l)}var L=class{constructor(){this.root=null,this.src="",this.token="",this.pos=0}getVars(e,t=null){t==null&&(t=this.root),t.op.startsWith("var:")&&e.add(t.op.substring(4));for(let i of t.c)this.getVars(e,i)}eval(e,t=null){switch(t==null&&(t=this.root),t.op){case"+":case"-":case"*":case"/":case"^":case"==":{let s=this.eval(e,t.c[0]).split(":"),n=this.eval(e,t.c[1]).split(":");switch(t.op){case"+":if(s[0]==="num"&&n[0]=="num")return"num:"+(x(s[1])+x(n[1]));break;case"-":if(s[0]==="num"&&n[0]=="num")return"num:"+(x(s[1])-x(n[1]));break;case"*":if(s[0]==="num"&&n[0]=="num")return"num:"+x(s[1])*x(n[1]);break;case"/":if(s[0]==="num"&&n[0]=="num")return"num:"+x(s[1])/x(n[1]);break;case"^":if(s[0]==="num"&&n[0]=="num")return"num:"+Math.pow(x(s[1]),x(n[1]));break;case"==":if(s[0]==="num"&&n[0]=="num")return"num:"+(Math.abs(x(s[1])-x(n[1]))<1e-9?1:0);break}let r="eval-error: "+s[0]+" "+t.op+" "+n[0];throw new Error(r)}case".-":case"sin":case"cos":case"tan":case"exp":case"ln":case"sqrt":{let s=this.eval(e,t.c[0]).split(":");switch(t.op){case".-":if(s[0]==="num")return"num:"+-x(s[1]);break;case"sin":if(s[0]==="num")return"num:"+Math.sin(x(s[1]));break;case"cos":if(s[0]==="num")return"num:"+Math.cos(x(s[1]));break;case"tan":if(s[0]==="num")return"num:"+Math.tan(x(s[1]));break;case"exp":if(s[0]==="num")return"num:"+Math.exp(x(s[1]));break;case"ln":if(s[0]==="num")return"num:"+Math.log(x(s[1]));break;case"sqrt":if(s[0]==="num")return"num:"+Math.sqrt(x(s[1]));break}let n="eval-error: "+t.op+"("+s[0]+")";throw new Error(n)}default:if(t.op.startsWith("num:"))return t.op;if(t.op.startsWith("var:")){let s=t.op.substring(4);if(s in e)return e[s];throw new Error("eval-error: unknown variable '"+s+"'")}throw new Error("UNIMPLEMENTED eval '"+t.op+"'")}}parse(e){if(this.src=e,this.token="",this.pos=0,this.next(),this.root=this.parseExpr(),this.token!=="")throw new Error("remaining tokens: "+this.token+"...")}parseExpr(){let e=this.parseMul();for(;["+","-"].includes(this.token);){let t=this.token;this.next(),e=new b(t,[e,this.parseMul()])}return e}parseMul(){let e=this.parsePow();for(;["*","/","("].includes(this.token)||this.token.length>0&&this.isAlpha(this.token[0]);){let t="*";["*","/"].includes(this.token)&&(t=this.token,this.next()),e=new b(t,[e,this.parsePow()])}return e}parsePow(){let e=this.parseUnary();if(["^"].includes(this.token)){let t=this.token;this.next(),e=new b(t,[e,this.parseUnary()])}return e}parseUnary(){return this.token==="-"?(this.next(),new b(".-",[this.parseMul()])):this.parseInfix()}parseInfix(){if(this.token.length==0)throw new Error("expected unary");if(this.isNum(this.token[0])){let e=this.token;return this.next(),this.token==="."&&(e+=".",this.next(),this.token.length>0&&(e+=this.token,this.next())),new b("num:"+e,[])}else if(["sin","cos","tan","exp","ln","sqrt"].includes(this.token)){let e=this.token;this.next();let t=!1;this.token==="("&&(t=!0,this.next());let i=new b(e,[t?this.parseExpr():this.parseMul()]);if(t)if(this.token===")")this.next();else throw Error("expected ')'");return i}else if(this.token==="("){this.next();let e=this.parseExpr();if(this.token+="",this.token===")")this.next();else throw Error("expected ')'");return e}else{if(this.token.toLowerCase()==="pi")return this.next(),new b("num:"+Math.PI,[]);if(this.token.toLowerCase()==="e")return this.next(),new b("num:"+Math.E,[]);if(this.isAlpha(this.token[0])){let e=this.token;return this.next(),new b("var:"+e,[])}else throw new Error("expected unary")}}compare(e){let i=new Set;this.getVars(i),e.getVars(i);for(let s=0;s<10;s++){let n={};for(let a of i)n[a]="num:"+Math.random();let r=new b("==",[this.root,e.root]);if(this.eval(n,r)==="num:0")return!1}return!0}next(){this.token="";let e=!1,t=this.src.length;for(;this.pos<t&&`	
 `.includes(this.src[this.pos]);)this.pos++;for(;!e&&this.pos<t;){let i=this.src[this.pos];if(this.token.length>0&&this.isNum(this.token[0])&&this.isAlpha(i))return;if(`^%#*$()[]{},.:;+-*/_!<>=?	
 `.includes(i)){if(this.token.length>0)return;e=!0}`	
 `.includes(i)==!1&&(this.token+=i),["x","y","z","t"].includes(this.token)&&(e=!0),this.pos++}}isNum(e){return e.charCodeAt(0)>=48&&e.charCodeAt(0)<=57}isAlpha(e){return e.charCodeAt(0)>=65&&e.charCodeAt(0)<=90||e.charCodeAt(0)>=97&&e.charCodeAt(0)<=122||e==="_"}};var H=class{constructor(e,t=!1){this.src=e,this.debug=t,this.instanceIdx=Math.floor(Math.random()*e.instances.length),this.choiceIdx=0,this.gapIdx=0,this.expected={},this.types={},this.student={},this.inputs={},this.qDiv=null,this.titleDiv=null,this.checkBtn=null,this.showSolution=!1}populateDom(e){if(this.qDiv=M(),e.appendChild(this.qDiv),this.qDiv.classList.add("question"),this.titleDiv=M(),this.qDiv.appendChild(this.titleDiv),this.titleDiv.classList.add("questionTitle"),this.titleDiv.innerHTML=this.src.title,this.src.error.length>0){let r=v(this.src.error);this.qDiv.appendChild(r),r.style.color="red";return}for(let r of this.src.text.children)this.qDiv.appendChild(this.generateText(r));let t=M();this.qDiv.appendChild(t),t.classList.add("buttonRow");let i=Object.keys(this.expected).length>0;i&&(this.checkBtn=j(),t.appendChild(this.checkBtn),this.checkBtn.innerHTML=Y);let s=v("&nbsp;&nbsp;&nbsp;");t.appendChild(s);let n=v("");if(t.appendChild(n),this.debug){if(this.src.variables.length>0){let a=M();a.classList.add("debugInfo"),a.innerHTML="Variables generated by Python Code",this.qDiv.appendChild(a);let p=M();p.classList.add("debugCode"),this.qDiv.appendChild(p);let u=this.src.instances[this.instanceIdx],f="",h=[...this.src.variables];h.sort();for(let c of h){let d=u[c].type,m=u[c].value;switch(d){case"vector":m="["+m+"]";break;case"set":m="{"+m+"}";break}f+=d+" "+c+" = "+m+"<br/>"}p.innerHTML=f}let r=["python_src_html","text_src_html"],o=["Python Source Code","Text Source Code"];for(let a=0;a<r.length;a++){let p=r[a];if(p in this.src&&this.src[p].length>0){let u=M();u.classList.add("debugInfo"),u.innerHTML=o[a],this.qDiv.appendChild(u);let f=M();f.classList.add("debugCode"),this.qDiv.append(f),f.innerHTML=this.src[p]}}}i&&this.checkBtn.addEventListener("click",()=>{n.innerHTML="";let r=0,o=0;for(let a in this.expected){let p=this.types[a],u=this.student[a],f=this.expected[a];switch(p){case"bool":u===f&&o++;break;case"string":{let h=this.inputs[a],c=u.trim().toUpperCase(),d=f.trim().toUpperCase(),m=c===d;m&&o++,h.style.color=m?"black":"white",h.style.backgroundColor=m?"transparent":"red";break}case"int":case"float":Math.abs(parseFloat(u)-parseFloat(f))<1e-9&&o++;break;case"term":{try{let h=new L;h.parse(f);let c=new L;c.parse(u),h.compare(c)&&o++}catch(h){this.debug&&console.log(h)}break}case"vector":case"complex":case"set":{f=f.split(","),r+=f.length-1,u=[];for(let h=0;h<f.length;h++)u.push(this.student[a+"-"+h]);if(p==="set")for(let h=0;h<f.length;h++){let c=parseFloat(f[h]);for(let d=0;d<u.length;d++){let m=parseFloat(u[d]);if(Math.abs(m-c)<1e-9){o++;break}}}else for(let h=0;h<f.length;h++){let c=parseFloat(u[h]),d=parseFloat(f[h]);Math.abs(c-d)<1e-9&&o++}break}case"matrix":{let h=new T(0,0);h.fromString(f),r+=h.m*h.n-1;for(let c=0;c<h.m;c++)for(let d=0;d<h.n;d++){let m=c*h.n+d;u=this.student[a+"-"+m];let I=h.v[m];try{let w=new L;w.parse(I);let y=new L;y.parse(u),w.compare(y)&&o++}catch(w){this.debug&&console.log(w)}}break}default:n.innerHTML="UNIMPLEMENTED EVAL OF TYPE "+p}r++}o==r?(n.style.color=this.titleDiv.style.color=this.checkBtn.style.backgroundColor=this.qDiv.style.borderColor="rgb(0,150,0)",this.qDiv.style.backgroundColor="rgba(0,150,0, 0.025)"):(this.titleDiv.style.color=n.style.color=this.checkBtn.style.backgroundColor=this.qDiv.style.borderColor="rgb(150,0,0)",this.qDiv.style.backgroundColor="rgba(150,0,0, 0.025)",r>=5&&(n.innerHTML=""+o+" / "+r))})}generateMathString(e){let t="";switch(e.type){case"math":case"display-math":for(let i of e.children)t+=this.generateMathString(i);break;case"text":return e.data;case"var":{let i=this.src.instances[this.instanceIdx],s=i[e.data].type,n=i[e.data].value;switch(s){case"vector":return"\\left["+n+"\\right]";case"set":return"\\left\\{"+n+"\\right\\}";case"complex":{let r=n.split(","),o=parseFloat(r[0]),a=parseFloat(r[1]),p="";return Math.abs(o)>1e-9&&(p+=o),Math.abs(a)>1e-9&&(p+=(a<0?"-":"+")+a+"i"),p}case"matrix":{let r=new T(0,0);return r.fromString(n),t=r.toTeX(e.data.includes("augmented")),t}case"term":{t=n.replaceAll("sin","\\sin").replaceAll("cos","\\cos").replaceAll("tan","\\tan").replaceAll("exp","\\exp").replaceAll("ln","\\ln").replaceAll("*","\\cdot ").replaceAll("(","\\left(").replaceAll(")","\\right)");break}default:t=n}}}return t}generateMatrixParenthesis(e,t){let i=document.createElement("td");i.style.width="3px";for(let s of["Top",e?"Left":"Right","Bottom"])i.style["border"+s+"Width"]="2px",i.style["border"+s+"Style"]="solid";return i.rowSpan=t,i}validateTermInput(e){let t=new L,i=!0,s=e.value;if(s.length>0)try{t.parse(s)}catch{i=!1}e.style.color=i?"black":"maroon"}generateText(e,t=!1){switch(e.type){case"paragraph":case"span":{let i=document.createElement(e.type=="span"||t?"span":"p");for(let s of e.children)i.appendChild(this.generateText(s));return i}case"text":return v(e.data);case"code":{let i=v(e.data);return i.classList.add("code"),i}case"italic":case"bold":{let i=v("");return i.append(...e.children.map(s=>this.generateText(s))),e.type==="bold"?i.style.fontWeight="bold":i.style.fontStyle="italic",i}case"math":case"display-math":{let i=this.generateMathString(e);return E(i,e.type==="display-math")}case"gap":{let i=v(""),s=Math.max(e.data.length*12,24),n=D(s),r="gap-"+this.gapIdx;return this.inputs[r]=n,this.expected[r]=e.data,this.types[r]="string",n.addEventListener("keyup",()=>{this.student[r]=n.value.trim()}),this.showSolution&&(this.student[r]=n.value=this.expected[r]),this.gapIdx++,i.appendChild(n),i}case"input":case"input2":{let i=e.type==="input2",s=v("");s.style.verticalAlign="text-bottom";let n=e.data,r=this.src.instances[this.instanceIdx][n];if(this.expected[n]=r.value,this.types[n]=r.type,!i)switch(r.type){case"set":s.append(E("\\{"),v(" "));break;case"vector":s.append(E("["),v(" "));break}if(r.type==="vector"||r.type==="set"){let o=r.value.split(","),a=o.length;for(let p=0;p<a;p++){p>0&&s.appendChild(v(" , "));let u=D(Math.max(o[p].length*12,24));s.appendChild(u),u.addEventListener("keyup",()=>{this.student[n+"-"+p]=u.value.trim(),this.validateTermInput(u)}),this.showSolution&&(this.student[n+"-"+p]=u.value=o[p])}}else if(r.type==="matrix"){let o=(f,h,c)=>{let d=M();f.innerHTML="",f.appendChild(d),d.style.position="relative",d.style.display="inline-block";let m=document.createElement("table");d.appendChild(m);let I=h.getMaxCellStrlen();I=Math.max(I*12,24);for(let g=0;g<c.m;g++){let k=document.createElement("tr");m.appendChild(k),g==0&&k.appendChild(this.generateMatrixParenthesis(!0,c.m));for(let q=0;q<c.n;q++){let z=g*c.n+q,F=document.createElement("td");k.appendChild(F);let A=D(I);A.style.textAlign="end",F.appendChild(A),A.addEventListener("keyup",()=>{this.student[n+"-"+z]=A.value.trim(),this.validateTermInput(A)}),this.showSolution&&(this.student[n+"-"+z]=A.value=""+c.v[z])}g==0&&k.appendChild(this.generateMatrixParenthesis(!1,c.m))}let w=["+","-","+","-"],y=[0,0,1,-1],B=[1,-1,0,0],C=[0,22,888,888],S=[888,888,-22,-22],U=[-22,-22,0,22],G=[h.n!=1,h.n!=1,h.m!=1,h.m!=1],J=[c.n>=10,c.n<=1,c.m>=10,c.m<=1];for(let g=0;g<4;g++){if(G[g]==!1)continue;let k=v(w[g]);C[g]!=888&&(k.style.top=""+C[g]+"px"),S[g]!=888&&(k.style.bottom=""+S[g]+"px"),U[g]!=888&&(k.style.right=""+U[g]+"px"),k.classList.add("matrixResizeButton"),d.appendChild(k),J[g]?k.style.opacity="0.5":k.addEventListener("click",()=>{c.resize(c.m+y[g],c.n+B[g],"0"),o(f,h,c)})}},a=new T(0,0);a.fromString(r.value);let p=new T(a.m==1?1:3,a.n==1?1:3);this.showSolution&&p.fromMatrix(a);let u=M();s.appendChild(u),o(u,a,p)}else if(r.type==="complex"){let o=r.value.split(",");for(let a=0;a<2;a++){let p=D(Math.max(Math.max(o[a].length*12,24),24));s.appendChild(p),this.showSolution&&(this.student[n+"-"+a]=p.value=o[a]),p.addEventListener("keyup",()=>{this.student[n+"-"+a]=p.value.trim(),this.validateTermInput(p)}),a==0?s.append(v(" "),E("+"),v(" ")):s.append(v(" "),E("i"))}}else{let o=D(Math.max(r.value.length*12,24));s.appendChild(o),o.addEventListener("keyup",()=>{this.student[n]=o.value.trim(),this.validateTermInput(o)}),this.showSolution&&(this.student[n]=o.value=r.value)}if(!i)switch(r.type){case"set":s.append(v(" "),E("\\}"));break;case"vector":s.append(v(" "),E("]"));break}return s}case"itemize":return R(e.children.map(i=>W(this.generateText(i))));case"single-choice":case"multi-choice":{let i=e.type=="multi-choice",s=document.createElement("table"),n=e.children.length,r=this.debug?K(n):$(n),o=i?Z:X,a=i?O:Q,p=[],u=[];for(let f=0;f<n;f++){let h=r[f],c=e.children[h],d="mc-"+this.choiceIdx+"-"+h;u.push(d);let m=c.children[0].type=="bool"?c.children[0].data:this.src.instances[this.instanceIdx][c.children[0].data].value;this.expected[d]=m,this.types[d]="bool",this.student[d]=this.showSolution?m:"false";let I=this.generateText(c.children[1],!0),w=document.createElement("tr");s.appendChild(w),w.style.cursor="pointer";let y=document.createElement("td");p.push(y),w.appendChild(y),y.innerHTML=this.student[d]=="true"?o:a;let B=document.createElement("td");w.appendChild(B),B.appendChild(I),i?w.addEventListener("click",()=>{this.student[d]=this.student[d]==="true"?"false":"true",this.student[d]==="true"?y.innerHTML=o:y.innerHTML=a}):w.addEventListener("click",()=>{for(let C of u)this.student[C]="false";this.student[d]="true";for(let C=0;C<u.length;C++){let S=r[C];p[S].innerHTML=this.student[u[S]]=="true"?o:a}})}return this.choiceIdx++,s}default:{let i=v("UNIMPLEMENTED("+e.type+")");return i.style.color="red",i}}}};function le(l,e){e&&(document.getElementById("debug").style.display="block"),document.getElementById("date").innerHTML=new Date().toISOString().split("T")[0],document.getElementById("title").innerHTML=l.title,document.getElementById("author").innerHTML=l.author,document.getElementById("courseInfo1").innerHTML=V[l.lang];let t='<span onclick="location.reload()" style="text-decoration: underline; font-weight: bold; cursor: pointer">'+_[l.lang]+"</span>";document.getElementById("courseInfo2").innerHTML=N[l.lang].replace("*",t);let i=[],s=document.getElementById("questions"),n=1;for(let r of l.questions){r.title=""+n+". "+r.title;let o=new H(r,e);o.showSolution=e,i.push(o),o.populateDom(s),e&&r.error.length==0&&o.checkBtn.click(),n++}}return re(ae);})();sell.init(quizSrc,debug);</script> </html>  
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
