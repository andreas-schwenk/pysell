#!/usr/bin/env python3

"""
======= pySELL =================================================================
        
        A Python based Simple E-Learning Language 
        for the simple creation of interactive courses

LICENSE GPLv3

AUTHOR  Andreas Schwenk <mailto:contact@compiler-construction.com>

DOCS    Refer to https://github.com/andreas-schwenk/pysell and read the
        descriptions at the end of the page

USAGE   Only file 'sell.py' is required to compile question files
        
        COMMAND    python3 [-J] sell.py PATH
        ARGUMENTS  -J is optional and generates a JSON output file for debugging        
        EXAMPLE    python3 sell.py examples/ex1.txt
        OUTPUT     examples/ex1.html, examples/ex1_DEBUG.html
"""


# TODO: embed variables into string via "{v}"


import json, sys, os, re
from typing import Self
from datetime import datetime


class Lexer:
    """Scanner that takes a string input and returns a sequence of tokens;
    one at a time."""

    def __init__(self, src: str) -> None:
        """sets the source to be scanned"""
        # the source code
        self.src: str = src
        # the current token
        self.token: str = ""
        # the current input position
        self.pos: int = 0
        # set the first token to self.token
        self.next()

    def next(self) -> None:
        """gets the next token"""
        # start with a fresh token
        self.token = ""
        # loop up to the next special character
        stop = False
        while not stop and self.pos < len(self.src):
            # get the next character from the input
            ch = self.src[self.pos]
            # in case that we get a special character (a.k.a delimiter),
            # we stop
            if ch in "`^'\"%#*$()[]\{\}\\,.:;+-*/_!<>\t\n =?|&":
                # if the current token is not empty, return it for now and
                # keep the delimiter to the next call of next()
                if len(self.token) > 0:
                    return
                # a delimiter stops further advancing in the input
                stop = True
                # keep quotes as a single token. Supported quote types are
                # double quotes ("...") and accent grave quotes (`...`)
                if ch in '"`':
                    kind = ch  # " or `
                    self.token += ch
                    self.pos += 1
                    # advance to the quotation end
                    while self.pos < len(self.src):
                        if self.src[self.pos] == kind:
                            break
                        self.token += self.src[self.pos]
                        self.pos += 1
            # add the current character to the token
            self.token += ch
            self.pos += 1


# # lexer tests
# lex = Lexer('a"x"bc 123 *blub* $`hello, world!`123$')
# while len(lex.token) > 0:
#     print(lex.token)
#     lex.next()
# exit(0)

# For drawing random variables and to calculate the sample solution, we will
# be executing Python code that is embedded in the quiz descriptions.
# The evaluation of code will populate local variables. Its data types also
# depend on the used libraries.
# The following lists cluster some of these types.
boolean_types = ["<class 'bool'>", "<class 'numpy.bool_'>"]
int_types = [
    "<class 'int'>",
    "<class 'numpy.int64'>",
    "<class 'sympy.core.numbers.Integer'>",
    "<class 'sage.rings.integer.Integer'>",
    "<class 'sage.rings.finite_rings.integer_mod.IntegerMod_int'>",
]
float_types = ["<class 'float'>"]

# The following list contains all of Pythons basic keywords. These are used
# in syntax highlighting in "*_DEBUG.html" files.
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

# The following list of identifiers may be in locals of Python source that
# uses "sympy". These identifiers must be skipped in the JSON output.
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

# The following (stringified) function rangeZ is provided as pseudo-intrinsic
# function in Python scripts, embedded into the question descriptions.
# It is an alternative version for "range", that excludes the zero.
# This is beneficial for drawing random numbers of questions for math classes.

# TODO: define directly?? should also be available in executed programs!?!
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

# TODO: add comments starting from here


class TextNode:
    """Tree structure for the question text"""

    def __init__(self, type: str, data: str = "") -> None:
        self.type: str = type
        self.data: str = data
        self.children: list[TextNode] = []

    def parse(self) -> None:
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
        # t := type, d := data, c := children
        return {
            "t": self.type,
            "d": self.data,
            "c": list(map(lambda o: o.to_dict(), self.children)),
        }


class Question:
    """Question of the quiz"""

    def __init__(self, src_line_no: int) -> None:
        self.src_line_no: int = src_line_no
        self.title: str = ""
        self.python_src: str = ""
        self.variables: set[str] = set()
        self.instances: list[dict] = []
        self.text_src: str = ""
        self.text: TextNode = None
        self.error: str = ""
        self.python_src_tokens: set[str] = set()

    def build(self) -> None:
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

    def post_process_text(self, node: TextNode, math=False) -> None:
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

    def float_to_str(self, v: float) -> str:
        """Converts float to string and cuts '.0' if applicable"""
        s = str(v)
        if s.endswith(".0"):
            return s[:-2]
        return s

    def analyze_python_code(self) -> None:
        """Get all tokens from Python source code. This is required to filter
        out all locals from libraries (refer to method run_python_code).
        Since relevant tokens are only those in the left-hand side of an
        assignment, we filter out non-assignment statements, as well as
        the right-hand side of statements. As a side effect, irrelevant symbols
        of packages are also filtered out (e.g. 'mod', is populated to the
        locals, when using 'sage.all.power_mod')"""
        lines = self.python_src.split("\n")
        for line in lines:
            if "=" not in line:
                continue
            lhs = line.split("=")[0]
            lex = Lexer(lhs)
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
            t = ""  # type
            v = ""  # value
            if type_str in boolean_types:
                t = "bool"
                v = str(value).lower()
            elif type_str in int_types:
                t = "int"
                v = str(value)
            elif type_str in float_types:
                t = "float"
                v = self.float_to_str(value)
            elif type_str == "<class 'complex'>":
                t = "complex"
                v = self.float_to_str(value.real) + "," + self.float_to_str(value.imag)
            elif type_str == "<class 'list'>":
                t = "vector"
                v = str(value).replace("[", "").replace("]", "").replace(" ", "")
            elif type_str == "<class 'set'>":
                t = "set"
                v = str(value).replace("{", "").replace("}", "").replace(" ", "")
            elif type_str == "<class 'sympy.matrices.dense.MutableDenseMatrix'>":
                # e.g. 'Matrix([[-1, 0, -2], [-1, 5*sin(x)*cos(x)/7, 2], [-1, 2, 0]])'
                t = "matrix"
                v = str(value)[7:-1]
            elif (
                type_str == "<class 'numpy.matrix'>"
                or type_str == "<class 'numpy.ndarray'>"
            ):
                # e.g. '[[ -6 -13 -12]\n [-17  -3 -20]\n [-14  -8 -16]\n [ -7 -15  -8]]'
                t = "matrix"
                v = re.sub(" +", " ", str(value))  # remove double spaces
                v = re.sub("\[ ", "[", v)  # remove space(s) after "["
                v = re.sub(" \]", "]", v)  # remove space(s) before "]"
                v = v.replace(" ", ",").replace("\n", "")
            else:
                t = "term"
                v = str(value).replace("**", "^")
            # t := type, v := value
            res[id] = {"t": t, "v": v}
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
        "date": datetime.today().strftime("%Y-%m-%d"),
        "info": info,
        "questions": list(map(lambda o: o.to_dict(), questions)),
    }


