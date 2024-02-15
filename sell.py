#!/usr/bin/env python3

"""SELL - Simple E-Learning Language
AUTHOR:  Andreas Schwenk <mailto:contact@compiler-construction.com>
LICENSE: GPLv3
"""

import json, sys, types, sys, os
import numpy, sympy


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
            if ch in '`^"%#*$()[]{}\\,.:;+-*/_!<> =?':
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


# lex = Lexer('a"x"bc 123 *blub* $`hello, world!`123$')
# while len(lex.token) > 0:
#     print(lex.token)
#     lex.next()
# exit(0)

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
skipVariables = [
    "E",
    "I",
    "nan",
    "oo",
    "pi",
    "zoo",
    "Catalan",
    "EulerGamma",
    "GoldenRatio",
    "TribonacciConstant",
    "true",
    "false",
    "EmptySequence",
    "Id",
    "EmptySet",
    "Reals",
    "ord0",
    "Naturals",
    "Naturals0",
    "UniversalSet",
    "Integers",
    "Rationals",
    "Complexes",
]


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
                self.children[-1].data += line + "\n"
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
                correct = option.startswith("[x]") or option.startswith("(x)")
                node = TextNode("answer")
                self.children.append(node)
                node.children.append(TextNode("bool", "true" if correct else "false"))
                node.children.append(TextNode("paragraph", option[3:].strip()))
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

    def parse_span(self, lex: Lexer):
        # grammar: span = { item };
        #          item = bold | math | text | input;
        #          bold = "*" { item } "*";
        #          math = "$" { item } "$";
        #          input = "%" ["!"] var;
        #          text = otherwise;
        span = TextNode("span")
        while lex.token != "":
            span.children.append(self.parse_item(lex))
        return span

    def parse_item(self, lex: Lexer, math_mode=False):
        if not math_mode and lex.token == "*":
            return self.parse_bold_italic(lex)
        elif lex.token == "$":
            return self.parse_math(lex)
        elif not math_mode and lex.token == "%":
            return self.parse_input(lex)
        else:
            n = TextNode("text", lex.token)
            lex.next()
            return n

    def parse_bold_italic(self, lex: Lexer):
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

    def parse_math(self, lex: Lexer):
        math = TextNode("math")
        if lex.token == "$":
            lex.next()
        while lex.token != "" and lex.token != "$":
            math.children.append(self.parse_item(lex, True))
        if lex.token == "$":
            lex.next()
        return math

    def parse_input(self, lex: Lexer):
        input = TextNode("input")
        if lex.token == "%":
            lex.next()
        if lex.token == "!":
            input.type = "input2"
            lex.next()
        input.data = lex.token.strip()
        lex.next()
        return input

    def optimize(self):
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

    def build(self):
        if len(self.python_src) > 0:
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

    def post_process_text(self, node, math=False):
        for c in node.children:
            self.post_process_text(c, math or node.type == "math")
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

    def format_float(self, v) -> str:
        s = str(v)
        if s.endswith(".0"):
            return s[:-2]
        return s

    def run_python_code(self) -> dict:
        locals = {}
        res = {}
        try:
            exec(self.python_src, globals(), locals)
        except Exception as e:
            # print(e)
            self.error += str(e) + ". "
            return res
        for id in locals:
            if id in skipVariables:
                continue
            value = locals[id]
            if isinstance(value, types.ModuleType):
                continue
            self.variables.add(id)
            if isinstance(value, sympy.Basic):
                res[id] = {"type": "term", "value": str(value)}
            elif isinstance(value, numpy.matrix):
                v = (
                    numpy.array2string(value, separator=",")
                    .replace("\n", "")
                    .replace(" ", "")
                )
                res[id] = {"type": "matrix", "value": v}
            elif isinstance(value, int):
                res[id] = {"type": "int", "value": str(value)}
            elif isinstance(value, float):
                res[id] = {"type": "float", "value": self.format_float(value)}
            elif isinstance(value, complex):
                res[id] = {
                    "type": "complex",
                    "value": self.format_float(value.real)
                    + ","
                    + self.format_float(value.imag),
                }
            elif isinstance(value, list):
                res[id] = {
                    "type": "vector",
                    "value": str(value)
                    .replace("[", "")
                    .replace("]", "")
                    .replace(" ", ""),
                }
            elif isinstance(value, set):
                res[id] = {
                    "type": "set",
                    "value": str(value)
                    .replace("{", "")
                    .replace("}", "")
                    .replace(" ", ""),
                }
            else:
                self.variables.remove(id)
            #    res[id] = {"type": "unknown", "value": str(value)}
        if len(self.variables) > 50:
            self.error += "ERROR: Wrong usage of Python imports. Refer to pySELL docs!"
            # TODO: write the docs...
        return res

    def to_dict(self) -> dict:
        # TODO: remove "*_html" entries for non-debug output !!
        return {
            "title": self.title,
            "error": self.error,
            "variables": list(self.variables),
            "instances": self.instances,
            "text": self.text.to_dict(),
            "text_src_html": self.syntax_highlight_text(self.text_src),
            "python_src_html": self.syntax_highlight_python(self.python_src),
        }

    def syntax_highlight_text_line(self, src):
        html = ""
        math = False
        code = False
        bold = False  # TODO
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
                math = not math
                if math:
                    html += '<span style="color:#FF5733; font-weight: bold;">'
                    html += ch
                else:
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

    def syntax_highlight_text(self, src):
        html = ""
        lines = src.split("\n")
        for line in lines:
            if len(line.strip()) == 0:
                continue
            if line.startswith("[") or line.startswith("(") or line.startswith("-"):
                n = 1 if line.startswith("-") else 3
                html += (
                    '<span style="color:#FF5733; font-weight:bold">'
                    + line[0:n].replace(" ", "&nbsp;")
                    + "</span>"
                )
                html += " " + self.syntax_highlight_text_line(line[(n + 1) :])
            else:
                html += self.syntax_highlight_text_line(line)
            html += "<br/>"
        return html

    def syntax_highlight_python(self, src):
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
html = """<!DOCTYPE html> <html> <head> <meta charset="UTF-8" /> <title>pySELL</title> <meta name="viewport" content="width=device-width, initial-scale=1.0" /> <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css" integrity="sha384-n8MVd4RsNIU0tAv4ct0nTaAbDJwPJzDEaqSD1odI+WdtXRGWt2kTvGFasHpSy3SV" crossorigin="anonymous" /> <script src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js" integrity="sha384-XjKyOOlGwcjNTAIQHIpgOno0Hl1YQqzUOEleOLALmuqehneUG+vnGctmUb0ZY0l8" crossorigin="anonymous" ></script> <style> html { font-family: Arial, Helvetica, sans-serif; } body { max-width: 1024px; margin-left: auto; margin-right: auto; padding-left: 5px; padding-right: 5px; } h1 { text-align: center; font-size: 28pt; } .author { text-align: center; font-size: 18pt; } .courseInfo { font-size: 14pt; font-style: italic; /*margin-bottom: 24px;*/ text-align: center; } .question { color: black; background-color: white; border-style: solid; border-radius: 5px; border-width: 3px; border-color: black; padding: 8px; margin-top: 20px; margin-bottom: 20px; -webkit-box-shadow: 4px 6px 8px -1px rgba(0, 0, 0, 0.93); box-shadow: 4px 6px 8px -1px rgba(0, 0, 0, 0.1); } .questionTitle { font-size: 24pt; } .code { font-family: "Courier New", Courier, monospace; color: black; background-color: rgb(235, 235, 235); padding: 2px 5px; border-radius: 5px; margin: 1px 2px; } .debugCode { font-family: "Courier New", Courier, monospace; padding: 4px; margin-bottom: 5px; background-color: black; color: white; border-radius: 5px; opacity: 0.85; overflow-x: scroll; } .debugInfo { text-align: center; font-size: 8pt; margin-top: 2px; } ul { margin-top: 0; margin-left: 0px; padding-left: 20px; } .inputField { width: 32px; height: 24px; font-size: 14pt; border-style: solid; border-color: black; border-radius: 5px; border-width: 0.2; padding-left: 5px; padding-right: 5px; outline-color: black; background-color: transparent; margin: 1px; } .inputField:focus { outline-color: maroon; } .button { padding-left: 8px; padding-right: 8px; padding-top: 5px; padding-bottom: 5px; font-size: 12pt; /*background-color: rgba(62, 146, 3, 0.767);*/ background-color: green; color: white; border-style: none; border-radius: 4px; height: 36px; cursor: pointer; } .buttonRow { display: flex; align-items: baseline; margin-top: 12px; } </style> </head> <body> <h1 id="title"></h1> <div class="author" id="author"></div> <p id="courseInfo1" class="courseInfo"></p> <p id="courseInfo2" class="courseInfo"></p> <h1 id="debug" class="debugInfo" style="display: none">DEBUG VERSION</h1> <div id="questions"></div> <p style="font-size: 8pt; font-style: italic; text-align: center"> This quiz was created using pySELL (Python-based Simple E-Learning Langauge, written by Andreas Schwenk) </p> <script>let debug = false; let quizSrc = {};var sell=(()=>{var S=Object.defineProperty;var R=Object.getOwnPropertyDescriptor;var Y=Object.getOwnPropertyNames;var K=Object.prototype.hasOwnProperty;var Z=(l,e)=>{for(var t in e)S(l,t,{get:e[t],enumerable:!0})},$=(l,e,t,i)=>{if(e&&typeof e=="object"||typeof e=="function")for(let s of Y(e))!K.call(l,s)&&s!==t&&S(l,s,{get:()=>e[s],enumerable:!(i=R(e,s))||i.enumerable});return l};var G=l=>$(S({},"__esModule",{value:!0}),l);var X={};Z(X,{init:()=>J});function w(l=[]){let e=document.createElement("div");return e.append(...l),e}function D(l=[]){let e=document.createElement("ul");return e.append(...l),e}function q(l){let e=document.createElement("li");return e.appendChild(l),e}function y(l){let e=document.createElement("input");return e.type="text",e.classList.add("inputField"),e.style.width=l+"px",e}function B(){let l=document.createElement("button");return l.type="button",l.classList.add("button"),l}function x(l,e=[]){let t=document.createElement("span");return e.length>0?t.append(...e):t.innerHTML=l,t}function k(l){let e=document.createElement("span");return katex.render(l,e,{throwOnError:!1}),e}var H='<svg xmlns="http://www.w3.org/2000/svg" height="28" viewBox="0 0 448 512"><path d="M384 80c8.8 0 16 7.2 16 16V416c0 8.8-7.2 16-16 16H64c-8.8 0-16-7.2-16-16V96c0-8.8 7.2-16 16-16H384zM64 32C28.7 32 0 60.7 0 96V416c0 35.3 28.7 64 64 64H384c35.3 0 64-28.7 64-64V96c0-35.3-28.7-64-64-64H64z"/></svg>',P='<svg xmlns="http://www.w3.org/2000/svg" height="28" viewBox="0 0 448 512"><path d="M64 80c-8.8 0-16 7.2-16 16V416c0 8.8 7.2 16 16 16H384c8.8 0 16-7.2 16-16V96c0-8.8-7.2-16-16-16H64zM0 96C0 60.7 28.7 32 64 32H384c35.3 0 64 28.7 64 64V416c0 35.3-28.7 64-64 64H64c-35.3 0-64-28.7-64-64V96zM337 209L209 337c-9.4 9.4-24.6 9.4-33.9 0l-64-64c-9.4-9.4-9.4-24.6 0-33.9s24.6-9.4 33.9 0l47 47L303 175c9.4-9.4 24.6-9.4 33.9 0s9.4 24.6 0 33.9z"/>',F='<svg xmlns="http://www.w3.org/2000/svg" height="28" viewBox="0 0 512 512"><path d="M464 256A208 208 0 1 0 48 256a208 208 0 1 0 416 0zM0 256a256 256 0 1 1 512 0A256 256 0 1 1 0 256z"/></svg>',U='<svg xmlns="http://www.w3.org/2000/svg" height="28" viewBox="0 0 512 512"><path d="M256 48a208 208 0 1 1 0 416 208 208 0 1 1 0-416zm0 464A256 256 0 1 0 256 0a256 256 0 1 0 0 512zM369 209c9.4-9.4 9.4-24.6 0-33.9s-24.6-9.4-33.9 0l-111 111-47-47c-9.4-9.4-24.6-9.4-33.9 0s-9.4 24.6 0 33.9l64 64c9.4 9.4 24.6 9.4 33.9 0L369 209z"/></svg>',z='<svg xmlns="http://www.w3.org/2000/svg" height="25" viewBox="0 0 384 512" fill="white"><path d="M73 39c-14.8-9.1-33.4-9.4-48.5-.9S0 62.6 0 80V432c0 17.4 9.4 33.4 24.5 41.9s33.7 8.1 48.5-.9L361 297c14.3-8.7 23-24.2 23-41s-8.7-32.2-23-41L73 39z"/></svg>';var V={de:"Diese Seite wird in Ihrem Browser ausgef\xFChrt und speichert keine Daten auf Servern.",en:"This page runs in your browser and does not store any data on servers."},N={de:"Sie k\xF6nnen diese Seite *, um neue randomisierte Aufgaben zu erhalten.",en:"You can * this page in order to get new randomized tasks."},_={de:"aktualisieren",en:"reload"};function W(l){let e=new Array(l);for(let t=0;t<l;t++)e[t]=t;return e}function j(l){let e=new Array(l);for(let t=0;t<l;t++)e[t]=t;for(let t=0;t<l;t++){let i=Math.floor(Math.random()*l),s=Math.floor(Math.random()*l),n=e[i];e[i]=e[s],e[s]=n}return e}var E=class{constructor(){this.m=0,this.n=0,this.v=[]}fromString(e){this.m=e.split("],[").length,this.v=e.replaceAll("[","").replaceAll("]","").split(",").map(t=>parseFloat(t)),this.n=this.v.length/this.m}getMaxCellStrlen(){let e=0;for(let t of this.v){let i=t.toString();i.length>e&&(e=i.length)}return e}},v=class{constructor(e,t){this.op=e,this.c=t}};function g(l){return parseFloat(l)}var L=class{constructor(){this.root=null,this.src="",this.token="",this.pos=0}getVars(e,t=null){t==null&&(t=this.root),t.op.startsWith("var:")&&e.add(t.op.substring(4));for(let i of t.c)this.getVars(e,i)}eval(e,t=null){switch(t==null&&(t=this.root),t.op){case"+":case"-":case"*":case"/":case"^":case"==":{let s=this.eval(e,t.c[0]).split(":"),n=this.eval(e,t.c[1]).split(":");switch(t.op){case"+":if(s[0]==="num"&&n[0]=="num")return"num:"+(g(s[1])+g(n[1]));break;case"-":if(s[0]==="num"&&n[0]=="num")return"num:"+(g(s[1])-g(n[1]));break;case"*":if(s[0]==="num"&&n[0]=="num")return"num:"+g(s[1])*g(n[1]);break;case"/":if(s[0]==="num"&&n[0]=="num")return"num:"+g(s[1])/g(n[1]);break;case"^":if(s[0]==="num"&&n[0]=="num")return"num:"+Math.pow(g(s[1]),g(n[1]));break;case"==":if(s[0]==="num"&&n[0]=="num")return"num:"+(Math.abs(g(s[1])-g(n[1]))<1e-9?1:0);break}let r="eval-error: "+s[0]+" "+t.op+" "+n[0];throw new Error(r)}case".-":case"sin":case"cos":case"tan":case"exp":case"ln":case"sqrt":{let s=this.eval(e,t.c[0]).split(":");switch(t.op){case".-":if(s[0]==="num")return"num:"+-g(s[1]);break;case"sin":if(s[0]==="num")return"num:"+Math.sin(g(s[1]));break;case"cos":if(s[0]==="num")return"num:"+Math.cos(g(s[1]));break;case"tan":if(s[0]==="num")return"num:"+Math.tan(g(s[1]));break;case"exp":if(s[0]==="num")return"num:"+Math.exp(g(s[1]));break;case"ln":if(s[0]==="num")return"num:"+Math.log(g(s[1]));break;case"sqrt":if(s[0]==="num")return"num:"+Math.sqrt(g(s[1]));break}let n="eval-error: "+t.op+"("+s[0]+")";throw new Error(n)}default:if(t.op.startsWith("num:"))return t.op;if(t.op.startsWith("var:")){let s=t.op.substring(4);if(s in e)return e[s];throw new Error("eval-error: unknown variable '"+s+"'")}throw new Error("UNIMPLEMENTED eval '"+t.op+"'")}}parse(e){if(this.src=e,this.token="",this.pos=0,this.next(),this.root=this.parseExpr(),this.token!=="")throw new Error("remaining tokens: "+this.token+"...")}parseExpr(){let e=this.parseMul();for(;["+","-"].includes(this.token);){let t=this.token;this.next(),e=new v(t,[e,this.parseMul()])}return e}parseMul(){let e=this.parsePow();for(;["*","/","("].includes(this.token)||this.token.length>0&&this.isAlpha(this.token[0]);){let t="*";["*","/"].includes(this.token)&&(t=this.token,this.next()),e=new v(t,[e,this.parsePow()])}return e}parsePow(){let e=this.parseUnary();if(["^"].includes(this.token)){let t=this.token;this.next(),e=new v(t,[e,this.parseUnary()])}return e}parseUnary(){return this.token==="-"?(this.next(),new v(".-",[this.parseMul()])):this.parseInfix()}parseInfix(){if(this.token.length==0)throw new Error("expected unary");if(this.isNum(this.token[0])){let e=this.token;return this.next(),this.token==="."&&(e+=".",this.next(),this.token.length>0&&(e+=this.token,this.next())),new v("num:"+e,[])}else if(["sin","cos","tan","exp","ln","sqrt"].includes(this.token)){let e=this.token;this.next();let t=!1;this.token==="("&&(t=!0,this.next());let i=new v(e,[this.parseMul()]);if(t)if(this.token===")")this.next();else throw Error("expected ')'");return i}else if(this.token==="("){this.next();let e=this.parseExpr();if(this.token+="",this.token===")")this.next();else throw Error("expected ')'");return e}else{if(this.token.toLowerCase()==="pi")return this.next(),new v("num:"+Math.PI,[]);if(this.token.toLowerCase()==="e")return this.next(),new v("num:"+Math.E,[]);if(this.isAlpha(this.token[0])){let e=this.token;return this.next(),new v("var:"+e,[])}else throw new Error("expected unary")}}compare(e){let i=new Set;this.getVars(i),e.getVars(i);for(let s=0;s<10;s++){let n={};for(let h of i)n[h]="num:"+Math.random();let r=new v("==",[this.root,e.root]);if(this.eval(n,r)==="num:0")return!1}return!0}next(){this.token="";let e=!1,t=this.src.length;for(;this.pos<t&&`	
 `.includes(this.src[this.pos]);)this.pos++;for(;!e&&this.pos<t;){let i=this.src[this.pos];if(this.token.length>0&&this.isNum(this.token[0])&&this.isAlpha(i))return;if(`^%#*$()[]{},.:;+-*/_!<>=?	
 `.includes(i)){if(this.token.length>0)return;e=!0}`	
 `.includes(i)==!1&&(this.token+=i),["x","y","z","t"].includes(this.token)&&(e=!0),this.pos++}}isNum(e){return e.charCodeAt(0)>=48&&e.charCodeAt(0)<=57}isAlpha(e){return e.charCodeAt(0)>=65&&e.charCodeAt(0)<=90||e.charCodeAt(0)>=97&&e.charCodeAt(0)<=122||e==="_"}};var A=class{constructor(e,t=!1){this.src=e,this.debug=t,this.instanceIdx=Math.floor(Math.random()*e.instances.length),this.choiceIdx=0,this.gapIdx=0,this.expected={},this.types={},this.student={},this.inputs={},this.qDiv=null,this.titleDiv=null,this.checkBtn=null,this.showSolution=!1}populateDom(e){if(this.qDiv=w(),e.appendChild(this.qDiv),this.qDiv.classList.add("question"),this.titleDiv=w(),this.qDiv.appendChild(this.titleDiv),this.titleDiv.classList.add("questionTitle"),this.titleDiv.innerHTML=this.src.title,this.src.error.length>0){let r=x(this.src.error);this.qDiv.appendChild(r),r.style.color="red";return}for(let r of this.src.text.children)this.qDiv.appendChild(this.generateText(r));let t=w();this.qDiv.appendChild(t),t.classList.add("buttonRow");let i=Object.keys(this.expected).length>0;i&&(this.checkBtn=B(),t.appendChild(this.checkBtn),this.checkBtn.innerHTML=z);let s=x("&nbsp;&nbsp;&nbsp;");t.appendChild(s);let n=x("");if(t.appendChild(n),this.debug){if(this.src.variables.length>0){let h=w();h.classList.add("debugInfo"),h.innerHTML="Variables generated by Python Code",this.qDiv.appendChild(h);let c=w();c.classList.add("debugCode"),this.qDiv.appendChild(c);let p=this.src.instances[this.instanceIdx],u="",o=[...this.src.variables];o.sort();for(let f of o){let d=p[f].type,m=p[f].value;switch(d){case"vector":m="["+m+"]";break;case"set":m="{"+m+"}";break}u+=d+" "+f+" = "+m+"; <br/>"}c.innerHTML=u}let r=["python_src_html","text_src_html"],a=["Python Source Code","Text Source Code"];for(let h=0;h<r.length;h++){let c=r[h];if(c in this.src&&this.src[c].length>0){let p=w();p.classList.add("debugInfo"),p.innerHTML=a[h],this.qDiv.appendChild(p);let u=w();u.classList.add("debugCode"),this.qDiv.append(u),u.innerHTML=this.src[c]}}}i&&this.checkBtn.addEventListener("click",()=>{n.innerHTML="";let r=0,a=0;for(let h in this.expected){let c=this.types[h],p=this.student[h],u=this.expected[h];switch(c){case"bool":p===u&&a++;break;case"string":{let o=this.inputs[h],f=p.trim().toUpperCase(),d=u.trim().toUpperCase(),m=f===d;m&&a++,o.style.color=m?"black":"white",o.style.backgroundColor=m?"transparent":"red";break}case"int":case"float":Math.abs(parseFloat(p)-parseFloat(u))<1e-9&&a++;break;case"term":{try{let o=new L;o.parse(u);let f=new L;f.parse(p),o.compare(f)&&a++}catch{}break}case"vector":case"complex":case"set":{u=u.split(","),r+=u.length-1,p=[];for(let o=0;o<u.length;o++)p.push(this.student[h+"-"+o]);if(c==="set")for(let o=0;o<u.length;o++){let f=parseFloat(u[o]);for(let d=0;d<p.length;d++){let m=parseFloat(p[d]);if(Math.abs(m-f)<1e-9){a++;break}}}else for(let o=0;o<u.length;o++){let f=parseFloat(p[o]),d=parseFloat(u[o]);Math.abs(f-d)<1e-9&&a++}break}case"matrix":{let o=new E;o.fromString(u),r+=o.m*o.n-1;for(let f=0;f<o.m;f++)for(let d=0;d<o.n;d++){let m=f*o.m+d;p=parseFloat(this.student[h+"-"+m]),Math.abs(o.v[m]-p)<1e-9&&a++}break}default:n.innerHTML="UNIMPLEMENTED EVAL OF TYPE "+c}r++}a==r?(n.style.color=this.titleDiv.style.color=this.checkBtn.style.backgroundColor=this.qDiv.style.borderColor="rgb(0,150,0)",this.qDiv.style.backgroundColor="rgba(0,150,0, 0.025)"):(this.titleDiv.style.color=n.style.color=this.checkBtn.style.backgroundColor=this.qDiv.style.borderColor="rgb(150,0,0)",this.qDiv.style.backgroundColor="rgba(150,0,0, 0.025)",r>=5&&(n.innerHTML=""+a+" / "+r))})}generateMathString(e){let t="";switch(e.type){case"math":for(let i of e.children)t+=this.generateMathString(i);break;case"text":return e.data;case"var":{let i=this.src.instances[this.instanceIdx],s=i[e.data].type,n=i[e.data].value;switch(s){case"vector":return"\\left["+n+"\\right]";case"set":return"\\left\\{"+n+"\\right\\}";case"complex":{let r=n.split(","),a=parseFloat(r[0]),h=parseFloat(r[1]),c="";return Math.abs(a)>1e-9&&(c+=a),Math.abs(h)>1e-9&&(c+=(h<0?"-":"+")+h+"i"),c}case"matrix":return t="\\begin{bmatrix}"+n.replaceAll("],[","\\\\").replaceAll(",","&").replaceAll("[","").replaceAll("]","")+"\\end{bmatrix}",t;case"term":{t=n.replaceAll("sin","\\sin").replaceAll("cos","\\cos").replaceAll("tan","\\tan").replaceAll("exp","\\exp").replaceAll("ln","\\ln").replaceAll("*","\\cdot").replaceAll("(","\\left(").replaceAll(")","\\right)");break}default:t=n}}}return t}generateMatrixParenthesis(e,t){let i=document.createElement("td");i.style.width="3px";for(let s of["Top",e?"Left":"Right","Bottom"])i.style["border"+s+"Width"]="2px",i.style["border"+s+"Style"]="solid";return i.rowSpan=t,i}generateText(e,t=!1){switch(e.type){case"paragraph":case"span":{let i=document.createElement(e.type=="span"||t?"span":"p");for(let s of e.children)i.appendChild(this.generateText(s));return i}case"text":return x(e.data);case"code":{let i=x(e.data);return i.classList.add("code"),i}case"italic":case"bold":{let i=x("");return i.append(...e.children.map(s=>this.generateText(s))),e.type==="bold"?i.style.fontWeight="bold":i.style.fontStyle="italic",i}case"math":return k(this.generateMathString(e));case"gap":{let i=x(""),s=Math.max(e.data.length*12,24),n=y(s),r="gap-"+this.gapIdx;return this.inputs[r]=n,this.expected[r]=e.data,this.types[r]="string",n.addEventListener("keyup",()=>{this.student[r]=n.value.trim()}),this.showSolution&&(this.student[r]=n.value=this.expected[r]),this.gapIdx++,i.appendChild(n),i}case"input":case"input2":{let i=e.type==="input2",s=x("");s.style.verticalAlign="text-bottom";let n=e.data,r=this.src.instances[this.instanceIdx][n];if(this.expected[n]=r.value,this.types[n]=r.type,!i)switch(r.type){case"set":s.append(k("\\{"),x(" "));break;case"vector":s.append(k("["),x(" "));break}if(r.type==="vector"||r.type==="set"){let a=r.value.split(","),h=a.length;for(let c=0;c<h;c++){c>0&&s.appendChild(x(" , "));let p=y(Math.max(a[c].length*12,24));s.appendChild(p),p.addEventListener("keyup",()=>{this.student[n+"-"+c]=p.value.trim()}),this.showSolution&&(this.student[n+"-"+c]=p.value=a[c])}}else if(r.type==="matrix"){let a=new E;a.fromString(r.value);let h=document.createElement("table");s.appendChild(h);let c=a.getMaxCellStrlen();c=Math.max(c*12,24);for(let p=0;p<a.m;p++){let u=document.createElement("tr");h.appendChild(u),p==0&&u.appendChild(this.generateMatrixParenthesis(!0,a.m));for(let o=0;o<a.n;o++){let f=p*a.n+o,d=document.createElement("td");u.appendChild(d);let m=y(c);m.style.textAlign="end",d.appendChild(m),m.addEventListener("keyup",()=>{this.student[n+"-"+f]=m.value.trim()}),this.showSolution&&(this.student[n+"-"+f]=m.value=""+a.v[f])}p==0&&u.appendChild(this.generateMatrixParenthesis(!1,a.m))}}else if(r.type==="complex"){let a=r.value.split(",");for(let h=0;h<2;h++){let c=y(Math.max(Math.max(a[h].length*12,24),24));s.appendChild(c),this.showSolution&&(this.student[n+"-"+h]=c.value=a[h]),c.addEventListener("keyup",()=>{this.student[n+"-"+h]=c.value.trim()}),h==0?s.append(x(" "),k("+"),x(" ")):s.append(x(" "),k("i"))}}else{let a=y(Math.max(r.value.length*12,24));s.appendChild(a),a.addEventListener("keyup",()=>{this.student[n]=a.value.trim()}),this.showSolution&&(this.student[n]=a.value=r.value)}if(!i)switch(r.type){case"set":s.append(x(" "),k("\\}"));break;case"vector":s.append(x(" "),k("]"));break}return s}case"itemize":return D(e.children.map(i=>q(this.generateText(i))));case"single-choice":case"multi-choice":{let i=e.type=="multi-choice",s=document.createElement("table"),n=e.children.length,r=this.debug?W(n):j(n),a=i?P:U,h=i?H:F,c=[],p=[];for(let u=0;u<n;u++){let o=r[u],f=e.children[o],d="mc-"+this.choiceIdx+"-"+o;p.push(d);let m=f.children[0].data;this.expected[d]=m,this.types[d]="bool",this.student[d]=this.showSolution?m:"false";let O=this.generateText(f.children[1],!0),b=document.createElement("tr");s.appendChild(b),b.style.cursor="pointer";let M=document.createElement("td");c.push(M),b.appendChild(M),M.innerHTML=this.student[d]=="true"?a:h;let I=document.createElement("td");b.appendChild(I),I.appendChild(O),i?b.addEventListener("click",()=>{this.student[d]=this.student[d]==="true"?"false":"true",this.student[d]==="true"?M.innerHTML=a:M.innerHTML=h}):b.addEventListener("click",()=>{for(let C of p)this.student[C]="false";this.student[d]="true";for(let C=0;C<p.length;C++){let T=r[C];c[T].innerHTML=this.student[p[T]]=="true"?a:h}})}return this.choiceIdx++,s}default:{let i=x("UNIMPLEMENTED("+e.type+")");return i.style.color="red",i}}}};function J(l,e){e&&(document.getElementById("debug").style.display="block"),document.getElementById("title").innerHTML=l.title,document.getElementById("author").innerHTML=l.author,document.getElementById("courseInfo1").innerHTML=V[l.lang];let t='<span onclick="location.reload()" style="text-decoration: underline; font-weight: bold; cursor: pointer">'+_[l.lang]+"</span>";document.getElementById("courseInfo2").innerHTML=N[l.lang].replace("*",t);let i=[],s=document.getElementById("questions"),n=1;for(let r of l.questions){r.title=""+n+". "+r.title;let a=new A(r,e);a.showSolution=e,i.push(a),a.populateDom(s),e&&r.error.length==0&&a.checkBtn.click(),n++}}return G(X);})();sell.init(quizSrc,debug);</script> </html>  
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
    for question in out["questions"]:
        del question["text_src_html"]
        del question["python_src_html"]
    output_json = json.dumps(out)

    # write test output
    if debug:
        f = open(output_json_path, "w")
        f.write(output_debug_json)
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
