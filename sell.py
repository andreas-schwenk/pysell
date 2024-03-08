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

FAQ
    
    Q:  Why is this file so long?
    A:  The intention is to provide pySelL as ONE file, that can easily be
        shared and modified.

    Q:  You could also package and publish pySELL as a package!
    A:  Sure. Maybe this will happen in the future..
"""


import base64
import datetime
import io
import json
import os
import re
import sys
from typing import Self


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
            if ch in "`^'\"%#*$()[]{}\\,.:;+-*/_!<>\t\n =?|&":
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


# The following function rangeZ is provided as pseudo-intrinsic
# function in Python scripts, embedded into the question descriptions.
# It is an alternative version for "range", that excludes the zero.
# This is beneficial for drawing random numbers of questions for math classes.
def rangeZ(*a):
    """implements 'range', but excludes the zero"""
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


# TODO: add comments starting from here


class TextNode:
    """Tree structure for the question text"""

    def __init__(self, type_: str, data: str = "") -> None:
        self.type: str = type_
        self.data: str = data
        self.children: list[TextNode] = []

    def parse(self) -> None:
        """parses text recursively"""
        if self.type == "root":
            self.children = [TextNode(" ", "")]
            lines = self.data.split("\n")
            self.data = ""
            for line in lines:
                line = line.strip()
                if len(line) == 0:
                    continue
                type_ = line[0]  # refer to "types" below
                if type_ not in "[(-!":
                    type_ = " "
                if type_ != self.children[-1].type:
                    self.children.append(TextNode(type_, ""))
                self.children[-1].type = type_
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
                "!": "command",
            }
            for child in self.children:
                child.type = types[child.type]
                child.parse()

        elif self.type in ("multi-choice", "single-choice"):
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

        elif self.type == "command":
            if (
                ".svg" in self.data
                or ".png" in self.data
                or ".jpg" in self.data
                or ".jpeg" in self.data
            ):
                self.parse_image()
            else:
                # TODO: report error
                pass

        else:
            raise Exception("unimplemented")

    def parse_image(self) -> Self:
        """parses an image inclusion"""
        img_path = self.data[1:].strip()
        img_width = 100  # percentage
        if ":" in img_path:
            tokens = img_path.split(":")
            img_path = tokens[0].strip()
            img_width = tokens[1].strip()
        self.type = "image"
        self.data = img_path
        self.children.append(TextNode("width", img_width))

    def parse_span(self, lex: Lexer) -> Self:
        """parses a span element"""
        # grammar: span = { item };
        #          item = bold | math | input | string_var | plus_minus | text;
        #          bold = "*" { item } "*";
        #          math = "$" { item } "$";
        #          input = "%" ["!"] var;
        #          string_var = "&" var;
        #          plus_minus = "+" "-";
        #          text = "\\" | otherwise;
        span = TextNode("span")
        while lex.token != "":
            span.children.append(self.parse_item(lex))
        return span

    def parse_item(self, lex: Lexer, math_mode=False) -> Self:
        """parses a single item of a span/paragraph"""
        if not math_mode and lex.token == "*":
            return self.parse_bold_italic(lex)
        if lex.token == "$":
            return self.parse_math(lex)
        if not math_mode and lex.token == "%":
            return self.parse_input(lex)
        if not math_mode and lex.token == "&":
            return self.parse_string_var(lex)
        if math_mode and lex.token == "+":
            n = TextNode("text", lex.token)
            lex.next()
            if lex.token == "-":
                # "+-" automatically chooses "+" or "-",
                # depending on the sign or the following variable.
                # For the variable itself, only its absolute value is used.
                n.data += lex.token
                n.type = "plus_minus"
                lex.next()
            return n
        if not math_mode and lex.token == "\\":
            lex.next()
            if lex.token == "\\":
                lex.next()
            return TextNode("text", "<br/>")
        n = TextNode("text", lex.token)
        lex.next()
        return n

    def parse_bold_italic(self, lex: Lexer) -> Self:
        """parses bold or italic text"""
        node = TextNode("italic")
        if lex.token == "*":
            lex.next()
        if lex.token == "*":
            node.type = "bold"
            lex.next()
        while lex.token not in ("", "*"):
            node.children.append(self.parse_item(lex))
        if lex.token == "*":
            lex.next()
        if lex.token == "*":
            lex.next()
        return node

    def parse_math(self, lex: Lexer) -> Self:
        """parses inline math or display style math"""
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
        """parses an input element field"""
        input_ = TextNode("input")
        if lex.token == "%":
            lex.next()
        if lex.token == "!":
            input_.type = "input2"
            lex.next()
        input_.data = lex.token.strip()
        lex.next()
        return input_

    def parse_string_var(self, lex: Lexer) -> Self:
        """parses a string variable"""
        sv = TextNode("string_var")
        if lex.token == "&":
            lex.next()
        sv.data = lex.token.strip()
        lex.next()
        return sv

    def optimize(self) -> Self:
        """optimizes the current text node recursively. E.g. multiple pure
        text items are concatenated into a single text node."""
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
        """recursively exports the text node instance to a dictionary"""
        # t := type, d := data, c := children
        return {
            "t": self.type,
            "d": self.data,
            "c": list(map(lambda o: o.to_dict(), self.children)),
        }


class Question:
    """Question of the quiz"""

    def __init__(self, input_dirname: str, src_line_no: int) -> None:
        self.input_dirname: str = input_dirname
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
        """builds a question from text and Python sources"""
        if len(self.python_src) > 0:
            self.analyze_python_code()
            instances_str = []
            if len(self.error) == 0:
                for _ in range(0, 5):
                    # try to generate instances distinct to prior once
                    # TODO: give up and keep less than 5, if applicable!
                    instance = {}
                    instance_str = ""
                    for _ in range(0, 10):
                        self.error = ""
                        instance = self.run_python_code()
                        instance_str = str(instance)
                        if instance_str not in instances_str:
                            break
                    instances_str.append(instance_str)
                    self.instances.append(instance)
                    # if there is no randomization in the input, then one instance is enough
                    if "rand" not in self.python_src:
                        break
                if "No module named" in self.error:
                    print("!!! " + self.error)
        self.text = TextNode("root", self.text_src)
        self.text.parse()
        self.post_process_text(self.text)
        self.text.optimize()

    def post_process_text(self, node: TextNode, math=False) -> None:
        """post processes the textual part. For example, a semantical check
        for the existing of referenced variables is applied. Also images
        are loaded and stringified."""
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
                self.error += f"Unknown input variable '{var_id}'. "
        elif node.type == "string_var":
            var_id = node.data
            if var_id not in self.variables:
                self.error += f"Unknown string variable '{var_id}'. "
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
        elif node.type == "image":
            # TODO: warning, if file size is (too) large
            path = os.path.join(self.input_dirname, node.data)
            img_type = os.path.splitext(path)[1][1:]
            supported_img_types = ["svg", "png", "jpg", "jpeg"]
            if img_type not in supported_img_types:
                self.error += f"ERROR: image type '{img_type}' is not supported. "
                self.error += f"Use one of {', '.join(supported_img_types)}"
            elif os.path.isfile(path) == False:
                self.error += "ERROR: cannot find image at path '" + path + '"'
            else:
                # load image
                f = open(path, "rb")
                data = f.read()
                f.close()
                b64 = base64.b64encode(data)
                node.children.append(TextNode("data", b64.decode("utf-8")))

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
        # check for forbidden code
        if "matplotlib" in self.python_src and "show(" in self.python_src:
            self.error += "Remove the call show(), "
            self.error += "since this would result in MANY open windows :-)"

    def run_python_code(self) -> dict:
        """Runs the questions python code and gathers all local variables."""
        locals = {}
        res = {}
        src = self.python_src
        try:
            exec(src, globals(), locals)
        except Exception as e:
            # print(e)
            self.error += str(e) + ". "
            return res
        for local_id, value in locals.items():
            if local_id in skipVariables or (local_id not in self.python_src_tokens):
                continue
            type_str = str(type(value))
            if type_str in ("<class 'module'>", "<class 'function'>"):
                continue
            self.variables.add(local_id)
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
            elif type_str == "<class 'str'>":
                t = "string"
                v = value
            else:
                t = "term"
                v = str(value).replace("**", "^")
                # in case that an ODE is contained in the question
                # and only one constant ("C1") is present, then substitute
                # "C1" by "C"
                if "dsolve" in self.python_src:
                    if "C2" not in v:
                        v = v.replace("C1", "C")
            # t := type, v := value
            v = v.replace("I", "i")  # reformat sympy imaginary part
            res[local_id] = {"t": t, "v": v}
        if len(self.variables) > 50:
            self.error += "ERROR: Wrong usage of Python imports. Refer to pySELL docs!"
            # TODO: write the docs...

        if "matplotlib" in self.python_src:
            import matplotlib.pyplot as plt

            buf = io.BytesIO()
            plt.savefig(buf, format="svg", transparent=True)
            buf.seek(0)
            svg = buf.read()
            b64 = base64.b64encode(svg)
            res["__svg_image"] = {"t": "svg", "v": b64.decode("utf-8")}
            plt.clf()
        return res

    def to_dict(self) -> dict:
        """recursively exports the question to a dictionary"""
        return {
            "title": self.title,
            "error": self.error,
            "is_ode": "dsolve"  # contains an Ordinary Differential Equation
            in self.python_src,
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
        """syntax highlights a single questions text line and returns the
        formatted code in HTML format"""
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

    def red_colored_span(self, inner_html: str) -> str:
        """embeds HTML code into a red colored span"""
        return '<span style="color:#FF5733; font-weight:bold">' + inner_html + "</span>"

    def syntax_highlight_text(self, src: str) -> str:
        """syntax highlights a questions text and returns the formatted code in
        HTML format"""
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
        """syntax highlights a questions python code and returns the formatted
        code in HTML format"""
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


def compile_input_file(input_dirname: str, src: str) -> dict:
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
        line_not_stripped = line
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
            question = Question(input_dirname, line_no + 1)
            questions.append(question)
            question.title = line[8:].strip()
            parsing_python = False
        elif question is not None:
            if line.startswith('"""'):
                parsing_python = not parsing_python
            else:
                if parsing_python:
                    question.python_src += (
                        line_not_stripped.replace("\t", "    ") + "\n"
                    )
                else:
                    question.text_src += line + "\n"
    for question in questions:
        question.build()
    return {
        "lang": lang,
        "title": title,
        "author": author,
        "date": datetime.datetime.today().strftime("%Y-%m-%d"),
        "info": info,
        "questions": list(map(lambda o: o.to_dict(), questions)),
    }


