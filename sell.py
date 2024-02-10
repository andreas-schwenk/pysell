#!/usr/bin/env python3

"""SELL - Simple E-Learning Language
AUTHOR:  Andreas Schwenk <mailto:contact@compiler-construction.com>
LICENSE: GPLv3
"""

# TODO: test python program with indents

import json, sys, numpy, types


class Lexer:
    def __init__(self, src: str):
        self.src = src
        self.token = ""
        self.pos = 0
        self.next()

    def next(self):
        self.token = ""
        stop = False
        while not stop and self.pos < len(self.src):
            ch = self.src[self.pos]
            if ch in "#*$()[]{},.:;+-*/_!<> ":
                if len(self.token) > 0:
                    return
                stop = True
            self.token += ch
            self.pos += 1


# lex = Lexer("abc 123 *blub* $123$")
# while len(lex.token) > 0:
#    print(lex.token)
#    lex.next()
# exit(0)


class TextNode:

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
        #          input = "#" var;
        #          text = otherwise;
        span = TextNode("span")
        while lex.token != "":
            span.children.append(self.parse_item(lex))
        return span

    def parse_item(self, lex: Lexer):
        if lex.token == "*":
            return self.parse_bold(lex)
        elif lex.token == "$":
            return self.parse_math(lex)
        elif lex.token == "#":
            return self.parse_input(lex)
        else:
            n = TextNode("text", lex.token)
            lex.next()
            return n

    def parse_bold(self, lex: Lexer):
        bold = TextNode("bold")
        if lex.token == "*":
            lex.next()
        while lex.token != "" and lex.token != "*":
            bold.children.append(self.parse_item(lex))
        if lex.token == "*":
            lex.next()
        return bold

    def parse_math(self, lex: Lexer):
        math = TextNode("math")
        if lex.token == "$":
            lex.next()
        while lex.token != "" and lex.token != "$":
            math.children.append(self.parse_item(lex))
        if lex.token == "$":
            lex.next()
        return math

    def parse_input(self, lex: Lexer):
        input = TextNode("input")
        if lex.token == "#":
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
                and len(children_opt) > 0
                and children_opt[-1].type == "text"
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
    """quiz question instance"""

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
            for i in range(0, 5):
                # TODO: some or all instances may be equal!!
                res = self.run_python_code()
                self.instances.append(res)
        self.text = TextNode("root", self.text_src)
        self.text.parse()
        self.post_process_text(self.text)
        self.text.optimize()

    def post_process_text(self, node, math=False):
        for c in node.children:
            self.post_process_text(c, math or node.type == "math")
        if node.type == "input":
            var_id = node.data
            if var_id not in self.variables:
                self.error += "Unknown input variable '" + var_id + "'. "
        elif math and node.type == "text":
            var_id = node.data
            if var_id in self.variables:
                node.type = "var"

    def run_python_code(self) -> dict:
        locals = {}
        res = {}
        try:
            exec(self.python_src, globals(), locals)
        except Exception as e:
            # print(e)
            self.error += e + ". "
            return res
        for id in locals:
            value = locals[id]
            if isinstance(value, types.ModuleType):
                continue
            self.variables.add(id)
            if isinstance(value, numpy.matrix):
                rows, cols = value.shape
                v = numpy.array2string(value, separator=",").replace("\\n", "")
                # TODO: res
            elif isinstance(value, int):
                res[id] = {"type": "int", "value": str(value)}
            elif isinstance(value, float):
                res[id] = {"type": "float", "value": str(value)}
            elif isinstance(value, complex):
                v = str(value).replace("j", "i")
                if v.startswith("("):
                    v = v[1:-1]
                res[id] = {"type": "complex", "value": v}
            elif isinstance(value, set):
                res[id] = {"type": "set", "value": str(value)}
            else:
                res[id] = {"type": "unknown", "value": str(value)}
        return res

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "error": self.error,
            "variables": list(self.variables),
            "instances": self.instances,
            "text": self.text.to_dict(),
        }


