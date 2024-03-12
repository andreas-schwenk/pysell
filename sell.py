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
                v = re.sub(r"\[ ", "[", v)  # remove space(s) after "["
                v = re.sub(r" \]", "]", v)  # remove space(s) before "]"
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
HTML += b'1 { text-align: center; font-size: 28pt; word-wrap: break-wo'
HTML += b'rd; } img { width: 100%; display: block; margin-left: auto; '
HTML += b'margin-right: auto; } .author { text-align: center; font-siz'
HTML += b'e: 18pt; } .courseInfo { font-size: 14pt; font-style: italic'
HTML += b'; /*margin-bottom: 24px;*/ text-align: center; } .question {'
HTML += b' position: relative; /* required for feedback overlays */ co'
HTML += b'lor: black; background-color: white; border-style: solid; bo'
HTML += b'rder-radius: 5px; border-width: 3px; border-color: black; pa'
HTML += b'dding: 8px; margin-top: 20px; margin-bottom: 20px; -webkit-b'
HTML += b'ox-shadow: 4px 6px 8px -1px rgba(0, 0, 0, 0.93); box-shadow:'
HTML += b' 4px 6px 8px -1px rgba(0, 0, 0, 0.1); overflow-x: auto; } .q'
HTML += b'uestionFeedback { z-index: 10; display: none; position: abso'
HTML += b'lute; pointer-events: none; left: 10%; top: 33%; width: 80%;'
HTML += b' /*height: 100%;*/ text-align: center; font-size: 24pt; text'
HTML += b'-shadow: 0px 0px 18px rgba(0, 0, 0, 0.33); background-color:'
HTML += b' rgba(255, 255, 255, 1); padding-top: 20px; padding-bottom: '
HTML += b'20px; /*border-style: solid; border-width: 4px; border-color'
HTML += b': rgb(200, 200, 200);*/ border-radius: 16px; -webkit-box-sha'
HTML += b'dow: 0px 0px 18px 5px rgba(0, 0, 0, 0.66); box-shadow: 0px 0'
HTML += b'px 18px 5px rgba(0, 0, 0, 0.66); } .questionTitle { font-siz'
HTML += b'e: 24pt; } .code { font-family: "Courier New", Courier, mono'
HTML += b'space; color: black; background-color: rgb(235, 235, 235); p'
HTML += b'adding: 2px 5px; border-radius: 5px; margin: 1px 2px; } .deb'
HTML += b'ugCode { font-family: "Courier New", Courier, monospace; pad'
HTML += b'ding: 4px; margin-bottom: 5px; background-color: black; colo'
HTML += b'r: white; border-radius: 5px; opacity: 0.85; overflow-x: scr'
HTML += b'oll; } .debugInfo { text-align: end; font-size: 10pt; margin'
HTML += b'-top: 2px; color: rgb(64, 64, 64); } ul { margin-top: 0; mar'
HTML += b'gin-left: 0px; padding-left: 20px; } .inputField { position:'
HTML += b' relative; width: 32px; height: 24px; font-size: 14pt; borde'
HTML += b'r-style: solid; border-color: black; border-radius: 5px; bor'
HTML += b'der-width: 0.2; padding-left: 5px; padding-right: 5px; outli'
HTML += b'ne-color: black; background-color: transparent; margin: 1px;'
HTML += b' } .inputField:focus { outline-color: maroon; } .equationPre'
HTML += b'view { position: absolute; top: 120%; left: 0%; padding-left'
HTML += b': 8px; padding-right: 8px; padding-top: 4px; padding-bottom:'
HTML += b' 4px; background-color: rgb(128, 0, 0); border-radius: 5px; '
HTML += b'font-size: 12pt; color: white; text-align: start; z-index: 2'
HTML += b'0; opacity: 0.95; } .button { padding-left: 8px; padding-rig'
HTML += b'ht: 8px; padding-top: 5px; padding-bottom: 5px; font-size: 1'
HTML += b'2pt; background-color: rgb(0, 150, 0); color: white; border-'
HTML += b'style: none; border-radius: 4px; height: 36px; cursor: point'
HTML += b'er; } .buttonRow { display: flex; align-items: baseline; mar'
HTML += b'gin-top: 12px; } .matrixResizeButton { width: 20px; backgrou'
HTML += b'nd-color: black; color: #fff; text-align: center; border-rad'
HTML += b'ius: 3px; position: absolute; z-index: 1; height: 20px; curs'
HTML += b'or: pointer; margin-bottom: 3px; } a { color: black; text-de'
HTML += b'coration: underline; } </style> </head> <body> <h1 id="title'
HTML += b'"></h1> <div class="author" id="author"></div> <p id="course'
HTML += b'Info1" class="courseInfo"></p> <p id="courseInfo2" class="co'
HTML += b'urseInfo"></p> <h1 id="debug" class="debugCode" style="displ'
HTML += b'ay: none">DEBUG VERSION</h1> <div id="questions"></div> <p s'
HTML += b'tyle="font-size: 8pt; font-style: italic; text-align: center'
HTML += b'"> This quiz was created using <a href="https://github.com/a'
HTML += b'ndreas-schwenk/pysell">pySELL</a>, the <i>Python-based Simpl'
HTML += b'e E-Learning Language</i>, written by Andreas Schwenk, GPLv3'
HTML += b'<br /> last update on <span id="date"></span> </p> <script>l'
HTML += b'et debug = false; let quizSrc = {};var sell=(()=>{var B=Obje'
HTML += b'ct.defineProperty;var se=Object.getOwnPropertyDescriptor;var'
HTML += b' re=Object.getOwnPropertyNames;var ne=Object.prototype.hasOw'
HTML += b'nProperty;var ae=(r,e)=>{for(var t in e)B(r,t,{get:e[t],enum'
HTML += b'erable:!0})},le=(r,e,t,i)=>{if(e&&typeof e=="object"||typeof'
HTML += b' e=="function")for(let s of re(e))!ne.call(r,s)&&s!==t&&B(r,'
HTML += b's,{get:()=>e[s],enumerable:!(i=se(e,s))||i.enumerable});retu'
HTML += b'rn r};var oe=r=>le(B({},"__esModule",{value:!0}),r);var pe={'
HTML += b'};ae(pe,{init:()=>ce});function x(r=[]){let e=document.creat'
HTML += b'eElement("div");return e.append(...r),e}function z(r=[]){let'
HTML += b' e=document.createElement("ul");return e.append(...r),e}func'
HTML += b'tion U(r){let e=document.createElement("li");return e.append'
HTML += b'Child(r),e}function R(r){let e=document.createElement("input'
HTML += b'");return e.spellcheck=!1,e.type="text",e.classList.add("inp'
HTML += b'utField"),e.style.width=r+"px",e}function j(){let r=document'
HTML += b'.createElement("button");return r.type="button",r.classList.'
HTML += b'add("button"),r}function g(r,e=[]){let t=document.createElem'
HTML += b'ent("span");return e.length>0?t.append(...e):t.innerHTML=r,t'
HTML += b'}function W(r,e,t=!1){katex.render(e,r,{throwOnError:!1,disp'
HTML += b'layMode:t,macros:{"\\\\RR":"\\\\mathbb{R}","\\\\NN":"\\\\mathbb{N}",'
HTML += b'"\\\\QQ":"\\\\mathbb{Q}","\\\\ZZ":"\\\\mathbb{Z}","\\\\CC":"\\\\mathbb{C'
HTML += b'}"}})}function y(r,e=!1){let t=document.createElement("span"'
HTML += b');return W(t,r,e),t}var O={en:"This page runs in your browse'
HTML += b'r and does not store any data on servers.",de:"Diese Seite w'
HTML += b'ird in Ihrem Browser ausgef\\xFChrt und speichert keine Daten'
HTML += b' auf Servern.",es:"Esta p\\xE1gina se ejecuta en su navegador'
HTML += b' y no almacena ning\\xFAn dato en los servidores.",it:"Questa'
HTML += b' pagina viene eseguita nel browser e non memorizza alcun dat'
HTML += b'o sui server.",fr:"Cette page fonctionne dans votre navigate'
HTML += b'ur et ne stocke aucune donn\\xE9e sur des serveurs."},F={en:"'
HTML += b'You can * this page in order to get new randomized tasks.",d'
HTML += b'e:"Sie k\\xF6nnen diese Seite *, um neue randomisierte Aufgab'
HTML += b'en zu erhalten.",es:"Puedes * esta p\\xE1gina para obtener nu'
HTML += b'evas tareas aleatorias.",it:"\\xC8 possibile * questa pagina '
HTML += b'per ottenere nuovi compiti randomizzati",fr:"Vous pouvez * c'
HTML += b'ette page pour obtenir de nouvelles t\\xE2ches al\\xE9atoires"'
HTML += b'},K={en:"reload",de:"aktualisieren",es:"recargar",it:"ricari'
HTML += b'care",fr:"recharger"},q={en:["awesome","great","well done","'
HTML += b'nice","you got it","good"],de:["super","gut gemacht","weiter'
HTML += b' so","richtig"],es:["impresionante","genial","correcto","bie'
HTML += b'n hecho"],it:["fantastico","grande","corretto","ben fatto"],'
HTML += b'fr:["g\\xE9nial","super","correct","bien fait"]},X={en:["try '
HTML += b'again","still some mistakes","wrong answer","no"],de:["leide'
HTML += b'r falsch","nicht richtig","versuch\'s nochmal"],es:["int\\xE9n'
HTML += b'talo de nuevo","todav\\xEDa algunos errores","respuesta incor'
HTML += b'recta"],it:["riprova","ancora qualche errore","risposta sbag'
HTML += b'liata"],fr:["r\\xE9essayer","encore des erreurs","mauvaise r\\'
HTML += b'xE9ponse"]};function Z(r,e){let t=Array(e.length+1).fill(nul'
HTML += b'l).map(()=>Array(r.length+1).fill(null));for(let i=0;i<=r.le'
HTML += b'ngth;i+=1)t[0][i]=i;for(let i=0;i<=e.length;i+=1)t[i][0]=i;f'
HTML += b'or(let i=1;i<=e.length;i+=1)for(let s=1;s<=r.length;s+=1){le'
HTML += b't a=r[s-1]===e[i-1]?0:1;t[i][s]=Math.min(t[i][s-1]+1,t[i-1]['
HTML += b"s]+1,t[i-1][s-1]+a)}return t[e.length][r.length]}var Y='<svg"
HTML += b' xmlns="http://www.w3.org/2000/svg" height="28" viewBox="0 0'
HTML += b' 448 512"><path d="M384 80c8.8 0 16 7.2 16 16V416c0 8.8-7.2 '
HTML += b'16-16 16H64c-8.8 0-16-7.2-16-16V96c0-8.8 7.2-16 16-16H384zM6'
HTML += b'4 32C28.7 32 0 60.7 0 96V416c0 35.3 28.7 64 64 64H384c35.3 0'
HTML += b' 64-28.7 64-64V96c0-35.3-28.7-64-64-64H64z"/></svg>\',G=\'<svg'
HTML += b' xmlns="http://www.w3.org/2000/svg" height="28" viewBox="0 0'
HTML += b' 448 512"><path d="M64 80c-8.8 0-16 7.2-16 16V416c0 8.8 7.2 '
HTML += b'16 16 16H384c8.8 0 16-7.2 16-16V96c0-8.8-7.2-16-16-16H64zM0 '
HTML += b'96C0 60.7 28.7 32 64 32H384c35.3 0 64 28.7 64 64V416c0 35.3-'
HTML += b'28.7 64-64 64H64c-35.3 0-64-28.7-64-64V96zM337 209L209 337c-'
HTML += b'9.4 9.4-24.6 9.4-33.9 0l-64-64c-9.4-9.4-9.4-24.6 0-33.9s24.6'
HTML += b'-9.4 33.9 0l47 47L303 175c9.4-9.4 24.6-9.4 33.9 0s9.4 24.6 0'
HTML += b' 33.9z"/>\',J=\'<svg xmlns="http://www.w3.org/2000/svg" height'
HTML += b'="28" viewBox="0 0 512 512"><path d="M464 256A208 208 0 1 0 '
HTML += b'48 256a208 208 0 1 0 416 0zM0 256a256 256 0 1 1 512 0A256 25'
HTML += b'6 0 1 1 0 256z"/></svg>\',$=\'<svg xmlns="http://www.w3.org/20'
HTML += b'00/svg" height="28" viewBox="0 0 512 512"><path d="M256 48a2'
HTML += b'08 208 0 1 1 0 416 208 208 0 1 1 0-416zm0 464A256 256 0 1 0 '
HTML += b'256 0a256 256 0 1 0 0 512zM369 209c9.4-9.4 9.4-24.6 0-33.9s-'
HTML += b'24.6-9.4-33.9 0l-111 111-47-47c-9.4-9.4-24.6-9.4-33.9 0s-9.4'
HTML += b' 24.6 0 33.9l64 64c9.4 9.4 24.6 9.4 33.9 0L369 209z"/></svg>'
HTML += b'\',I=\'<svg xmlns="http://www.w3.org/2000/svg" height="25" vie'
HTML += b'wBox="0 0 384 512" fill="white"><path d="M73 39c-14.8-9.1-33'
HTML += b'.4-9.4-48.5-.9S0 62.6 0 80V432c0 17.4 9.4 33.4 24.5 41.9s33.'
HTML += b'7 8.1 48.5-.9L361 297c14.3-8.7 23-24.2 23-41s-8.7-32.2-23-41'
HTML += b'L73 39z"/></svg>\',ee=\'<svg xmlns="http://www.w3.org/2000/svg'
HTML += b'" height="25" viewBox="0 0 512 512" fill="white"><path d="M0'
HTML += b' 224c0 17.7 14.3 32 32 32s32-14.3 32-32c0-53 43-96 96-96H320'
HTML += b'v32c0 12.9 7.8 24.6 19.8 29.6s25.7 2.2 34.9-6.9l64-64c12.5-1'
HTML += b'2.5 12.5-32.8 0-45.3l-64-64c-9.2-9.2-22.9-11.9-34.9-6.9S320 '
HTML += b'19.1 320 32V64H160C71.6 64 0 135.6 0 224zm512 64c0-17.7-14.3'
HTML += b'-32-32-32s-32 14.3-32 32c0 53-43 96-96 96H192V352c0-12.9-7.8'
HTML += b'-24.6-19.8-29.6s-25.7-2.2-34.9 6.9l-64 64c-12.5 12.5-12.5 32'
HTML += b'.8 0 45.3l64 64c9.2 9.2 22.9 11.9 34.9 6.9s19.8-16.6 19.8-29'
HTML += b'.6V448H352c88.4 0 160-71.6 160-160z"/></svg>\';function P(r,e'
HTML += b'=!1){let t=new Array(r);for(let i=0;i<r;i++)t[i]=i;if(e)for('
HTML += b'let i=0;i<r;i++){let s=Math.floor(Math.random()*r),a=Math.fl'
HTML += b'oor(Math.random()*r),o=t[s];t[s]=t[a],t[a]=o}return t}functi'
HTML += b'on _(r,e,t=-1){if(t<0&&(t=r.length),t==1){e.push([...r]);ret'
HTML += b'urn}for(let i=0;i<t;i++){_(r,e,t-1);let s=t%2==0?i:0,a=r[s];'
HTML += b'r[s]=r[t-1],r[t-1]=a}}var C=class r{constructor(e,t){this.m='
HTML += b'e,this.n=t,this.v=new Array(e*t).fill("0")}getElement(e,t){r'
HTML += b'eturn e<0||e>=this.m||t<0||t>=this.n?"0":this.v[e*this.n+t]}'
HTML += b'resize(e,t,i){if(e<1||e>50||t<1||t>50)return!1;let s=new r(e'
HTML += b',t);s.v.fill(i);for(let a=0;a<s.m;a++)for(let o=0;o<s.n;o++)'
HTML += b's.v[a*s.n+o]=this.getElement(a,o);return this.fromMatrix(s),'
HTML += b'!0}fromMatrix(e){this.m=e.m,this.n=e.n,this.v=[...e.v]}fromS'
HTML += b'tring(e){this.m=e.split("],").length,this.v=e.replaceAll("["'
HTML += b',"").replaceAll("]","").split(",").map(t=>t.trim()),this.n=t'
HTML += b'his.v.length/this.m}getMaxCellStrlen(){let e=0;for(let t of '
HTML += b'this.v)t.length>e&&(e=t.length);return e}toTeXString(e=!1,t='
HTML += b'!0){let i="";t?i+=e?"\\\\left[\\\\begin{array}":"\\\\begin{bmatrix'
HTML += b'}":i+=e?"\\\\left(\\\\begin{array}":"\\\\begin{pmatrix}",e&&(i+="{'
HTML += b'"+"c".repeat(this.n-1)+"|c}");for(let s=0;s<this.m;s++){for('
HTML += b'let a=0;a<this.n;a++){a>0&&(i+="&");let o=this.getElement(s,'
HTML += b'a);try{o=f.parse(o).toTexString()}catch{}i+=o}i+="\\\\\\\\"}retu'
HTML += b'rn t?i+=e?"\\\\end{array}\\\\right]":"\\\\end{bmatrix}":i+=e?"\\\\en'
HTML += b'd{array}\\\\right)":"\\\\end{pmatrix}",i}},f=class r{constructor'
HTML += b'(){this.root=null,this.src="",this.token="",this.skippedWhit'
HTML += b'eSpace=!1,this.pos=0}clone(){let e=new r;return e.root=this.'
HTML += b'root.clone(),e}getVars(e,t="",i=null){if(i==null&&(i=this.ro'
HTML += b'ot),i.op.startsWith("var:")){let s=i.op.substring(4);(t.leng'
HTML += b'th==0||t.length>0&&s.startsWith(t))&&e.add(s)}for(let s of i'
HTML += b'.c)this.getVars(e,t,s)}setVars(e,t=null){t==null&&(t=this.ro'
HTML += b'ot);for(let i of t.c)this.setVars(e,i);if(t.op.startsWith("v'
HTML += b'ar:")){let i=t.op.substring(4);if(i in e){let s=e[i].clone()'
HTML += b';t.op=s.op,t.c=s.c,t.re=s.re,t.im=s.im}}}renameVar(e,t,i=nul'
HTML += b'l){i==null&&(i=this.root);for(let s of i.c)this.renameVar(e,'
HTML += b't,s);i.op.startsWith("var:")&&i.op.substring(4)===e&&(i.op="'
HTML += b'var:"+t)}eval(e,t=null){let s=d.const(),a=0,o=0,l=null;switc'
HTML += b'h(t==null&&(t=this.root),t.op){case"const":s=t;break;case"+"'
HTML += b':case"-":case"*":case"/":case"^":{let n=this.eval(e,t.c[0]),'
HTML += b'h=this.eval(e,t.c[1]);switch(t.op){case"+":s.re=n.re+h.re,s.'
HTML += b'im=n.im+h.im;break;case"-":s.re=n.re-h.re,s.im=n.im-h.im;bre'
HTML += b'ak;case"*":s.re=n.re*h.re-n.im*h.im,s.im=n.re*h.im+n.im*h.re'
HTML += b';break;case"/":a=h.re*h.re+h.im*h.im,s.re=(n.re*h.re+n.im*h.'
HTML += b'im)/a,s.im=(n.im*h.re-n.re*h.im)/a;break;case"^":l=new d("ex'
HTML += b'p",[new d("*",[h,new d("ln",[n])])]),s=this.eval(e,l);break}'
HTML += b'break}case".-":case"abs":case"sin":case"sinc":case"cos":case'
HTML += b'"tan":case"cot":case"exp":case"ln":case"log":case"sqrt":{let'
HTML += b' n=this.eval(e,t.c[0]);switch(t.op){case".-":s.re=-n.re,s.im'
HTML += b'=-n.im;break;case"abs":s.re=Math.sqrt(n.re*n.re+n.im*n.im),s'
HTML += b'.im=0;break;case"sin":s.re=Math.sin(n.re)*Math.cosh(n.im),s.'
HTML += b'im=Math.cos(n.re)*Math.sinh(n.im);break;case"sinc":l=new d("'
HTML += b'/",[new d("sin",[n]),n]),s=this.eval(e,l);break;case"cos":s.'
HTML += b're=Math.cos(n.re)*Math.cosh(n.im),s.im=-Math.sin(n.re)*Math.'
HTML += b'sinh(n.im);break;case"tan":a=Math.cos(n.re)*Math.cos(n.re)+M'
HTML += b'ath.sinh(n.im)*Math.sinh(n.im),s.re=Math.sin(n.re)*Math.cos('
HTML += b'n.re)/a,s.im=Math.sinh(n.im)*Math.cosh(n.im)/a;break;case"co'
HTML += b't":a=Math.sin(n.re)*Math.sin(n.re)+Math.sinh(n.im)*Math.sinh'
HTML += b'(n.im),s.re=Math.sin(n.re)*Math.cos(n.re)/a,s.im=-(Math.sinh'
HTML += b'(n.im)*Math.cosh(n.im))/a;break;case"exp":s.re=Math.exp(n.re'
HTML += b')*Math.cos(n.im),s.im=Math.exp(n.re)*Math.sin(n.im);break;ca'
HTML += b'se"ln":case"log":s.re=Math.log(Math.sqrt(n.re*n.re+n.im*n.im'
HTML += b')),a=Math.abs(n.im)<1e-9?0:n.im,s.im=Math.atan2(a,n.re);brea'
HTML += b'k;case"sqrt":l=new d("^",[n,d.const(.5)]),s=this.eval(e,l);b'
HTML += b'reak}break}default:if(t.op.startsWith("var:")){let n=t.op.su'
HTML += b'bstring(4);if(n==="pi")return d.const(Math.PI);if(n==="e")re'
HTML += b'turn d.const(Math.E);if(n==="i")return d.const(0,1);if(n in '
HTML += b'e)return e[n];throw new Error("eval-error: unknown variable '
HTML += b'\'"+n+"\'")}else throw new Error("UNIMPLEMENTED eval \'"+t.op+"'
HTML += b'\'")}return s}static parse(e){let t=new r;if(t.src=e,t.token='
HTML += b'"",t.skippedWhiteSpace=!1,t.pos=0,t.next(),t.root=t.parseExp'
HTML += b'r(!1),t.token!=="")throw new Error("remaining tokens: "+t.to'
HTML += b'ken+"...");return t}parseExpr(e){return this.parseAdd(e)}par'
HTML += b'seAdd(e){let t=this.parseMul(e);for(;["+","-"].includes(this'
HTML += b'.token)&&!(e&&this.skippedWhiteSpace);){let i=this.token;thi'
HTML += b's.next(),t=new d(i,[t,this.parseMul(e)])}return t}parseMul(e'
HTML += b'){let t=this.parsePow(e);for(;!(e&&this.skippedWhiteSpace);)'
HTML += b'{let i="*";if(["*","/"].includes(this.token))i=this.token,th'
HTML += b'is.next();else if(!e&&this.token==="(")i="*";else if(this.to'
HTML += b'ken.length>0&&(this.isAlpha(this.token[0])||this.isNum(this.'
HTML += b'token[0])))i="*";else break;t=new d(i,[t,this.parsePow(e)])}'
HTML += b'return t}parsePow(e){let t=this.parseUnary(e);for(;["^"].inc'
HTML += b'ludes(this.token)&&!(e&&this.skippedWhiteSpace);){let i=this'
HTML += b'.token;this.next(),t=new d(i,[t,this.parseUnary(e)])}return '
HTML += b't}parseUnary(e){return this.token==="-"?(this.next(),new d("'
HTML += b'.-",[this.parseMul(e)])):this.parseInfix(e)}parseInfix(e){if'
HTML += b'(this.token.length==0)throw new Error("expected unary");if(t'
HTML += b'his.isNum(this.token[0])){let t=this.token;return this.next('
HTML += b'),this.token==="."&&(t+=".",this.next(),this.token.length>0&'
HTML += b'&(t+=this.token,this.next())),new d("const",[],parseFloat(t)'
HTML += b')}else if(this.fun1().length>0){let t=this.fun1();this.next('
HTML += b't.length);let i=null;if(this.token==="(")if(this.next(),i=th'
HTML += b'is.parseExpr(e),this.token+="",this.token===")")this.next();'
HTML += b'else throw Error("expected \')\'");else i=this.parseMul(!0);re'
HTML += b'turn new d(t,[i])}else if(this.token==="("){this.next();let '
HTML += b't=this.parseExpr(e);if(this.token+="",this.token===")")this.'
HTML += b'next();else throw Error("expected \')\'");return t.explicitPar'
HTML += b'entheses=!0,t}else if(this.token==="|"){this.next();let t=th'
HTML += b'is.parseExpr(e);if(this.token+="",this.token==="|")this.next'
HTML += b'();else throw Error("expected \'|\'");return new d("abs",[t])}'
HTML += b'else if(this.isAlpha(this.token[0])){let t="";return this.to'
HTML += b'ken.startsWith("pi")?t="pi":this.token.startsWith("C1")?t="C'
HTML += b'1":this.token.startsWith("C2")?t="C2":t=this.token[0],t==="I'
HTML += b'"&&(t="i"),this.next(t.length),new d("var:"+t,[])}else throw'
HTML += b' new Error("expected unary")}static compare(e,t,i={}){let o='
HTML += b'new Set;e.getVars(o),t.getVars(o);for(let l=0;l<10;l++){let '
HTML += b'n={};for(let k of o)k in i?n[k]=i[k]:n[k]=d.const(Math.rando'
HTML += b'm(),Math.random());let h=e.eval(n),p=t.eval(n),u=h.re-p.re,c'
HTML += b'=h.im-p.im;if(Math.sqrt(u*u+c*c)>1e-9)return!1}return!0}fun1'
HTML += b'(){let e=["abs","sinc","sin","cos","tan","cot","exp","ln","s'
HTML += b'qrt"];for(let t of e)if(this.token.toLowerCase().startsWith('
HTML += b't))return t;return""}next(e=-1){if(e>0&&this.token.length>e)'
HTML += b'{this.token=this.token.substring(e),this.skippedWhiteSpace=!'
HTML += b'1;return}this.token="";let t=!1,i=this.src.length;for(this.s'
HTML += b'kippedWhiteSpace=!1;this.pos<i&&`\t\n `.includes(this.src[this'
HTML += b'.pos]);)this.skippedWhiteSpace=!0,this.pos++;for(;!t&&this.p'
HTML += b'os<i;){let s=this.src[this.pos];if(this.token.length>0&&(thi'
HTML += b's.isNum(this.token[0])&&this.isAlpha(s)||this.isAlpha(this.t'
HTML += b'oken[0])&&this.isNum(s))&&this.token!="C")return;if(`^%#*$()'
HTML += b'[]{},.:;+-*/_!<>=?|\t\n `.includes(s)){if(this.token.length>0)'
HTML += b'return;t=!0}`\t\n `.includes(s)==!1&&(this.token+=s),this.pos+'
HTML += b'+}}isNum(e){return e.charCodeAt(0)>=48&&e.charCodeAt(0)<=57}'
HTML += b'isAlpha(e){return e.charCodeAt(0)>=65&&e.charCodeAt(0)<=90||'
HTML += b'e.charCodeAt(0)>=97&&e.charCodeAt(0)<=122||e==="_"}toString('
HTML += b'){return this.root==null?"":this.root.toString()}toTexString'
HTML += b'(){return this.root==null?"":this.root.toTexString()}},d=cla'
HTML += b'ss r{constructor(e,t,i=0,s=0){this.op=e,this.c=t,this.re=i,t'
HTML += b'his.im=s,this.explicitParentheses=!1}clone(){let e=new r(thi'
HTML += b's.op,this.c.map(t=>t.clone()),this.re,this.im);return e.expl'
HTML += b'icitParentheses=this.explicitParentheses,e}static const(e=0,'
HTML += b't=0){return new r("const",[],e,t)}compare(e,t=0,i=1e-9){let '
HTML += b's=this.re-e,a=this.im-t;return Math.sqrt(s*s+a*a)<i}toString'
HTML += b'(){let e="";if(this.op==="const"){let t=Math.abs(this.re)>1e'
HTML += b'-14,i=Math.abs(this.im)>1e-14;t&&i&&this.im>=0?e="("+this.re'
HTML += b'+"+"+this.im+"i)":t&&i&&this.im<0?e="("+this.re+"-"+-this.im'
HTML += b'+"i)":t&&this.re>0?e=""+this.re:t&&this.re<0?e="("+this.re+"'
HTML += b')":i?e="("+this.im+"i)":e="0"}else this.op.startsWith("var")'
HTML += b'?e=this.op.split(":")[1]:this.c.length==1?e=(this.op===".-"?'
HTML += b'"-":this.op)+"("+this.c.toString()+")":e="("+this.c.map(t=>t'
HTML += b'.toString()).join(this.op)+")";return e}toTexString(e=!1){le'
HTML += b't i="";switch(this.op){case"const":{let s=Math.abs(this.re)>'
HTML += b'1e-9,a=Math.abs(this.im)>1e-9,o=s?""+this.re:"",l=a?""+this.'
HTML += b'im+"i":"";l==="1i"?l="i":l==="-1i"&&(l="-i"),!s&&!a?i="0":(a'
HTML += b'&&this.im>=0&&s&&(l="+"+l),i=o+l);break}case".-":i="-"+this.'
HTML += b'c[0].toTexString();break;case"+":case"-":case"*":case"^":{le'
HTML += b't s=this.c[0].toTexString(),a=this.c[1].toTexString(),o=this'
HTML += b'.op==="*"?"\\\\cdot ":this.op;i="{"+s+"}"+o+"{"+a+"}";break}ca'
HTML += b'se"/":{let s=this.c[0].toTexString(!0),a=this.c[1].toTexStri'
HTML += b'ng(!0);i="\\\\frac{"+s+"}{"+a+"}";break}case"sin":case"sinc":c'
HTML += b'ase"cos":case"tan":case"cot":case"exp":case"ln":{let s=this.'
HTML += b'c[0].toTexString(!0);i+="\\\\"+this.op+"\\\\left("+s+"\\\\right)";'
HTML += b'break}case"sqrt":{let s=this.c[0].toTexString(!0);i+="\\\\"+th'
HTML += b'is.op+"{"+s+"}";break}case"abs":{let s=this.c[0].toTexString'
HTML += b'(!0);i+="\\\\left|"+s+"\\\\right|";break}default:if(this.op.star'
HTML += b'tsWith("var:")){let s=this.op.substring(4);switch(s){case"pi'
HTML += b'":s="\\\\pi";break}i=" "+s+" "}else{let s="warning: Node.toStr'
HTML += b'ing(..):";s+=" unimplemented operator \'"+this.op+"\'",console'
HTML += b'.log(s),i=this.op,this.c.length>0&&(i+="\\\\left({"+this.c.map'
HTML += b'(a=>a.toTexString(!0)).join(",")+"}\\\\right)")}}return!e&&thi'
HTML += b's.explicitParentheses&&(i="\\\\left({"+i+"}\\\\right)"),i}};func'
HTML += b'tion te(r,e){let t=1e-9;if(f.compare(r,e))return!0;r=r.clone'
HTML += b'(),e=e.clone(),N(r.root),N(e.root);let i=new Set;r.getVars(i'
HTML += b'),e.getVars(i);let s=[],a=[];for(let n of i.keys())n.startsW'
HTML += b'ith("C")?s.push(n):a.push(n);let o=s.length;for(let n=0;n<o;'
HTML += b'n++){let h=s[n];r.renameVar(h,"_C"+n),e.renameVar(h,"_C"+n)}'
HTML += b'for(let n=0;n<o;n++)r.renameVar("_C"+n,"C"+n),e.renameVar("_'
HTML += b'C"+n,"C"+n);s=[];for(let n=0;n<o;n++)s.push("C"+n);let l=[];'
HTML += b'_(P(o),l);for(let n of l){let h=r.clone(),p=e.clone();for(le'
HTML += b't c=0;c<o;c++)p.renameVar("C"+c,"__C"+n[c]);for(let c=0;c<o;'
HTML += b'c++)p.renameVar("__C"+c,"C"+c);let u=!0;for(let c=0;c<o;c++)'
HTML += b'{let m="C"+c,k={};k[m]=new d("*",[new d("var:C"+c,[]),new d('
HTML += b'"var:K",[])]),p.setVars(k);let v={};v[m]=d.const(Math.random'
HTML += b'(),Math.random());for(let b=0;b<o;b++)c!=b&&(v["C"+b]=d.cons'
HTML += b't(0,0));let S=new d("abs",[new d("-",[h.root,p.root])]),T=ne'
HTML += b'w f;T.root=S;for(let b of a)v[b]=d.const(Math.random(),Math.'
HTML += b'random());let M=he(T,"K",v)[0];p.setVars({K:d.const(M,0)}),v'
HTML += b'={};for(let b=0;b<o;b++)c!=b&&(v["C"+b]=d.const(0,0));if(f.c'
HTML += b'ompare(h,p,v)==!1){u=!1;break}}if(u&&f.compare(h,p))return!0'
HTML += b'}return!1}function he(r,e,t){let i=1e-11,s=1e3,a=0,o=0,l=1,n'
HTML += b'=888;for(;a<s;){t[e]=d.const(o);let p=r.eval(t).re;t[e]=d.co'
HTML += b'nst(o+l);let u=r.eval(t).re;t[e]=d.const(o-l);let c=r.eval(t'
HTML += b').re,m=0;if(u<p&&(p=u,m=1),c<p&&(p=c,m=-1),m==1&&(o+=l),m==-'
HTML += b'1&&(o-=l),p<i)break;(m==0||m!=n)&&(l/=2),n=m,a++}t[e]=d.cons'
HTML += b't(o);let h=r.eval(t).re;return[o,h]}function N(r){for(let e '
HTML += b'of r.c)N(e);switch(r.op){case"+":case"-":case"*":case"/":cas'
HTML += b'e"^":{let e=[r.c[0].op,r.c[1].op],t=[e[0]==="const",e[1]==="'
HTML += b'const"],i=[e[0].startsWith("var:C"),e[1].startsWith("var:C")'
HTML += b'];i[0]&&t[1]?(r.op=r.c[0].op,r.c=[]):i[1]&&t[0]?(r.op=r.c[1]'
HTML += b'.op,r.c=[]):i[0]&&i[1]&&e[0]==e[1]&&(r.op=r.c[0].op,r.c=[]);'
HTML += b'break}case".-":case"abs":case"sin":case"sinc":case"cos":case'
HTML += b'"tan":case"cot":case"exp":case"ln":case"log":case"sqrt":r.c['
HTML += b'0].op.startsWith("var:C")&&(r.op=r.c[0].op,r.c=[]);break}}fu'
HTML += b'nction ie(r){r.feedbackSpan.innerHTML="",r.numChecked=0,r.nu'
HTML += b'mCorrect=0;for(let i in r.expected){let s=r.types[i],a=r.stu'
HTML += b'dent[i],o=r.expected[i];switch(s){case"bool":r.numChecked++,'
HTML += b'a===o&&r.numCorrect++;break;case"string":{r.numChecked++;let'
HTML += b' l=r.gapInputs[i],n=a.trim().toUpperCase(),h=o.trim().toUppe'
HTML += b'rCase().split("|"),p=!1;for(let u of h)if(Z(n,u)<=1){p=!0,r.'
HTML += b'numCorrect++,r.gapInputs[i].value=u,r.student[i]=u;break}l.s'
HTML += b'tyle.color=p?"black":"white",l.style.backgroundColor=p?"tran'
HTML += b'sparent":"maroon";break}case"int":r.numChecked++,Math.abs(pa'
HTML += b'rseFloat(a)-parseFloat(o))<1e-9&&r.numCorrect++;break;case"f'
HTML += b'loat":case"term":{r.numChecked++;try{let l=f.parse(o),n=f.pa'
HTML += b'rse(a),h=!1;r.src.is_ode?h=te(l,n):h=f.compare(l,n),h&&r.num'
HTML += b'Correct++}catch(l){r.debug&&(console.log("term invalid"),con'
HTML += b'sole.log(l))}break}case"vector":case"complex":case"set":{let'
HTML += b' l=o.split(",");r.numChecked+=l.length;let n=[];for(let h=0;'
HTML += b'h<l.length;h++)n.push(r.student[i+"-"+h]);if(s==="set")for(l'
HTML += b'et h=0;h<l.length;h++)try{let p=f.parse(l[h]);for(let u=0;u<'
HTML += b'n.length;u++){let c=f.parse(n[u]);if(f.compare(p,c)){r.numCo'
HTML += b'rrect++;break}}}catch(p){r.debug&&console.log(p)}else for(le'
HTML += b't h=0;h<l.length;h++)try{let p=f.parse(n[h]),u=f.parse(l[h])'
HTML += b';f.compare(p,u)&&r.numCorrect++}catch(p){r.debug&&console.lo'
HTML += b'g(p)}break}case"matrix":{let l=new C(0,0);l.fromString(o),r.'
HTML += b'numChecked+=l.m*l.n;for(let n=0;n<l.m;n++)for(let h=0;h<l.n;'
HTML += b'h++){let p=n*l.n+h;a=r.student[i+"-"+p];let u=l.v[p];try{let'
HTML += b' c=f.parse(u),m=f.parse(a);f.compare(c,m)&&r.numCorrect++}ca'
HTML += b'tch(c){r.debug&&console.log(c)}}break}default:r.feedbackSpan'
HTML += b'.innerHTML="UNIMPLEMENTED EVAL OF TYPE "+s}}r.state=r.numCor'
HTML += b'rect==r.numChecked?w.passed:w.errors,r.updateVisualQuestionS'
HTML += b'tate();let e=r.state===w.passed?q[r.language]:X[r.language],'
HTML += b't=e[Math.floor(Math.random()*e.length)];r.feedbackPopupDiv.i'
HTML += b'nnerHTML=t,r.feedbackPopupDiv.style.color=r.state===w.passed'
HTML += b'?"green":"maroon",r.feedbackPopupDiv.style.display="block",s'
HTML += b'etTimeout(()=>{r.feedbackPopupDiv.style.display="none"},500)'
HTML += b',r.state===w.passed?r.src.instances.length>0?r.checkAndRepea'
HTML += b'tBtn.innerHTML=ee:r.checkAndRepeatBtn.style.display="none":r'
HTML += b'.checkAndRepeatBtn.innerHTML=I}var A=class{constructor(e,t,i'
HTML += b',s){t.student[i]="",this.question=t,this.inputId=i,i.length='
HTML += b'=0&&(this.inputId="gap-"+t.gapIdx,t.types[this.inputId]="str'
HTML += b'ing",t.expected[this.inputId]=s,t.gapIdx++);let a=s.split("|'
HTML += b'"),o=0;for(let p=0;p<a.length;p++){let u=a[p];u.length>o&&(o'
HTML += b'=u.length)}let l=g("");e.appendChild(l);let n=Math.max(o*15,'
HTML += b'24),h=R(n);if(t.gapInputs[this.inputId]=h,h.addEventListener'
HTML += b'("keyup",()=>{this.question.editedQuestion(),h.value=h.value'
HTML += b'.toUpperCase(),this.question.student[this.inputId]=h.value.t'
HTML += b'rim()}),l.appendChild(h),this.question.showSolution&&(this.q'
HTML += b'uestion.student[this.inputId]=h.value=a[0],a.length>1)){let '
HTML += b'p=g("["+a.join("|")+"]");p.style.fontSize="small",p.style.te'
HTML += b'xtDecoration="underline",l.appendChild(p)}}},E=class{constru'
HTML += b'ctor(e,t,i,s,a,o){t.student[i]="",this.question=t,this.input'
HTML += b'Id=i,this.outerSpan=g(""),this.outerSpan.style.position="rel'
HTML += b'ative",e.appendChild(this.outerSpan),this.inputElement=R(Mat'
HTML += b'h.max(s*12,48)),this.outerSpan.appendChild(this.inputElement'
HTML += b'),this.equationPreviewDiv=x(),this.equationPreviewDiv.classL'
HTML += b'ist.add("equationPreview"),this.equationPreviewDiv.style.dis'
HTML += b'play="none",this.outerSpan.appendChild(this.equationPreviewD'
HTML += b'iv),this.inputElement.addEventListener("click",()=>{this.que'
HTML += b'stion.editedQuestion(),this.edited()}),this.inputElement.add'
HTML += b'EventListener("keyup",()=>{this.question.editedQuestion(),th'
HTML += b'is.edited()}),this.inputElement.addEventListener("focusout",'
HTML += b'()=>{this.equationPreviewDiv.innerHTML="",this.equationPrevi'
HTML += b'ewDiv.style.display="none"}),this.inputElement.addEventListe'
HTML += b'ner("keydown",l=>{let n="abcdefghijklmnopqrstuvwxyz";n+="ABC'
HTML += b'DEFGHIJKLMNOPQRSTUVWXYZ",n+="0123456789",n+="+-*/^(). <>=|",'
HTML += b'o&&(n="-0123456789"),l.key.length<3&&n.includes(l.key)==!1&&'
HTML += b'l.preventDefault();let h=this.inputElement.value.length*12;t'
HTML += b'his.inputElement.offsetWidth<h&&(this.inputElement.style.wid'
HTML += b'th=""+h+"px")}),this.question.showSolution&&(t.student[i]=th'
HTML += b'is.inputElement.value=a)}edited(){let e=this.inputElement.va'
HTML += b'lue.trim(),t="",i=!1;try{let s=f.parse(e);i=s.root.op==="con'
HTML += b'st",t=s.toTexString(),this.inputElement.style.color="black",'
HTML += b'this.equationPreviewDiv.style.backgroundColor="green"}catch{'
HTML += b't=e.replaceAll("^","\\\\hat{~}").replaceAll("_","\\\\_"),this.in'
HTML += b'putElement.style.color="maroon",this.equationPreviewDiv.styl'
HTML += b'e.backgroundColor="maroon"}W(this.equationPreviewDiv,t,!0),t'
HTML += b'his.equationPreviewDiv.style.display=e.length>0&&!i?"block":'
HTML += b'"none",this.question.student[this.inputId]=e}},V=class{const'
HTML += b'ructor(e,t,i,s){this.parent=e,this.question=t,this.inputId=i'
HTML += b',this.matExpected=new C(0,0),this.matExpected.fromString(s),'
HTML += b'this.matStudent=new C(this.matExpected.m==1?1:3,this.matExpe'
HTML += b'cted.n==1?1:3),t.showSolution&&this.matStudent.fromMatrix(th'
HTML += b'is.matExpected),this.genMatrixDom()}genMatrixDom(){let e=x()'
HTML += b';this.parent.innerHTML="",this.parent.appendChild(e),e.style'
HTML += b'.position="relative",e.style.display="inline-block";let t=do'
HTML += b'cument.createElement("table");e.appendChild(t);let i=this.ma'
HTML += b'tExpected.getMaxCellStrlen();for(let c=0;c<this.matStudent.m'
HTML += b';c++){let m=document.createElement("tr");t.appendChild(m),c='
HTML += b'=0&&m.appendChild(this.generateMatrixParenthesis(!0,this.mat'
HTML += b'Student.m));for(let k=0;k<this.matStudent.n;k++){let v=c*thi'
HTML += b's.matStudent.n+k,S=document.createElement("td");m.appendChil'
HTML += b'd(S);let T=this.inputId+"-"+v;new E(S,this.question,T,i,this'
HTML += b'.matStudent.v[v],!1)}c==0&&m.appendChild(this.generateMatrix'
HTML += b'Parenthesis(!1,this.matStudent.m))}let s=["+","-","+","-"],a'
HTML += b'=[0,0,1,-1],o=[1,-1,0,0],l=[0,22,888,888],n=[888,888,-22,-22'
HTML += b'],h=[-22,-22,0,22],p=[this.matExpected.n!=1,this.matExpected'
HTML += b'.n!=1,this.matExpected.m!=1,this.matExpected.m!=1],u=[this.m'
HTML += b'atStudent.n>=10,this.matStudent.n<=1,this.matStudent.m>=10,t'
HTML += b'his.matStudent.m<=1];for(let c=0;c<4;c++){if(p[c]==!1)contin'
HTML += b'ue;let m=g(s[c]);l[c]!=888&&(m.style.top=""+l[c]+"px"),n[c]!'
HTML += b'=888&&(m.style.bottom=""+n[c]+"px"),h[c]!=888&&(m.style.righ'
HTML += b't=""+h[c]+"px"),m.classList.add("matrixResizeButton"),e.appe'
HTML += b'ndChild(m),u[c]?m.style.opacity="0.5":m.addEventListener("cl'
HTML += b'ick",()=>{this.matStudent.resize(this.matStudent.m+a[c],this'
HTML += b'.matStudent.n+o[c],"0"),this.genMatrixDom()})}}generateMatri'
HTML += b'xParenthesis(e,t){let i=document.createElement("td");i.style'
HTML += b'.width="3px";for(let s of["Top",e?"Left":"Right","Bottom"])i'
HTML += b'.style["border"+s+"Width"]="2px",i.style["border"+s+"Style"]'
HTML += b'="solid";return this.question.language=="de"&&(e?i.style.bor'
HTML += b'derTopLeftRadius="5px":i.style.borderTopRightRadius="5px",e?'
HTML += b'i.style.borderBottomLeftRadius="5px":i.style.borderBottomRig'
HTML += b'htRadius="5px"),i.rowSpan=t,i}};var w={init:0,errors:1,passe'
HTML += b'd:2},H=class{constructor(e,t,i,s){this.state=w.init,this.lan'
HTML += b'guage=i,this.src=t,this.debug=s,this.instanceOrder=P(t.insta'
HTML += b'nces.length,!0),this.instanceIdx=0,this.choiceIdx=0,this.gap'
HTML += b'Idx=0,this.expected={},this.types={},this.student={},this.ga'
HTML += b'pInputs={},this.parentDiv=e,this.questionDiv=null,this.feedb'
HTML += b'ackPopupDiv=null,this.titleDiv=null,this.checkAndRepeatBtn=n'
HTML += b'ull,this.showSolution=!1,this.feedbackSpan=null,this.numCorr'
HTML += b'ect=0,this.numChecked=0}reset(){this.instanceIdx=(this.insta'
HTML += b'nceIdx+1)%this.src.instances.length}getCurrentInstance(){let'
HTML += b' e=this.instanceOrder[this.instanceIdx];return this.src.inst'
HTML += b'ances[e]}editedQuestion(){this.state=w.init,this.updateVisua'
HTML += b'lQuestionState(),this.questionDiv.style.color="black",this.c'
HTML += b'heckAndRepeatBtn.innerHTML=I,this.checkAndRepeatBtn.style.di'
HTML += b'splay="block",this.checkAndRepeatBtn.style.color="black"}upd'
HTML += b'ateVisualQuestionState(){let e="black",t="transparent";switc'
HTML += b'h(this.state){case w.init:e="rgb(0,0,0)",t="transparent";bre'
HTML += b'ak;case w.passed:e="rgb(0,150,0)",t="rgba(0,150,0, 0.025)";b'
HTML += b'reak;case w.errors:e="rgb(150,0,0)",t="rgba(150,0,0, 0.025)"'
HTML += b',this.numChecked>=5&&(this.feedbackSpan.innerHTML=""+this.nu'
HTML += b'mCorrect+" / "+this.numChecked);break}this.questionDiv.style'
HTML += b'.color=this.feedbackSpan.style.color=this.titleDiv.style.col'
HTML += b'or=this.checkAndRepeatBtn.style.backgroundColor=this.questio'
HTML += b'nDiv.style.borderColor=e,this.questionDiv.style.backgroundCo'
HTML += b'lor=t}populateDom(){if(this.parentDiv.innerHTML="",this.ques'
HTML += b'tionDiv=x(),this.parentDiv.appendChild(this.questionDiv),thi'
HTML += b's.questionDiv.classList.add("question"),this.feedbackPopupDi'
HTML += b'v=x(),this.feedbackPopupDiv.classList.add("questionFeedback"'
HTML += b'),this.questionDiv.appendChild(this.feedbackPopupDiv),this.f'
HTML += b'eedbackPopupDiv.innerHTML="awesome",this.debug&&"src_line"in'
HTML += b' this.src){let a=x();a.classList.add("debugInfo"),a.innerHTM'
HTML += b'L="Source code: lines "+this.src.src_line+"..",this.question'
HTML += b'Div.appendChild(a)}if(this.titleDiv=x(),this.questionDiv.app'
HTML += b'endChild(this.titleDiv),this.titleDiv.classList.add("questio'
HTML += b'nTitle"),this.titleDiv.innerHTML=this.src.title,this.src.err'
HTML += b'or.length>0){let a=g(this.src.error);this.questionDiv.append'
HTML += b'Child(a),a.style.color="red";return}let e=this.getCurrentIns'
HTML += b'tance();if(e!=null&&"__svg_image"in e){let a=e.__svg_image.v'
HTML += b',o=x();this.questionDiv.appendChild(o);let l=document.create'
HTML += b'Element("img");o.appendChild(l),l.classList.add("img"),l.src'
HTML += b'="data:image/svg+xml;base64,"+a}for(let a of this.src.text.c'
HTML += b')this.questionDiv.appendChild(this.generateText(a));let t=x('
HTML += b');this.questionDiv.appendChild(t),t.classList.add("buttonRow'
HTML += b'");let i=Object.keys(this.expected).length>0;i&&(this.checkA'
HTML += b'ndRepeatBtn=j(),t.appendChild(this.checkAndRepeatBtn),this.c'
HTML += b'heckAndRepeatBtn.innerHTML=I,this.checkAndRepeatBtn.style.ba'
HTML += b'ckgroundColor="black");let s=g("&nbsp;&nbsp;&nbsp;");if(t.ap'
HTML += b'pendChild(s),this.feedbackSpan=g(""),t.appendChild(this.feed'
HTML += b'backSpan),this.debug){if(this.src.variables.length>0){let l='
HTML += b'x();l.classList.add("debugInfo"),l.innerHTML="Variables gene'
HTML += b'rated by Python Code",this.questionDiv.appendChild(l);let n='
HTML += b'x();n.classList.add("debugCode"),this.questionDiv.appendChil'
HTML += b'd(n);let h=this.getCurrentInstance(),p="",u=[...this.src.var'
HTML += b'iables];u.sort();for(let c of u){let m=h[c].t,k=h[c].v;switc'
HTML += b'h(m){case"vector":k="["+k+"]";break;case"set":k="{"+k+"}";br'
HTML += b'eak}p+=m+" "+c+" = "+k+"<br/>"}n.innerHTML=p}let a=["python_'
HTML += b'src_html","text_src_html"],o=["Python Source Code","Text Sou'
HTML += b'rce Code"];for(let l=0;l<a.length;l++){let n=a[l];if(n in th'
HTML += b'is.src&&this.src[n].length>0){let h=x();h.classList.add("deb'
HTML += b'ugInfo"),h.innerHTML=o[l],this.questionDiv.appendChild(h);le'
HTML += b't p=x();p.classList.add("debugCode"),this.questionDiv.append'
HTML += b'(p),p.innerHTML=this.src[n]}}}i&&this.checkAndRepeatBtn.addE'
HTML += b'ventListener("click",()=>{this.state==w.passed?(this.state=w'
HTML += b'.init,this.reset(),this.populateDom()):ie(this)})}generateMa'
HTML += b'thString(e){let t="";switch(e.t){case"math":case"display-mat'
HTML += b'h":for(let i of e.c){let s=this.generateMathString(i);i.t==='
HTML += b'"var"&&t.includes("!PM")&&(s.startsWith("{-")?(s="{"+s.subst'
HTML += b'ring(2),t=t.replaceAll("!PM","-")):t=t.replaceAll("!PM","+")'
HTML += b'),t+=s}break;case"text":return e.d;case"plus_minus":{t+=" !P'
HTML += b'M ";break}case"var":{let i=this.getCurrentInstance(),s=i[e.d'
HTML += b'].t,a=i[e.d].v;switch(s){case"vector":return"\\\\left["+a+"\\\\r'
HTML += b'ight]";case"set":return"\\\\left\\\\{"+a+"\\\\right\\\\}";case"compl'
HTML += b'ex":{let o=a.split(","),l=parseFloat(o[0]),n=parseFloat(o[1]'
HTML += b');return d.const(l,n).toTexString()}case"matrix":{let o=new '
HTML += b'C(0,0);return o.fromString(a),t=o.toTeXString(e.d.includes("'
HTML += b'augmented"),this.language!="de"),t}case"term":{try{t=f.parse'
HTML += b'(a).toTexString()}catch{}break}default:t=a}}}return e.t==="p'
HTML += b'lus_minus"?t:"{"+t+"}"}generateText(e,t=!1){switch(e.t){case'
HTML += b'"paragraph":case"span":{let i=document.createElement(e.t=="s'
HTML += b'pan"||t?"span":"p");for(let s of e.c)i.appendChild(this.gene'
HTML += b'rateText(s));return i}case"text":return g(e.d);case"code":{l'
HTML += b'et i=g(e.d);return i.classList.add("code"),i}case"italic":ca'
HTML += b'se"bold":{let i=g("");return i.append(...e.c.map(s=>this.gen'
HTML += b'erateText(s))),e.t==="bold"?i.style.fontWeight="bold":i.styl'
HTML += b'e.fontStyle="italic",i}case"math":case"display-math":{let i='
HTML += b'this.generateMathString(e);return y(i,e.t==="display-math")}'
HTML += b'case"string_var":{let i=g(""),s=this.getCurrentInstance(),a='
HTML += b's[e.d].t,o=s[e.d].v;return a==="string"?i.innerHTML=o:(i.inn'
HTML += b'erHTML="EXPECTED VARIABLE OF TYPE STRING",i.style.color="red'
HTML += b'"),i}case"gap":{let i=g("");return new A(i,this,"",e.d),i}ca'
HTML += b'se"input":case"input2":{let i=e.t==="input2",s=g("");s.style'
HTML += b'.verticalAlign="text-bottom";let a=e.d,o=this.getCurrentInst'
HTML += b'ance()[a];if(this.expected[a]=o.v,this.types[a]=o.t,!i)switc'
HTML += b'h(o.t){case"set":s.append(y("\\\\{"),g(" "));break;case"vector'
HTML += b'":s.append(y("["),g(" "));break}if(o.t==="string")new A(s,th'
HTML += b'is,a,this.expected[a]);else if(o.t==="vector"||o.t==="set"){'
HTML += b'let l=o.v.split(","),n=l.length;for(let h=0;h<n;h++){h>0&&s.'
HTML += b'appendChild(g(" , "));let p=a+"-"+h;new E(s,this,p,l[h].leng'
HTML += b'th,l[h],!1)}}else if(o.t==="matrix"){let l=x();s.appendChild'
HTML += b'(l),new V(l,this,a,o.v)}else if(o.t==="complex"){let l=o.v.s'
HTML += b'plit(",");new E(s,this,a+"-0",l[0].length,l[0],!1),s.append('
HTML += b'g(" "),y("+"),g(" ")),new E(s,this,a+"-1",l[1].length,l[1],!'
HTML += b'1),s.append(g(" "),y("i"))}else{let l=o.t==="int";new E(s,th'
HTML += b'is,a,o.v.length,o.v,l)}if(!i)switch(o.t){case"set":s.append('
HTML += b'g(" "),y("\\\\}"));break;case"vector":s.append(g(" "),y("]"));'
HTML += b'break}return s}case"itemize":return z(e.c.map(i=>U(this.gene'
HTML += b'rateText(i))));case"single-choice":case"multi-choice":{let i'
HTML += b'=e.t=="multi-choice",s=document.createElement("table"),a=e.c'
HTML += b'.length,o=this.debug==!1,l=P(a,o),n=i?G:$,h=i?Y:J,p=[],u=[];'
HTML += b'for(let c=0;c<a;c++){let m=l[c],k=e.c[m],v="mc-"+this.choice'
HTML += b'Idx+"-"+m;u.push(v);let S=k.c[0].t=="bool"?k.c[0].d:this.get'
HTML += b'CurrentInstance()[k.c[0].d].v;this.expected[v]=S,this.types['
HTML += b'v]="bool",this.student[v]=this.showSolution?S:"false";let T='
HTML += b'this.generateText(k.c[1],!0),M=document.createElement("tr");'
HTML += b's.appendChild(M),M.style.cursor="pointer";let D=document.cre'
HTML += b'ateElement("td");p.push(D),M.appendChild(D),D.innerHTML=this'
HTML += b'.student[v]=="true"?n:h;let b=document.createElement("td");M'
HTML += b'.appendChild(b),b.appendChild(T),i?M.addEventListener("click'
HTML += b'",()=>{this.editedQuestion(),this.student[v]=this.student[v]'
HTML += b'==="true"?"false":"true",this.student[v]==="true"?D.innerHTM'
HTML += b'L=n:D.innerHTML=h}):M.addEventListener("click",()=>{this.edi'
HTML += b'tedQuestion();for(let L of u)this.student[L]="false";this.st'
HTML += b'udent[v]="true";for(let L=0;L<u.length;L++){let Q=l[L];p[Q].'
HTML += b'innerHTML=this.student[u[Q]]=="true"?n:h}})}return this.choi'
HTML += b'ceIdx++,s}case"image":{let i=x(),a=e.d.split("."),o=a[a.leng'
HTML += b'th-1],l=e.c[0].d,n=e.c[1].d,h=document.createElement("img");'
HTML += b'i.appendChild(h),h.classList.add("img"),h.style.width=l+"%";'
HTML += b'let p={svg:"svg+xml",png:"png",jpg:"jpeg"};return h.src="dat'
HTML += b'a:image/"+p[o]+";base64,"+n,i}default:{let i=g("UNIMPLEMENTE'
HTML += b'D("+e.t+")");return i.style.color="red",i}}}};function ce(r,'
HTML += b'e){["en","de","es","it","fr"].includes(r.lang)==!1&&(r.lang='
HTML += b'"en"),e&&(document.getElementById("debug").style.display="bl'
HTML += b'ock"),document.getElementById("date").innerHTML=r.date,docum'
HTML += b'ent.getElementById("title").innerHTML=r.title,document.getEl'
HTML += b'ementById("author").innerHTML=r.author,document.getElementBy'
HTML += b'Id("courseInfo1").innerHTML=O[r.lang];let t=\'<span onclick="'
HTML += b'location.reload()" style="text-decoration: underline; font-w'
HTML += b'eight: bold; cursor: pointer">\'+K[r.lang]+"</span>";document'
HTML += b'.getElementById("courseInfo2").innerHTML=F[r.lang].replace("'
HTML += b'*",t);let i=[],s=document.getElementById("questions"),a=1;fo'
HTML += b'r(let o of r.questions){o.title=""+a+". "+o.title;let l=x();'
HTML += b's.appendChild(l);let n=new H(l,o,r.lang,e);n.showSolution=e,'
HTML += b'i.push(n),n.populateDom(),e&&o.error.length==0&&n.checkAndRe'
HTML += b'peatBtn.click(),a++}}return oe(pe);})();sell.init(quizSrc,de'
HTML += b'bug);</script></body> </html> '
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