# the following code is automatically generated and updated by file "build.py"
# @begin(html)
HTML: str = b''
HTML += b'<!DOCTYPE html> <html> <head> <meta charset="UTF-8" /> <titl'
HTML += b'e>pySELL Quiz</title> <meta name="viewport" content="width=d'
HTML += b'evice-width, initial-scale=1.0" /> <link rel="icon" type="im'
HTML += b'age/x-icon" href="data:image/x-icon;base64,AAABAAEAEBAAAAEAI'
HTML += b'ABoBAAAFgAAACgAAAAQAAAAIAAAAAEAIAAAAAAAAAQAAAAAAAAAAAAAAAAAA'
HTML += b'AAAAACqqqr/PDw8/0VFRf/V1dX////////////09Pb/trbO/3t7q/9wcLH/c'
HTML += b'XG0/3NzqP+iosH/5OTr////////////j4+P/wAAAP8KCgr/x8fH///////k5'
HTML += b'Or/bGym/y4ukP8kJJD/IiKR/yIikv8jI5H/KCiP/1BQnP/Jydz//////5CQk'
HTML += b'P8BAQH/DAwM/8jIyP/7+/v/cHCo/yIij/8lJZP/KSmR/z4+lf9AQJH/Li6Q/'
HTML += b'yUlkv8jI5H/TEya/9/f6P+QkJD/AQEB/wwMDP/Ly8r/ycna/y4ujv8lJZP/N'
HTML += b'DSU/5+fw//j4+v/5+fs/76+0v9LS5f/JSWS/yYmkP+Skrr/kJCQ/wAAAP8MD'
HTML += b'Az/zc3L/5aWvP8iIo//ISGQ/39/sf////7/////////////////n5+7/yMjj'
HTML += b'P8kJJH/bm6p/5CQkP8BAQH/CgoK/6SkpP+Skp//XV2N/1dXi//Hx9X//////'
HTML += b'///////////9fX1/39/rP8kJI7/JCSR/25upP+QkJD/AQEB/wEBAf8ODg7/F'
HTML += b'BQT/xUVE/8hIR//XV1c/8vL0P/IyNv/lZW7/1panP8rK5D/JiaT/ycnjv+bm'
HTML += b'7v/kJCQ/wEBAf8AAAD/AAAA/wAAAP8AAAD/AAAH/wAAK/8aGmv/LCyO/yQkj'
HTML += b'/8jI5L/JSWT/yIikP9dXZ//6enu/5CQkP8BAQH/BQUF/0xMTP9lZWT/Pz9N/'
HTML += b'wUFVP8AAGz/AABu/xYWhf8jI5L/JCSP/zY2k/92dq7/4ODo//////+QkJD/A'
HTML += b'QEB/wwMDP/IyMj//Pz9/2lppf8ZGYf/AgJw/wAAZ/8cHHL/Zmak/5ubv//X1'
HTML += b'+T//v7+////////////kJCQ/wEBAf8MDAz/ycnJ/9/f6f85OZT/IyOR/wcHZ'
HTML += b'P8AAB7/UVFZ//n5+P//////0dHd/7i4yf++vs7/7e3z/5CQkP8AAAD/DAwM/'
HTML += b'87Ozf/Y2OP/MjKQ/x8fjv8EBEr/AAAA/1xcWv//////6ent/0tLlf8kJIn/M'
HTML += b'jKL/8fH2v+QkJD/AQEB/wcHB/98fHv/jo6T/yUlc/8JCXj/AABi/wAAK/9eX'
HTML += b'nj/trbS/2xspv8nJ5H/IyOT/0pKm//m5uz/kJCQ/wEBAf8AAAD/AAAA/wAAA'
HTML += b'P8AACH/AABk/wAAbf8EBHD/IyOM/ykpkv8jI5H/IyOS/ysrjP+kpMP//////'
HTML += b'5GRkf8CAgL/AQEB/wEBAf8BAQH/AgIE/woKK/8ZGWj/IyOG/ycnj/8nJ4//M'
HTML += b'DCS/0xMmf+lpcP/+vr6///////Pz8//kZGR/5CQkP+QkJD/kJCQ/5OTk/+ws'
HTML += b'K//zs7V/8LC2f+goL3/oaG+/8PD2P/n5+z/////////////////AAAAAAAAA'
HTML += b'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
HTML += b'AAAAAAAAAAAAAAAAA==" sizes="16x16" /> <link rel="stylesheet"'
HTML += b' href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.'
HTML += b'min.css" integrity="sha384-n8MVd4RsNIU0tAv4ct0nTaAbDJwPJzDEa'
HTML += b'qSD1odI+WdtXRGWt2kTvGFasHpSy3SV" crossorigin="anonymous" /> '
HTML += b'<script src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/'
HTML += b'katex.min.js" integrity="sha384-XjKyOOlGwcjNTAIQHIpgOno0Hl1Y'
HTML += b'QqzUOEleOLALmuqehneUG+vnGctmUb0ZY0l8" crossorigin="anonymous'
HTML += b'" ></script> <style> html { font-family: Arial, Helvetica, s'
HTML += b'ans-serif; } body { max-width: 1024px; margin-left: auto; ma'
HTML += b'rgin-right: auto; padding-left: 5px; padding-right: 5px; } h'
HTML += b'1 { text-align: center; font-size: 28pt; } img { width: 100%'
HTML += b'; display: block; margin-left: auto; margin-right: auto; } .'
HTML += b'author { text-align: center; font-size: 18pt; } .courseInfo '
HTML += b'{ font-size: 14pt; font-style: italic; /*margin-bottom: 24px'
HTML += b';*/ text-align: center; } .question { position: relative; /*'
HTML += b' required for feedback overlays */ color: black; background-'
HTML += b'color: white; border-style: solid; border-radius: 5px; borde'
HTML += b'r-width: 3px; border-color: black; padding: 8px; margin-top:'
HTML += b' 20px; margin-bottom: 20px; -webkit-box-shadow: 4px 6px 8px '
HTML += b'-1px rgba(0, 0, 0, 0.93); box-shadow: 4px 6px 8px -1px rgba('
HTML += b'0, 0, 0, 0.1); overflow-x: auto; } .questionFeedback { z-ind'
HTML += b'ex: 10; display: none; position: absolute; pointer-events: n'
HTML += b'one; left: 10%; top: 33%; width: 80%; /*height: 100%;*/ text'
HTML += b'-align: center; font-size: 24pt; text-shadow: 0px 0px 18px r'
HTML += b'gba(0, 0, 0, 0.33); background-color: rgba(255, 255, 255, 1)'
HTML += b'; padding-top: 20px; padding-bottom: 20px; /*border-style: s'
HTML += b'olid; border-width: 4px; border-color: rgb(200, 200, 200);*/'
HTML += b' border-radius: 16px; -webkit-box-shadow: 0px 0px 18px 5px r'
HTML += b'gba(0, 0, 0, 0.66); box-shadow: 0px 0px 18px 5px rgba(0, 0, '
HTML += b'0, 0.66); } .questionTitle { font-size: 24pt; } .code { font'
HTML += b'-family: "Courier New", Courier, monospace; color: black; ba'
HTML += b'ckground-color: rgb(235, 235, 235); padding: 2px 5px; border'
HTML += b'-radius: 5px; margin: 1px 2px; } .debugCode { font-family: "'
HTML += b'Courier New", Courier, monospace; padding: 4px; margin-botto'
HTML += b'm: 5px; background-color: black; color: white; border-radius'
HTML += b': 5px; opacity: 0.85; overflow-x: scroll; } .debugInfo { tex'
HTML += b't-align: end; font-size: 10pt; margin-top: 2px; color: rgb(6'
HTML += b'4, 64, 64); } ul { margin-top: 0; margin-left: 0px; padding-'
HTML += b'left: 20px; } .inputField { position: relative; width: 32px;'
HTML += b' height: 24px; font-size: 14pt; border-style: solid; border-'
HTML += b'color: black; border-radius: 5px; border-width: 0.2; padding'
HTML += b'-left: 5px; padding-right: 5px; outline-color: black; backgr'
HTML += b'ound-color: transparent; margin: 1px; } .inputField:focus { '
HTML += b'outline-color: maroon; } .equationPreview { position: absolu'
HTML += b'te; top: 120%; left: 0%; padding-left: 8px; padding-right: 8'
HTML += b'px; padding-top: 4px; padding-bottom: 4px; background-color:'
HTML += b' rgb(128, 0, 0); border-radius: 5px; font-size: 12pt; color:'
HTML += b' white; text-align: start; z-index: 20; opacity: 0.95; } .bu'
HTML += b'tton { padding-left: 8px; padding-right: 8px; padding-top: 5'
HTML += b'px; padding-bottom: 5px; font-size: 12pt; background-color: '
HTML += b'rgb(0, 150, 0); color: white; border-style: none; border-rad'
HTML += b'ius: 4px; height: 36px; cursor: pointer; } .buttonRow { disp'
HTML += b'lay: flex; align-items: baseline; margin-top: 12px; } .matri'
HTML += b'xResizeButton { width: 20px; background-color: black; color:'
HTML += b' #fff; text-align: center; border-radius: 3px; position: abs'
HTML += b'olute; z-index: 1; height: 20px; cursor: pointer; margin-bot'
HTML += b'tom: 3px; } a { color: black; text-decoration: underline; } '
HTML += b'</style> </head> <body> <h1 id="title"></h1> <div class="aut'
HTML += b'hor" id="author"></div> <p id="courseInfo1" class="courseInf'
HTML += b'o"></p> <p id="courseInfo2" class="courseInfo"></p> <h1 id="'
HTML += b'debug" class="debugCode" style="display: none">DEBUG VERSION'
HTML += b'</h1> <div id="questions"></div> <p style="font-size: 8pt; f'
HTML += b'ont-style: italic; text-align: center"> This quiz was create'
HTML += b'd using <a href="https://github.com/andreas-schwenk/pysell">'
HTML += b'pySELL</a>, the <i>Python-based Simple E-Learning Language</'
HTML += b'i>, written by Andreas Schwenk, GPLv3<br /> last update on <'
HTML += b'span id="date"></span> </p> <script>let debug = false; let q'
HTML += b'uizSrc = {};var sell=(()=>{var B=Object.defineProperty;var s'
HTML += b'e=Object.getOwnPropertyDescriptor;var re=Object.getOwnProper'
HTML += b'tyNames;var ne=Object.prototype.hasOwnProperty;var ae=(r,e)='
HTML += b'>{for(var t in e)B(r,t,{get:e[t],enumerable:!0})},le=(r,e,t,'
HTML += b'i)=>{if(e&&typeof e=="object"||typeof e=="function")for(let '
HTML += b's of re(e))!ne.call(r,s)&&s!==t&&B(r,s,{get:()=>e[s],enumera'
HTML += b'ble:!(i=se(e,s))||i.enumerable});return r};var oe=r=>le(B({}'
HTML += b',"__esModule",{value:!0}),r);var pe={};ae(pe,{init:()=>ce});'
HTML += b'function x(r=[]){let e=document.createElement("div");return '
HTML += b'e.append(...r),e}function z(r=[]){let e=document.createEleme'
HTML += b'nt("ul");return e.append(...r),e}function U(r){let e=documen'
HTML += b't.createElement("li");return e.appendChild(r),e}function R(r'
HTML += b'){let e=document.createElement("input");return e.spellcheck='
HTML += b'!1,e.type="text",e.classList.add("inputField"),e.style.width'
HTML += b'=r+"px",e}function j(){let r=document.createElement("button"'
HTML += b');return r.type="button",r.classList.add("button"),r}functio'
HTML += b'n g(r,e=[]){let t=document.createElement("span");return e.le'
HTML += b'ngth>0?t.append(...e):t.innerHTML=r,t}function W(r,e,t=!1){k'
HTML += b'atex.render(e,r,{throwOnError:!1,displayMode:t,macros:{"\\\\RR'
HTML += b'":"\\\\mathbb{R}","\\\\NN":"\\\\mathbb{N}","\\\\QQ":"\\\\mathbb{Q}","\\'
HTML += b'\\ZZ":"\\\\mathbb{Z}","\\\\CC":"\\\\mathbb{C}"}})}function y(r,e=!1'
HTML += b'){let t=document.createElement("span");return W(t,r,e),t}var'
HTML += b' O={en:"This page runs in your browser and does not store an'
HTML += b'y data on servers.",de:"Diese Seite wird in Ihrem Browser au'
HTML += b'sgef\\xFChrt und speichert keine Daten auf Servern.",es:"Esta'
HTML += b' p\\xE1gina se ejecuta en su navegador y no almacena ning\\xFA'
HTML += b'n dato en los servidores.",it:"Questa pagina viene eseguita '
HTML += b'nel browser e non memorizza alcun dato sui server.",fr:"Cett'
HTML += b'e page fonctionne dans votre navigateur et ne stocke aucune '
HTML += b'donn\\xE9e sur des serveurs."},F={en:"You can * this page in '
HTML += b'order to get new randomized tasks.",de:"Sie k\\xF6nnen diese '
HTML += b'Seite *, um neue randomisierte Aufgaben zu erhalten.",es:"Pu'
HTML += b'edes * esta p\\xE1gina para obtener nuevas tareas aleatorias.'
HTML += b'",it:"\\xC8 possibile * questa pagina per ottenere nuovi comp'
HTML += b'iti randomizzati",fr:"Vous pouvez * cette page pour obtenir '
HTML += b'de nouvelles t\\xE2ches al\\xE9atoires"},K={en:"reload",de:"ak'
HTML += b'tualisieren",es:"recargar",it:"ricaricare",fr:"recharger"},q'
HTML += b'={en:["awesome","great","well done","nice","you got it","goo'
HTML += b'd"],de:["super","gut gemacht","weiter so","richtig"],es:["im'
HTML += b'presionante","genial","correcto","bien hecho"],it:["fantasti'
HTML += b'co","grande","corretto","ben fatto"],fr:["g\\xE9nial","super"'
HTML += b',"correct","bien fait"]},X={en:["try again","still some mist'
HTML += b'akes","wrong answer","no"],de:["leider falsch","nicht richti'
HTML += b'g","versuch\'s nochmal"],es:["int\\xE9ntalo de nuevo","todav\\x'
HTML += b'EDa algunos errores","respuesta incorrecta"],it:["riprova","'
HTML += b'ancora qualche errore","risposta sbagliata"],fr:["r\\xE9essay'
HTML += b'er","encore des erreurs","mauvaise r\\xE9ponse"]};function Z('
HTML += b'r,e){let t=Array(e.length+1).fill(null).map(()=>Array(r.leng'
HTML += b'th+1).fill(null));for(let i=0;i<=r.length;i+=1)t[0][i]=i;for'
HTML += b'(let i=0;i<=e.length;i+=1)t[i][0]=i;for(let i=1;i<=e.length;'
HTML += b'i+=1)for(let s=1;s<=r.length;s+=1){let a=r[s-1]===e[i-1]?0:1'
HTML += b';t[i][s]=Math.min(t[i][s-1]+1,t[i-1][s]+1,t[i-1][s-1]+a)}ret'
HTML += b'urn t[e.length][r.length]}var Y=\'<svg xmlns="http://www.w3.o'
HTML += b'rg/2000/svg" height="28" viewBox="0 0 448 512"><path d="M384'
HTML += b' 80c8.8 0 16 7.2 16 16V416c0 8.8-7.2 16-16 16H64c-8.8 0-16-7'
HTML += b'.2-16-16V96c0-8.8 7.2-16 16-16H384zM64 32C28.7 32 0 60.7 0 9'
HTML += b'6V416c0 35.3 28.7 64 64 64H384c35.3 0 64-28.7 64-64V96c0-35.'
HTML += b'3-28.7-64-64-64H64z"/></svg>\',G=\'<svg xmlns="http://www.w3.o'
HTML += b'rg/2000/svg" height="28" viewBox="0 0 448 512"><path d="M64 '
HTML += b'80c-8.8 0-16 7.2-16 16V416c0 8.8 7.2 16 16 16H384c8.8 0 16-7'
HTML += b'.2 16-16V96c0-8.8-7.2-16-16-16H64zM0 96C0 60.7 28.7 32 64 32'
HTML += b'H384c35.3 0 64 28.7 64 64V416c0 35.3-28.7 64-64 64H64c-35.3 '
HTML += b'0-64-28.7-64-64V96zM337 209L209 337c-9.4 9.4-24.6 9.4-33.9 0'
HTML += b'l-64-64c-9.4-9.4-9.4-24.6 0-33.9s24.6-9.4 33.9 0l47 47L303 1'
HTML += b'75c9.4-9.4 24.6-9.4 33.9 0s9.4 24.6 0 33.9z"/>\',J=\'<svg xmln'
HTML += b's="http://www.w3.org/2000/svg" height="28" viewBox="0 0 512 '
HTML += b'512"><path d="M464 256A208 208 0 1 0 48 256a208 208 0 1 0 41'
HTML += b'6 0zM0 256a256 256 0 1 1 512 0A256 256 0 1 1 0 256z"/></svg>'
HTML += b'\',$=\'<svg xmlns="http://www.w3.org/2000/svg" height="28" vie'
HTML += b'wBox="0 0 512 512"><path d="M256 48a208 208 0 1 1 0 416 208 '
HTML += b'208 0 1 1 0-416zm0 464A256 256 0 1 0 256 0a256 256 0 1 0 0 5'
HTML += b'12zM369 209c9.4-9.4 9.4-24.6 0-33.9s-24.6-9.4-33.9 0l-111 11'
HTML += b'1-47-47c-9.4-9.4-24.6-9.4-33.9 0s-9.4 24.6 0 33.9l64 64c9.4 '
HTML += b'9.4 24.6 9.4 33.9 0L369 209z"/></svg>\',I=\'<svg xmlns="http:/'
HTML += b'/www.w3.org/2000/svg" height="25" viewBox="0 0 384 512" fill'
HTML += b'="white"><path d="M73 39c-14.8-9.1-33.4-9.4-48.5-.9S0 62.6 0'
HTML += b' 80V432c0 17.4 9.4 33.4 24.5 41.9s33.7 8.1 48.5-.9L361 297c1'
HTML += b'4.3-8.7 23-24.2 23-41s-8.7-32.2-23-41L73 39z"/></svg>\',ee=\'<'
HTML += b'svg xmlns="http://www.w3.org/2000/svg" height="25" viewBox="'
HTML += b'0 0 512 512" fill="white"><path d="M0 224c0 17.7 14.3 32 32 '
HTML += b'32s32-14.3 32-32c0-53 43-96 96-96H320v32c0 12.9 7.8 24.6 19.'
HTML += b'8 29.6s25.7 2.2 34.9-6.9l64-64c12.5-12.5 12.5-32.8 0-45.3l-6'
HTML += b'4-64c-9.2-9.2-22.9-11.9-34.9-6.9S320 19.1 320 32V64H160C71.6'
HTML += b' 64 0 135.6 0 224zm512 64c0-17.7-14.3-32-32-32s-32 14.3-32 3'
HTML += b'2c0 53-43 96-96 96H192V352c0-12.9-7.8-24.6-19.8-29.6s-25.7-2'
HTML += b'.2-34.9 6.9l-64 64c-12.5 12.5-12.5 32.8 0 45.3l64 64c9.2 9.2'
HTML += b' 22.9 11.9 34.9 6.9s19.8-16.6 19.8-29.6V448H352c88.4 0 160-7'
HTML += b'1.6 160-160z"/></svg>\';function P(r,e=!1){let t=new Array(r)'
HTML += b';for(let i=0;i<r;i++)t[i]=i;if(e)for(let i=0;i<r;i++){let s='
HTML += b'Math.floor(Math.random()*r),a=Math.floor(Math.random()*r),o='
HTML += b't[s];t[s]=t[a],t[a]=o}return t}function _(r,e,t=-1){if(t<0&&'
HTML += b'(t=r.length),t==1){e.push([...r]);return}for(let i=0;i<t;i++'
HTML += b'){_(r,e,t-1);let s=t%2==0?i:0,a=r[s];r[s]=r[t-1],r[t-1]=a}}v'
HTML += b'ar C=class r{constructor(e,t){this.m=e,this.n=t,this.v=new A'
HTML += b'rray(e*t).fill("0")}getElement(e,t){return e<0||e>=this.m||t'
HTML += b'<0||t>=this.n?"0":this.v[e*this.n+t]}resize(e,t,i){if(e<1||e'
HTML += b'>50||t<1||t>50)return!1;let s=new r(e,t);s.v.fill(i);for(let'
HTML += b' a=0;a<s.m;a++)for(let o=0;o<s.n;o++)s.v[a*s.n+o]=this.getEl'
HTML += b'ement(a,o);return this.fromMatrix(s),!0}fromMatrix(e){this.m'
HTML += b'=e.m,this.n=e.n,this.v=[...e.v]}fromString(e){this.m=e.split'
HTML += b'("],").length,this.v=e.replaceAll("[","").replaceAll("]","")'
HTML += b'.split(",").map(t=>t.trim()),this.n=this.v.length/this.m}get'
HTML += b'MaxCellStrlen(){let e=0;for(let t of this.v)t.length>e&&(e=t'
HTML += b'.length);return e}toTeXString(e=!1,t=!0){let i="";t?i+=e?"\\\\'
HTML += b'left[\\\\begin{array}":"\\\\begin{bmatrix}":i+=e?"\\\\left(\\\\begin'
HTML += b'{array}":"\\\\begin{pmatrix}",e&&(i+="{"+"c".repeat(this.n-1)+'
HTML += b'"|c}");for(let s=0;s<this.m;s++){for(let a=0;a<this.n;a++){a'
HTML += b'>0&&(i+="&");let o=this.getElement(s,a);try{o=f.parse(o).toT'
HTML += b'exString()}catch{}i+=o}i+="\\\\\\\\"}return t?i+=e?"\\\\end{array}'
HTML += b'\\\\right]":"\\\\end{bmatrix}":i+=e?"\\\\end{array}\\\\right)":"\\\\en'
HTML += b'd{pmatrix}",i}},f=class r{constructor(){this.root=null,this.'
HTML += b'src="",this.token="",this.skippedWhiteSpace=!1,this.pos=0}cl'
HTML += b'one(){let e=new r;return e.root=this.root.clone(),e}getVars('
HTML += b'e,t="",i=null){if(i==null&&(i=this.root),i.op.startsWith("va'
HTML += b'r:")){let s=i.op.substring(4);(t.length==0||t.length>0&&s.st'
HTML += b'artsWith(t))&&e.add(s)}for(let s of i.c)this.getVars(e,t,s)}'
HTML += b'setVars(e,t=null){t==null&&(t=this.root);for(let i of t.c)th'
HTML += b'is.setVars(e,i);if(t.op.startsWith("var:")){let i=t.op.subst'
HTML += b'ring(4);if(i in e){let s=e[i].clone();t.op=s.op,t.c=s.c,t.re'
HTML += b'=s.re,t.im=s.im}}}renameVar(e,t,i=null){i==null&&(i=this.roo'
HTML += b't);for(let s of i.c)this.renameVar(e,t,s);i.op.startsWith("v'
HTML += b'ar:")&&i.op.substring(4)===e&&(i.op="var:"+t)}eval(e,t=null)'
HTML += b'{let s=d.const(),a=0,o=0,l=null;switch(t==null&&(t=this.root'
HTML += b'),t.op){case"const":s=t;break;case"+":case"-":case"*":case"/'
HTML += b'":case"^":{let n=this.eval(e,t.c[0]),h=this.eval(e,t.c[1]);s'
HTML += b'witch(t.op){case"+":s.re=n.re+h.re,s.im=n.im+h.im;break;case'
HTML += b'"-":s.re=n.re-h.re,s.im=n.im-h.im;break;case"*":s.re=n.re*h.'
HTML += b're-n.im*h.im,s.im=n.re*h.im+n.im*h.re;break;case"/":a=h.re*h'
HTML += b'.re+h.im*h.im,s.re=(n.re*h.re+n.im*h.im)/a,s.im=(n.im*h.re-n'
HTML += b'.re*h.im)/a;break;case"^":l=new d("exp",[new d("*",[h,new d('
HTML += b'"ln",[n])])]),s=this.eval(e,l);break}break}case".-":case"abs'
HTML += b'":case"sin":case"sinc":case"cos":case"tan":case"cot":case"ex'
HTML += b'p":case"ln":case"log":case"sqrt":{let n=this.eval(e,t.c[0]);'
HTML += b'switch(t.op){case".-":s.re=-n.re,s.im=-n.im;break;case"abs":'
HTML += b's.re=Math.sqrt(n.re*n.re+n.im*n.im),s.im=0;break;case"sin":s'
HTML += b'.re=Math.sin(n.re)*Math.cosh(n.im),s.im=Math.cos(n.re)*Math.'
HTML += b'sinh(n.im);break;case"sinc":l=new d("/",[new d("sin",[n]),n]'
HTML += b'),s=this.eval(e,l);break;case"cos":s.re=Math.cos(n.re)*Math.'
HTML += b'cosh(n.im),s.im=-Math.sin(n.re)*Math.sinh(n.im);break;case"t'
HTML += b'an":a=Math.cos(n.re)*Math.cos(n.re)+Math.sinh(n.im)*Math.sin'
HTML += b'h(n.im),s.re=Math.sin(n.re)*Math.cos(n.re)/a,s.im=Math.sinh('
HTML += b'n.im)*Math.cosh(n.im)/a;break;case"cot":a=Math.sin(n.re)*Mat'
HTML += b'h.sin(n.re)+Math.sinh(n.im)*Math.sinh(n.im),s.re=Math.sin(n.'
HTML += b're)*Math.cos(n.re)/a,s.im=-(Math.sinh(n.im)*Math.cosh(n.im))'
HTML += b'/a;break;case"exp":s.re=Math.exp(n.re)*Math.cos(n.im),s.im=M'
HTML += b'ath.exp(n.re)*Math.sin(n.im);break;case"ln":case"log":s.re=M'
HTML += b'ath.log(Math.sqrt(n.re*n.re+n.im*n.im)),a=Math.abs(n.im)<1e-'
HTML += b'9?0:n.im,s.im=Math.atan2(a,n.re);break;case"sqrt":l=new d("^'
HTML += b'",[n,d.const(.5)]),s=this.eval(e,l);break}break}default:if(t'
HTML += b'.op.startsWith("var:")){let n=t.op.substring(4);if(n==="pi")'
HTML += b'return d.const(Math.PI);if(n==="e")return d.const(Math.E);if'
HTML += b'(n==="i")return d.const(0,1);if(n in e)return e[n];throw new'
HTML += b' Error("eval-error: unknown variable \'"+n+"\'")}else throw ne'
HTML += b'w Error("UNIMPLEMENTED eval \'"+t.op+"\'")}return s}static par'
HTML += b'se(e){let t=new r;if(t.src=e,t.token="",t.skippedWhiteSpace='
HTML += b'!1,t.pos=0,t.next(),t.root=t.parseExpr(!1),t.token!=="")thro'
HTML += b'w new Error("remaining tokens: "+t.token+"...");return t}par'
HTML += b'seExpr(e){return this.parseAdd(e)}parseAdd(e){let t=this.par'
HTML += b'seMul(e);for(;["+","-"].includes(this.token)&&!(e&&this.skip'
HTML += b'pedWhiteSpace);){let i=this.token;this.next(),t=new d(i,[t,t'
HTML += b'his.parseMul(e)])}return t}parseMul(e){let t=this.parsePow(e'
HTML += b');for(;!(e&&this.skippedWhiteSpace);){let i="*";if(["*","/"]'
HTML += b'.includes(this.token))i=this.token,this.next();else if(!e&&t'
HTML += b'his.token==="(")i="*";else if(this.token.length>0&&(this.isA'
HTML += b'lpha(this.token[0])||this.isNum(this.token[0])))i="*";else b'
HTML += b'reak;t=new d(i,[t,this.parsePow(e)])}return t}parsePow(e){le'
HTML += b't t=this.parseUnary(e);for(;["^"].includes(this.token)&&!(e&'
HTML += b'&this.skippedWhiteSpace);){let i=this.token;this.next(),t=ne'
HTML += b'w d(i,[t,this.parseUnary(e)])}return t}parseUnary(e){return '
HTML += b'this.token==="-"?(this.next(),new d(".-",[this.parseMul(e)])'
HTML += b'):this.parseInfix(e)}parseInfix(e){if(this.token.length==0)t'
HTML += b'hrow new Error("expected unary");if(this.isNum(this.token[0]'
HTML += b')){let t=this.token;return this.next(),this.token==="."&&(t+'
HTML += b'=".",this.next(),this.token.length>0&&(t+=this.token,this.ne'
HTML += b'xt())),new d("const",[],parseFloat(t))}else if(this.fun1().l'
HTML += b'ength>0){let t=this.fun1();this.next(t.length);let i=null;if'
HTML += b'(this.token==="(")if(this.next(),i=this.parseExpr(e),this.to'
HTML += b'ken+="",this.token===")")this.next();else throw Error("expec'
HTML += b'ted \')\'");else i=this.parseMul(!0);return new d(t,[i])}else '
HTML += b'if(this.token==="("){this.next();let t=this.parseExpr(e);if('
HTML += b'this.token+="",this.token===")")this.next();else throw Error'
HTML += b'("expected \')\'");return t.explicitParentheses=!0,t}else if(t'
HTML += b'his.token==="|"){this.next();let t=this.parseExpr(e);if(this'
HTML += b'.token+="",this.token==="|")this.next();else throw Error("ex'
HTML += b'pected \'|\'");return new d("abs",[t])}else if(this.isAlpha(th'
HTML += b'is.token[0])){let t="";return this.token.startsWith("pi")?t='
HTML += b'"pi":this.token.startsWith("C1")?t="C1":this.token.startsWit'
HTML += b'h("C2")?t="C2":t=this.token[0],t==="I"&&(t="i"),this.next(t.'
HTML += b'length),new d("var:"+t,[])}else throw new Error("expected un'
HTML += b'ary")}static compare(e,t,i={}){let o=new Set;e.getVars(o),t.'
HTML += b'getVars(o);for(let l=0;l<10;l++){let n={};for(let k of o)k i'
HTML += b'n i?n[k]=i[k]:n[k]=d.const(Math.random(),Math.random());let '
HTML += b'h=e.eval(n),p=t.eval(n),u=h.re-p.re,c=h.im-p.im;if(Math.sqrt'
HTML += b'(u*u+c*c)>1e-9)return!1}return!0}fun1(){let e=["abs","sinc",'
HTML += b'"sin","cos","tan","cot","exp","ln","sqrt"];for(let t of e)if'
HTML += b'(this.token.toLowerCase().startsWith(t))return t;return""}ne'
HTML += b'xt(e=-1){if(e>0&&this.token.length>e){this.token=this.token.'
HTML += b'substring(e),this.skippedWhiteSpace=!1;return}this.token="";'
HTML += b'let t=!1,i=this.src.length;for(this.skippedWhiteSpace=!1;thi'
HTML += b's.pos<i&&`\t\n `.includes(this.src[this.pos]);)this.skippedWhi'
HTML += b'teSpace=!0,this.pos++;for(;!t&&this.pos<i;){let s=this.src[t'
HTML += b'his.pos];if(this.token.length>0&&(this.isNum(this.token[0])&'
HTML += b'&this.isAlpha(s)||this.isAlpha(this.token[0])&&this.isNum(s)'
HTML += b')&&this.token!="C")return;if(`^%#*$()[]{},.:;+-*/_!<>=?|\t\n `'
HTML += b'.includes(s)){if(this.token.length>0)return;t=!0}`\t\n `.inclu'
HTML += b'des(s)==!1&&(this.token+=s),this.pos++}}isNum(e){return e.ch'
HTML += b'arCodeAt(0)>=48&&e.charCodeAt(0)<=57}isAlpha(e){return e.cha'
HTML += b'rCodeAt(0)>=65&&e.charCodeAt(0)<=90||e.charCodeAt(0)>=97&&e.'
HTML += b'charCodeAt(0)<=122||e==="_"}toString(){return this.root==nul'
HTML += b'l?"":this.root.toString()}toTexString(){return this.root==nu'
HTML += b'll?"":this.root.toTexString()}},d=class r{constructor(e,t,i='
HTML += b'0,s=0){this.op=e,this.c=t,this.re=i,this.im=s,this.explicitP'
HTML += b'arentheses=!1}clone(){let e=new r(this.op,this.c.map(t=>t.cl'
HTML += b'one()),this.re,this.im);return e.explicitParentheses=this.ex'
HTML += b'plicitParentheses,e}static const(e=0,t=0){return new r("cons'
HTML += b't",[],e,t)}compare(e,t=0,i=1e-9){let s=this.re-e,a=this.im-t'
HTML += b';return Math.sqrt(s*s+a*a)<i}toString(){let e="";if(this.op='
HTML += b'=="const"){let t=Math.abs(this.re)>1e-14,i=Math.abs(this.im)'
HTML += b'>1e-14;t&&i&&this.im>=0?e="("+this.re+"+"+this.im+"i)":t&&i&'
HTML += b'&this.im<0?e="("+this.re+"-"+-this.im+"i)":t&&this.re>0?e=""'
HTML += b'+this.re:t&&this.re<0?e="("+this.re+")":i?e="("+this.im+"i)"'
HTML += b':e="0"}else this.op.startsWith("var")?e=this.op.split(":")[1'
HTML += b']:this.c.length==1?e=(this.op===".-"?"-":this.op)+"("+this.c'
HTML += b'.toString()+")":e="("+this.c.map(t=>t.toString()).join(this.'
HTML += b'op)+")";return e}toTexString(e=!1){let i="";switch(this.op){'
HTML += b'case"const":{let s=Math.abs(this.re)>1e-9,a=Math.abs(this.im'
HTML += b')>1e-9,o=s?""+this.re:"",l=a?""+this.im+"i":"";l==="1i"?l="i'
HTML += b'":l==="-1i"&&(l="-i"),!s&&!a?i="0":(a&&this.im>=0&&s&&(l="+"'
HTML += b'+l),i=o+l);break}case".-":i="-"+this.c[0].toTexString();brea'
HTML += b'k;case"+":case"-":case"*":case"^":{let s=this.c[0].toTexStri'
HTML += b'ng(),a=this.c[1].toTexString(),o=this.op==="*"?"\\\\cdot ":thi'
HTML += b's.op;i="{"+s+"}"+o+"{"+a+"}";break}case"/":{let s=this.c[0].'
HTML += b'toTexString(!0),a=this.c[1].toTexString(!0);i="\\\\frac{"+s+"}'
HTML += b'{"+a+"}";break}case"sin":case"sinc":case"cos":case"tan":case'
HTML += b'"cot":case"exp":case"ln":{let s=this.c[0].toTexString(!0);i+'
HTML += b'="\\\\"+this.op+"\\\\left("+s+"\\\\right)";break}case"sqrt":{let s'
HTML += b'=this.c[0].toTexString(!0);i+="\\\\"+this.op+"{"+s+"}";break}c'
HTML += b'ase"abs":{let s=this.c[0].toTexString(!0);i+="\\\\left|"+s+"\\\\'
HTML += b'right|";break}default:if(this.op.startsWith("var:")){let s=t'
HTML += b'his.op.substring(4);switch(s){case"pi":s="\\\\pi";break}i=" "+'
HTML += b's+" "}else{let s="warning: Node.toString(..):";s+=" unimplem'
HTML += b'ented operator \'"+this.op+"\'",console.log(s),i=this.op,this.'
HTML += b'c.length>0&&(i+="\\\\left({"+this.c.map(a=>a.toTexString(!0)).'
HTML += b'join(",")+"}\\\\right)")}}return!e&&this.explicitParentheses&&'
HTML += b'(i="\\\\left({"+i+"}\\\\right)"),i}};function te(r,e){let t=1e-9'
HTML += b';if(f.compare(r,e))return!0;r=r.clone(),e=e.clone(),N(r.root'
HTML += b'),N(e.root);let i=new Set;r.getVars(i),e.getVars(i);let s=[]'
HTML += b',a=[];for(let n of i.keys())n.startsWith("C")?s.push(n):a.pu'
HTML += b'sh(n);let o=s.length;for(let n=0;n<o;n++){let h=s[n];r.renam'
HTML += b'eVar(h,"_C"+n),e.renameVar(h,"_C"+n)}for(let n=0;n<o;n++)r.r'
HTML += b'enameVar("_C"+n,"C"+n),e.renameVar("_C"+n,"C"+n);s=[];for(le'
HTML += b't n=0;n<o;n++)s.push("C"+n);let l=[];_(P(o),l);for(let n of '
HTML += b'l){let h=r.clone(),p=e.clone();for(let c=0;c<o;c++)p.renameV'
HTML += b'ar("C"+c,"__C"+n[c]);for(let c=0;c<o;c++)p.renameVar("__C"+c'
HTML += b',"C"+c);let u=!0;for(let c=0;c<o;c++){let m="C"+c,k={};k[m]='
HTML += b'new d("*",[new d("var:C"+c,[]),new d("var:K",[])]),p.setVars'
HTML += b'(k);let v={};v[m]=d.const(Math.random(),Math.random());for(l'
HTML += b'et b=0;b<o;b++)c!=b&&(v["C"+b]=d.const(0,0));let S=new d("ab'
HTML += b's",[new d("-",[h.root,p.root])]),T=new f;T.root=S;for(let b '
HTML += b'of a)v[b]=d.const(Math.random(),Math.random());let M=he(T,"K'
HTML += b'",v)[0];p.setVars({K:d.const(M,0)}),v={};for(let b=0;b<o;b++'
HTML += b')c!=b&&(v["C"+b]=d.const(0,0));if(f.compare(h,p,v)==!1){u=!1'
HTML += b';break}}if(u&&f.compare(h,p))return!0}return!1}function he(r'
HTML += b',e,t){let i=1e-11,s=1e3,a=0,o=0,l=1,n=888;for(;a<s;){t[e]=d.'
HTML += b'const(o);let p=r.eval(t).re;t[e]=d.const(o+l);let u=r.eval(t'
HTML += b').re;t[e]=d.const(o-l);let c=r.eval(t).re,m=0;if(u<p&&(p=u,m'
HTML += b'=1),c<p&&(p=c,m=-1),m==1&&(o+=l),m==-1&&(o-=l),p<i)break;(m='
HTML += b'=0||m!=n)&&(l/=2),n=m,a++}t[e]=d.const(o);let h=r.eval(t).re'
HTML += b';return[o,h]}function N(r){for(let e of r.c)N(e);switch(r.op'
HTML += b'){case"+":case"-":case"*":case"/":case"^":{let e=[r.c[0].op,'
HTML += b'r.c[1].op],t=[e[0]==="const",e[1]==="const"],i=[e[0].startsW'
HTML += b'ith("var:C"),e[1].startsWith("var:C")];i[0]&&t[1]?(r.op=r.c['
HTML += b'0].op,r.c=[]):i[1]&&t[0]?(r.op=r.c[1].op,r.c=[]):i[0]&&i[1]&'
HTML += b'&e[0]==e[1]&&(r.op=r.c[0].op,r.c=[]);break}case".-":case"abs'
HTML += b'":case"sin":case"sinc":case"cos":case"tan":case"cot":case"ex'
HTML += b'p":case"ln":case"log":case"sqrt":r.c[0].op.startsWith("var:C'
HTML += b'")&&(r.op=r.c[0].op,r.c=[]);break}}function ie(r){r.feedback'
HTML += b'Span.innerHTML="",r.numChecked=0,r.numCorrect=0;for(let i in'
HTML += b' r.expected){let s=r.types[i],a=r.student[i],o=r.expected[i]'
HTML += b';switch(s){case"bool":r.numChecked++,a===o&&r.numCorrect++;b'
HTML += b'reak;case"string":{r.numChecked++;let l=r.gapInputs[i],n=a.t'
HTML += b'rim().toUpperCase(),h=o.trim().toUpperCase().split("|"),p=!1'
HTML += b';for(let u of h)if(Z(n,u)<=1){p=!0,r.numCorrect++,r.gapInput'
HTML += b's[i].value=u,r.student[i]=u;break}l.style.color=p?"black":"w'
HTML += b'hite",l.style.backgroundColor=p?"transparent":"maroon";break'
HTML += b'}case"int":r.numChecked++,Math.abs(parseFloat(a)-parseFloat('
HTML += b'o))<1e-9&&r.numCorrect++;break;case"float":case"term":{r.num'
HTML += b'Checked++;try{let l=f.parse(o),n=f.parse(a),h=!1;r.src.is_od'
HTML += b'e?h=te(l,n):h=f.compare(l,n),h&&r.numCorrect++}catch(l){r.de'
HTML += b'bug&&(console.log("term invalid"),console.log(l))}break}case'
HTML += b'"vector":case"complex":case"set":{let l=o.split(",");r.numCh'
HTML += b'ecked+=l.length;let n=[];for(let h=0;h<l.length;h++)n.push(r'
HTML += b'.student[i+"-"+h]);if(s==="set")for(let h=0;h<l.length;h++)t'
HTML += b'ry{let p=f.parse(l[h]);for(let u=0;u<n.length;u++){let c=f.p'
HTML += b'arse(n[u]);if(f.compare(p,c)){r.numCorrect++;break}}}catch(p'
HTML += b'){r.debug&&console.log(p)}else for(let h=0;h<l.length;h++)tr'
HTML += b'y{let p=f.parse(n[h]),u=f.parse(l[h]);f.compare(p,u)&&r.numC'
HTML += b'orrect++}catch(p){r.debug&&console.log(p)}break}case"matrix"'
HTML += b':{let l=new C(0,0);l.fromString(o),r.numChecked+=l.m*l.n;for'
HTML += b'(let n=0;n<l.m;n++)for(let h=0;h<l.n;h++){let p=n*l.n+h;a=r.'
HTML += b'student[i+"-"+p];let u=l.v[p];try{let c=f.parse(u),m=f.parse'
HTML += b'(a);f.compare(c,m)&&r.numCorrect++}catch(c){r.debug&&console'
HTML += b'.log(c)}}break}default:r.feedbackSpan.innerHTML="UNIMPLEMENT'
HTML += b'ED EVAL OF TYPE "+s}}r.state=r.numCorrect==r.numChecked?w.pa'
HTML += b'ssed:w.errors,r.updateVisualQuestionState();let e=r.state==='
HTML += b'w.passed?q[r.language]:X[r.language],t=e[Math.floor(Math.ran'
HTML += b'dom()*e.length)];r.feedbackPopupDiv.innerHTML=t,r.feedbackPo'
HTML += b'pupDiv.style.color=r.state===w.passed?"green":"maroon",r.fee'
HTML += b'dbackPopupDiv.style.display="block",setTimeout(()=>{r.feedba'
HTML += b'ckPopupDiv.style.display="none"},500),r.state===w.passed?r.s'
HTML += b'rc.instances.length>0?r.checkAndRepeatBtn.innerHTML=ee:r.che'
HTML += b'ckAndRepeatBtn.style.display="none":r.checkAndRepeatBtn.inne'
HTML += b'rHTML=I}var A=class{constructor(e,t,i,s){t.student[i]="",thi'
HTML += b's.question=t,this.inputId=i,i.length==0&&(this.inputId="gap-'
HTML += b'"+t.gapIdx,t.types[this.inputId]="string",t.expected[this.in'
HTML += b'putId]=s,t.gapIdx++);let a=s.split("|"),o=0;for(let p=0;p<a.'
HTML += b'length;p++){let u=a[p];u.length>o&&(o=u.length)}let l=g("");'
HTML += b'e.appendChild(l);let n=Math.max(o*15,24),h=R(n);if(t.gapInpu'
HTML += b'ts[this.inputId]=h,h.addEventListener("keyup",()=>{this.ques'
HTML += b'tion.editedQuestion(),h.value=h.value.toUpperCase(),this.que'
HTML += b'stion.student[this.inputId]=h.value.trim()}),l.appendChild(h'
HTML += b'),this.question.showSolution&&(this.question.student[this.in'
HTML += b'putId]=h.value=a[0],a.length>1)){let p=g("["+a.join("|")+"]"'
HTML += b');p.style.fontSize="small",p.style.textDecoration="underline'
HTML += b'",l.appendChild(p)}}},E=class{constructor(e,t,i,s,a,o){t.stu'
HTML += b'dent[i]="",this.question=t,this.inputId=i,this.outerSpan=g("'
HTML += b'"),this.outerSpan.style.position="relative",e.appendChild(th'
HTML += b'is.outerSpan),this.inputElement=R(Math.max(s*12,48)),this.ou'
HTML += b'terSpan.appendChild(this.inputElement),this.equationPreviewD'
HTML += b'iv=x(),this.equationPreviewDiv.classList.add("equationPrevie'
HTML += b'w"),this.equationPreviewDiv.style.display="none",this.outerS'
HTML += b'pan.appendChild(this.equationPreviewDiv),this.inputElement.a'
HTML += b'ddEventListener("click",()=>{this.question.editedQuestion(),'
HTML += b'this.edited()}),this.inputElement.addEventListener("keyup",('
HTML += b')=>{this.question.editedQuestion(),this.edited()}),this.inpu'
HTML += b'tElement.addEventListener("focusout",()=>{this.equationPrevi'
HTML += b'ewDiv.innerHTML="",this.equationPreviewDiv.style.display="no'
HTML += b'ne"}),this.inputElement.addEventListener("keydown",l=>{let n'
HTML += b'="abcdefghijklmnopqrstuvwxyz";n+="ABCDEFGHIJKLMNOPQRSTUVWXYZ'
HTML += b'",n+="0123456789",n+="+-*/^(). <>=|",o&&(n="-0123456789"),l.'
HTML += b'key.length<3&&n.includes(l.key)==!1&&l.preventDefault();let '
HTML += b'h=this.inputElement.value.length*12;this.inputElement.offset'
HTML += b'Width<h&&(this.inputElement.style.width=""+h+"px")}),this.qu'
HTML += b'estion.showSolution&&(t.student[i]=this.inputElement.value=a'
HTML += b')}edited(){let e=this.inputElement.value.trim(),t="",i=!1;tr'
HTML += b'y{let s=f.parse(e);i=s.root.op==="const",t=s.toTexString(),t'
HTML += b'his.inputElement.style.color="black",this.equationPreviewDiv'
HTML += b'.style.backgroundColor="green"}catch{t=e.replaceAll("^","\\\\h'
HTML += b'at{~}").replaceAll("_","\\\\_"),this.inputElement.style.color='
HTML += b'"maroon",this.equationPreviewDiv.style.backgroundColor="maro'
HTML += b'on"}W(this.equationPreviewDiv,t,!0),this.equationPreviewDiv.'
HTML += b'style.display=e.length>0&&!i?"block":"none",this.question.st'
HTML += b'udent[this.inputId]=e}},V=class{constructor(e,t,i,s){this.pa'
HTML += b'rent=e,this.question=t,this.inputId=i,this.matExpected=new C'
HTML += b'(0,0),this.matExpected.fromString(s),this.matStudent=new C(t'
HTML += b'his.matExpected.m==1?1:3,this.matExpected.n==1?1:3),t.showSo'
HTML += b'lution&&this.matStudent.fromMatrix(this.matExpected),this.ge'
HTML += b'nMatrixDom()}genMatrixDom(){let e=x();this.parent.innerHTML='
HTML += b'"",this.parent.appendChild(e),e.style.position="relative",e.'
HTML += b'style.display="inline-block";let t=document.createElement("t'
HTML += b'able");e.appendChild(t);let i=this.matExpected.getMaxCellStr'
HTML += b'len();for(let c=0;c<this.matStudent.m;c++){let m=document.cr'
HTML += b'eateElement("tr");t.appendChild(m),c==0&&m.appendChild(this.'
HTML += b'generateMatrixParenthesis(!0,this.matStudent.m));for(let k=0'
HTML += b';k<this.matStudent.n;k++){let v=c*this.matStudent.n+k,S=docu'
HTML += b'ment.createElement("td");m.appendChild(S);let T=this.inputId'
HTML += b'+"-"+v;new E(S,this.question,T,i,this.matStudent.v[v],!1)}c='
HTML += b'=0&&m.appendChild(this.generateMatrixParenthesis(!1,this.mat'
HTML += b'Student.m))}let s=["+","-","+","-"],a=[0,0,1,-1],o=[1,-1,0,0'
HTML += b'],l=[0,22,888,888],n=[888,888,-22,-22],h=[-22,-22,0,22],p=[t'
HTML += b'his.matExpected.n!=1,this.matExpected.n!=1,this.matExpected.'
HTML += b'm!=1,this.matExpected.m!=1],u=[this.matStudent.n>=10,this.ma'
HTML += b'tStudent.n<=1,this.matStudent.m>=10,this.matStudent.m<=1];fo'
HTML += b'r(let c=0;c<4;c++){if(p[c]==!1)continue;let m=g(s[c]);l[c]!='
HTML += b'888&&(m.style.top=""+l[c]+"px"),n[c]!=888&&(m.style.bottom="'
HTML += b'"+n[c]+"px"),h[c]!=888&&(m.style.right=""+h[c]+"px"),m.class'
HTML += b'List.add("matrixResizeButton"),e.appendChild(m),u[c]?m.style'
HTML += b'.opacity="0.5":m.addEventListener("click",()=>{this.matStude'
HTML += b'nt.resize(this.matStudent.m+a[c],this.matStudent.n+o[c],"0")'
HTML += b',this.genMatrixDom()})}}generateMatrixParenthesis(e,t){let i'
HTML += b'=document.createElement("td");i.style.width="3px";for(let s '
HTML += b'of["Top",e?"Left":"Right","Bottom"])i.style["border"+s+"Widt'
HTML += b'h"]="2px",i.style["border"+s+"Style"]="solid";return this.qu'
HTML += b'estion.language=="de"&&(e?i.style.borderTopLeftRadius="5px":'
HTML += b'i.style.borderTopRightRadius="5px",e?i.style.borderBottomLef'
HTML += b'tRadius="5px":i.style.borderBottomRightRadius="5px"),i.rowSp'
HTML += b'an=t,i}};var w={init:0,errors:1,passed:2},H=class{constructo'
HTML += b'r(e,t,i,s){this.state=w.init,this.language=i,this.src=t,this'
HTML += b'.debug=s,this.instanceOrder=P(t.instances.length,!0),this.in'
HTML += b'stanceIdx=0,this.choiceIdx=0,this.gapIdx=0,this.expected={},'
HTML += b'this.types={},this.student={},this.gapInputs={},this.parentD'
HTML += b'iv=e,this.questionDiv=null,this.feedbackPopupDiv=null,this.t'
HTML += b'itleDiv=null,this.checkAndRepeatBtn=null,this.showSolution=!'
HTML += b'1,this.feedbackSpan=null,this.numCorrect=0,this.numChecked=0'
HTML += b'}reset(){this.instanceIdx=(this.instanceIdx+1)%this.src.inst'
HTML += b'ances.length}getCurrentInstance(){let e=this.instanceOrder[t'
HTML += b'his.instanceIdx];return this.src.instances[e]}editedQuestion'
HTML += b'(){this.state=w.init,this.updateVisualQuestionState(),this.q'
HTML += b'uestionDiv.style.color="black",this.checkAndRepeatBtn.innerH'
HTML += b'TML=I,this.checkAndRepeatBtn.style.display="block",this.chec'
HTML += b'kAndRepeatBtn.style.color="black"}updateVisualQuestionState('
HTML += b'){let e="black",t="transparent";switch(this.state){case w.in'
HTML += b'it:e="rgb(0,0,0)",t="transparent";break;case w.passed:e="rgb'
HTML += b'(0,150,0)",t="rgba(0,150,0, 0.025)";break;case w.errors:e="r'
HTML += b'gb(150,0,0)",t="rgba(150,0,0, 0.025)",this.numChecked>=5&&(t'
HTML += b'his.feedbackSpan.innerHTML=""+this.numCorrect+" / "+this.num'
HTML += b'Checked);break}this.questionDiv.style.color=this.feedbackSpa'
HTML += b'n.style.color=this.titleDiv.style.color=this.checkAndRepeatB'
HTML += b'tn.style.backgroundColor=this.questionDiv.style.borderColor='
HTML += b'e,this.questionDiv.style.backgroundColor=t}populateDom(){if('
HTML += b'this.parentDiv.innerHTML="",this.questionDiv=x(),this.parent'
HTML += b'Div.appendChild(this.questionDiv),this.questionDiv.classList'
HTML += b'.add("question"),this.feedbackPopupDiv=x(),this.feedbackPopu'
HTML += b'pDiv.classList.add("questionFeedback"),this.questionDiv.appe'
HTML += b'ndChild(this.feedbackPopupDiv),this.feedbackPopupDiv.innerHT'
HTML += b'ML="awesome",this.debug&&"src_line"in this.src){let a=x();a.'
HTML += b'classList.add("debugInfo"),a.innerHTML="Source code: lines "'
HTML += b'+this.src.src_line+"..",this.questionDiv.appendChild(a)}if(t'
HTML += b'his.titleDiv=x(),this.questionDiv.appendChild(this.titleDiv)'
HTML += b',this.titleDiv.classList.add("questionTitle"),this.titleDiv.'
HTML += b'innerHTML=this.src.title,this.src.error.length>0){let a=g(th'
HTML += b'is.src.error);this.questionDiv.appendChild(a),a.style.color='
HTML += b'"red";return}let e=this.getCurrentInstance();if(e!=null&&"__'
HTML += b'svg_image"in e){let a=e.__svg_image.v,o=x();this.questionDiv'
HTML += b'.appendChild(o);let l=document.createElement("img");o.append'
HTML += b'Child(l),l.classList.add("img"),l.src="data:image/svg+xml;ba'
HTML += b'se64,"+a}for(let a of this.src.text.c)this.questionDiv.appen'
HTML += b'dChild(this.generateText(a));let t=x();this.questionDiv.appe'
HTML += b'ndChild(t),t.classList.add("buttonRow");let i=Object.keys(th'
HTML += b'is.expected).length>0;i&&(this.checkAndRepeatBtn=j(),t.appen'
HTML += b'dChild(this.checkAndRepeatBtn),this.checkAndRepeatBtn.innerH'
HTML += b'TML=I,this.checkAndRepeatBtn.style.backgroundColor="black");'
HTML += b'let s=g("&nbsp;&nbsp;&nbsp;");if(t.appendChild(s),this.feedb'
HTML += b'ackSpan=g(""),t.appendChild(this.feedbackSpan),this.debug){i'
HTML += b'f(this.src.variables.length>0){let l=x();l.classList.add("de'
HTML += b'bugInfo"),l.innerHTML="Variables generated by Python Code",t'
HTML += b'his.questionDiv.appendChild(l);let n=x();n.classList.add("de'
HTML += b'bugCode"),this.questionDiv.appendChild(n);let h=this.getCurr'
HTML += b'entInstance(),p="",u=[...this.src.variables];u.sort();for(le'
HTML += b't c of u){let m=h[c].t,k=h[c].v;switch(m){case"vector":k="["'
HTML += b'+k+"]";break;case"set":k="{"+k+"}";break}p+=m+" "+c+" = "+k+'
HTML += b'"<br/>"}n.innerHTML=p}let a=["python_src_html","text_src_htm'
HTML += b'l"],o=["Python Source Code","Text Source Code"];for(let l=0;'
HTML += b'l<a.length;l++){let n=a[l];if(n in this.src&&this.src[n].len'
HTML += b'gth>0){let h=x();h.classList.add("debugInfo"),h.innerHTML=o['
HTML += b'l],this.questionDiv.appendChild(h);let p=x();p.classList.add'
HTML += b'("debugCode"),this.questionDiv.append(p),p.innerHTML=this.sr'
HTML += b'c[n]}}}i&&this.checkAndRepeatBtn.addEventListener("click",()'
HTML += b'=>{this.state==w.passed?(this.state=w.init,this.reset(),this'
HTML += b'.populateDom()):ie(this)})}generateMathString(e){let t="";sw'
HTML += b'itch(e.t){case"math":case"display-math":for(let i of e.c){le'
HTML += b't s=this.generateMathString(i);i.t==="var"&&t.includes("!PM"'
HTML += b')&&(s.startsWith("{-")?(s="{"+s.substring(2),t=t.replaceAll('
HTML += b'"!PM","-")):t=t.replaceAll("!PM","+")),t+=s}break;case"text"'
HTML += b':return e.d;case"plus_minus":{t+=" !PM ";break}case"var":{le'
HTML += b't i=this.getCurrentInstance(),s=i[e.d].t,a=i[e.d].v;switch(s'
HTML += b'){case"vector":return"\\\\left["+a+"\\\\right]";case"set":return'
HTML += b'"\\\\left\\\\{"+a+"\\\\right\\\\}";case"complex":{let o=a.split(",")'
HTML += b',l=parseFloat(o[0]),n=parseFloat(o[1]);return d.const(l,n).t'
HTML += b'oTexString()}case"matrix":{let o=new C(0,0);return o.fromStr'
HTML += b'ing(a),t=o.toTeXString(e.d.includes("augmented"),this.langua'
HTML += b'ge!="de"),t}case"term":{try{t=f.parse(a).toTexString()}catch'
HTML += b'{}break}default:t=a}}}return e.t==="plus_minus"?t:"{"+t+"}"}'
HTML += b'generateText(e,t=!1){switch(e.t){case"paragraph":case"span":'
HTML += b'{let i=document.createElement(e.t=="span"||t?"span":"p");for'
HTML += b'(let s of e.c)i.appendChild(this.generateText(s));return i}c'
HTML += b'ase"text":return g(e.d);case"code":{let i=g(e.d);return i.cl'
HTML += b'assList.add("code"),i}case"italic":case"bold":{let i=g("");r'
HTML += b'eturn i.append(...e.c.map(s=>this.generateText(s))),e.t==="b'
HTML += b'old"?i.style.fontWeight="bold":i.style.fontStyle="italic",i}'
HTML += b'case"math":case"display-math":{let i=this.generateMathString'
HTML += b'(e);return y(i,e.t==="display-math")}case"string_var":{let i'
HTML += b'=g(""),s=this.getCurrentInstance(),a=s[e.d].t,o=s[e.d].v;ret'
HTML += b'urn a==="string"?i.innerHTML=o:(i.innerHTML="EXPECTED VARIAB'
HTML += b'LE OF TYPE STRING",i.style.color="red"),i}case"gap":{let i=g'
HTML += b'("");return new A(i,this,"",e.d),i}case"input":case"input2":'
HTML += b'{let i=e.t==="input2",s=g("");s.style.verticalAlign="text-bo'
HTML += b'ttom";let a=e.d,o=this.getCurrentInstance()[a];if(this.expec'
HTML += b'ted[a]=o.v,this.types[a]=o.t,!i)switch(o.t){case"set":s.appe'
HTML += b'nd(y("\\\\{"),g(" "));break;case"vector":s.append(y("["),g(" "'
HTML += b'));break}if(o.t==="string")new A(s,this,a,this.expected[a]);'
HTML += b'else if(o.t==="vector"||o.t==="set"){let l=o.v.split(","),n='
HTML += b'l.length;for(let h=0;h<n;h++){h>0&&s.appendChild(g(" , "));l'
HTML += b'et p=a+"-"+h;new E(s,this,p,l[h].length,l[h],!1)}}else if(o.'
HTML += b't==="matrix"){let l=x();s.appendChild(l),new V(l,this,a,o.v)'
HTML += b'}else if(o.t==="complex"){let l=o.v.split(",");new E(s,this,'
HTML += b'a+"-0",l[0].length,l[0],!1),s.append(g(" "),y("+"),g(" ")),n'
HTML += b'ew E(s,this,a+"-1",l[1].length,l[1],!1),s.append(g(" "),y("i'
HTML += b'"))}else{let l=o.t==="int";new E(s,this,a,o.v.length,o.v,l)}'
HTML += b'if(!i)switch(o.t){case"set":s.append(g(" "),y("\\\\}"));break;'
HTML += b'case"vector":s.append(g(" "),y("]"));break}return s}case"ite'
HTML += b'mize":return z(e.c.map(i=>U(this.generateText(i))));case"sin'
HTML += b'gle-choice":case"multi-choice":{let i=e.t=="multi-choice",s='
HTML += b'document.createElement("table"),a=e.c.length,o=this.debug==!'
HTML += b'1,l=P(a,o),n=i?G:$,h=i?Y:J,p=[],u=[];for(let c=0;c<a;c++){le'
HTML += b't m=l[c],k=e.c[m],v="mc-"+this.choiceIdx+"-"+m;u.push(v);let'
HTML += b' S=k.c[0].t=="bool"?k.c[0].d:this.getCurrentInstance()[k.c[0'
HTML += b'].d].v;this.expected[v]=S,this.types[v]="bool",this.student['
HTML += b'v]=this.showSolution?S:"false";let T=this.generateText(k.c[1'
HTML += b'],!0),M=document.createElement("tr");s.appendChild(M),M.styl'
HTML += b'e.cursor="pointer";let D=document.createElement("td");p.push'
HTML += b'(D),M.appendChild(D),D.innerHTML=this.student[v]=="true"?n:h'
HTML += b';let b=document.createElement("td");M.appendChild(b),b.appen'
HTML += b'dChild(T),i?M.addEventListener("click",()=>{this.editedQuest'
HTML += b'ion(),this.student[v]=this.student[v]==="true"?"false":"true'
HTML += b'",this.student[v]==="true"?D.innerHTML=n:D.innerHTML=h}):M.a'
HTML += b'ddEventListener("click",()=>{this.editedQuestion();for(let L'
HTML += b' of u)this.student[L]="false";this.student[v]="true";for(let'
HTML += b' L=0;L<u.length;L++){let Q=l[L];p[Q].innerHTML=this.student['
HTML += b'u[Q]]=="true"?n:h}})}return this.choiceIdx++,s}case"image":{'
HTML += b'let i=x(),a=e.d.split("."),o=a[a.length-1],l=e.c[0].d,n=e.c['
HTML += b'1].d,h=document.createElement("img");i.appendChild(h),h.clas'
HTML += b'sList.add("img"),h.style.width=l+"%";let p={svg:"svg+xml",pn'
HTML += b'g:"png",jpg:"jpeg"};return h.src="data:image/"+p[o]+";base64'
HTML += b',"+n,i}default:{let i=g("UNIMPLEMENTED("+e.t+")");return i.s'
HTML += b'tyle.color="red",i}}}};function ce(r,e){["en","de","es","it"'
HTML += b',"fr"].includes(r.lang)==!1&&(r.lang="en"),e&&(document.getE'
HTML += b'lementById("debug").style.display="block"),document.getEleme'
HTML += b'ntById("date").innerHTML=r.date,document.getElementById("tit'
HTML += b'le").innerHTML=r.title,document.getElementById("author").inn'
HTML += b'erHTML=r.author,document.getElementById("courseInfo1").inner'
HTML += b'HTML=O[r.lang];let t=\'<span onclick="location.reload()" styl'
HTML += b'e="text-decoration: underline; font-weight: bold; cursor: po'
HTML += b'inter">\'+K[r.lang]+"</span>";document.getElementById("course'
HTML += b'Info2").innerHTML=F[r.lang].replace("*",t);let i=[],s=docume'
HTML += b'nt.getElementById("questions"),a=1;for(let o of r.questions)'
HTML += b'{o.title=""+a+". "+o.title;let l=x();s.appendChild(l);let n='
HTML += b'new H(l,o,r.lang,e);n.showSolution=e,i.push(n),n.populateDom'
HTML += b'(),e&&o.error.length==0&&n.checkAndRepeatBtn.click(),a++}}re'
HTML += b'turn oe(pe);})();sell.init(quizSrc,debug);</script></body> <'
HTML += b'/html> '
HTML = HTML.decode('utf-8')
# @end(html)