def compile(src: str) -> str:
    """compiles an"""

    lines = src.split("\n")

    lang = "en"
    title = ""
    author = ""
    info = ""
    questions = []

    question = None
    parsing_python = False
    for line in lines:
        line = line.strip()
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
                    question.python_src += line + "\n"
                else:
                    question.text_src += line + "\n"
    for question in questions:
        question.build()
    output = {
        "lang": lang,
        "title": title,
        "author": author,
        "info": info,
        "questions": list(map(lambda o: o.to_dict(), questions)),
    }
    output_json = json.dumps(output)
    return output_json


# @begin(html)
html = """<!DOCTYPE html>
<html>
  <head>
    <meta charset="UTF-8" />
    <title>SELL Quiz</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />

    <link
      rel="stylesheet"
      href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css"
      integrity="sha384-n8MVd4RsNIU0tAv4ct0nTaAbDJwPJzDEaqSD1odI+WdtXRGWt2kTvGFasHpSy3SV"
      crossorigin="anonymous"
    />
    <script
      src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js"
      integrity="sha384-XjKyOOlGwcjNTAIQHIpgOno0Hl1YQqzUOEleOLALmuqehneUG+vnGctmUb0ZY0l8"
      crossorigin="anonymous"
    ></script>

    <style>
      html {
        font-family: Arial, Helvetica, sans-serif;
      }
      body {
        max-width: 1024px;
        margin-left: auto;
        margin-right: auto;
        padding-left: 5px;
        padding-right: 5px;
      }
      h1 {
        text-align: center;
        font-size: 28pt;
      }
      .author {
        text-align: center;
        font-size: 18pt;
      }
      .courseInfo {
        font-size: 14pt;
        font-style: italic;
        /*margin-bottom: 24px;*/
        text-align: center;
      }
      .question {
        border-style: solid;
        border-radius: 5px;
        border-width: 2px;
        border-color: black;
        padding: 8px;
        margin-top: 20px;
        margin-bottom: 20px;
        -webkit-box-shadow: 4px 6px 8px -1px rgba(0, 0, 0, 0.93);
        box-shadow: 4px 6px 8px -1px rgba(0, 0, 0, 0.1);
      }
      .questionTitle {
        font-size: 18pt;
        font-weight: bold;
      }
      ul {
        margin-top: 0;
        margin-left: 0px;
        padding-left: 20px;
      }
      .inputField {
        width: 64px;
        height: 24px;
        font-size: 14pt;
        border-style: solid;
        border-color: black;
        border-radius: 5px;
        border-width: 0.2;
        padding-left: 5px;
        padding-right: 5px;
        outline-color: black;
        background-color: transparent;
      }
      .inputField:focus {
        outline-color: gray;
      }
      .button {
        padding-left: 8px;
        padding-right: 8px;
        padding-top: 3px;
        padding-bottom: 3px;
        font-size: 12pt;
        /*background-color: rgba(62, 146, 3, 0.767);*/
        background-color: green;
        color: white;
        border-style: none;
        border-radius: 2px;
        height: 32px;
        cursor: pointer;
      }
      .buttonRow {
        display: flex;
        align-items: baseline;
      }
    </style>
  </head>
  <body>
    <h1 id="title"></h1>
    <div class="author" id="author"></div>
    <p class="courseInfo">
      This page runs in your browser and does not store any data on servers.
    </p>
    <p class="courseInfo">
      You can
      <span
        onclick="location.reload()"
        style="text-decoration: underline; font-weight: bold; cursor: pointer"
        >reload</span
      >
      this page in order to get new randomized tasks.
    </p>
    <div id="questions"></div>
    <p style="font-size: 8pt; font-style: italic; text-align: center">
      Technology: SELL Quiz by Andreas Schwenk
    </p>
    <script>
      let quizSrc = {};
      var sell=(()=>{var m=Object.defineProperty;var w=Object.getOwnPropertyDescriptor;var E=Object.getOwnPropertyNames;var C=Object.prototype.hasOwnProperty;var y=(l,t)=>{for(var s in t)m(l,s,{get:t[s],enumerable:!0})},L=(l,t,s,e)=>{if(t&&typeof t=="object"||typeof t=="function")for(let n of E(t))!C.call(l,n)&&n!==s&&m(l,n,{get:()=>t[n],enumerable:!(e=w(t,n))||e.enumerable});return l};var T=l=>L(m({},"__esModule",{value:!0}),l);var k={};y(k,{init:()=>V});var g='<svg xmlns="http://www.w3.org/2000/svg" height="28" viewBox="0 0 448 512"><path d="M384 80c8.8 0 16 7.2 16 16V416c0 8.8-7.2 16-16 16H64c-8.8 0-16-7.2-16-16V96c0-8.8 7.2-16 16-16H384zM64 32C28.7 32 0 60.7 0 96V416c0 35.3 28.7 64 64 64H384c35.3 0 64-28.7 64-64V96c0-35.3-28.7-64-64-64H64z"/></svg>',f='<svg xmlns="http://www.w3.org/2000/svg" height="28" viewBox="0 0 448 512"><path d="M64 80c-8.8 0-16 7.2-16 16V416c0 8.8 7.2 16 16 16H384c8.8 0 16-7.2 16-16V96c0-8.8-7.2-16-16-16H64zM0 96C0 60.7 28.7 32 64 32H384c35.3 0 64 28.7 64 64V416c0 35.3-28.7 64-64 64H64c-35.3 0-64-28.7-64-64V96zM337 209L209 337c-9.4 9.4-24.6 9.4-33.9 0l-64-64c-9.4-9.4-9.4-24.6 0-33.9s24.6-9.4 33.9 0l47 47L303 175c9.4-9.4 24.6-9.4 33.9 0s9.4 24.6 0 33.9z"/>',M='<svg xmlns="http://www.w3.org/2000/svg" height="25" viewBox="0 0 384 512" fill="white"><path d="M73 39c-14.8-9.1-33.4-9.4-48.5-.9S0 62.6 0 80V432c0 17.4 9.4 33.4 24.5 41.9s33.7 8.1 48.5-.9L361 297c14.3-8.7 23-24.2 23-41s-8.7-32.2-23-41L73 39z"/></svg>';function b(l){let t=new Array(l);for(let s=0;s<l;s++)t[s]=s;for(let s=0;s<l;s++){let e=Math.floor(Math.random()*l),n=Math.floor(Math.random()*l),i=t[e];t[e]=t[n],t[n]=i}return t}var x=class{constructor(t){this.src=t,this.instanceIdx=Math.floor(Math.random()*t.instances.length),this.choiceIdx=0,this.expectedValues={},this.expectedTypes={},this.studentValues={},this.qDiv=null}populateDom(t){this.qDiv=document.createElement("div"),t.appendChild(this.qDiv),this.qDiv.classList.add("question");let s=document.createElement("div");this.qDiv.appendChild(s),s.classList.add("questionTitle"),s.innerHTML=this.src.title;for(let a of this.src.text.children)this.qDiv.appendChild(this.generateText(a));let e=document.createElement("div");this.qDiv.appendChild(e),e.classList.add("buttonRow");let n=document.createElement("button");e.appendChild(n),n.type="button",n.classList.add("button"),n.innerHTML=M;let i=document.createElement("span");i.innerHTML="&nbsp;&nbsp;&nbsp;",e.appendChild(i);let c=document.createElement("span");e.appendChild(c),c.innerHTML="",n.addEventListener("click",()=>{let a=0,d=0;for(let r in this.expectedValues){console.log("comparing answer "+r);let h=this.expectedTypes[r];console.log("type = "+h);let p=this.studentValues[r];console.log("student = "+p);let o=this.expectedValues[r];switch(console.log("expected = "+o),h){case"int":case"bool":p==o&&d++;break;default:c.innerHTML="UNIMPLEMENTED EVAL OF TYPE "+h}a++}d==a?(c.style.color=n.style.backgroundColor=this.qDiv.style.borderColor="rgb(0,150,0)",this.qDiv.style.backgroundColor="rgba(0,150,0, 0.05)"):(c.style.color=n.style.backgroundColor=this.qDiv.style.borderColor="rgb(150,0,0)",this.qDiv.style.backgroundColor="rgba(150,0,0, 0.05)",a>=5&&(c.innerHTML=""+d+" / "+a))})}generateMathString(t){let s="";switch(t.type){case"math":{for(let e of t.children)s+=this.generateMathString(e);break}case"text":return t.data;case"var":return this.src.instances[this.instanceIdx][t.data].value}return s}generateText(t,s=!1){switch(t.type){case"paragraph":case"span":{let e=document.createElement(t.type=="span"||s?"span":"p");for(let n of t.children)e.appendChild(this.generateText(n));return e}case"text":{let e=document.createElement("span");return e.innerHTML=t.data,e}case"bold":{let e=document.createElement("span");e.style.fontWeight="bold";for(let n of t.children)e.appendChild(this.generateText(n));return e}case"math":{let e=document.createElement("span"),n=this.generateMathString(t);return katex.render(n,e,{throwOnError:!1}),e}case"input":{let e=document.createElement("span"),n=t.data,i=this.src.instances[this.instanceIdx][n];this.expectedValues[n]=i.value,this.expectedTypes[n]=i.type;let c=document.createElement("input");c.type="text",c.classList.add("inputField"),e.appendChild(c),c.addEventListener("keyup",()=>{this.studentValues[n]=c.value.trim()});let a=document.createElement("span");return a.innerHTML="&nbsp;",e.appendChild(a),e}case"itemize":{let e=document.createElement("ul");for(let n of t.children){let i=document.createElement("li");e.appendChild(i),i.appendChild(this.generateText(n))}return e}case"multi-choice":{let e=document.createElement("table"),n=t.children.length,i=b(n);for(let c=0;c<n;c++){let a=i[c],d=t.children[a],r="mc-"+this.choiceIdx+"-"+a,h=d.children[0].data;this.expectedValues[r]=h,this.expectedTypes[r]="bool",this.studentValues[r]="false";let p=this.generateText(d.children[1],!0),o=document.createElement("tr");e.appendChild(o),o.style.cursor="pointer";let u=document.createElement("td");o.appendChild(u),u.innerHTML=g;let v=document.createElement("td");o.appendChild(v),v.appendChild(p),o.addEventListener("click",()=>{this.studentValues[r]=this.studentValues[r]==="true"?"false":"true",this.studentValues[r]==="true"?u.innerHTML=f:u.innerHTML=g})}return this.choiceIdx++,e}default:{let e=document.createElement("span");return e.style.color="red",e.innerHTML="UNIMPLEMENTED("+t.type+")",e}}}};function V(l){document.getElementById("title").innerHTML=l.title,document.getElementById("author").innerHTML=l.author;let t=[],s=document.getElementById("questions");for(let e of l.questions){let n=new x(e);t.push(n),n.populateDom(s)}}return T(k);})();
      sell.init(quizSrc);
    </script>
  </body>
</html>
"""
# @end(html)


if __name__ == "__main__":

    # TODO: get path from args

    # read input
    f = open("examples/ex1.txt")
    src = f.read()
    f.close()
    # compile
    out = compile(src)
    # write output
    f = open("examples/ex1.json", "w")
    f.write(out)
    f.close()
    # write html
    f = open("examples/ex1.html", "w")
    f.write(html.replace("let quizSrc = {};", "let quizSrc = " + out + ";"))
    f.close()
    # exit normally
    sys.exit(0)
