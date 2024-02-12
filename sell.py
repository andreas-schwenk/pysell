#!/usr/bin/env python3

"""SELL - Simple E-Learning Language
AUTHOR:  Andreas Schwenk <mailto:contact@compiler-construction.com>
LICENSE: GPLv3
"""

import json, sys, numpy, types, sys, os

# TODO: publish python package
# TODO: debug output: show all python variable values
# TODO: matrix input, set input, complex numbers, ...


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
            if ch in "%#*$()[]{},.:;+-*/_!<> ":
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
        #          input = "%" var;
        #          text = otherwise;
        span = TextNode("span")
        while lex.token != "":
            span.children.append(self.parse_item(lex))
        return span

    def parse_item(self, lex: Lexer, allowInput=True):
        if lex.token == "*":
            return self.parse_bold(lex)
        elif lex.token == "$":
            return self.parse_math(lex)
        elif allowInput and lex.token == "%":
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
            math.children.append(self.parse_item(lex, False))
        if lex.token == "$":
            lex.next()
        return math

    def parse_input(self, lex: Lexer):
        input = TextNode("input")
        if lex.token == "%":
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
            self.error += str(e) + ". "
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
            elif isinstance(value, list):
                res[id] = {
                    "type": "vector",
                    "value": str(value).replace("[", "").replace("]", ""),
                }
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
html = """<!DOCTYPE html> <html> <head> <meta charset="UTF-8" /> <title>SELL Quiz</title> <meta name="viewport" content="width=device-width, initial-scale=1.0" />  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css" integrity="sha384-n8MVd4RsNIU0tAv4ct0nTaAbDJwPJzDEaqSD1odI+WdtXRGWt2kTvGFasHpSy3SV" crossorigin="anonymous" /> <script src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js" integrity="sha384-XjKyOOlGwcjNTAIQHIpgOno0Hl1YQqzUOEleOLALmuqehneUG+vnGctmUb0ZY0l8" crossorigin="anonymous" ></script>  <style> html { /*background-color: rgb(15, 15, 15);*/ font-family: Arial, Helvetica, sans-serif; } body { max-width: 1024px; margin-left: auto; margin-right: auto; padding-left: 5px; padding-right: 5px; } h1 { text-align: center; font-size: 28pt; } .author { text-align: center; font-size: 18pt; } .courseInfo { font-size: 14pt; font-style: italic; /*margin-bottom: 24px;*/ text-align: center; } .question { color: black; background-color: white; border-style: solid; border-radius: 5px; border-width: 3px; border-color: black; padding: 8px; margin-top: 20px; margin-bottom: 20px; -webkit-box-shadow: 4px 6px 8px -1px rgba(0, 0, 0, 0.93); box-shadow: 4px 6px 8px -1px rgba(0, 0, 0, 0.1); } .questionTitle { font-size: 24pt; } ul { margin-top: 0; margin-left: 0px; padding-left: 20px; } .inputField { width: 64px; height: 24px; font-size: 14pt; border-style: solid; border-color: black; border-radius: 5px; border-width: 0.2; padding-left: 5px; padding-right: 5px; outline-color: black; background-color: transparent; } .inputField:focus { outline-color: maroon; } .button { padding-left: 8px; padding-right: 8px; padding-top: 5px; padding-bottom: 5px; font-size: 12pt; /*background-color: rgba(62, 146, 3, 0.767);*/ background-color: green; color: white; border-style: none; border-radius: 4px; height: 36px; cursor: pointer; } .buttonRow { display: flex; align-items: baseline; margin-top: 12px; } </style> </head> <body> <h1 id="title"></h1> <div class="author" id="author"></div> <p id="courseInfo1" class="courseInfo"></p> <p id="courseInfo2" class="courseInfo"></p> <h1 id="debug" style="font-size: 12pt; color: red; display: none"> !! DEBUG VERSION !! </h1> <div id="questions"></div> <p style="font-size: 8pt; font-style: italic; text-align: center"> Technology: SELL Quiz by Andreas Schwenk </p> <script>let debug = false; let quizSrc = {};var sell=(()=>{var v=Object.defineProperty;var z=Object.getOwnPropertyDescriptor;var V=Object.getOwnPropertyNames;var A=Object.prototype.hasOwnProperty;var U=(i,e)=>{for(var l in e)v(i,l,{get:e[l],enumerable:!0})},P=(i,e,l,t)=>{if(e&&typeof e=="object"||typeof e=="function")for(let n of V(e))!A.call(i,n)&&n!==l&&v(i,n,{get:()=>e[n],enumerable:!(t=z(e,n))||t.enumerable});return i};var N=i=>P(v({},"__esModule",{value:!0}),i);var K={};U(K,{init:()=>Y});var C='<svg xmlns="http://www.w3.org/2000/svg" height="28" viewBox="0 0 448 512"><path d="M384 80c8.8 0 16 7.2 16 16V416c0 8.8-7.2 16-16 16H64c-8.8 0-16-7.2-16-16V96c0-8.8 7.2-16 16-16H384zM64 32C28.7 32 0 60.7 0 96V416c0 35.3 28.7 64 64 64H384c35.3 0 64-28.7 64-64V96c0-35.3-28.7-64-64-64H64z"/></svg>',L='<svg xmlns="http://www.w3.org/2000/svg" height="28" viewBox="0 0 448 512"><path d="M64 80c-8.8 0-16 7.2-16 16V416c0 8.8 7.2 16 16 16H384c8.8 0 16-7.2 16-16V96c0-8.8-7.2-16-16-16H64zM0 96C0 60.7 28.7 32 64 32H384c35.3 0 64 28.7 64 64V416c0 35.3-28.7 64-64 64H64c-35.3 0-64-28.7-64-64V96zM337 209L209 337c-9.4 9.4-24.6 9.4-33.9 0l-64-64c-9.4-9.4-9.4-24.6 0-33.9s24.6-9.4 33.9 0l47 47L303 175c9.4-9.4 24.6-9.4 33.9 0s9.4 24.6 0 33.9z"/>',b='<svg xmlns="http://www.w3.org/2000/svg" height="28" viewBox="0 0 512 512"><path d="M464 256A208 208 0 1 0 48 256a208 208 0 1 0 416 0zM0 256a256 256 0 1 1 512 0A256 256 0 1 1 0 256z"/></svg>',T='<svg xmlns="http://www.w3.org/2000/svg" height="28" viewBox="0 0 512 512"><path d="M256 48a208 208 0 1 1 0 416 208 208 0 1 1 0-416zm0 464A256 256 0 1 0 256 0a256 256 0 1 0 0 512zM369 209c9.4-9.4 9.4-24.6 0-33.9s-24.6-9.4-33.9 0l-111 111-47-47c-9.4-9.4-24.6-9.4-33.9 0s-9.4 24.6 0 33.9l64 64c9.4 9.4 24.6 9.4 33.9 0L369 209z"/></svg>',I='<svg xmlns="http://www.w3.org/2000/svg" height="25" viewBox="0 0 384 512" fill="white"><path d="M73 39c-14.8-9.1-33.4-9.4-48.5-.9S0 62.6 0 80V432c0 17.4 9.4 33.4 24.5 41.9s33.7 8.1 48.5-.9L361 297c14.3-8.7 23-24.2 23-41s-8.7-32.2-23-41L73 39z"/></svg>';var D={de:"Diese Seite wird in Ihrem Browser ausgef\xFChrt und speichert keine Daten auf Servern.",en:"This page runs in your browser and does not store any data on servers."},H={de:"Sie k\xF6nnen diese Seite *, um neue randomisierte Aufgaben zu erhalten.",en:"You can * this page in order to get new randomized tasks."},B={de:"aktualisieren",en:"reload"};function F(i){let e=new Array(i);for(let l=0;l<i;l++)e[l]=l;for(let l=0;l<i;l++){let t=Math.floor(Math.random()*i),n=Math.floor(Math.random()*i),s=e[t];e[t]=e[n],e[n]=s}return e}function q(){let i=document.createElement("input");return i.type="text",i.classList.add("inputField"),i}function f(i){let e=document.createElement("span");return e.innerHTML=i,e}function O(i){let e=document.createElement("span");return katex.render(i,e,{throwOnError:!1}),e}var x=class{constructor(e){this.src=e,this.instanceIdx=Math.floor(Math.random()*e.instances.length),this.choiceIdx=0,this.expected={},this.types={},this.student={},this.qDiv=null,this.titleDiv=null,this.checkBtn=null,this.showSolution=!1}populateDom(e){if(this.qDiv=document.createElement("div"),e.appendChild(this.qDiv),this.qDiv.classList.add("question"),this.titleDiv=document.createElement("div"),this.qDiv.appendChild(this.titleDiv),this.titleDiv.classList.add("questionTitle"),this.titleDiv.innerHTML=this.src.title,this.src.error.length>0){let s=document.createElement("span");this.qDiv.appendChild(s),s.style.color="red",s.innerHTML=this.src.error;return}for(let s of this.src.text.children)this.qDiv.appendChild(this.generateText(s));let l=document.createElement("div");this.qDiv.appendChild(l),l.classList.add("buttonRow"),this.checkBtn=document.createElement("button"),l.appendChild(this.checkBtn),this.checkBtn.type="button",this.checkBtn.classList.add("button"),this.checkBtn.innerHTML=I;let t=document.createElement("span");t.innerHTML="&nbsp;&nbsp;&nbsp;",l.appendChild(t);let n=document.createElement("span");l.appendChild(n),this.checkBtn.addEventListener("click",()=>{n.innerHTML="";let s=0,r=0;for(let o in this.expected){let c=this.types[o],a=this.student[o],d=this.expected[o];switch(c){case"int":case"bool":a==d&&r++;break;default:n.innerHTML="UNIMPLEMENTED EVAL OF TYPE "+c}s++}r==s?(n.style.color=this.titleDiv.style.color=this.checkBtn.style.backgroundColor=this.qDiv.style.borderColor="rgb(0,150,0)",this.qDiv.style.backgroundColor="rgba(0,150,0, 0.025)"):(this.titleDiv.style.color=n.style.color=this.checkBtn.style.backgroundColor=this.qDiv.style.borderColor="rgb(150,0,0)",this.qDiv.style.backgroundColor="rgba(150,0,0, 0.025)",s>=5&&(n.innerHTML=""+r+" / "+s))})}generateMathString(e){let l="";switch(e.type){case"math":{for(let t of e.children)l+=this.generateMathString(t);break}case"text":return e.data;case"var":return this.src.instances[this.instanceIdx][e.data].value}return l}generateText(e,l=!1){switch(e.type){case"paragraph":case"span":{let t=document.createElement(e.type=="span"||l?"span":"p");for(let n of e.children)t.appendChild(this.generateText(n));return t}case"text":{let t=document.createElement("span");return t.innerHTML=e.data,t}case"bold":{let t=document.createElement("span");t.style.fontWeight="bold";for(let n of e.children)t.appendChild(this.generateText(n));return t}case"math":{let t=this.generateMathString(e);return O(t)}case"input":{let t=document.createElement("span"),n=e.data,s=this.src.instances[this.instanceIdx][n];if(s.type=="vector"){let r=s.value.split(",").map(c=>c.trim()),o=r.length;t.appendChild(f(" "));for(let c=0;c<o;c++){this.expected[n+c]=r[c],this.types[n+c]="int",c>0&&t.appendChild(f(" , "));let a=q();t.appendChild(a),a.addEventListener("keyup",()=>{this.student[n+c]=a.value.trim()}),this.showSolution&&(this.student[n+c]=a.value=r[c])}t.appendChild(f(" "))}else{this.expected[n]=s.value,this.types[n]=s.type;let r=q();t.appendChild(r),r.addEventListener("keyup",()=>{this.student[n]=r.value.trim()}),this.showSolution&&(this.student[n]=r.value=s.value)}return t}case"itemize":{let t=document.createElement("ul");for(let n of e.children){let s=document.createElement("li");t.appendChild(s),s.appendChild(this.generateText(n))}return t}case"single-choice":case"multi-choice":{let t=e.type=="multi-choice",n=document.createElement("table"),s=e.children.length,r=F(s),o=t?L:T,c=t?C:b,a=[],d=[];for(let g=0;g<s;g++){let w=r[g],M=e.children[w],h="mc-"+this.choiceIdx+"-"+w;d.push(h);let y=M.children[0].data;this.expected[h]=y,this.types[h]="bool",this.student[h]=this.showSolution?y:"false";let S=this.generateText(M.children[1],!0),u=document.createElement("tr");n.appendChild(u),u.style.cursor="pointer";let p=document.createElement("td");a.push(p),u.appendChild(p),p.innerHTML=this.student[h]=="true"?o:c;let E=document.createElement("td");u.appendChild(E),E.appendChild(S),t?u.addEventListener("click",()=>{this.student[h]=this.student[h]==="true"?"false":"true",this.student[h]==="true"?p.innerHTML=o:p.innerHTML=c}):u.addEventListener("click",()=>{for(let m of d)this.student[m]="false";this.student[h]="true";for(let m=0;m<d.length;m++){let k=r[m];a[k].innerHTML=this.student[d[k]]=="true"?o:c}})}return this.choiceIdx++,n}default:{let t=document.createElement("span");return t.style.color="red",t.innerHTML="UNIMPLEMENTED("+e.type+")",t}}}};function Y(i,e){e&&(document.getElementById("debug").style.display="block"),document.getElementById("title").innerHTML=i.title,document.getElementById("author").innerHTML=i.author,document.getElementById("courseInfo1").innerHTML=D[i.lang];let l='<span onclick="location.reload()" style="text-decoration: underline; font-weight: bold; cursor: pointer">'+B[i.lang]+"</span>";document.getElementById("courseInfo2").innerHTML=H[i.lang].replace("*",l);let t=[],n=document.getElementById("questions");for(let s of i.questions){let r=new x(s);r.showSolution=e,t.push(r),r.populateDom(n),e&&s.error.length==0&&r.checkBtn.click()}}return N(K);})();sell.init(quizSrc,debug);</script> </html>  
"""
# @end(html)


if __name__ == "__main__":
    # get input and output path
    if len(sys.argv) < 2:
        print("usage: python sell.py [-D] INPUT_PATH.txt")
        exit(-1)
    debug = "-D" in sys.argv
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
    # write test output
    if debug:
        f = open(output_json_path, "w")
        f.write(out)
        f.close()
    # write html
    # (a) release version (*.html)
    f = open(output_path, "w")
    f.write(html.replace("let quizSrc = {};", "let quizSrc = " + out + ";"))
    f.close()
    # (a) debug version (*_DEBUG.html)
    f = open(output_debug_path, "w")
    f.write(
        html.replace("let quizSrc = {};", "let quizSrc = " + out + ";").replace(
            "let debug = false;", "let debug = true;"
        )
    )
    f.close()
    # exit normally
    sys.exit(0)
