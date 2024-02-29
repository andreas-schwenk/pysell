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
                # convert "-0" to "0"
                real = 0 if value.real == 0 else value.real
                imag = 0 if value.imag == 0 else value.imag
                v = self.float_to_str(real) + "," + self.float_to_str(imag)
            elif type_str == "<class 'list'>":
                t = "vector"
                v = str(value).replace("[", "").replace("]", "").replace(" ", "")
            elif type_str == "<class 'set'>":
                t = "set"
                v = (
                    str(value)
                    .replace("{", "")
                    .replace("}", "")
                    .replace(" ", "")
                    .replace("j", "i")
                )
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
            v = v.replace("I", "i")  # reformat sympy imaginary part
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
html += b'reateElement("div");return e.append(...r),e}function N(r=[])'
html += b'{let e=document.createElement("ul");return e.append(...r),e}'
html += b'function W(r){let e=document.createElement("li");return e.ap'
html += b'pendChild(r),e}function L(r){let e=document.createElement("i'
html += b'nput");return e.spellcheck=!1,e.type="text",e.classList.add('
html += b'"inputField"),e.style.width=r+"px",e}function U(){let r=docu'
html += b'ment.createElement("button");return r.type="button",r.classL'
html += b'ist.add("button"),r}function f(r,e=[]){let t=document.create'
html += b'Element("span");return e.length>0?t.append(...e):t.innerHTML'
html += b'=r,t}function B(r,e,t=!1){katex.render(e,r,{throwOnError:!1,'
html += b'displayMode:t,macros:{"\\\\RR":"\\\\mathbb{R}","\\\\NN":"\\\\mathbb{'
html += b'N}","\\\\QQ":"\\\\mathbb{Q}","\\\\ZZ":"\\\\mathbb{Z}","\\\\CC":"\\\\math'
html += b'bb{C}"}})}function M(r,e=!1){let t=document.createElement("s'
html += b'pan");return B(t,r,e),t}var z={en:"This page runs in your br'
html += b'owser and does not store any data on servers.",de:"Diese Sei'
html += b'te wird in Ihrem Browser ausgef\\xFChrt und speichert keine D'
html += b'aten auf Servern.",es:"Esta p\\xE1gina se ejecuta en su naveg'
html += b'ador y no almacena ning\\xFAn dato en los servidores.",it:"Qu'
html += b'esta pagina viene eseguita nel browser e non memorizza alcun'
html += b' dato sui server.",fr:"Cette page fonctionne dans votre navi'
html += b'gateur et ne stocke aucune donn\\xE9e sur des serveurs."},F={'
html += b'en:"You can * this page in order to get new randomized tasks'
html += b'.",de:"Sie k\\xF6nnen diese Seite *, um neue randomisierte Au'
html += b'fgaben zu erhalten.",es:"Puedes * esta p\\xE1gina para obtene'
html += b'r nuevas tareas aleatorias.",it:"\\xC8 possibile * questa pag'
html += b'ina per ottenere nuovi compiti randomizzati",fr:"Vous pouvez'
html += b' * cette page pour obtenir de nouvelles t\\xE2ches al\\xE9atoi'
html += b'res"},j={en:"reload",de:"aktualisieren",es:"recargar",it:"ri'
html += b'caricare",fr:"recharger"},O={en:["awesome","great","well don'
html += b'e","nice","you got it","good"],de:["super","gut gemacht","we'
html += b'iter so","richtig"],es:["impresionante","genial","correcto",'
html += b'"bien hecho"],it:["fantastico","grande","corretto","ben fatt'
html += b'o"],fr:["g\\xE9nial","super","correct","bien fait"]},_={en:["'
html += b'try again","still some mistakes","wrong answer","no"],de:["l'
html += b'eider falsch","nicht richtig","versuch\'s nochmal"],es:["int\\'
html += b'xE9ntalo de nuevo","todav\\xEDa algunos errores","respuesta i'
html += b'ncorrecta"],it:["riprova","ancora qualche errore","risposta '
html += b'sbagliata"],fr:["r\\xE9essayer","encore des erreurs","mauvais'
html += b'e r\\xE9ponse"]};function Z(r,e){let t=Array(e.length+1).fill'
html += b'(null).map(()=>Array(r.length+1).fill(null));for(let s=0;s<='
html += b'r.length;s+=1)t[0][s]=s;for(let s=0;s<=e.length;s+=1)t[s][0]'
html += b'=s;for(let s=1;s<=e.length;s+=1)for(let i=1;i<=r.length;i+=1'
html += b'){let a=r[i-1]===e[s-1]?0:1;t[s][i]=Math.min(t[s][i-1]+1,t[s'
html += b"-1][i]+1,t[s-1][i-1]+a)}return t[e.length][r.length]}var q='"
html += b'<svg xmlns="http://www.w3.org/2000/svg" height="28" viewBox='
html += b'"0 0 448 512"><path d="M384 80c8.8 0 16 7.2 16 16V416c0 8.8-'
html += b'7.2 16-16 16H64c-8.8 0-16-7.2-16-16V96c0-8.8 7.2-16 16-16H38'
html += b'4zM64 32C28.7 32 0 60.7 0 96V416c0 35.3 28.7 64 64 64H384c35'
html += b'.3 0 64-28.7 64-64V96c0-35.3-28.7-64-64-64H64z"/></svg>\',K=\''
html += b'<svg xmlns="http://www.w3.org/2000/svg" height="28" viewBox='
html += b'"0 0 448 512"><path d="M64 80c-8.8 0-16 7.2-16 16V416c0 8.8 '
html += b'7.2 16 16 16H384c8.8 0 16-7.2 16-16V96c0-8.8-7.2-16-16-16H64'
html += b'zM0 96C0 60.7 28.7 32 64 32H384c35.3 0 64 28.7 64 64V416c0 3'
html += b'5.3-28.7 64-64 64H64c-35.3 0-64-28.7-64-64V96zM337 209L209 3'
html += b'37c-9.4 9.4-24.6 9.4-33.9 0l-64-64c-9.4-9.4-9.4-24.6 0-33.9s'
html += b'24.6-9.4 33.9 0l47 47L303 175c9.4-9.4 24.6-9.4 33.9 0s9.4 24'
html += b'.6 0 33.9z"/>\',X=\'<svg xmlns="http://www.w3.org/2000/svg" he'
html += b'ight="28" viewBox="0 0 512 512"><path d="M464 256A208 208 0 '
html += b'1 0 48 256a208 208 0 1 0 416 0zM0 256a256 256 0 1 1 512 0A25'
html += b'6 256 0 1 1 0 256z"/></svg>\',Y=\'<svg xmlns="http://www.w3.or'
html += b'g/2000/svg" height="28" viewBox="0 0 512 512"><path d="M256 '
html += b'48a208 208 0 1 1 0 416 208 208 0 1 1 0-416zm0 464A256 256 0 '
html += b'1 0 256 0a256 256 0 1 0 0 512zM369 209c9.4-9.4 9.4-24.6 0-33'
html += b'.9s-24.6-9.4-33.9 0l-111 111-47-47c-9.4-9.4-24.6-9.4-33.9 0s'
html += b'-9.4 24.6 0 33.9l64 64c9.4 9.4 24.6 9.4 33.9 0L369 209z"/></'
html += b'svg>\',T=\'<svg xmlns="http://www.w3.org/2000/svg" height="25"'
html += b' viewBox="0 0 384 512" fill="white"><path d="M73 39c-14.8-9.'
html += b'1-33.4-9.4-48.5-.9S0 62.6 0 80V432c0 17.4 9.4 33.4 24.5 41.9'
html += b's33.7 8.1 48.5-.9L361 297c14.3-8.7 23-24.2 23-41s-8.7-32.2-2'
html += b'3-41L73 39z"/></svg>\',G=\'<svg xmlns="http://www.w3.org/2000/'
html += b'svg" height="25" viewBox="0 0 512 512" fill="white"><path d='
html += b'"M0 224c0 17.7 14.3 32 32 32s32-14.3 32-32c0-53 43-96 96-96H'
html += b'320v32c0 12.9 7.8 24.6 19.8 29.6s25.7 2.2 34.9-6.9l64-64c12.'
html += b'5-12.5 12.5-32.8 0-45.3l-64-64c-9.2-9.2-22.9-11.9-34.9-6.9S3'
html += b'20 19.1 320 32V64H160C71.6 64 0 135.6 0 224zm512 64c0-17.7-1'
html += b'4.3-32-32-32s-32 14.3-32 32c0 53-43 96-96 96H192V352c0-12.9-'
html += b'7.8-24.6-19.8-29.6s-25.7-2.2-34.9 6.9l-64 64c-12.5 12.5-12.5'
html += b' 32.8 0 45.3l64 64c9.2 9.2 22.9 11.9 34.9 6.9s19.8-16.6 19.8'
html += b'-29.6V448H352c88.4 0 160-71.6 160-160z"/></svg>\';function R('
html += b'r,e=!1){let t=new Array(r);for(let s=0;s<r;s++)t[s]=s;if(e)f'
html += b'or(let s=0;s<r;s++){let i=Math.floor(Math.random()*r),a=Math'
html += b'.floor(Math.random()*r),l=t[i];t[i]=t[a],t[a]=l}return t}var'
html += b' b=class r{constructor(e,t){this.m=e,this.n=t,this.v=new Arr'
html += b'ay(e*t).fill("0")}getElement(e,t){return e<0||e>=this.m||t<0'
html += b'||t>=this.n?"0":this.v[e*this.n+t]}resize(e,t,s){if(e<1||e>5'
html += b'0||t<1||t>50)return!1;let i=new r(e,t);i.v.fill(s);for(let a'
html += b'=0;a<i.m;a++)for(let l=0;l<i.n;l++)i.v[a*i.n+l]=this.getElem'
html += b'ent(a,l);return this.fromMatrix(i),!0}fromMatrix(e){this.m=e'
html += b'.m,this.n=e.n,this.v=[...e.v]}fromString(e){this.m=e.split("'
html += b'],").length,this.v=e.replaceAll("[","").replaceAll("]","").s'
html += b'plit(",").map(t=>t.trim()),this.n=this.v.length/this.m}getMa'
html += b'xCellStrlen(){let e=0;for(let t of this.v)t.length>e&&(e=t.l'
html += b'ength);return e}toTeXString(e=!1){let t=e?"\\\\left[\\\\begin{ar'
html += b'ray}":"\\\\begin{bmatrix}";e&&(t+="{"+"c".repeat(this.n-1)+"|c'
html += b'}");for(let s=0;s<this.m;s++){for(let i=0;i<this.n;i++){i>0&'
html += b'&(t+="&");let a=this.getElement(s,i);try{a=k.parse(a).toTexS'
html += b'tring()}catch{}t+=a}t+="\\\\\\\\"}return t+=e?"\\\\end{array}\\\\rig'
html += b'ht]":"\\\\end{bmatrix}",t}},k=class r{constructor(){this.root='
html += b'null,this.src="",this.token="",this.skippedWhiteSpace=!1,thi'
html += b's.pos=0}getVars(e,t=null){t==null&&(t=this.root),t.op.starts'
html += b'With("var:")&&e.add(t.op.substring(4));for(let s of t.c)this'
html += b'.getVars(e,s)}eval(e,t=null){let i=p.const(),a=0,l=0,h=null;'
html += b'switch(t==null&&(t=this.root),t.op){case"const":i=t;break;ca'
html += b'se"+":case"-":case"*":case"/":case"^":case"==":{let n=this.e'
html += b'val(e,t.c[0]),o=this.eval(e,t.c[1]);switch(t.op){case"+":i.r'
html += b'e=n.re+o.re,i.im=n.im+o.im;break;case"-":i.re=n.re-o.re,i.im'
html += b'=n.im-o.im;break;case"*":i.re=n.re*o.re-n.im*o.im,i.im=n.re*'
html += b'o.im+n.im*o.re;break;case"/":a=o.re*o.re+o.im*o.im,i.re=(n.r'
html += b'e*o.re+n.im*o.im)/a,i.im=(n.im*o.re-n.re*o.im)/a;break;case"'
html += b'^":h=new p("exp",[new p("*",[o,new p("ln",[n])])]),i=this.ev'
html += b'al(e,h);break;case"==":a=n.re-o.re,l=n.im-o.im,i.re=Math.sqr'
html += b't(a*a+l*l)<1e-9?1:0,i.im=0;break}break}case".-":case"abs":ca'
html += b'se"sin":case"sinc":case"cos":case"tan":case"cot":case"exp":c'
html += b'ase"ln":case"log":case"sqrt":{let n=this.eval(e,t.c[0]);swit'
html += b'ch(t.op){case".-":i.re=-n.re,i.im=-n.im;break;case"abs":i.re'
html += b'=Math.sqrt(n.re*n.re+n.im*n.im),i.im=0;break;case"sin":i.re='
html += b'Math.sin(n.re)*Math.cosh(n.im),i.im=Math.cos(n.re)*Math.sinh'
html += b'(n.im);break;case"sinc":h=new p("/",[new p("sin",[n]),n]),i='
html += b'this.eval(e,h);break;case"cos":i.re=Math.cos(n.re)*Math.cosh'
html += b'(n.im),i.im=-Math.sin(n.re)*Math.sinh(n.im);break;case"tan":'
html += b'a=Math.cos(n.re)*Math.cos(n.re)+Math.sinh(n.im)*Math.sinh(n.'
html += b'im),i.re=Math.sin(n.re)*Math.cos(n.re)/a,i.im=Math.sinh(n.im'
html += b')*Math.cosh(n.im)/a;break;case"cot":a=Math.sin(n.re)*Math.si'
html += b'n(n.re)+Math.sinh(n.im)*Math.sinh(n.im),i.re=Math.sin(n.re)*'
html += b'Math.cos(n.re)/a,i.im=-(Math.sinh(n.im)*Math.cosh(n.im))/a;b'
html += b'reak;case"exp":i.re=Math.exp(n.re)*Math.cos(n.im),i.im=Math.'
html += b'exp(n.re)*Math.sin(n.im);break;case"ln":case"log":i.re=Math.'
html += b'log(Math.sqrt(n.re*n.re+n.im*n.im)),a=Math.abs(n.im)<1e-9?0:'
html += b'n.im,i.im=Math.atan2(a,n.re);break;case"sqrt":h=new p("^",[n'
html += b',p.const(.5)]),i=this.eval(e,h);break}break}default:if(t.op.'
html += b'startsWith("var:")){let n=t.op.substring(4);if(n==="pi")retu'
html += b'rn p.const(Math.PI);if(n==="e")return p.const(Math.E);if(n=='
html += b'="i")return p.const(0,1);if(n in e)return e[n];throw new Err'
html += b'or("eval-error: unknown variable \'"+n+"\'")}else throw new Er'
html += b'ror("UNIMPLEMENTED eval \'"+t.op+"\'")}return i}static parse(e'
html += b'){let t=new r;if(t.src=e,t.token="",t.skippedWhiteSpace=!1,t'
html += b'.pos=0,t.next(),t.root=t.parseExpr(!1),t.token!=="")throw ne'
html += b'w Error("remaining tokens: "+t.token+"...");return t}parseEx'
html += b'pr(e){return this.parseAdd(e)}parseAdd(e){let t=this.parseMu'
html += b'l(e);for(;["+","-"].includes(this.token)&&!(e&&this.skippedW'
html += b'hiteSpace);){let s=this.token;this.next(),t=new p(s,[t,this.'
html += b'parseMul(e)])}return t}parseMul(e){let t=this.parsePow(e);fo'
html += b'r(;!(e&&this.skippedWhiteSpace);){let s="*";if(["*","/"].inc'
html += b'ludes(this.token))s=this.token,this.next();else if(!e&&this.'
html += b'token==="(")s="*";else if(this.token.length>0&&(this.isAlpha'
html += b'(this.token[0])||this.isNum(this.token[0])))s="*";else break'
html += b';t=new p(s,[t,this.parsePow(e)])}return t}parsePow(e){let t='
html += b'this.parseUnary(e);for(;["^"].includes(this.token)&&!(e&&thi'
html += b's.skippedWhiteSpace);){let s=this.token;this.next(),t=new p('
html += b's,[t,this.parseUnary(e)])}return t}parseUnary(e){return this'
html += b'.token==="-"?(this.next(),new p(".-",[this.parseMul(e)])):th'
html += b'is.parseInfix(e)}parseInfix(e){if(this.token.length==0)throw'
html += b' new Error("expected unary");if(this.isNum(this.token[0])){l'
html += b'et t=this.token;return this.next(),this.token==="."&&(t+="."'
html += b',this.next(),this.token.length>0&&(t+=this.token,this.next()'
html += b')),new p("const",[],parseFloat(t))}else if(this.fun1().lengt'
html += b'h>0){let t=this.fun1();this.next(t.length);let s=null;if(thi'
html += b's.token==="(")if(this.next(),s=this.parseExpr(e),this.token+'
html += b'="",this.token===")")this.next();else throw Error("expected '
html += b'\')\'");else s=this.parseMul(!0);return new p(t,[s])}else if(t'
html += b'his.token==="("){this.next();let t=this.parseExpr(e);if(this'
html += b'.token+="",this.token===")")this.next();else throw Error("ex'
html += b'pected \')\'");return t.explicitParentheses=!0,t}else if(this.'
html += b'token==="|"){this.next();let t=this.parseExpr(e);if(this.tok'
html += b'en+="",this.token==="|")this.next();else throw Error("expect'
html += b'ed \'|\'");return new p("abs",[t])}else if(this.isAlpha(this.t'
html += b'oken[0])){let t="";return this.token.startsWith("pi")?t="pi"'
html += b':t=this.token[0],t==="I"&&(t="i"),this.next(t.length),new p('
html += b'"var:"+t,[])}else throw new Error("expected unary")}compare('
html += b'e){let i=new Set;this.getVars(i),e.getVars(i);for(let a=0;a<'
html += b'10;a++){let l={};for(let o of i)l[o]=p.const(Math.random(),M'
html += b'ath.random());let h=new p("==",[this.root,e.root]),n=this.ev'
html += b'al(l,h);if(Math.abs(n.re)<1e-9)return!1}return!0}fun1(){let '
html += b'e=["abs","sinc","sin","cos","tan","cot","exp","ln","sqrt"];f'
html += b'or(let t of e)if(this.token.toLowerCase().startsWith(t))retu'
html += b'rn t;return""}next(e=-1){if(e>0&&this.token.length>e){this.t'
html += b'oken=this.token.substring(e),this.skippedWhiteSpace=!1;retur'
html += b'n}this.token="";let t=!1,s=this.src.length;for(this.skippedW'
html += b'hiteSpace=!1;this.pos<s&&`\t\n `.includes(this.src[this.pos]);'
html += b')this.skippedWhiteSpace=!0,this.pos++;for(;!t&&this.pos<s;){'
html += b'let i=this.src[this.pos];if(this.token.length>0&&(this.isNum'
html += b'(this.token[0])&&this.isAlpha(i)||this.isAlpha(this.token[0]'
html += b')&&this.isNum(i)))return;if(`^%#*$()[]{},.:;+-*/_!<>=?|\t\n `.'
html += b'includes(i)){if(this.token.length>0)return;t=!0}`\t\n `.includ'
html += b'es(i)==!1&&(this.token+=i),this.pos++}}isNum(e){return e.cha'
html += b'rCodeAt(0)>=48&&e.charCodeAt(0)<=57}isAlpha(e){return e.char'
html += b'CodeAt(0)>=65&&e.charCodeAt(0)<=90||e.charCodeAt(0)>=97&&e.c'
html += b'harCodeAt(0)<=122||e==="_"}toString(){return this.root==null'
html += b'?"":this.root.toString()}toTexString(){return this.root==nul'
html += b'l?"":this.root.toTexString()}},p=class r{constructor(e,t,s=0'
html += b',i=0){this.op=e,this.c=t,this.re=s,this.im=i,this.explicitPa'
html += b'rentheses=!1}static const(e=0,t=0){return new r("const",[],e'
html += b',t)}compare(e,t=0,s=1e-9){let i=this.re-e,a=this.im-t;return'
html += b' Math.sqrt(i*i+a*a)<s}toString(){let e="";if(this.op==="cons'
html += b't"){let t=Math.abs(this.re)>1e-14,s=Math.abs(this.im)>1e-14;'
html += b't&&s&&this.im>=0?e="("+this.re+"+"+this.im+"i)":t&&s&&this.i'
html += b'm<0?e="("+this.re+"-"+-this.im+"i)":t?e=""+this.re:s&&(e="("'
html += b'+this.im+"i)")}else this.op.startsWith("var")?e=this.op.spli'
html += b't(":")[1]:this.c.length==1?e=(this.op===".-"?"-":this.op)+"('
html += b'"+this.c.toString()+")":e="("+this.c.map(t=>t.toString()).jo'
html += b'in(this.op)+")";return e}toTexString(e=!1){let s="";switch(t'
html += b'his.op){case"const":{let i=Math.abs(this.re)>1e-9,a=Math.abs'
html += b'(this.im)>1e-9,l=i?""+this.re:"",h=a?""+this.im+"i":"";h==="'
html += b'1i"?h="i":h==="-1i"&&(h="-i"),!i&&!a?s="0":(a&&this.im>=0&&i'
html += b'&&(h="+"+h),s=l+h);break}case".-":s="-"+this.c[0].toTexStrin'
html += b'g();break;case"+":case"-":case"*":case"^":{let i=this.c[0].t'
html += b'oTexString(),a=this.c[1].toTexString(),l=this.op==="*"?"\\\\cd'
html += b'ot ":this.op;s="{"+i+"}"+l+"{"+a+"}";break}case"/":{let i=th'
html += b'is.c[0].toTexString(!0),a=this.c[1].toTexString(!0);s="\\\\fra'
html += b'c{"+i+"}{"+a+"}";break}case"sin":case"sinc":case"cos":case"t'
html += b'an":case"cot":case"exp":case"ln":{let i=this.c[0].toTexStrin'
html += b'g(!0);s+="\\\\"+this.op+"\\\\left("+i+"\\\\right)";break}case"sqrt'
html += b'":{let i=this.c[0].toTexString(!0);s+="\\\\"+this.op+"{"+i+"}"'
html += b';break}case"abs":{let i=this.c[0].toTexString(!0);s+="\\\\left'
html += b'|"+i+"\\\\right|";break}default:if(this.op.startsWith("var:"))'
html += b'{let i=this.op.substring(4);switch(i){case"pi":i="\\\\pi";brea'
html += b'k}s=" "+i+" "}else{let i="warning: Node.toString(..):";i+=" '
html += b'unimplemented operator \'"+this.op+"\'",console.log(i),s=this.'
html += b'op,this.c.length>0&&(s+="\\\\left({"+this.c.map(a=>a.toTexStri'
html += b'ng(!0)).join(",")+"}\\\\right)")}}return!e&&this.explicitParen'
html += b'theses&&(s="\\\\left({"+s+"}\\\\right)"),s}};function J(r){r.fee'
html += b'dbackSpan.innerHTML="",r.numChecked=0,r.numCorrect=0;for(let'
html += b' s in r.expected){let i=r.types[s],a=r.student[s],l=r.expect'
html += b'ed[s];switch(i){case"bool":r.numChecked++,a===l&&r.numCorrec'
html += b't++;break;case"string":{r.numChecked++;let h=r.gapInputs[s],'
html += b'n=a.trim().toUpperCase(),o=l.trim().toUpperCase(),u=Z(n,o)<='
html += b'1;u&&(r.numCorrect++,r.gapInputs[s].value=o,r.student[s]=o),'
html += b'h.style.color=u?"black":"white",h.style.backgroundColor=u?"t'
html += b'ransparent":"maroon";break}case"int":r.numChecked++,Math.abs'
html += b'(parseFloat(a)-parseFloat(l))<1e-9&&r.numCorrect++;break;cas'
html += b'e"float":case"term":{r.numChecked++;try{let h=k.parse(l),n=k'
html += b'.parse(a);h.compare(n)&&r.numCorrect++}catch(h){r.debug&&(co'
html += b'nsole.log("term invalid"),console.log(h))}break}case"vector"'
html += b':case"complex":case"set":{let h=l.split(",");r.numChecked+=h'
html += b'.length;let n=[];for(let o=0;o<h.length;o++)n.push(r.student'
html += b'[s+"-"+o]);if(i==="set")for(let o=0;o<h.length;o++)try{let m'
html += b'=k.parse(h[o]);for(let u=0;u<n.length;u++){let c=k.parse(n[u'
html += b']);if(m.compare(c)){r.numCorrect++;break}}}catch(m){r.debug&'
html += b'&console.log(m)}else for(let o=0;o<h.length;o++)try{let m=k.'
html += b'parse(n[o]),u=k.parse(h[o]);m.compare(u)&&r.numCorrect++}cat'
html += b'ch(m){r.debug&&console.log(m)}break}case"matrix":{let h=new '
html += b'b(0,0);h.fromString(l),r.numChecked+=h.m*h.n;for(let n=0;n<h'
html += b'.m;n++)for(let o=0;o<h.n;o++){let m=n*h.n+o;a=r.student[s+"-'
html += b'"+m];let u=h.v[m];try{let c=k.parse(u),d=k.parse(a);c.compar'
html += b'e(d)&&r.numCorrect++}catch(c){r.debug&&console.log(c)}}break'
html += b'}default:r.feedbackSpan.innerHTML="UNIMPLEMENTED EVAL OF TYP'
html += b'E "+i}}r.state=r.numCorrect==r.numChecked?v.passed:v.errors,'
html += b'r.updateVisualQuestionState();let e=r.state===v.passed?O[r.l'
html += b'anguage]:_[r.language],t=e[Math.floor(Math.random()*e.length'
html += b')];r.feedbackPopupDiv.innerHTML=t,r.feedbackPopupDiv.style.c'
html += b'olor=r.state===v.passed?"green":"maroon",r.feedbackPopupDiv.'
html += b'style.display="block",setTimeout(()=>{r.feedbackPopupDiv.sty'
html += b'le.display="none"},500),r.state===v.passed?r.src.instances.l'
html += b'ength>0?r.checkAndRepeatBtn.innerHTML=G:r.checkAndRepeatBtn.'
html += b'style.display="none":r.checkAndRepeatBtn.innerHTML=T}var y=c'
html += b'lass{constructor(e,t,s,i,a,l){t.student[s]="",this.question='
html += b't,this.inputId=s,this.outerSpan=f(""),this.outerSpan.style.p'
html += b'osition="relative",e.appendChild(this.outerSpan),this.inputE'
html += b'lement=L(Math.max(i*12,48)),this.outerSpan.appendChild(this.'
html += b'inputElement),this.equationPreviewDiv=g(),this.equationPrevi'
html += b'ewDiv.classList.add("equationPreview"),this.equationPreviewD'
html += b'iv.style.display="none",this.outerSpan.appendChild(this.equa'
html += b'tionPreviewDiv),this.inputElement.addEventListener("click",('
html += b')=>{this.question.editedQuestion(),this.edited()}),this.inpu'
html += b'tElement.addEventListener("keyup",()=>{this.question.editedQ'
html += b'uestion(),this.edited()}),this.inputElement.addEventListener'
html += b'("focusout",()=>{this.equationPreviewDiv.innerHTML="",this.e'
html += b'quationPreviewDiv.style.display="none"}),this.inputElement.a'
html += b'ddEventListener("keydown",h=>{let n="abcdefghijklmnopqrstuvw'
html += b'xyz";n+="ABCDEFGHIJKLMNOPQRSTUVWXYZ",n+="0123456789",n+="+-*'
html += b'/^(). <>=|",l&&(n="-0123456789"),h.key.length<3&&n.includes('
html += b'h.key)==!1&&h.preventDefault();let o=this.inputElement.value'
html += b'.length*12;this.inputElement.offsetWidth<o&&(this.inputEleme'
html += b'nt.style.width=""+o+"px")}),this.question.showSolution&&(t.s'
html += b'tudent[s]=this.inputElement.value=a)}edited(){let e=this.inp'
html += b'utElement.value.trim(),t="",s=!1;try{let i=k.parse(e);s=i.ro'
html += b'ot.op==="const",t=i.toTexString(),this.inputElement.style.co'
html += b'lor="black",this.equationPreviewDiv.style.backgroundColor="g'
html += b'reen"}catch{t=e.replaceAll("^","\\\\hat{~}").replaceAll("_","\\'
html += b'\\_"),this.inputElement.style.color="maroon",this.equationPre'
html += b'viewDiv.style.backgroundColor="maroon"}B(this.equationPrevie'
html += b'wDiv,t,!0),this.equationPreviewDiv.style.display=e.length>0&'
html += b'&!s?"block":"none",this.question.student[this.inputId]=e}},I'
html += b'=class{constructor(e,t,s,i){this.parent=e,this.question=t,th'
html += b'is.inputId=s,this.matExpected=new b(0,0),this.matExpected.fr'
html += b'omString(i),this.matStudent=new b(this.matExpected.m==1?1:3,'
html += b'this.matExpected.n==1?1:3),t.showSolution&&this.matStudent.f'
html += b'romMatrix(this.matExpected),this.genMatrixDom()}genMatrixDom'
html += b'(){let e=g();this.parent.innerHTML="",this.parent.appendChil'
html += b'd(e),e.style.position="relative",e.style.display="inline-blo'
html += b'ck";let t=document.createElement("table");e.appendChild(t);l'
html += b'et s=this.matExpected.getMaxCellStrlen();for(let c=0;c<this.'
html += b'matStudent.m;c++){let d=document.createElement("tr");t.appen'
html += b'dChild(d),c==0&&d.appendChild(this.generateMatrixParenthesis'
html += b'(!0,this.matStudent.m));for(let w=0;w<this.matStudent.n;w++)'
html += b'{let x=c*this.matStudent.n+w,E=document.createElement("td");'
html += b'd.appendChild(E);let H=this.inputId+"-"+x;new y(E,this.quest'
html += b'ion,H,s,this.matStudent.v[x],!1)}c==0&&d.appendChild(this.ge'
html += b'nerateMatrixParenthesis(!1,this.matStudent.m))}let i=["+","-'
html += b'","+","-"],a=[0,0,1,-1],l=[1,-1,0,0],h=[0,22,888,888],n=[888'
html += b',888,-22,-22],o=[-22,-22,0,22],m=[this.matExpected.n!=1,this'
html += b'.matExpected.n!=1,this.matExpected.m!=1,this.matExpected.m!='
html += b'1],u=[this.matStudent.n>=10,this.matStudent.n<=1,this.matStu'
html += b'dent.m>=10,this.matStudent.m<=1];for(let c=0;c<4;c++){if(m[c'
html += b']==!1)continue;let d=f(i[c]);h[c]!=888&&(d.style.top=""+h[c]'
html += b'+"px"),n[c]!=888&&(d.style.bottom=""+n[c]+"px"),o[c]!=888&&('
html += b'd.style.right=""+o[c]+"px"),d.classList.add("matrixResizeBut'
html += b'ton"),e.appendChild(d),u[c]?d.style.opacity="0.5":d.addEvent'
html += b'Listener("click",()=>{this.matStudent.resize(this.matStudent'
html += b'.m+a[c],this.matStudent.n+l[c],"0"),this.genMatrixDom()})}}g'
html += b'enerateMatrixParenthesis(e,t){let s=document.createElement("'
html += b'td");s.style.width="3px";for(let i of["Top",e?"Left":"Right"'
html += b',"Bottom"])s.style["border"+i+"Width"]="2px",s.style["border'
html += b'"+i+"Style"]="solid";return s.rowSpan=t,s}};var v={init:0,er'
html += b'rors:1,passed:2},P=class{constructor(e,t,s,i){this.state=v.i'
html += b'nit,this.language=s,this.src=t,this.debug=i,this.instanceOrd'
html += b'er=R(t.instances.length,!0),this.instanceIdx=0,this.choiceId'
html += b'x=0,this.gapIdx=0,this.expected={},this.types={},this.studen'
html += b't={},this.gapInputs={},this.parentDiv=e,this.questionDiv=nul'
html += b'l,this.feedbackPopupDiv=null,this.titleDiv=null,this.checkAn'
html += b'dRepeatBtn=null,this.showSolution=!1,this.feedbackSpan=null,'
html += b'this.numCorrect=0,this.numChecked=0}reset(){this.instanceIdx'
html += b'=(this.instanceIdx+1)%this.src.instances.length}getCurrentIn'
html += b'stance(){return this.src.instances[this.instanceOrder[this.i'
html += b'nstanceIdx]]}editedQuestion(){this.state=v.init,this.updateV'
html += b'isualQuestionState(),this.questionDiv.style.color="black",th'
html += b'is.checkAndRepeatBtn.innerHTML=T,this.checkAndRepeatBtn.styl'
html += b'e.display="block",this.checkAndRepeatBtn.style.color="black"'
html += b'}updateVisualQuestionState(){let e="black",t="transparent";s'
html += b'witch(this.state){case v.init:e="rgb(0,0,0)",t="transparent"'
html += b';break;case v.passed:e="rgb(0,150,0)",t="rgba(0,150,0, 0.025'
html += b')";break;case v.errors:e="rgb(150,0,0)",t="rgba(150,0,0, 0.0'
html += b'25)",this.numChecked>=5&&(this.feedbackSpan.innerHTML=""+thi'
html += b's.numCorrect+" / "+this.numChecked);break}this.questionDiv.s'
html += b'tyle.color=this.feedbackSpan.style.color=this.titleDiv.style'
html += b'.color=this.checkAndRepeatBtn.style.backgroundColor=this.que'
html += b'stionDiv.style.borderColor=e,this.questionDiv.style.backgrou'
html += b'ndColor=t}populateDom(){if(this.parentDiv.innerHTML="",this.'
html += b'questionDiv=g(),this.parentDiv.appendChild(this.questionDiv)'
html += b',this.questionDiv.classList.add("question"),this.feedbackPop'
html += b'upDiv=g(),this.feedbackPopupDiv.classList.add("questionFeedb'
html += b'ack"),this.questionDiv.appendChild(this.feedbackPopupDiv),th'
html += b'is.feedbackPopupDiv.innerHTML="awesome",this.debug&&"src_lin'
html += b'e"in this.src){let i=g();i.classList.add("debugInfo"),i.inne'
html += b'rHTML="Source code: lines "+this.src.src_line+"..",this.ques'
html += b'tionDiv.appendChild(i)}if(this.titleDiv=g(),this.questionDiv'
html += b'.appendChild(this.titleDiv),this.titleDiv.classList.add("que'
html += b'stionTitle"),this.titleDiv.innerHTML=this.src.title,this.src'
html += b'.error.length>0){let i=f(this.src.error);this.questionDiv.ap'
html += b'pendChild(i),i.style.color="red";return}for(let i of this.sr'
html += b'c.text.c)this.questionDiv.appendChild(this.generateText(i));'
html += b'let e=g();this.questionDiv.appendChild(e),e.classList.add("b'
html += b'uttonRow");let t=Object.keys(this.expected).length>0;t&&(thi'
html += b's.checkAndRepeatBtn=U(),e.appendChild(this.checkAndRepeatBtn'
html += b'),this.checkAndRepeatBtn.innerHTML=T,this.checkAndRepeatBtn.'
html += b'style.backgroundColor="black");let s=f("&nbsp;&nbsp;&nbsp;")'
html += b';if(e.appendChild(s),this.feedbackSpan=f(""),e.appendChild(t'
html += b'his.feedbackSpan),this.debug){if(this.src.variables.length>0'
html += b'){let l=g();l.classList.add("debugInfo"),l.innerHTML="Variab'
html += b'les generated by Python Code",this.questionDiv.appendChild(l'
html += b');let h=g();h.classList.add("debugCode"),this.questionDiv.ap'
html += b'pendChild(h);let n=this.getCurrentInstance(),o="",m=[...this'
html += b'.src.variables];m.sort();for(let u of m){let c=n[u].t,d=n[u]'
html += b'.v;switch(c){case"vector":d="["+d+"]";break;case"set":d="{"+'
html += b'd+"}";break}o+=c+" "+u+" = "+d+"<br/>"}h.innerHTML=o}let i=['
html += b'"python_src_html","text_src_html"],a=["Python Source Code","'
html += b'Text Source Code"];for(let l=0;l<i.length;l++){let h=i[l];if'
html += b'(h in this.src&&this.src[h].length>0){let n=g();n.classList.'
html += b'add("debugInfo"),n.innerHTML=a[l],this.questionDiv.appendChi'
html += b'ld(n);let o=g();o.classList.add("debugCode"),this.questionDi'
html += b'v.append(o),o.innerHTML=this.src[h]}}}t&&this.checkAndRepeat'
html += b'Btn.addEventListener("click",()=>{this.state==v.passed?(this'
html += b'.state=v.init,this.reset(),this.populateDom()):J(this)})}gen'
html += b'erateMathString(e){let t="";switch(e.t){case"math":case"disp'
html += b'lay-math":for(let s of e.c)t+=this.generateMathString(s);bre'
html += b'ak;case"text":return e.d;case"var":{let s=this.getCurrentIns'
html += b'tance(),i=s[e.d].t,a=s[e.d].v;switch(i){case"vector":return"'
html += b'\\\\left["+a+"\\\\right]";case"set":return"\\\\left\\\\{"+a+"\\\\right'
html += b'\\\\}";case"complex":{let l=a.split(","),h=parseFloat(l[0]),n='
html += b'parseFloat(l[1]);return p.const(h,n).toTexString()}case"matr'
html += b'ix":{let l=new b(0,0);return l.fromString(a),t=l.toTeXString'
html += b'(e.d.includes("augmented")),t}case"term":{try{t=k.parse(a).t'
html += b'oTexString()}catch{}break}default:t=a}}}return"{"+t+"}"}gene'
html += b'rateText(e,t=!1){switch(e.t){case"paragraph":case"span":{let'
html += b' s=document.createElement(e.t=="span"||t?"span":"p");for(let'
html += b' i of e.c)s.appendChild(this.generateText(i));return s}case"'
html += b'text":return f(e.d);case"code":{let s=f(e.d);return s.classL'
html += b'ist.add("code"),s}case"italic":case"bold":{let s=f("");retur'
html += b'n s.append(...e.c.map(i=>this.generateText(i))),e.t==="bold"'
html += b'?s.style.fontWeight="bold":s.style.fontStyle="italic",s}case'
html += b'"math":case"display-math":{let s=this.generateMathString(e);'
html += b'return M(s,e.t==="display-math")}case"gap":{let s=f(""),i=Ma'
html += b'th.max(e.d.length*14,24),a=L(i),l="gap-"+this.gapIdx;return '
html += b'this.gapInputs[l]=a,this.expected[l]=e.d,this.types[l]="stri'
html += b'ng",a.addEventListener("keyup",()=>{this.editedQuestion(),a.'
html += b'value=a.value.toUpperCase(),this.student[l]=a.value.trim()})'
html += b',this.student[l]="",this.showSolution&&(this.student[l]=a.va'
html += b'lue=this.expected[l]),this.gapIdx++,s.appendChild(a),s}case"'
html += b'input":case"input2":{let s=e.t==="input2",i=f("");i.style.ve'
html += b'rticalAlign="text-bottom";let a=e.d,l=this.getCurrentInstanc'
html += b'e()[a];if(this.expected[a]=l.v,this.types[a]=l.t,!s)switch(l'
html += b'.t){case"set":i.append(M("\\\\{"),f(" "));break;case"vector":i'
html += b'.append(M("["),f(" "));break}if(l.t==="vector"||l.t==="set")'
html += b'{let h=l.v.split(","),n=h.length;for(let o=0;o<n;o++){o>0&&i'
html += b'.appendChild(f(" , "));let m=a+"-"+o;new y(i,this,m,h[o].len'
html += b'gth,h[o],!1)}}else if(l.t==="matrix"){let h=g();i.appendChil'
html += b'd(h),new I(h,this,a,l.v)}else if(l.t==="complex"){let h=l.v.'
html += b'split(",");new y(i,this,a+"-0",h[0].length,h[0],!1),i.append'
html += b'(f(" "),M("+"),f(" ")),new y(i,this,a+"-1",h[1].length,h[1],'
html += b'!1),i.append(f(" "),M("i"))}else{let h=l.t==="int";new y(i,t'
html += b'his,a,l.v.length,l.v,h)}if(!s)switch(l.t){case"set":i.append'
html += b'(f(" "),M("\\\\}"));break;case"vector":i.append(f(" "),M("]"))'
html += b';break}return i}case"itemize":return N(e.c.map(s=>W(this.gen'
html += b'erateText(s))));case"single-choice":case"multi-choice":{let '
html += b's=e.t=="multi-choice",i=document.createElement("table"),a=e.'
html += b'c.length,l=this.debug==!1,h=R(a,l),n=s?K:Y,o=s?q:X,m=[],u=[]'
html += b';for(let c=0;c<a;c++){let d=h[c],w=e.c[d],x="mc-"+this.choic'
html += b'eIdx+"-"+d;u.push(x);let E=w.c[0].t=="bool"?w.c[0].d:this.ge'
html += b'tCurrentInstance()[w.c[0].d].v;this.expected[x]=E,this.types'
html += b'[x]="bool",this.student[x]=this.showSolution?E:"false";let H'
html += b'=this.generateText(w.c[1],!0),C=document.createElement("tr")'
html += b';i.appendChild(C),C.style.cursor="pointer";let S=document.cr'
html += b'eateElement("td");m.push(S),C.appendChild(S),S.innerHTML=thi'
html += b's.student[x]=="true"?n:o;let V=document.createElement("td");'
html += b'C.appendChild(V),V.appendChild(H),s?C.addEventListener("clic'
html += b'k",()=>{this.editedQuestion(),this.student[x]=this.student[x'
html += b']==="true"?"false":"true",this.student[x]==="true"?S.innerHT'
html += b'ML=n:S.innerHTML=o}):C.addEventListener("click",()=>{this.ed'
html += b'itedQuestion();for(let D of u)this.student[D]="false";this.s'
html += b'tudent[x]="true";for(let D=0;D<u.length;D++){let Q=h[D];m[Q]'
html += b'.innerHTML=this.student[u[Q]]=="true"?n:o}})}return this.cho'
html += b'iceIdx++,i}default:{let s=f("UNIMPLEMENTED("+e.t+")");return'
html += b' s.style.color="red",s}}}};function re(r,e){["en","de","es",'
html += b'"it","fr"].includes(r.lang)==!1&&(r.lang="en"),e&&(document.'
html += b'getElementById("debug").style.display="block"),document.getE'
html += b'lementById("date").innerHTML=r.date,document.getElementById('
html += b'"title").innerHTML=r.title,document.getElementById("author")'
html += b'.innerHTML=r.author,document.getElementById("courseInfo1").i'
html += b'nnerHTML=z[r.lang];let t=\'<span onclick="location.reload()" '
html += b'style="text-decoration: underline; font-weight: bold; cursor'
html += b': pointer">\'+j[r.lang]+"</span>";document.getElementById("co'
html += b'urseInfo2").innerHTML=F[r.lang].replace("*",t);let s=[],i=do'
html += b'cument.getElementById("questions"),a=1;for(let l of r.questi'
html += b'ons){l.title=""+a+". "+l.title;let h=g();i.appendChild(h);le'
html += b't n=new P(h,l,r.lang,e);n.showSolution=e,s.push(n),n.populat'
html += b'eDom(),e&&l.error.length==0&&n.checkAndRepeatBtn.click(),a++'
html += b'}}return ne(ae);})();sell.init(quizSrc,debug);</script></bod'
html += b'y> </html> '
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