# the following code is automatically generated and updated by file "build.py"
# @begin(html)
html = b''
html += b'<!DOCTYPE html> <html> <head> <meta charset="UTF-8" /> <titl'
html += b'e>pySELL Quiz</title> <meta name="viewport" content="width=d'
html += b'evice-width, initial-scale=1.0" /> <link rel="icon" type="im'
html += b'age/x-icon" href="data:image/x-icon;base64,AAABAAEAEBAAAAEAI'
html += b'ABoBAAAFgAAACgAAAAQAAAAIAAAAAEAIAAAAAAAAAQAAAAAAAAAAAAAAAAAA'
html += b'AAAAACqqqr/PDw8/0VFRf/V1dX////////////09Pb/trbO/3t7q/9wcLH/c'
html += b'XG0/3NzqP+iosH/5OTr////////////j4+P/wAAAP8KCgr/x8fH///////k5'
html += b'Or/bGym/y4ukP8kJJD/IiKR/yIikv8jI5H/KCiP/1BQnP/Jydz//////5CQk'
html += b'P8BAQH/DAwM/8jIyP/7+/v/cHCo/yIij/8lJZP/KSmR/z4+lf9AQJH/Li6Q/'
html += b'yUlkv8jI5H/TEya/9/f6P+QkJD/AQEB/wwMDP/Ly8r/ycna/y4ujv8lJZP/N'
html += b'DSU/5+fw//j4+v/5+fs/76+0v9LS5f/JSWS/yYmkP+Skrr/kJCQ/wAAAP8MD'
html += b'Az/zc3L/5aWvP8iIo//ISGQ/39/sf////7/////////////////n5+7/yMjj'
html += b'P8kJJH/bm6p/5CQkP8BAQH/CgoK/6SkpP+Skp//XV2N/1dXi//Hx9X//////'
html += b'///////////9fX1/39/rP8kJI7/JCSR/25upP+QkJD/AQEB/wEBAf8ODg7/F'
html += b'BQT/xUVE/8hIR//XV1c/8vL0P/IyNv/lZW7/1panP8rK5D/JiaT/ycnjv+bm'
html += b'7v/kJCQ/wEBAf8AAAD/AAAA/wAAAP8AAAD/AAAH/wAAK/8aGmv/LCyO/yQkj'
html += b'/8jI5L/JSWT/yIikP9dXZ//6enu/5CQkP8BAQH/BQUF/0xMTP9lZWT/Pz9N/'
html += b'wUFVP8AAGz/AABu/xYWhf8jI5L/JCSP/zY2k/92dq7/4ODo//////+QkJD/A'
html += b'QEB/wwMDP/IyMj//Pz9/2lppf8ZGYf/AgJw/wAAZ/8cHHL/Zmak/5ubv//X1'
html += b'+T//v7+////////////kJCQ/wEBAf8MDAz/ycnJ/9/f6f85OZT/IyOR/wcHZ'
html += b'P8AAB7/UVFZ//n5+P//////0dHd/7i4yf++vs7/7e3z/5CQkP8AAAD/DAwM/'
html += b'87Ozf/Y2OP/MjKQ/x8fjv8EBEr/AAAA/1xcWv//////6ent/0tLlf8kJIn/M'
html += b'jKL/8fH2v+QkJD/AQEB/wcHB/98fHv/jo6T/yUlc/8JCXj/AABi/wAAK/9eX'
html += b'nj/trbS/2xspv8nJ5H/IyOT/0pKm//m5uz/kJCQ/wEBAf8AAAD/AAAA/wAAA'
html += b'P8AACH/AABk/wAAbf8EBHD/IyOM/ykpkv8jI5H/IyOS/ysrjP+kpMP//////'
html += b'5GRkf8CAgL/AQEB/wEBAf8BAQH/AgIE/woKK/8ZGWj/IyOG/ycnj/8nJ4//M'
html += b'DCS/0xMmf+lpcP/+vr6///////Pz8//kZGR/5CQkP+QkJD/kJCQ/5OTk/+ws'
html += b'K//zs7V/8LC2f+goL3/oaG+/8PD2P/n5+z/////////////////AAAAAAAAA'
html += b'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
html += b'AAAAAAAAAAAAAAAAA==" sizes="16x16" /> <link rel="stylesheet"'
html += b' href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.'
html += b'min.css" integrity="sha384-n8MVd4RsNIU0tAv4ct0nTaAbDJwPJzDEa'
html += b'qSD1odI+WdtXRGWt2kTvGFasHpSy3SV" crossorigin="anonymous" /> '
html += b'<script src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/'
html += b'katex.min.js" integrity="sha384-XjKyOOlGwcjNTAIQHIpgOno0Hl1Y'
html += b'QqzUOEleOLALmuqehneUG+vnGctmUb0ZY0l8" crossorigin="anonymous'
html += b'" ></script> <style> html { font-family: Arial, Helvetica, s'
html += b'ans-serif; } body { max-width: 1024px; margin-left: auto; ma'
html += b'rgin-right: auto; padding-left: 5px; padding-right: 5px; } h'
html += b'1 { text-align: center; font-size: 28pt; } .author { text-al'
html += b'ign: center; font-size: 18pt; } .courseInfo { font-size: 14p'
html += b't; font-style: italic; /*margin-bottom: 24px;*/ text-align: '
html += b'center; } .question { position: relative; /* required for fe'
html += b'edback overlays */ color: black; background-color: white; bo'
html += b'rder-style: solid; border-radius: 5px; border-width: 3px; bo'
html += b'rder-color: black; padding: 8px; margin-top: 20px; margin-bo'
html += b'ttom: 20px; -webkit-box-shadow: 4px 6px 8px -1px rgba(0, 0, '
html += b'0, 0.93); box-shadow: 4px 6px 8px -1px rgba(0, 0, 0, 0.1); }'
html += b' .questionFeedback { z-index: 10; display: none; position: a'
html += b'bsolute; pointer-events: none; left: 0; top: 33%; width: 100'
html += b'%; height: 100%; text-align: center; font-size: 8vw; text-sh'
html += b'adow: 0px 0px 18px rgba(0, 0, 0, 0.7); } .questionTitle { fo'
html += b'nt-size: 24pt; } .code { font-family: "Courier New", Courier'
html += b', monospace; color: black; background-color: rgb(235, 235, 2'
html += b'35); padding: 2px 5px; border-radius: 5px; margin: 1px 2px; '
html += b'} .debugCode { font-family: "Courier New", Courier, monospac'
html += b'e; padding: 4px; margin-bottom: 5px; background-color: black'
html += b'; color: white; border-radius: 5px; opacity: 0.85; overflow-'
html += b'x: scroll; } .debugInfo { text-align: end; font-size: 10pt; '
html += b'margin-top: 2px; color: rgb(64, 64, 64); } ul { margin-top: '
html += b'0; margin-left: 0px; padding-left: 20px; } .inputField { pos'
html += b'ition: relative; width: 32px; height: 24px; font-size: 14pt;'
html += b' border-style: solid; border-color: black; border-radius: 5p'
html += b'x; border-width: 0.2; padding-left: 5px; padding-right: 5px;'
html += b' outline-color: black; background-color: transparent; margin'
html += b': 1px; } .inputField:focus { outline-color: maroon; } .equat'
html += b'ionPreview { position: absolute; top: 120%; left: 0%; paddin'
html += b'g-left: 8px; padding-right: 8px; padding-top: 4px; padding-b'
html += b'ottom: 4px; background-color: rgb(128, 0, 0); border-radius:'
html += b' 5px; font-size: 12pt; color: white; text-align: start; z-in'
html += b'dex: 20; opacity: 0.95; } .button { padding-left: 8px; paddi'
html += b'ng-right: 8px; padding-top: 5px; padding-bottom: 5px; font-s'
html += b'ize: 12pt; background-color: rgb(0, 150, 0); color: white; b'
html += b'order-style: none; border-radius: 4px; height: 36px; cursor:'
html += b' pointer; } .buttonRow { display: flex; align-items: baselin'
html += b'e; margin-top: 12px; } .matrixResizeButton { width: 20px; ba'
html += b'ckground-color: black; color: #fff; text-align: center; bord'
html += b'er-radius: 3px; position: absolute; z-index: 1; height: 20px'
html += b'; cursor: pointer; margin-bottom: 3px; } a { color: black; t'
html += b'ext-decoration: underline; } </style> </head> <body> <h1 id='
html += b'"title"></h1> <div class="author" id="author"></div> <p id="'
html += b'courseInfo1" class="courseInfo"></p> <p id="courseInfo2" cla'
html += b'ss="courseInfo"></p> <h1 id="debug" class="debugCode" style='
html += b'"display: none">DEBUG VERSION</h1> <div id="questions"></div'
html += b'> <p style="font-size: 8pt; font-style: italic; text-align: '
html += b'center"> This quiz was created using <a href="https://github'
html += b'.com/andreas-schwenk/pysell">pySELL</a>, the <i>Python-based'
html += b' Simple E-Learning Language</i>, written by Andreas Schwenk,'
html += b' GPLv3<br /> last update on <span id="date"></span> </p> <sc'
html += b'ript>let debug = false; let quizSrc = {};var sell=(()=>{var '
html += b'A=Object.defineProperty;var $=Object.getOwnPropertyDescripto'
html += b'r;var ee=Object.getOwnPropertyNames;var te=Object.prototype.'
html += b'hasOwnProperty;var ie=(r,e)=>{for(var t in e)A(r,t,{get:e[t]'
html += b',enumerable:!0})},se=(r,e,t,s)=>{if(e&&typeof e=="object"||t'
html += b'ypeof e=="function")for(let i of ee(e))!te.call(r,i)&&i!==t&'
html += b'&A(r,i,{get:()=>e[i],enumerable:!(s=$(e,i))||s.enumerable});'
html += b'return r};var ne=r=>se(A({},"__esModule",{value:!0}),r);var '
html += b'ae={};ie(ae,{init:()=>re});function g(r=[]){let e=document.c'
html += b'reateElement("div");return e.append(...r),e}function W(r=[])'
html += b'{let e=document.createElement("ul");return e.append(...r),e}'
html += b'function N(r){let e=document.createElement("li");return e.ap'
html += b'pendChild(r),e}function L(r){let e=document.createElement("i'
html += b'nput");return e.spellcheck=!1,e.type="text",e.classList.add('
html += b'"inputField"),e.style.width=r+"px",e}function U(){let r=docu'
html += b'ment.createElement("button");return r.type="button",r.classL'
html += b'ist.add("button"),r}function f(r,e=[]){let t=document.create'
html += b'Element("span");return e.length>0?t.append(...e):t.innerHTML'
html += b'=r,t}function B(r,e,t=!1){katex.render(e,r,{throwOnError:!1,'
html += b'displayMode:t,macros:{"\\\\RR":"\\\\mathbb{R}","\\\\NN":"\\\\mathbb{'
html += b'N}","\\\\QQ":"\\\\mathbb{Q}","\\\\ZZ":"\\\\mathbb{Z}"}})}function M('
html += b'r,e=!1){let t=document.createElement("span");return B(t,r,e)'
html += b',t}var z={en:"This page runs in your browser and does not st'
html += b'ore any data on servers.",de:"Diese Seite wird in Ihrem Brow'
html += b'ser ausgef\\xFChrt und speichert keine Daten auf Servern.",es'
html += b':"Esta p\\xE1gina se ejecuta en su navegador y no almacena ni'
html += b'ng\\xFAn dato en los servidores.",it:"Questa pagina viene ese'
html += b'guita nel browser e non memorizza alcun dato sui server.",fr'
html += b':"Cette page fonctionne dans votre navigateur et ne stocke a'
html += b'ucune donn\\xE9e sur des serveurs."},F={en:"You can * this pa'
html += b'ge in order to get new randomized tasks.",de:"Sie k\\xF6nnen '
html += b'diese Seite *, um neue randomisierte Aufgaben zu erhalten.",'
html += b'es:"Puedes * esta p\\xE1gina para obtener nuevas tareas aleat'
html += b'orias.",it:"\\xC8 possibile * questa pagina per ottenere nuov'
html += b'i compiti randomizzati",fr:"Vous pouvez * cette page pour ob'
html += b'tenir de nouvelles t\\xE2ches al\\xE9atoires"},j={en:"reload",'
html += b'de:"aktualisieren",es:"recargar",it:"ricaricare",fr:"recharg'
html += b'er"},O={en:["awesome","great","well done","nice","you got it'
html += b'","good"],de:["super","gut gemacht","weiter so","richtig"],e'
html += b's:["impresionante","genial","correcto","bien hecho"],it:["fa'
html += b'ntastico","grande","corretto","ben fatto"],fr:["g\\xE9nial","'
html += b'super","correct","bien fait"]},_={en:["try again","still som'
html += b'e mistakes","wrong answer","no"],de:["leider falsch","nicht '
html += b'richtig","versuch\'s nochmal"],es:["int\\xE9ntalo de nuevo","t'
html += b'odav\\xEDa algunos errores","respuesta incorrecta"],it:["ripr'
html += b'ova","ancora qualche errore","risposta sbagliata"],fr:["r\\xE'
html += b'9essayer","encore des erreurs","mauvaise r\\xE9ponse"]};funct'
html += b'ion Z(r,e){let t=Array(e.length+1).fill(null).map(()=>Array('
html += b'r.length+1).fill(null));for(let s=0;s<=r.length;s+=1)t[0][s]'
html += b'=s;for(let s=0;s<=e.length;s+=1)t[s][0]=s;for(let s=1;s<=e.l'
html += b'ength;s+=1)for(let i=1;i<=r.length;i+=1){let a=r[i-1]===e[s-'
html += b'1]?0:1;t[s][i]=Math.min(t[s][i-1]+1,t[s-1][i]+1,t[s-1][i-1]+'
html += b'a)}return t[e.length][r.length]}var q=\'<svg xmlns="http://ww'
html += b'w.w3.org/2000/svg" height="28" viewBox="0 0 448 512"><path d'
html += b'="M384 80c8.8 0 16 7.2 16 16V416c0 8.8-7.2 16-16 16H64c-8.8 '
html += b'0-16-7.2-16-16V96c0-8.8 7.2-16 16-16H384zM64 32C28.7 32 0 60'
html += b'.7 0 96V416c0 35.3 28.7 64 64 64H384c35.3 0 64-28.7 64-64V96'
html += b'c0-35.3-28.7-64-64-64H64z"/></svg>\',K=\'<svg xmlns="http://ww'
html += b'w.w3.org/2000/svg" height="28" viewBox="0 0 448 512"><path d'
html += b'="M64 80c-8.8 0-16 7.2-16 16V416c0 8.8 7.2 16 16 16H384c8.8 '
html += b'0 16-7.2 16-16V96c0-8.8-7.2-16-16-16H64zM0 96C0 60.7 28.7 32'
html += b' 64 32H384c35.3 0 64 28.7 64 64V416c0 35.3-28.7 64-64 64H64c'
html += b'-35.3 0-64-28.7-64-64V96zM337 209L209 337c-9.4 9.4-24.6 9.4-'
html += b'33.9 0l-64-64c-9.4-9.4-9.4-24.6 0-33.9s24.6-9.4 33.9 0l47 47'
html += b'L303 175c9.4-9.4 24.6-9.4 33.9 0s9.4 24.6 0 33.9z"/>\',X=\'<sv'
html += b'g xmlns="http://www.w3.org/2000/svg" height="28" viewBox="0 '
html += b'0 512 512"><path d="M464 256A208 208 0 1 0 48 256a208 208 0 '
html += b'1 0 416 0zM0 256a256 256 0 1 1 512 0A256 256 0 1 1 0 256z"/>'
html += b'</svg>\',Y=\'<svg xmlns="http://www.w3.org/2000/svg" height="2'
html += b'8" viewBox="0 0 512 512"><path d="M256 48a208 208 0 1 1 0 41'
html += b'6 208 208 0 1 1 0-416zm0 464A256 256 0 1 0 256 0a256 256 0 1'
html += b' 0 0 512zM369 209c9.4-9.4 9.4-24.6 0-33.9s-24.6-9.4-33.9 0l-'
html += b'111 111-47-47c-9.4-9.4-24.6-9.4-33.9 0s-9.4 24.6 0 33.9l64 6'
html += b'4c9.4 9.4 24.6 9.4 33.9 0L369 209z"/></svg>\',T=\'<svg xmlns="'
html += b'http://www.w3.org/2000/svg" height="25" viewBox="0 0 384 512'
html += b'" fill="white"><path d="M73 39c-14.8-9.1-33.4-9.4-48.5-.9S0 '
html += b'62.6 0 80V432c0 17.4 9.4 33.4 24.5 41.9s33.7 8.1 48.5-.9L361'
html += b' 297c14.3-8.7 23-24.2 23-41s-8.7-32.2-23-41L73 39z"/></svg>\''
html += b',G=\'<svg xmlns="http://www.w3.org/2000/svg" height="25" view'
html += b'Box="0 0 512 512" fill="white"><path d="M0 224c0 17.7 14.3 3'
html += b'2 32 32s32-14.3 32-32c0-53 43-96 96-96H320v32c0 12.9 7.8 24.'
html += b'6 19.8 29.6s25.7 2.2 34.9-6.9l64-64c12.5-12.5 12.5-32.8 0-45'
html += b'.3l-64-64c-9.2-9.2-22.9-11.9-34.9-6.9S320 19.1 320 32V64H160'
html += b'C71.6 64 0 135.6 0 224zm512 64c0-17.7-14.3-32-32-32s-32 14.3'
html += b'-32 32c0 53-43 96-96 96H192V352c0-12.9-7.8-24.6-19.8-29.6s-2'
html += b'5.7-2.2-34.9 6.9l-64 64c-12.5 12.5-12.5 32.8 0 45.3l64 64c9.'
html += b'2 9.2 22.9 11.9 34.9 6.9s19.8-16.6 19.8-29.6V448H352c88.4 0 '
html += b'160-71.6 160-160z"/></svg>\';function R(r,e=!1){let t=new Arr'
html += b'ay(r);for(let s=0;s<r;s++)t[s]=s;if(e)for(let s=0;s<r;s++){l'
html += b'et i=Math.floor(Math.random()*r),a=Math.floor(Math.random()*'
html += b'r),h=t[i];t[i]=t[a],t[a]=h}return t}var b=class r{constructo'
html += b'r(e,t){this.m=e,this.n=t,this.v=new Array(e*t).fill("0")}get'
html += b'Element(e,t){return e<0||e>=this.m||t<0||t>=this.n?"0":this.'
html += b'v[e*this.n+t]}resize(e,t,s){if(e<1||e>50||t<1||t>50)return!1'
html += b';let i=new r(e,t);i.v.fill(s);for(let a=0;a<i.m;a++)for(let '
html += b'h=0;h<i.n;h++)i.v[a*i.n+h]=this.getElement(a,h);return this.'
html += b'fromMatrix(i),!0}fromMatrix(e){this.m=e.m,this.n=e.n,this.v='
html += b'[...e.v]}fromString(e){this.m=e.split("],").length,this.v=e.'
html += b'replaceAll("[","").replaceAll("]","").split(",").map(t=>t.tr'
html += b'im()),this.n=this.v.length/this.m}getMaxCellStrlen(){let e=0'
html += b';for(let t of this.v)t.length>e&&(e=t.length);return e}toTeX'
html += b'String(e=!1){let t=e?"\\\\left[\\\\begin{array}":"\\\\begin{bmatri'
html += b'x}";e&&(t+="{"+"c".repeat(this.n-1)+"|c}");for(let s=0;s<thi'
html += b's.m;s++){for(let i=0;i<this.n;i++){i>0&&(t+="&");let a=this.'
html += b'getElement(s,i);try{a=k.parse(a).toTexString()}catch{}t+=a}t'
html += b'+="\\\\\\\\"}return t+=e?"\\\\end{array}\\\\right]":"\\\\end{bmatrix}"'
html += b',t}},k=class r{constructor(){this.root=null,this.src="",this'
html += b'.token="",this.skippedWhiteSpace=!1,this.pos=0}getVars(e,t=n'
html += b'ull){t==null&&(t=this.root),t.op.startsWith("var:")&&e.add(t'
html += b'.op.substring(4));for(let s of t.c)this.getVars(e,s)}eval(e,'
html += b't=null){let i=d.const(),a=0,h=0,l=null;switch(t==null&&(t=th'
html += b'is.root),t.op){case"const":i=t;break;case"+":case"-":case"*"'
html += b':case"/":case"^":case"==":{let n=this.eval(e,t.c[0]),o=this.'
html += b'eval(e,t.c[1]);switch(t.op){case"+":i.re=n.re+o.re,i.im=n.im'
html += b'+o.im;break;case"-":i.re=n.re-o.re,i.im=n.im-o.im;break;case'
html += b'"*":i.re=n.re*o.re-n.im*o.im,i.im=n.re*o.im+n.im*o.re;break;'
html += b'case"/":a=o.re*o.re+o.im*o.im,i.re=(n.re*o.re+n.im*o.im)/a,i'
html += b'.im=(n.im*o.re-n.re*o.im)/a;break;case"^":l=new d("exp",[new'
html += b' d("*",[o,new d("ln",[n])])]),i=this.eval(e,l);break;case"=='
html += b'":a=n.re-o.re,h=n.im-o.im,i.re=Math.sqrt(a*a+h*h)<1e-9?1:0,i'
html += b'.im=0;break}break}case".-":case"abs":case"sin":case"sinc":ca'
html += b'se"cos":case"tan":case"cot":case"exp":case"ln":case"log":cas'
html += b'e"sqrt":{let n=this.eval(e,t.c[0]);switch(t.op){case".-":i.r'
html += b'e=-n.re,i.im=-n.im;break;case"abs":i.re=Math.sqrt(n.re*n.re+'
html += b'n.im*n.im),i.im=0;break;case"sin":i.re=Math.sin(n.re)*Math.c'
html += b'osh(n.im),i.im=Math.cos(n.re)*Math.sinh(n.im);break;case"sin'
html += b'c":l=new d("/",[new d("sin",[n]),n]),i=this.eval(e,l);break;'
html += b'case"cos":i.re=Math.cos(n.re)*Math.cosh(n.im),i.im=-Math.sin'
html += b'(n.re)*Math.sinh(n.im);break;case"tan":a=Math.cos(n.re)*Math'
html += b'.cos(n.re)+Math.sinh(n.im)*Math.sinh(n.im),i.re=Math.sin(n.r'
html += b'e)*Math.cos(n.re)/a,i.im=Math.sinh(n.im)*Math.cosh(n.im)/a;b'
html += b'reak;case"cot":a=Math.sin(n.re)*Math.sin(n.re)+Math.sinh(n.i'
html += b'm)*Math.sinh(n.im),i.re=Math.sin(n.re)*Math.cos(n.re)/a,i.im'
html += b'=-(Math.sinh(n.im)*Math.cosh(n.im))/a;break;case"exp":i.re=M'
html += b'ath.exp(n.re)*Math.cos(n.im),i.im=Math.exp(n.re)*Math.sin(n.'
html += b'im);break;case"ln":case"log":i.re=Math.log(Math.sqrt(n.re*n.'
html += b're+n.im*n.im)),a=Math.abs(n.im)<1e-9?0:n.im,i.im=Math.atan2('
html += b'a,n.re);break;case"sqrt":l=new d("^",[n,d.const(.5)]),i=this'
html += b'.eval(e,l);break}break}default:if(t.op.startsWith("var:")){l'
html += b'et n=t.op.substring(4);if(n==="pi")return d.const(Math.PI);i'
html += b'f(n==="e")return d.const(Math.E);if(n==="i")return d.const(0'
html += b',1);if(n in e)return e[n];throw new Error("eval-error: unkno'
html += b'wn variable \'"+n+"\'")}else throw new Error("UNIMPLEMENTED ev'
html += b'al \'"+t.op+"\'")}return i}static parse(e){let t=new r;if(t.sr'
html += b'c=e,t.token="",t.skippedWhiteSpace=!1,t.pos=0,t.next(),t.roo'
html += b't=t.parseExpr(!1),t.token!=="")throw new Error("remaining to'
html += b'kens: "+t.token+"...");return t}parseExpr(e){return this.par'
html += b'seAdd(e)}parseAdd(e){let t=this.parseMul(e);for(;["+","-"].i'
html += b'ncludes(this.token)&&!(e&&this.skippedWhiteSpace);){let s=th'
html += b'is.token;this.next(),t=new d(s,[t,this.parseMul(e)])}return '
html += b't}parseMul(e){let t=this.parsePow(e);for(;!(e&&this.skippedW'
html += b'hiteSpace);){let s="*";if(["*","/"].includes(this.token))s=t'
html += b'his.token,this.next();else if(!e&&this.token==="(")s="*";els'
html += b'e if(this.token.length>0&&(this.isAlpha(this.token[0])||this'
html += b'.isNum(this.token[0])))s="*";else break;t=new d(s,[t,this.pa'
html += b'rsePow(e)])}return t}parsePow(e){let t=this.parseUnary(e);fo'
html += b'r(;["^"].includes(this.token)&&!(e&&this.skippedWhiteSpace);'
html += b'){let s=this.token;this.next(),t=new d(s,[t,this.parseUnary('
html += b'e)])}return t}parseUnary(e){return this.token==="-"?(this.ne'
html += b'xt(),new d(".-",[this.parseMul(e)])):this.parseInfix(e)}pars'
html += b'eInfix(e){if(this.token.length==0)throw new Error("expected '
html += b'unary");if(this.isNum(this.token[0])){let t=this.token;retur'
html += b'n this.next(),this.token==="."&&(t+=".",this.next(),this.tok'
html += b'en.length>0&&(t+=this.token,this.next())),new d("const",[],p'
html += b'arseFloat(t))}else if(this.fun1().length>0){let t=this.fun1('
html += b');this.next(t.length);let s=null;if(this.token==="(")if(this'
html += b'.next(),s=this.parseExpr(e),this.token+="",this.token===")")'
html += b'this.next();else throw Error("expected \')\'");else s=this.par'
html += b'seMul(!0);return new d(t,[s])}else if(this.token==="("){this'
html += b'.next();let t=this.parseExpr(e);if(this.token+="",this.token'
html += b'===")")this.next();else throw Error("expected \')\'");return t'
html += b'.explicitParentheses=!0,t}else if(this.token==="|"){this.nex'
html += b't();let t=this.parseExpr(e);if(this.token+="",this.token==="'
html += b'|")this.next();else throw Error("expected \'|\'");return new d'
html += b'("abs",[t])}else if(this.isAlpha(this.token[0])){let t="";re'
html += b'turn this.token.startsWith("pi")?t="pi":t=this.token[0],this'
html += b'.next(t.length),new d("var:"+t,[])}else throw new Error("exp'
html += b'ected unary")}compare(e){let i=new Set;this.getVars(i),e.get'
html += b'Vars(i);for(let a=0;a<10;a++){let h={};for(let o of i)h[o]=d'
html += b'.const(Math.random(),Math.random());let l=new d("==",[this.r'
html += b'oot,e.root]),n=this.eval(h,l);if(Math.abs(n.re)<1e-9)return!'
html += b'1}return!0}fun1(){let e=["abs","sinc","sin","cos","tan","cot'
html += b'","exp","ln","sqrt"];for(let t of e)if(this.token.startsWith'
html += b'(t))return t;return""}next(e=-1){if(e>0&&this.token.length>e'
html += b'){this.token=this.token.substring(e),this.skippedWhiteSpace='
html += b'!1;return}this.token="";let t=!1,s=this.src.length;for(this.'
html += b'skippedWhiteSpace=!1;this.pos<s&&`\t\n `.includes(this.src[thi'
html += b's.pos]);)this.skippedWhiteSpace=!0,this.pos++;for(;!t&&this.'
html += b'pos<s;){let i=this.src[this.pos];if(this.token.length>0&&(th'
html += b'is.isNum(this.token[0])&&this.isAlpha(i)||this.isAlpha(this.'
html += b'token[0])&&this.isNum(i)))return;if(`^%#*$()[]{},.:;+-*/_!<>'
html += b'=?|\t\n `.includes(i)){if(this.token.length>0)return;t=!0}`\t\n '
html += b'`.includes(i)==!1&&(this.token+=i),this.pos++}}isNum(e){retu'
html += b'rn e.charCodeAt(0)>=48&&e.charCodeAt(0)<=57}isAlpha(e){retur'
html += b'n e.charCodeAt(0)>=65&&e.charCodeAt(0)<=90||e.charCodeAt(0)>'
html += b'=97&&e.charCodeAt(0)<=122||e==="_"}toString(){return this.ro'
html += b'ot==null?"":this.root.toString()}toTexString(){return this.r'
html += b'oot==null?"":this.root.toTexString()}},d=class r{constructor'
html += b'(e,t,s=0,i=0){this.op=e,this.c=t,this.re=s,this.im=i,this.ex'
html += b'plicitParentheses=!1}static const(e=0,t=0){return new r("con'
html += b'st",[],e,t)}compare(e,t=0,s=1e-9){let i=this.re-e,a=this.im-'
html += b't;return Math.sqrt(i*i+a*a)<s}toString(){let e="";if(this.op'
html += b'==="const"){let t=Math.abs(this.re)>1e-14,s=Math.abs(this.im'
html += b')>1e-14;t&&s&&this.im>=0?e="("+this.re+"+"+this.im+"i)":t&&s'
html += b'&&this.im<0?e="("+this.re+"-"+-this.im+"i)":t?e=""+this.re:s'
html += b'&&(e="("+this.im+"i)")}else this.op.startsWith("var")?e=this'
html += b'.op.split(":")[1]:this.c.length==1?e=(this.op===".-"?"-":thi'
html += b's.op)+"("+this.c.toString()+")":e="("+this.c.map(t=>t.toStri'
html += b'ng()).join(this.op)+")";return e}toTexString(e=!1){let s="";'
html += b'switch(this.op){case"const":{let i=Math.abs(this.re)>1e-9,a='
html += b'Math.abs(this.im)>1e-9,h=i?""+this.re:"",l=a?""+this.im+"i":'
html += b'"";l==="1i"?l="i":l==="-1i"&&(l="-i"),a&&this.im>=0&&i&&(l="'
html += b'+"+l),!i&&!a?s="0":s=h+l;break}case".-":s="-"+this.c[0].toTe'
html += b'xString();break;case"+":case"-":case"*":case"^":{let i=this.'
html += b'c[0].toTexString(),a=this.c[1].toTexString(),h=this.op==="*"'
html += b'?"\\\\cdot ":this.op;s="{"+i+"}"+h+"{"+a+"}";break}case"/":{le'
html += b't i=this.c[0].toTexString(!0),a=this.c[1].toTexString(!0);s='
html += b'"\\\\frac{"+i+"}{"+a+"}";break}case"sin":case"sinc":case"cos":'
html += b'case"tan":case"cot":case"exp":case"ln":{let i=this.c[0].toTe'
html += b'xString(!0);s+="\\\\"+this.op+"\\\\left("+i+"\\\\right)";break}cas'
html += b'e"sqrt":{let i=this.c[0].toTexString(!0);s+="\\\\"+this.op+"{"'
html += b'+i+"}";break}case"abs":{let i=this.c[0].toTexString(!0);s+="'
html += b'\\\\left|"+i+"\\\\right|";break}default:if(this.op.startsWith("v'
html += b'ar:")){let i=this.op.substring(4);switch(i){case"pi":i="\\\\pi'
html += b'";break}s=" "+i+" "}else{let i="warning: Node.toString(..):"'
html += b';i+=" unimplemented operator \'"+this.op+"\'",console.log(i),s'
html += b'=this.op,this.c.length>0&&(s+="\\\\left({"+this.c.map(a=>a.toT'
html += b'exString(!0)).join(",")+"}\\\\right)")}}return!e&&this.explici'
html += b'tParentheses&&(s="\\\\left({"+s+"}\\\\right)"),s}};function J(r)'
html += b'{r.feedbackSpan.innerHTML="",r.numChecked=0,r.numCorrect=0;f'
html += b'or(let s in r.expected){let i=r.types[s],a=r.student[s],h=r.'
html += b'expected[s];switch(i){case"bool":r.numChecked++,a===h&&r.num'
html += b'Correct++;break;case"string":{r.numChecked++;let l=r.gapInpu'
html += b'ts[s],n=a.trim().toUpperCase(),o=h.trim().toUpperCase(),u=Z('
html += b'n,o)<=1;u&&(r.numCorrect++,r.gapInputs[s].value=o,r.student['
html += b's]=o),l.style.color=u?"black":"white",l.style.backgroundColo'
html += b'r=u?"transparent":"maroon";break}case"int":r.numChecked++,Ma'
html += b'th.abs(parseFloat(a)-parseFloat(h))<1e-9&&r.numCorrect++;bre'
html += b'ak;case"float":case"term":{r.numChecked++;try{let l=k.parse('
html += b'h),n=k.parse(a);l.compare(n)&&r.numCorrect++}catch(l){r.debu'
html += b'g&&(console.log("term invalid"),console.log(l))}break}case"v'
html += b'ector":case"complex":case"set":{let l=h.split(",");r.numChec'
html += b'ked+=l.length;let n=[];for(let o=0;o<l.length;o++)n.push(r.s'
html += b'tudent[s+"-"+o]);if(i==="set")for(let o=0;o<l.length;o++)try'
html += b'{let m=k.parse(l[o]);for(let u=0;u<n.length;u++){let c=k.par'
html += b'se(n[u]);if(m.compare(c)){r.numCorrect++;break}}}catch(m){r.'
html += b'debug&&console.log(m)}else for(let o=0;o<l.length;o++)try{le'
html += b't m=k.parse(n[o]),u=k.parse(l[o]);m.compare(u)&&r.numCorrect'
html += b'++}catch(m){r.debug&&console.log(m)}break}case"matrix":{let '
html += b'l=new b(0,0);l.fromString(h),r.numChecked+=l.m*l.n;for(let n'
html += b'=0;n<l.m;n++)for(let o=0;o<l.n;o++){let m=n*l.n+o;a=r.studen'
html += b't[s+"-"+m];let u=l.v[m];try{let c=k.parse(u),p=k.parse(a);c.'
html += b'compare(p)&&r.numCorrect++}catch(c){r.debug&&console.log(c)}'
html += b'}break}default:r.feedbackSpan.innerHTML="UNIMPLEMENTED EVAL '
html += b'OF TYPE "+i}}r.state=r.numCorrect==r.numChecked?v.passed:v.e'
html += b'rrors,r.updateVisualQuestionState();let e=r.state===v.passed'
html += b'?O[r.language]:_[r.language],t=e[Math.floor(Math.random()*e.'
html += b'length)];r.feedbackPopupDiv.innerHTML=t,r.feedbackPopupDiv.s'
html += b'tyle.color=r.state===v.passed?"green":"maroon",r.feedbackPop'
html += b'upDiv.style.display="block",setTimeout(()=>{r.feedbackPopupD'
html += b'iv.style.display="none"},500),r.state===v.passed?r.src.insta'
html += b'nces.length>0?r.checkAndRepeatBtn.innerHTML=G:r.checkAndRepe'
html += b'atBtn.style.display="none":r.checkAndRepeatBtn.innerHTML=T}v'
html += b'ar y=class{constructor(e,t,s,i,a,h){t.student[s]="",this.que'
html += b'stion=t,this.inputId=s,this.outerSpan=f(""),this.outerSpan.s'
html += b'tyle.position="relative",e.appendChild(this.outerSpan),this.'
html += b'inputElement=L(Math.max(i*12,48)),this.outerSpan.appendChild'
html += b'(this.inputElement),this.equationPreviewDiv=g(),this.equatio'
html += b'nPreviewDiv.classList.add("equationPreview"),this.equationPr'
html += b'eviewDiv.style.display="none",this.outerSpan.appendChild(thi'
html += b's.equationPreviewDiv),this.inputElement.addEventListener("cl'
html += b'ick",()=>{this.question.editedQuestion(),this.edited()}),thi'
html += b's.inputElement.addEventListener("keyup",()=>{this.question.e'
html += b'ditedQuestion(),this.edited()}),this.inputElement.addEventLi'
html += b'stener("focusout",()=>{this.equationPreviewDiv.innerHTML="",'
html += b'this.equationPreviewDiv.style.display="none"}),this.inputEle'
html += b'ment.addEventListener("keydown",l=>{let n="abcdefghijklmnopq'
html += b'rstuvwxyz";n+="ABCDEFGHIJKLMNOPQRSTUVWXYZ",n+="0123456789",n'
html += b'+="+-*/^(). <>=|",h&&(n="-0123456789"),l.key.length<3&&n.inc'
html += b'ludes(l.key)==!1&&l.preventDefault();let o=this.inputElement'
html += b'.value.length*12;this.inputElement.offsetWidth<o&&(this.inpu'
html += b'tElement.style.width=""+o+"px")}),this.question.showSolution'
html += b'&&(t.student[s]=this.inputElement.value=a)}edited(){let e=th'
html += b'is.inputElement.value.trim(),t="",s=!1;try{let i=k.parse(e);'
html += b's=i.root.op==="const",t=i.toTexString(),this.inputElement.st'
html += b'yle.color="black",this.equationPreviewDiv.style.backgroundCo'
html += b'lor="green"}catch{t=e.replaceAll("^","\\\\hat{~}").replaceAll('
html += b'"_","\\\\_"),this.inputElement.style.color="maroon",this.equat'
html += b'ionPreviewDiv.style.backgroundColor="maroon"}B(this.equation'
html += b'PreviewDiv,t,!0),this.equationPreviewDiv.style.display=e.len'
html += b'gth>0&&!s?"block":"none",this.question.student[this.inputId]'
html += b'=e}},I=class{constructor(e,t,s,i){this.parent=e,this.questio'
html += b'n=t,this.inputId=s,this.matExpected=new b(0,0),this.matExpec'
html += b'ted.fromString(i),this.matStudent=new b(this.matExpected.m=='
html += b'1?1:3,this.matExpected.n==1?1:3),t.showSolution&&this.matStu'
html += b'dent.fromMatrix(this.matExpected),this.genMatrixDom()}genMat'
html += b'rixDom(){let e=g();this.parent.innerHTML="",this.parent.appe'
html += b'ndChild(e),e.style.position="relative",e.style.display="inli'
html += b'ne-block";let t=document.createElement("table");e.appendChil'
html += b'd(t);let s=this.matExpected.getMaxCellStrlen();for(let c=0;c'
html += b'<this.matStudent.m;c++){let p=document.createElement("tr");t'
html += b'.appendChild(p),c==0&&p.appendChild(this.generateMatrixParen'
html += b'thesis(!0,this.matStudent.m));for(let w=0;w<this.matStudent.'
html += b'n;w++){let x=c*this.matStudent.n+w,E=document.createElement('
html += b'"td");p.appendChild(E);let H=this.inputId+"-"+x;new y(E,this'
html += b'.question,H,s,this.matStudent.v[x],!1)}c==0&&p.appendChild(t'
html += b'his.generateMatrixParenthesis(!1,this.matStudent.m))}let i=['
html += b'"+","-","+","-"],a=[0,0,1,-1],h=[1,-1,0,0],l=[0,22,888,888],'
html += b'n=[888,888,-22,-22],o=[-22,-22,0,22],m=[this.matExpected.n!='
html += b'1,this.matExpected.n!=1,this.matExpected.m!=1,this.matExpect'
html += b'ed.m!=1],u=[this.matStudent.n>=10,this.matStudent.n<=1,this.'
html += b'matStudent.m>=10,this.matStudent.m<=1];for(let c=0;c<4;c++){'
html += b'if(m[c]==!1)continue;let p=f(i[c]);l[c]!=888&&(p.style.top="'
html += b'"+l[c]+"px"),n[c]!=888&&(p.style.bottom=""+n[c]+"px"),o[c]!='
html += b'888&&(p.style.right=""+o[c]+"px"),p.classList.add("matrixRes'
html += b'izeButton"),e.appendChild(p),u[c]?p.style.opacity="0.5":p.ad'
html += b'dEventListener("click",()=>{this.matStudent.resize(this.matS'
html += b'tudent.m+a[c],this.matStudent.n+h[c],"0"),this.genMatrixDom('
html += b')})}}generateMatrixParenthesis(e,t){let s=document.createEle'
html += b'ment("td");s.style.width="3px";for(let i of["Top",e?"Left":"'
html += b'Right","Bottom"])s.style["border"+i+"Width"]="2px",s.style["'
html += b'border"+i+"Style"]="solid";return s.rowSpan=t,s}};var v={ini'
html += b't:0,errors:1,passed:2},P=class{constructor(e,t,s,i){this.sta'
html += b'te=v.init,this.language=s,this.src=t,this.debug=i,this.insta'
html += b'nceOrder=R(t.instances.length,!0),this.instanceIdx=0,this.ch'
html += b'oiceIdx=0,this.gapIdx=0,this.expected={},this.types={},this.'
html += b'student={},this.gapInputs={},this.parentDiv=e,this.questionD'
html += b'iv=null,this.feedbackPopupDiv=null,this.titleDiv=null,this.c'
html += b'heckAndRepeatBtn=null,this.showSolution=!1,this.feedbackSpan'
html += b'=null,this.numCorrect=0,this.numChecked=0}reset(){this.insta'
html += b'nceIdx=(this.instanceIdx+1)%this.src.instances.length}getCur'
html += b'rentInstance(){return this.src.instances[this.instanceOrder['
html += b'this.instanceIdx]]}editedQuestion(){this.state=v.init,this.u'
html += b'pdateVisualQuestionState(),this.questionDiv.style.color="bla'
html += b'ck",this.checkAndRepeatBtn.innerHTML=T,this.checkAndRepeatBt'
html += b'n.style.display="block",this.checkAndRepeatBtn.style.color="'
html += b'black"}updateVisualQuestionState(){let e="black",t="transpar'
html += b'ent";switch(this.state){case v.init:e="rgb(0,0,0)",t="transp'
html += b'arent";break;case v.passed:e="rgb(0,150,0)",t="rgba(0,150,0,'
html += b' 0.025)";break;case v.errors:e="rgb(150,0,0)",t="rgba(150,0,'
html += b'0, 0.025)",this.numChecked>=5&&(this.feedbackSpan.innerHTML='
html += b'""+this.numCorrect+" / "+this.numChecked);break}this.questio'
html += b'nDiv.style.color=this.feedbackSpan.style.color=this.titleDiv'
html += b'.style.color=this.checkAndRepeatBtn.style.backgroundColor=th'
html += b'is.questionDiv.style.borderColor=e,this.questionDiv.style.ba'
html += b'ckgroundColor=t}populateDom(){if(this.parentDiv.innerHTML=""'
html += b',this.questionDiv=g(),this.parentDiv.appendChild(this.questi'
html += b'onDiv),this.questionDiv.classList.add("question"),this.feedb'
html += b'ackPopupDiv=g(),this.feedbackPopupDiv.classList.add("questio'
html += b'nFeedback"),this.questionDiv.appendChild(this.feedbackPopupD'
html += b'iv),this.feedbackPopupDiv.innerHTML="awesome",this.debug&&"s'
html += b'rc_line"in this.src){let i=g();i.classList.add("debugInfo"),'
html += b'i.innerHTML="Source code: lines "+this.src.src_line+"..",thi'
html += b's.questionDiv.appendChild(i)}if(this.titleDiv=g(),this.quest'
html += b'ionDiv.appendChild(this.titleDiv),this.titleDiv.classList.ad'
html += b'd("questionTitle"),this.titleDiv.innerHTML=this.src.title,th'
html += b'is.src.error.length>0){let i=f(this.src.error);this.question'
html += b'Div.appendChild(i),i.style.color="red";return}for(let i of t'
html += b'his.src.text.c)this.questionDiv.appendChild(this.generateTex'
html += b't(i));let e=g();this.questionDiv.appendChild(e),e.classList.'
html += b'add("buttonRow");let t=Object.keys(this.expected).length>0;t'
html += b'&&(this.checkAndRepeatBtn=U(),e.appendChild(this.checkAndRep'
html += b'eatBtn),this.checkAndRepeatBtn.innerHTML=T,this.checkAndRepe'
html += b'atBtn.style.backgroundColor="black");let s=f("&nbsp;&nbsp;&n'
html += b'bsp;");if(e.appendChild(s),this.feedbackSpan=f(""),e.appendC'
html += b'hild(this.feedbackSpan),this.debug){if(this.src.variables.le'
html += b'ngth>0){let h=g();h.classList.add("debugInfo"),h.innerHTML="'
html += b'Variables generated by Python Code",this.questionDiv.appendC'
html += b'hild(h);let l=g();l.classList.add("debugCode"),this.question'
html += b'Div.appendChild(l);let n=this.getCurrentInstance(),o="",m=[.'
html += b'..this.src.variables];m.sort();for(let u of m){let c=n[u].t,'
html += b'p=n[u].v;switch(c){case"vector":p="["+p+"]";break;case"set":'
html += b'p="{"+p+"}";break}o+=c+" "+u+" = "+p+"<br/>"}l.innerHTML=o}l'
html += b'et i=["python_src_html","text_src_html"],a=["Python Source C'
html += b'ode","Text Source Code"];for(let h=0;h<i.length;h++){let l=i'
html += b'[h];if(l in this.src&&this.src[l].length>0){let n=g();n.clas'
html += b'sList.add("debugInfo"),n.innerHTML=a[h],this.questionDiv.app'
html += b'endChild(n);let o=g();o.classList.add("debugCode"),this.ques'
html += b'tionDiv.append(o),o.innerHTML=this.src[l]}}}t&&this.checkAnd'
html += b'RepeatBtn.addEventListener("click",()=>{this.state==v.passed'
html += b'?(this.state=v.init,this.reset(),this.populateDom()):J(this)'
html += b'})}generateMathString(e){let t="";switch(e.t){case"math":cas'
html += b'e"display-math":for(let s of e.c)t+=this.generateMathString('
html += b's);break;case"text":return e.d;case"var":{let s=this.getCurr'
html += b'entInstance(),i=s[e.d].t,a=s[e.d].v;switch(i){case"vector":r'
html += b'eturn"\\\\left["+a+"\\\\right]";case"set":return"\\\\left\\\\{"+a+"\\'
html += b'\\right\\\\}";case"complex":{let h=a.split(","),l=parseFloat(h['
html += b'0]),n=parseFloat(h[1]),o="";return Math.abs(l)>1e-9&&(o+=l),'
html += b'Math.abs(n)>1e-9&&(o+=(n<0?"-":"+")+n+"i"),o}case"matrix":{l'
html += b'et h=new b(0,0);return h.fromString(a),t=h.toTeXString(e.d.i'
html += b'ncludes("augmented")),t}case"term":{try{t=k.parse(a).toTexSt'
html += b'ring()}catch{}break}default:t=a}}}return"{"+t+"}"}generateTe'
html += b'xt(e,t=!1){switch(e.t){case"paragraph":case"span":{let s=doc'
html += b'ument.createElement(e.t=="span"||t?"span":"p");for(let i of '
html += b'e.c)s.appendChild(this.generateText(i));return s}case"text":'
html += b'return f(e.d);case"code":{let s=f(e.d);return s.classList.ad'
html += b'd("code"),s}case"italic":case"bold":{let s=f("");return s.ap'
html += b'pend(...e.c.map(i=>this.generateText(i))),e.t==="bold"?s.sty'
html += b'le.fontWeight="bold":s.style.fontStyle="italic",s}case"math"'
html += b':case"display-math":{let s=this.generateMathString(e);return'
html += b' M(s,e.t==="display-math")}case"gap":{let s=f(""),i=Math.max'
html += b'(e.d.length*14,24),a=L(i),h="gap-"+this.gapIdx;return this.g'
html += b'apInputs[h]=a,this.expected[h]=e.d,this.types[h]="string",a.'
html += b'addEventListener("keyup",()=>{this.editedQuestion(),a.value='
html += b'a.value.toUpperCase(),this.student[h]=a.value.trim()}),this.'
html += b'student[h]="",this.showSolution&&(this.student[h]=a.value=th'
html += b'is.expected[h]),this.gapIdx++,s.appendChild(a),s}case"input"'
html += b':case"input2":{let s=e.t==="input2",i=f("");i.style.vertical'
html += b'Align="text-bottom";let a=e.d,h=this.getCurrentInstance()[a]'
html += b';if(this.expected[a]=h.v,this.types[a]=h.t,!s)switch(h.t){ca'
html += b'se"set":i.append(M("\\\\{"),f(" "));break;case"vector":i.appen'
html += b'd(M("["),f(" "));break}if(h.t==="vector"||h.t==="set"){let l'
html += b'=h.v.split(","),n=l.length;for(let o=0;o<n;o++){o>0&&i.appen'
html += b'dChild(f(" , "));let m=a+"-"+o;new y(i,this,m,l[o].length,l['
html += b'o],!1)}}else if(h.t==="matrix"){let l=g();i.appendChild(l),n'
html += b'ew I(l,this,a,h.v)}else if(h.t==="complex"){let l=h.v.split('
html += b'",");new y(i,this,a+"-0",l[0].length,l[0],!1),i.append(f(" "'
html += b'),M("+"),f(" ")),new y(i,this,a+"-1",l[1].length,l[1],!1),i.'
html += b'append(f(" "),M("i"))}else{let l=h.t==="int";new y(i,this,a,'
html += b'h.v.length,h.v,l)}if(!s)switch(h.t){case"set":i.append(f(" "'
html += b'),M("\\\\}"));break;case"vector":i.append(f(" "),M("]"));break'
html += b'}return i}case"itemize":return W(e.c.map(s=>N(this.generateT'
html += b'ext(s))));case"single-choice":case"multi-choice":{let s=e.t='
html += b'="multi-choice",i=document.createElement("table"),a=e.c.leng'
html += b'th,h=this.debug==!1,l=R(a,h),n=s?K:Y,o=s?q:X,m=[],u=[];for(l'
html += b'et c=0;c<a;c++){let p=l[c],w=e.c[p],x="mc-"+this.choiceIdx+"'
html += b'-"+p;u.push(x);let E=w.c[0].t=="bool"?w.c[0].d:this.getCurre'
html += b'ntInstance()[w.c[0].d].v;this.expected[x]=E,this.types[x]="b'
html += b'ool",this.student[x]=this.showSolution?E:"false";let H=this.'
html += b'generateText(w.c[1],!0),C=document.createElement("tr");i.app'
html += b'endChild(C),C.style.cursor="pointer";let S=document.createEl'
html += b'ement("td");m.push(S),C.appendChild(S),S.innerHTML=this.stud'
html += b'ent[x]=="true"?n:o;let V=document.createElement("td");C.appe'
html += b'ndChild(V),V.appendChild(H),s?C.addEventListener("click",()='
html += b'>{this.editedQuestion(),this.student[x]=this.student[x]==="t'
html += b'rue"?"false":"true",this.student[x]==="true"?S.innerHTML=n:S'
html += b'.innerHTML=o}):C.addEventListener("click",()=>{this.editedQu'
html += b'estion();for(let D of u)this.student[D]="false";this.student'
html += b'[x]="true";for(let D=0;D<u.length;D++){let Q=l[D];m[Q].inner'
html += b'HTML=this.student[u[Q]]=="true"?n:o}})}return this.choiceIdx'
html += b'++,i}default:{let s=f("UNIMPLEMENTED("+e.t+")");return s.sty'
html += b'le.color="red",s}}}};function re(r,e){["en","de","es","it","'
html += b'fr"].includes(r.lang)==!1&&(r.lang="en"),e&&(document.getEle'
html += b'mentById("debug").style.display="block"),document.getElement'
html += b'ById("date").innerHTML=r.date,document.getElementById("title'
html += b'").innerHTML=r.title,document.getElementById("author").inner'
html += b'HTML=r.author,document.getElementById("courseInfo1").innerHT'
html += b'ML=z[r.lang];let t=\'<span onclick="location.reload()" style='
html += b'"text-decoration: underline; font-weight: bold; cursor: poin'
html += b'ter">\'+j[r.lang]+"</span>";document.getElementById("courseIn'
html += b'fo2").innerHTML=F[r.lang].replace("*",t);let s=[],i=document'
html += b'.getElementById("questions"),a=1;for(let h of r.questions){h'
html += b'.title=""+a+". "+h.title;let l=g();i.appendChild(l);let n=ne'
html += b'w P(l,h,r.lang,e);n.showSolution=e,s.push(n),n.populateDom()'
html += b',e&&h.error.length==0&&n.checkAndRepeatBtn.click(),a++}}retu'
html += b'rn ne(ae);})();sell.init(quizSrc,debug);</script></body> </h'
html += b'tml> '
html = html.decode('utf-8')
# @end(html)


if __name__ == "__main__":

    # get input and output path
    if len(sys.argv) < 2:
        print("usage: python sell.py [-J] INPUT_PATH.txt")
        print("   option -J enables to output a JSON file for debugging purposes")
        exit(-1)
    write_explicit_json_file = "-J" in sys.argv
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
    if write_explicit_json_file:
        f = open(output_json_path, "w")
        f.write(output_debug_json_formatted)
        # f.write(output_debug_json)
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
