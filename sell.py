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
html = """<!DOCTYPE html> <html> <head> <meta charset="UTF-8" /> <title>pySELL</title> <meta name="viewport" content="width=device-width, initial-scale=1.0" /> <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css" integrity="sha384-n8MVd4RsNIU0tAv4ct0nTaAbDJwPJzDEaqSD1odI+WdtXRGWt2kTvGFasHpSy3SV" crossorigin="anonymous" /> <script src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js" integrity="sha384-XjKyOOlGwcjNTAIQHIpgOno0Hl1YQqzUOEleOLALmuqehneUG+vnGctmUb0ZY0l8" crossorigin="anonymous" ></script> <style> html { font-family: Arial, Helvetica, sans-serif; } body { max-width: 1024px; margin-left: auto; margin-right: auto; padding-left: 5px; padding-right: 5px; } h1 { text-align: center; font-size: 28pt; } .author { text-align: center; font-size: 18pt; } .courseInfo { font-size: 14pt; font-style: italic; /*margin-bottom: 24px;*/ text-align: center; } .question { color: black; background-color: white; border-style: solid; border-radius: 5px; border-width: 3px; border-color: black; padding: 8px; margin-top: 20px; margin-bottom: 20px; -webkit-box-shadow: 4px 6px 8px -1px rgba(0, 0, 0, 0.93); box-shadow: 4px 6px 8px -1px rgba(0, 0, 0, 0.1); } .questionTitle { font-size: 24pt; } .code { font-family: "Courier New", Courier, monospace; color: black; background-color: rgb(235, 235, 235); padding: 2px 5px; border-radius: 5px; margin: 1px 2px; } .debugCode { font-family: "Courier New", Courier, monospace; padding: 4px; margin-bottom: 5px; background-color: black; color: white; border-radius: 5px; opacity: 0.85; overflow-x: scroll; } .debugInfo { text-align: center; font-size: 8pt; margin-top: 2px; } ul { margin-top: 0; margin-left: 0px; padding-left: 20px; } .inputField { width: 32px; height: 24px; font-size: 14pt; border-style: solid; border-color: black; border-radius: 5px; border-width: 0.2; padding-left: 5px; padding-right: 5px; outline-color: black; background-color: transparent; margin: 1px; } .inputField:focus { outline-color: maroon; } .button { padding-left: 8px; padding-right: 8px; padding-top: 5px; padding-bottom: 5px; font-size: 12pt; /*background-color: rgba(62, 146, 3, 0.767);*/ background-color: green; color: white; border-style: none; border-radius: 4px; height: 36px; cursor: pointer; } .buttonRow { display: flex; align-items: baseline; margin-top: 12px; } .matrixResizeButton { width: 20px; background-color: black; color: #fff; text-align: center; border-radius: 3px; position: absolute; z-index: 1; height: 20px; cursor: pointer; margin-bottom: 3px; } a { color: black; text-decoration: underline; } </style> </head> <body> <h1 id="title"></h1> <div class="author" id="author"></div> <p id="courseInfo1" class="courseInfo"></p> <p id="courseInfo2" class="courseInfo"></p> <h1 id="debug" class="debugCode" style="display: none">DEBUG VERSION</h1> <div id="questions"></div> <p style="font-size: 8pt; font-style: italic; text-align: center"> This quiz was created using <a href="https://github.com/andreas-schwenk/pysell">pySELL</a>, the <i>Python-based Simple E-Learning Language</i>, written by Andreas Schwenk, GPLv3<br /> last update on <span id="date"></span> </p> <script>let debug = false; let quizSrc = {};var sell=(()=>{var z=Object.defineProperty;var G=Object.getOwnPropertyDescriptor;var J=Object.getOwnPropertyNames;var ee=Object.prototype.hasOwnProperty;var te=(h,e)=>{for(var t in e)z(h,t,{get:e[t],enumerable:!0})},ie=(h,e,t,r)=>{if(e&&typeof e=="object"||typeof e=="function")for(let s of J(e))!ee.call(h,s)&&s!==t&&z(h,s,{get:()=>e[s],enumerable:!(r=G(e,s))||r.enumerable});return h};var se=h=>ie(z({},"__esModule",{value:!0}),h);var ae={};te(ae,{init:()=>ne});var U={en:"This page runs in your browser and does not store any data on servers.",de:"Diese Seite wird in Ihrem Browser ausgef\xFChrt und speichert keine Daten auf Servern.",es:"Esta p\xE1gina se ejecuta en su navegador y no almacena ning\xFAn dato en los servidores.",it:"Questa pagina viene eseguita nel browser e non memorizza alcun dato sui server.",fr:"Cette page fonctionne dans votre navigateur et ne stocke aucune donn\xE9e sur des serveurs."},V={en:"You can * this page in order to get new randomized tasks.",de:"Sie k\xF6nnen diese Seite *, um neue randomisierte Aufgaben zu erhalten.",es:"Puedes * esta p\xE1gina para obtener nuevas tareas aleatorias.",it:"\xC8 possibile * questa pagina per ottenere nuovi compiti randomizzati",fr:"Vous pouvez * cette page pour obtenir de nouvelles t\xE2ches al\xE9atoires"},W={en:"reload",de:"aktualisieren",es:"recargar",it:"ricaricare",fr:"recharger"};function w(h=[]){let e=document.createElement("div");return e.append(...h),e}function F(h=[]){let e=document.createElement("ul");return e.append(...h),e}function j(h){let e=document.createElement("li");return e.appendChild(h),e}function S(h){let e=document.createElement("input");return e.spellcheck=!1,e.type="text",e.classList.add("inputField"),e.style.width=h+"px",e}function R(){let h=document.createElement("button");return h.type="button",h.classList.add("button"),h}function x(h,e=[]){let t=document.createElement("span");return e.length>0?t.append(...e):t.innerHTML=h,t}function C(h,e=!1){let t=document.createElement("span");return katex.render(h,t,{throwOnError:!1,displayMode:e,macros:{"\\RR":"\\mathbb{R}","\\NN":"\\mathbb{N}","\\QQ":"\\mathbb{Q}","\\ZZ":"\\mathbb{Z}"}}),t}var O='<svg xmlns="http://www.w3.org/2000/svg" height="28" viewBox="0 0 448 512"><path d="M384 80c8.8 0 16 7.2 16 16V416c0 8.8-7.2 16-16 16H64c-8.8 0-16-7.2-16-16V96c0-8.8 7.2-16 16-16H384zM64 32C28.7 32 0 60.7 0 96V416c0 35.3 28.7 64 64 64H384c35.3 0 64-28.7 64-64V96c0-35.3-28.7-64-64-64H64z"/></svg>',_='<svg xmlns="http://www.w3.org/2000/svg" height="28" viewBox="0 0 448 512"><path d="M64 80c-8.8 0-16 7.2-16 16V416c0 8.8 7.2 16 16 16H384c8.8 0 16-7.2 16-16V96c0-8.8-7.2-16-16-16H64zM0 96C0 60.7 28.7 32 64 32H384c35.3 0 64 28.7 64 64V416c0 35.3-28.7 64-64 64H64c-35.3 0-64-28.7-64-64V96zM337 209L209 337c-9.4 9.4-24.6 9.4-33.9 0l-64-64c-9.4-9.4-9.4-24.6 0-33.9s24.6-9.4 33.9 0l47 47L303 175c9.4-9.4 24.6-9.4 33.9 0s9.4 24.6 0 33.9z"/>',Q='<svg xmlns="http://www.w3.org/2000/svg" height="28" viewBox="0 0 512 512"><path d="M464 256A208 208 0 1 0 48 256a208 208 0 1 0 416 0zM0 256a256 256 0 1 1 512 0A256 256 0 1 1 0 256z"/></svg>',Z='<svg xmlns="http://www.w3.org/2000/svg" height="28" viewBox="0 0 512 512"><path d="M256 48a208 208 0 1 1 0 416 208 208 0 1 1 0-416zm0 464A256 256 0 1 0 256 0a256 256 0 1 0 0 512zM369 209c9.4-9.4 9.4-24.6 0-33.9s-24.6-9.4-33.9 0l-111 111-47-47c-9.4-9.4-24.6-9.4-33.9 0s-9.4 24.6 0 33.9l64 64c9.4 9.4 24.6 9.4 33.9 0L369 209z"/></svg>',K='<svg xmlns="http://www.w3.org/2000/svg" height="25" viewBox="0 0 384 512" fill="white"><path d="M73 39c-14.8-9.1-33.4-9.4-48.5-.9S0 62.6 0 80V432c0 17.4 9.4 33.4 24.5 41.9s33.7 8.1 48.5-.9L361 297c14.3-8.7 23-24.2 23-41s-8.7-32.2-23-41L73 39z"/></svg>';function X(h,e=!1){let t=new Array(h);for(let r=0;r<h;r++)t[r]=r;if(e)for(let r=0;r<h;r++){let s=Math.floor(Math.random()*h),n=Math.floor(Math.random()*h),a=t[s];t[s]=t[n],t[n]=a}return t}var T=class h{constructor(e,t){this.m=e,this.n=t,this.v=new Array(e*t).fill("0")}getElement(e,t){return e<0||e>=this.m||t<0||t>=this.n?"0":this.v[e*this.n+t]}resize(e,t,r){if(e<1||e>50||t<1||t>50)return!1;let s=new h(e,t);s.v.fill(r);for(let n=0;n<s.m;n++)for(let a=0;a<s.n;a++)s.v[n*s.n+a]=this.getElement(n,a);return this.fromMatrix(s),!0}fromMatrix(e){this.m=e.m,this.n=e.n,this.v=[...e.v]}fromString(e){this.m=e.split("],").length,this.v=e.replaceAll("[","").replaceAll("]","").split(",").map(t=>t.trim()),this.n=this.v.length/this.m}getMaxCellStrlen(){let e=0;for(let t of this.v)t.length>e&&(e=t.length);return e}toTeX(e=!1){let t=e?"\\left[\\begin{array}":"\\begin{bmatrix}";e&&(t+="{"+"c".repeat(this.n-1)+"|c}");for(let r=0;r<this.m;r++){for(let s=0;s<this.n;s++){s>0&&(t+="&");let n=this.getElement(r,s);t+=n}t+="\\\\"}return t+=e?"\\end{array}\\right]":"\\end{bmatrix}",t}};function re(h){return parseFloat(h)}var g=class h{constructor(e,t,r=0,s=0){this.op=e,this.c=t,this.re=r,this.im=s}static const(e=0,t=0){return new h("const",[],e,t)}compare(e,t=0,r=1e-9){let s=this.re-e,n=this.im-t;return Math.sqrt(s*s+n*n)<r}toString(){let e="";if(this.op==="const"){let t=Math.abs(this.re)>1e-14,r=Math.abs(this.im)>1e-14;t&&r&&this.im>=0?e="("+this.re+"+"+this.im+"i)":t&&r&&this.im<0?e="("+this.re+"-"+-this.im+"i)":t?e=""+this.re:r&&(e="("+this.im+"i)")}else this.op.startsWith("var")?e=this.op.split(":")[1]:this.c.length==1?e=(this.op===".-"?"-":this.op)+"("+this.c.toString()+")":e="("+this.c.map(t=>t.toString()).join(this.op)+")";return e}},E=class h{constructor(){this.root=null,this.src="",this.token="",this.skippedWhiteSpace=!1,this.pos=0}getVars(e,t=null){t==null&&(t=this.root),t.op.startsWith("var:")&&e.add(t.op.substring(4));for(let r of t.c)this.getVars(e,r)}eval(e,t=null){let s=g.const(),n=0,a=0,o=null;switch(t==null&&(t=this.root),t.op){case"const":s=t;break;case"+":case"-":case"*":case"/":case"^":case"==":{let i=this.eval(e,t.c[0]),l=this.eval(e,t.c[1]);switch(t.op){case"+":s.re=i.re+l.re,s.im=i.im+l.im;break;case"-":s.re=i.re-l.re,s.im=i.im-l.im;break;case"*":s.re=i.re*l.re-i.im*l.im,s.im=i.re*l.im+i.im*l.re;break;case"/":n=l.re*l.re+l.im*l.im,s.re=(i.re*l.re+i.im*l.im)/n,s.im=(i.im*l.re-i.re*l.im)/n;break;case"^":o=new g("exp",[new g("*",[l,new g("ln",[i])])]),s=this.eval(e,o);break;case"==":n=i.re-l.re,a=i.im-l.im,s.re=Math.sqrt(n*n+a*a)<1e-9?1:0,s.im=0;break}break}case".-":case"sin":case"cos":case"tan":case"cot":case"exp":case"ln":case"log":case"sqrt":{let i=this.eval(e,t.c[0]);switch(t.op){case".-":s.re=-i.re,s.im=-i.im;break;case"sin":s.re=Math.sin(i.re)*Math.cosh(i.im),s.im=Math.cos(i.re)*Math.sinh(i.im);break;case"cos":s.re=Math.cos(i.re)*Math.cosh(i.im),s.im=-Math.sin(i.re)*Math.sinh(i.im);break;case"tan":n=Math.cos(i.re)*Math.cos(i.re)+Math.sinh(i.im)*Math.sinh(i.im),s.re=Math.sin(i.re)*Math.cos(i.re)/n,s.im=Math.sinh(i.im)*Math.cosh(i.im)/n;break;case"cot":n=Math.sin(i.re)*Math.sin(i.re)+Math.sinh(i.im)*Math.sinh(i.im),s.re=Math.sin(i.re)*Math.cos(i.re)/n,s.im=-(Math.sinh(i.im)*Math.cosh(i.im))/n;break;case"exp":s.re=Math.exp(i.re)*Math.cos(i.im),s.im=Math.exp(i.re)*Math.sin(i.im);break;case"ln":case"log":s.re=Math.log(Math.sqrt(i.re*i.re+i.im*i.im)),n=Math.abs(i.im)<1e-9?0:i.im,s.im=Math.atan2(n,i.re);break;case"sqrt":o=new g("^",[i,g.const(.5)]),s=this.eval(e,o);break}break}default:if(t.op.startsWith("var:")){let i=t.op.substring(4);if(i==="pi")return g.const(Math.PI);if(i==="e")return g.const(Math.E);if(i==="i")return g.const(0,1);if(i in e)return e[i];throw new Error("eval-error: unknown variable '"+i+"'")}else throw new Error("UNIMPLEMENTED eval '"+t.op+"'")}return s}static parse(e){let t=new h;if(t.src=e,t.token="",t.skippedWhiteSpace=!1,t.pos=0,t.next(),t.root=t.parseExpr(!1),t.token!=="")throw new Error("remaining tokens: "+t.token+"...");return t}parseExpr(e){return this.parseAdd(e)}parseAdd(e){let t=this.parseMul(e);for(;["+","-"].includes(this.token)&&!(e&&this.skippedWhiteSpace);){let r=this.token;this.next(),t=new g(r,[t,this.parseMul(e)])}return t}parseMul(e){let t=this.parsePow(e);for(;!(e&&this.skippedWhiteSpace);){let r="*";if(["*","/"].includes(this.token))r=this.token,this.next();else if(!e&&this.token==="(")r="*";else if(this.token.length>0&&(this.isAlpha(this.token[0])||this.isNum(this.token[0])))r="*";else break;t=new g(r,[t,this.parsePow(e)])}return t}parsePow(e){let t=this.parseUnary(e);for(;["^"].includes(this.token)&&!(e&&this.skippedWhiteSpace);){let r=this.token;this.next(),t=new g(r,[t,this.parseUnary(e)])}return t}parseUnary(e){return this.token==="-"?(this.next(),new g(".-",[this.parseMul(e)])):this.parseInfix(e)}parseInfix(e){if(this.token.length==0)throw new Error("expected unary");if(this.isNum(this.token[0])){let t=this.token;return this.next(),this.token==="."&&(t+=".",this.next(),this.token.length>0&&(t+=this.token,this.next())),new g("const",[],re(t))}else if(this.fun1().length>0){let t=this.fun1();this.next(t.length);let r=null;if(this.token==="(")if(this.next(),r=this.parseExpr(e),this.token+="",this.token===")")this.next();else throw Error("expected ')'");else r=this.parseMul(!0);return new g(t,[r])}else if(this.token==="("){this.next();let t=this.parseExpr(e);if(this.token+="",this.token===")")this.next();else throw Error("expected ')'");return t}else if(this.isAlpha(this.token[0])){let t="";return this.token.startsWith("pi")?t="pi":t=this.token[0],this.next(t.length),new g("var:"+t,[])}else throw new Error("expected unary")}compare(e){let s=new Set;this.getVars(s),e.getVars(s);for(let n=0;n<10;n++){let a={};for(let l of s)a[l]=g.const(Math.random(),Math.random());let o=new g("==",[this.root,e.root]),i=this.eval(a,o);if(Math.abs(i.re)<1e-9)return!1}return!0}fun1(){let e=["sin","cos","tan","cot","exp","ln","sqrt"];for(let t of e)if(this.token.startsWith(t))return t;return""}next(e=-1){if(e>0&&this.token.length>e){this.token=this.token.substring(e),this.skippedWhiteSpace=!1;return}this.token="";let t=!1,r=this.src.length;for(this.skippedWhiteSpace=!1;this.pos<r&&`	
 `.includes(this.src[this.pos]);)this.skippedWhiteSpace=!0,this.pos++;for(;!t&&this.pos<r;){let s=this.src[this.pos];if(this.token.length>0&&(this.isNum(this.token[0])&&this.isAlpha(s)||this.isAlpha(this.token[0])&&this.isNum(s)))return;if(`^%#*$()[]{},.:;+-*/_!<>=?	
 `.includes(s)){if(this.token.length>0)return;t=!0}`	
 `.includes(s)==!1&&(this.token+=s),this.pos++}}isNum(e){return e.charCodeAt(0)>=48&&e.charCodeAt(0)<=57}isAlpha(e){return e.charCodeAt(0)>=65&&e.charCodeAt(0)<=90||e.charCodeAt(0)>=97&&e.charCodeAt(0)<=122||e==="_"}toString(){return this.root==null?"":this.root.toString()}};var B=class{constructor(e,t=!1){this.src=e,this.debug=t,this.instanceIdx=Math.floor(Math.random()*e.instances.length),this.choiceIdx=0,this.gapIdx=0,this.expected={},this.types={},this.student={},this.inputs={},this.qDiv=null,this.titleDiv=null,this.checkBtn=null,this.showSolution=!1}populateDom(e){if(this.qDiv=w(),e.appendChild(this.qDiv),this.qDiv.classList.add("question"),this.titleDiv=w(),this.qDiv.appendChild(this.titleDiv),this.titleDiv.classList.add("questionTitle"),this.titleDiv.innerHTML=this.src.title,this.src.error.length>0){let a=x(this.src.error);this.qDiv.appendChild(a),a.style.color="red";return}for(let a of this.src.text.children)this.qDiv.appendChild(this.generateText(a));let t=w();this.qDiv.appendChild(t),t.classList.add("buttonRow");let r=Object.keys(this.expected).length>0;r&&(this.checkBtn=R(),t.appendChild(this.checkBtn),this.checkBtn.innerHTML=K);let s=x("&nbsp;&nbsp;&nbsp;");t.appendChild(s);let n=x("");if(t.appendChild(n),this.debug){if(this.src.variables.length>0){let i=w();i.classList.add("debugInfo"),i.innerHTML="Variables generated by Python Code",this.qDiv.appendChild(i);let l=w();l.classList.add("debugCode"),this.qDiv.appendChild(l);let d=this.src.instances[this.instanceIdx],u="",c=[...this.src.variables];c.sort();for(let p of c){let m=d[p].type,f=d[p].value;switch(m){case"vector":f="["+f+"]";break;case"set":f="{"+f+"}";break}u+=m+" "+p+" = "+f+"<br/>"}l.innerHTML=u}let a=["python_src_html","text_src_html"],o=["Python Source Code","Text Source Code"];for(let i=0;i<a.length;i++){let l=a[i];if(l in this.src&&this.src[l].length>0){let d=w();d.classList.add("debugInfo"),d.innerHTML=o[i],this.qDiv.appendChild(d);let u=w();u.classList.add("debugCode"),this.qDiv.append(u),u.innerHTML=this.src[l]}}}r&&this.checkBtn.addEventListener("click",()=>{n.innerHTML="";let a=0,o=0;for(let i in this.expected){let l=this.types[i],d=this.student[i],u=this.expected[i];switch(l){case"bool":d===u&&o++;break;case"string":{let c=this.inputs[i],p=d.trim().toUpperCase(),m=u.trim().toUpperCase(),f=p===m;f&&o++,c.style.color=f?"black":"white",c.style.backgroundColor=f?"transparent":"red";break}case"int":case"float":Math.abs(parseFloat(d)-parseFloat(u))<1e-9&&o++;break;case"term":{try{let c=E.parse(u),p=E.parse(d);c.compare(p)&&o++}catch(c){this.debug&&console.log(c)}break}case"vector":case"complex":case"set":{u=u.split(","),a+=u.length-1,d=[];for(let c=0;c<u.length;c++)d.push(this.student[i+"-"+c]);if(l==="set")for(let c=0;c<u.length;c++){let p=parseFloat(u[c]);for(let m=0;m<d.length;m++){let f=parseFloat(d[m]);if(Math.abs(f-p)<1e-9){o++;break}}}else for(let c=0;c<u.length;c++){let p=parseFloat(d[c]),m=parseFloat(u[c]);Math.abs(p-m)<1e-9&&o++}break}case"matrix":{let c=new T(0,0);c.fromString(u),a+=c.m*c.n-1;for(let p=0;p<c.m;p++)for(let m=0;m<c.n;m++){let f=p*c.n+m;d=this.student[i+"-"+f];let M=c.v[f];try{let L=E.parse(M),b=E.parse(d);L.compare(b)&&o++}catch(L){this.debug&&console.log(L)}}break}default:n.innerHTML="UNIMPLEMENTED EVAL OF TYPE "+l}a++}o==a?(n.style.color=this.titleDiv.style.color=this.checkBtn.style.backgroundColor=this.qDiv.style.borderColor="rgb(0,150,0)",this.qDiv.style.backgroundColor="rgba(0,150,0, 0.025)"):(this.titleDiv.style.color=n.style.color=this.checkBtn.style.backgroundColor=this.qDiv.style.borderColor="rgb(150,0,0)",this.qDiv.style.backgroundColor="rgba(150,0,0, 0.025)",a>=5&&(n.innerHTML=""+o+" / "+a))})}generateMathString(e){let t="";switch(e.type){case"math":case"display-math":for(let r of e.children)t+=this.generateMathString(r);break;case"text":return e.data;case"var":{let r=this.src.instances[this.instanceIdx],s=r[e.data].type,n=r[e.data].value;switch(s){case"vector":return"\\left["+n+"\\right]";case"set":return"\\left\\{"+n+"\\right\\}";case"complex":{let a=n.split(","),o=parseFloat(a[0]),i=parseFloat(a[1]),l="";return Math.abs(o)>1e-9&&(l+=o),Math.abs(i)>1e-9&&(l+=(i<0?"-":"+")+i+"i"),l}case"matrix":{let a=new T(0,0);return a.fromString(n),t=a.toTeX(e.data.includes("augmented")),t}case"term":{t=n.replaceAll("sin","\\sin").replaceAll("cos","\\cos").replaceAll("tan","\\tan").replaceAll("exp","\\exp").replaceAll("ln","\\ln").replaceAll("*","\\cdot ").replaceAll("(","\\left(").replaceAll(")","\\right)");break}default:t=n}}}return t}generateMatrixParenthesis(e,t){let r=document.createElement("td");r.style.width="3px";for(let s of["Top",e?"Left":"Right","Bottom"])r.style["border"+s+"Width"]="2px",r.style["border"+s+"Style"]="solid";return r.rowSpan=t,r}validateTermInput(e){let t=!0,r=e.value;if(r.length>0)try{E.parse(r)}catch{t=!1}e.style.color=t?"black":"maroon"}generateText(e,t=!1){switch(e.type){case"paragraph":case"span":{let r=document.createElement(e.type=="span"||t?"span":"p");for(let s of e.children)r.appendChild(this.generateText(s));return r}case"text":return x(e.data);case"code":{let r=x(e.data);return r.classList.add("code"),r}case"italic":case"bold":{let r=x("");return r.append(...e.children.map(s=>this.generateText(s))),e.type==="bold"?r.style.fontWeight="bold":r.style.fontStyle="italic",r}case"math":case"display-math":{let r=this.generateMathString(e);return C(r,e.type==="display-math")}case"gap":{let r=x(""),s=Math.max(e.data.length*12,24),n=S(s),a="gap-"+this.gapIdx;return this.inputs[a]=n,this.expected[a]=e.data,this.types[a]="string",n.addEventListener("keyup",()=>{this.student[a]=n.value.trim()}),this.showSolution&&(this.student[a]=n.value=this.expected[a]),this.gapIdx++,r.appendChild(n),r}case"input":case"input2":{let r=e.type==="input2",s=x("");s.style.verticalAlign="text-bottom";let n=e.data,a=this.src.instances[this.instanceIdx][n];if(this.expected[n]=a.value,this.types[n]=a.type,!r)switch(a.type){case"set":s.append(C("\\{"),x(" "));break;case"vector":s.append(C("["),x(" "));break}if(a.type==="vector"||a.type==="set"){let o=a.value.split(","),i=o.length;for(let l=0;l<i;l++){l>0&&s.appendChild(x(" , "));let d=S(Math.max(o[l].length*12,24));s.appendChild(d),d.addEventListener("keyup",()=>{this.student[n+"-"+l]=d.value.trim(),this.validateTermInput(d)}),this.showSolution&&(this.student[n+"-"+l]=d.value=o[l])}}else if(a.type==="matrix"){let o=(u,c,p)=>{let m=w();u.innerHTML="",u.appendChild(m),m.style.position="relative",m.style.display="inline-block";let f=document.createElement("table");m.appendChild(f);let M=c.getMaxCellStrlen();M=Math.max(M*12,24);for(let v=0;v<p.m;v++){let k=document.createElement("tr");f.appendChild(k),v==0&&k.appendChild(this.generateMatrixParenthesis(!0,p.m));for(let H=0;H<p.n;H++){let P=v*p.n+H,N=document.createElement("td");k.appendChild(N);let D=S(M);D.style.textAlign="end",N.appendChild(D),D.addEventListener("keyup",()=>{this.student[n+"-"+P]=D.value.trim(),this.validateTermInput(D)}),this.showSolution&&(this.student[n+"-"+P]=D.value=""+p.v[P])}v==0&&k.appendChild(this.generateMatrixParenthesis(!1,p.m))}let L=["+","-","+","-"],b=[0,0,1,-1],I=[1,-1,0,0],A=[0,22,888,888],y=[888,888,-22,-22],q=[-22,-22,0,22],Y=[c.n!=1,c.n!=1,c.m!=1,c.m!=1],$=[p.n>=10,p.n<=1,p.m>=10,p.m<=1];for(let v=0;v<4;v++){if(Y[v]==!1)continue;let k=x(L[v]);A[v]!=888&&(k.style.top=""+A[v]+"px"),y[v]!=888&&(k.style.bottom=""+y[v]+"px"),q[v]!=888&&(k.style.right=""+q[v]+"px"),k.classList.add("matrixResizeButton"),m.appendChild(k),$[v]?k.style.opacity="0.5":k.addEventListener("click",()=>{p.resize(p.m+b[v],p.n+I[v],"0"),o(u,c,p)})}},i=new T(0,0);i.fromString(a.value);let l=new T(i.m==1?1:3,i.n==1?1:3);this.showSolution&&l.fromMatrix(i);let d=w();s.appendChild(d),o(d,i,l)}else if(a.type==="complex"){let o=a.value.split(",");for(let i=0;i<2;i++){let l=S(Math.max(Math.max(o[i].length*12,24),24));s.appendChild(l),this.showSolution&&(this.student[n+"-"+i]=l.value=o[i]),l.addEventListener("keyup",()=>{this.student[n+"-"+i]=l.value.trim(),this.validateTermInput(l)}),i==0?s.append(x(" "),C("+"),x(" ")):s.append(x(" "),C("i"))}}else{let o=S(Math.max(a.value.length*12,24));s.appendChild(o),o.addEventListener("keyup",()=>{this.student[n]=o.value.trim(),this.validateTermInput(o)}),this.showSolution&&(this.student[n]=o.value=a.value)}if(!r)switch(a.type){case"set":s.append(x(" "),C("\\}"));break;case"vector":s.append(x(" "),C("]"));break}return s}case"itemize":return F(e.children.map(r=>j(this.generateText(r))));case"single-choice":case"multi-choice":{let r=e.type=="multi-choice",s=document.createElement("table"),n=e.children.length,a=this.debug==!1,o=X(n,a),i=r?_:Z,l=r?O:Q,d=[],u=[];for(let c=0;c<n;c++){let p=o[c],m=e.children[p],f="mc-"+this.choiceIdx+"-"+p;u.push(f);let M=m.children[0].type=="bool"?m.children[0].data:this.src.instances[this.instanceIdx][m.children[0].data].value;this.expected[f]=M,this.types[f]="bool",this.student[f]=this.showSolution?M:"false";let L=this.generateText(m.children[1],!0),b=document.createElement("tr");s.appendChild(b),b.style.cursor="pointer";let I=document.createElement("td");d.push(I),b.appendChild(I),I.innerHTML=this.student[f]=="true"?i:l;let A=document.createElement("td");b.appendChild(A),A.appendChild(L),r?b.addEventListener("click",()=>{this.student[f]=this.student[f]==="true"?"false":"true",this.student[f]==="true"?I.innerHTML=i:I.innerHTML=l}):b.addEventListener("click",()=>{for(let y of u)this.student[y]="false";this.student[f]="true";for(let y=0;y<u.length;y++){let q=o[y];d[q].innerHTML=this.student[u[q]]=="true"?i:l}})}return this.choiceIdx++,s}default:{let r=x("UNIMPLEMENTED("+e.type+")");return r.style.color="red",r}}}};function ne(h,e){["en","de","es","it","fr"].includes(h.lang)==!1&&(h.lang="en"),e&&(document.getElementById("debug").style.display="block"),document.getElementById("date").innerHTML=new Date().toISOString().split("T")[0],document.getElementById("title").innerHTML=h.title,document.getElementById("author").innerHTML=h.author,document.getElementById("courseInfo1").innerHTML=U[h.lang];let t='<span onclick="location.reload()" style="text-decoration: underline; font-weight: bold; cursor: pointer">'+W[h.lang]+"</span>";document.getElementById("courseInfo2").innerHTML=V[h.lang].replace("*",t);let r=[],s=document.getElementById("questions"),n=1;for(let a of h.questions){a.title=""+n+". "+a.title;let o=new B(a,e);o.showSolution=e,r.push(o),o.populateDom(s),e&&a.error.length==0&&o.checkBtn.click(),n++}}return se(ae);})();sell.init(quizSrc,debug);</script></body> </html>
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