def main():
    """the main function"""

    # get input and output path
    if len(sys.argv) < 2:
        print("usage: python sell.py [-J] INPUT_PATH.txt")
        print("   option -J enables to output a JSON file for debugging purposes")
        sys.exit(-1)
    write_explicit_json_file = "-J" in sys.argv
    input_path = sys.argv[-1]
    input_dirname = os.path.dirname(input_path)
    output_path = input_path.replace(".txt", ".html")
    output_debug_path = input_path.replace(".txt", "_DEBUG.html")
    output_json_path = input_path.replace(".txt", ".json")
    if os.path.isfile(input_path) is False:
        print("error: input file path does not exist")
        sys.exit(-1)

    # read input
    input_src: str = ""
    with open(input_path, mode="r", encoding="utf-8") as f:
        input_src = f.read()

    # compile
    out = compile_input_file(input_dirname, input_src)
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
        with open(output_json_path, "w", encoding="utf-8") as f:
            f.write(output_debug_json_formatted)

    # write html
    # (a) debug version (*_DEBUG.html)
    with open(output_debug_path, "w", encoding="utf-8") as f:
        f.write(
            HTML.replace(
                "let quizSrc = {};", "let quizSrc = " + output_debug_json + ";"
            ).replace("let debug = false;", "let debug = true;")
        )
    # (b) release version (*.html)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(HTML.replace("let quizSrc = {};", "let quizSrc = " + output_json + ";"))

    # exit normally
    sys.exit(0)


if __name__ == "__main__":
    main()
