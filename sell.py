#!/usr/bin/env python3

# pylint: disable=too-many-lines

"""
======= pySELL =================================================================

        A Python based Simple E-Learning Language
        for the simple creation of interactive courses

        https://pysell.org

LICENSE GPLv3

AUTHOR  Andreas Schwenk <mailto:contact@compiler-construction.com>

DOCS    Refer to https://github.com/andreas-schwenk/pysell and read the
        descriptions at the end of the page

INSTALL Run 'pip install pysell', or use the stand-alone implementation sell.py

CMD     pysell [-J] [-S] PATH

        -J          is optional and generates a JSON output file for debugging
        -S          silent mode (no info prints)

EXAMPLE pysell examples/ex1.txt

        outputs files examples/ex1.html and examples/ex1_DEBUG.html

FAQ

    Q: Why is this file so large?
    A: The goal is to offer pySELL as a single file for easy sharing.

    Q: Why not package and publish pySELL as a module?
    A: That's already available! Simply run "pip install pysell"
       to install it as a package.
"""


import base64
import datetime
import io
import json
import os
import re
import sys
from typing import Self


class SellError(Exception):
    """exception"""


# pylint: disable-next=too-few-public-methods
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
# (the next line disables a warning, about camel-case function names)
# pylint: disable-next=invalid-name
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

    # pylint: disable-next=too-many-branches,too-many-statements
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
                    # TODO: check, if variable exists and is of type bool
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
            raise SellError("unimplemented")

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

    # pylint: disable-next=too-many-return-statements
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
        while lex.token not in ("", "$"):
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


# pylint: disable-next=too-many-instance-attributes
class Question:
    """Question of the quiz"""

    def __init__(self, input_dirname: str, src_line_no: int) -> None:
        self.input_dirname: str = input_dirname
        self.src_line_no: int = src_line_no
        self.title: str = ""
        self.points: int = 1
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
        var_occurrences: set[str] = set()
        self.post_process_text(self.text, False, var_occurrences)
        self.text.optimize()

    # pylint: disable-next=too-many-branches
    def post_process_text(
        self, node: TextNode, math, var_occurrences: set[str]
    ) -> None:
        """post processes the textual part. For example, a semantical check
        for the existing of referenced variables is applied. Also images
        are loaded and stringified."""
        for c in node.children:
            self.post_process_text(
                c,
                math or node.type == "math" or node.type == "display-math",
                var_occurrences,
            )
        if node.type == "input":
            if node.data.startswith('"'):
                # gap question
                node.type = "gap"
                node.data = node.data.replace('"', "")
            elif node.data in self.variables:
                var_id = node.data
                if var_id in var_occurrences:
                    self.error += "It is not allowed to refer to a variable "
                    self.error += "twice or more. Hint: Create a copy of "
                    self.error += f"variable '{var_id}' in Python and ask for "
                    self.error += "the new variable name. "
                    self.error += f"Example code: '{var_id}2 = {var_id}'."
                    self.error += f"Then ask for '%{var_id}2'."
                else:
                    var_occurrences.add(var_id)
            elif node.data not in self.variables:
                # ask for numerical/term variable
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
            elif os.path.isfile(path) is False:
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

    # pylint: disable-next=too-many-locals,too-many-branches,too-many-statements
    def run_python_code(self) -> dict:
        """Runs the questions python code and gathers all local variables."""
        local_variables = {}
        res = {}
        src = self.python_src
        try:
            # pylint: disable-next=exec-used
            exec(src, globals(), local_variables)
        # pylint: disable-next=broad-exception-caught
        except Exception as e:
            # print(e)
            self.error += str(e) + ". "
            return res
        for local_id, value in local_variables.items():
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
                v = v.replace("**", "^")
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

        if "matplotlib" in self.python_src and "plt" in local_variables:
            plt = local_variables["plt"]
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
            "points": self.points,
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

    # pylint: disable-next=too-many-branches,too-many-statements
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
    lang = "en"  # language
    quiz_titel = ""
    author = ""
    topic = ""  # TODO: not yet processed!
    info = ""
    timer = -1  # time limit for the worksheet (default: off)
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
            quiz_titel = line[5:].strip()
        elif line.startswith("AUTHOR"):
            author = line[6:].strip()
        elif line.startswith("TOPIC"):
            topic = line[5:].strip()
        elif line.startswith("INFO"):
            info = line[4:].strip()
        elif line.startswith("TIMER"):
            timer = int(line[5:].strip())  # TODO: handle parse integer errors
        elif line.startswith("QUESTION"):
            question = Question(input_dirname, line_no + 1)
            questions.append(question)
            # extract title and points
            #   pattern = TITLE [ "(" INT "pts)" ];
            pattern = r"(?P<title>.+?)(?:\s\((?P<num>\d+)\spts\))?$"
            match = re.match(pattern, line[8:].strip())
            title = ""
            num = None
            if match:
                title = match.group("title").strip()
                num = match.group("num")  # This will be None if not present
                # print(f"Title: {title}, Points: {num}")
            question.title = title
            question.points = 1 if num is None else int(num)
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
        "title": quiz_titel,
        "author": author,
        "date": datetime.datetime.today().strftime("%Y-%m-%d"),
        "info": info,
        "timer": timer,
        "questions": list(map(lambda o: o.to_dict(), questions)),
    }


# the following code is automatically generated and updated by file "build.py"
# @begin(html)
HTML: str = b""
HTML += b'<!DOCTYPE html> <html> <head> <meta charset="UTF-8" /> <titl'
HTML += b'e>pySELL Quiz</title> <meta name="viewport" content="width=d'
HTML += b'evice-width, initial-scale=1.0" /> <link rel="icon" type="im'
HTML += b'age/x-icon" href="data:image/x-icon;base64,AAABAAEAEBAAAAEAI'
HTML += b"ABoBAAAFgAAACgAAAAQAAAAIAAAAAEAIAAAAAAAAAQAAAAAAAAAAAAAAAAAA"
HTML += b"AAAAACqqqr/PDw8/0VFRf/V1dX////////////09Pb/trbO/3t7q/9wcLH/c"
HTML += b"XG0/3NzqP+iosH/5OTr////////////j4+P/wAAAP8KCgr/x8fH///////k5"
HTML += b"Or/bGym/y4ukP8kJJD/IiKR/yIikv8jI5H/KCiP/1BQnP/Jydz//////5CQk"
HTML += b"P8BAQH/DAwM/8jIyP/7+/v/cHCo/yIij/8lJZP/KSmR/z4+lf9AQJH/Li6Q/"
HTML += b"yUlkv8jI5H/TEya/9/f6P+QkJD/AQEB/wwMDP/Ly8r/ycna/y4ujv8lJZP/N"
HTML += b"DSU/5+fw//j4+v/5+fs/76+0v9LS5f/JSWS/yYmkP+Skrr/kJCQ/wAAAP8MD"
HTML += b"Az/zc3L/5aWvP8iIo//ISGQ/39/sf////7/////////////////n5+7/yMjj"
HTML += b"P8kJJH/bm6p/5CQkP8BAQH/CgoK/6SkpP+Skp//XV2N/1dXi//Hx9X//////"
HTML += b"///////////9fX1/39/rP8kJI7/JCSR/25upP+QkJD/AQEB/wEBAf8ODg7/F"
HTML += b"BQT/xUVE/8hIR//XV1c/8vL0P/IyNv/lZW7/1panP8rK5D/JiaT/ycnjv+bm"
HTML += b"7v/kJCQ/wEBAf8AAAD/AAAA/wAAAP8AAAD/AAAH/wAAK/8aGmv/LCyO/yQkj"
HTML += b"/8jI5L/JSWT/yIikP9dXZ//6enu/5CQkP8BAQH/BQUF/0xMTP9lZWT/Pz9N/"
HTML += b"wUFVP8AAGz/AABu/xYWhf8jI5L/JCSP/zY2k/92dq7/4ODo//////+QkJD/A"
HTML += b"QEB/wwMDP/IyMj//Pz9/2lppf8ZGYf/AgJw/wAAZ/8cHHL/Zmak/5ubv//X1"
HTML += b"+T//v7+////////////kJCQ/wEBAf8MDAz/ycnJ/9/f6f85OZT/IyOR/wcHZ"
HTML += b"P8AAB7/UVFZ//n5+P//////0dHd/7i4yf++vs7/7e3z/5CQkP8AAAD/DAwM/"
HTML += b"87Ozf/Y2OP/MjKQ/x8fjv8EBEr/AAAA/1xcWv//////6ent/0tLlf8kJIn/M"
HTML += b"jKL/8fH2v+QkJD/AQEB/wcHB/98fHv/jo6T/yUlc/8JCXj/AABi/wAAK/9eX"
HTML += b"nj/trbS/2xspv8nJ5H/IyOT/0pKm//m5uz/kJCQ/wEBAf8AAAD/AAAA/wAAA"
HTML += b"P8AACH/AABk/wAAbf8EBHD/IyOM/ykpkv8jI5H/IyOS/ysrjP+kpMP//////"
HTML += b"5GRkf8CAgL/AQEB/wEBAf8BAQH/AgIE/woKK/8ZGWj/IyOG/ycnj/8nJ4//M"
HTML += b"DCS/0xMmf+lpcP/+vr6///////Pz8//kZGR/5CQkP+QkJD/kJCQ/5OTk/+ws"
HTML += b"K//zs7V/8LC2f+goL3/oaG+/8PD2P/n5+z/////////////////AAAAAAAAA"
HTML += b"AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
HTML += b'AAAAAAAAAAAAAAAAA==" sizes="16x16" /> <link rel="stylesheet"'
HTML += b' href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.'
HTML += b'min.css" integrity="sha384-n8MVd4RsNIU0tAv4ct0nTaAbDJwPJzDEa'
HTML += b'qSD1odI+WdtXRGWt2kTvGFasHpSy3SV" crossorigin="anonymous" /> '
HTML += b'<script src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/'
HTML += b'katex.min.js" integrity="sha384-XjKyOOlGwcjNTAIQHIpgOno0Hl1Y'
HTML += b'QqzUOEleOLALmuqehneUG+vnGctmUb0ZY0l8" crossorigin="anonymous'
HTML += b'" ></script> <style> :root { --pysell-black: #000000; --pyse'
HTML += b"ll-white: #ffffff; --pysell-grey: #5a5a5a; --pysell-green: r"
HTML += b"gb(24, 82, 1); --pysell-red: rgb(123, 0, 0); } html, body { "
HTML += b"font-family: Arial, Helvetica, sans-serif; margin: 0; paddin"
HTML += b"g: 0; background-color: white; } /* TODO: .pysell-ul as div "
HTML += b"element */ ul { user-select: none; margin-top: 0; margin-lef"
HTML += b"t: 0px; padding-left: 20px; } a { color: black; text-decorat"
HTML += b"ion: underline; } h1 { text-align: center; font-size: 28pt; "
HTML += b"word-wrap: break-word; margin-bottom: 10px; user-select: non"
HTML += b"e; }  .contents { max-width: 800px; margin-left: auto; margi"
HTML += b"n-right: auto; padding: 0; } .footer { position: relative; b"
HTML += b"ottom: 0; font-size: small; text-align: center; line-height:"
HTML += b" 1.8; color: var(--pysell-grey); margin: 0; padding: 10px 10"
HTML += b"px; user-select: none; }  .pysell-img { width: 100%; display"
HTML += b": block; margin-left: auto; margin-right: auto; user-select:"
HTML += b" none; } .pysell-author { text-align: center; font-size: 16p"
HTML += b"t; margin-bottom: 24px; user-select: none; } .pysell-course-"
HTML += b"info { text-align: center; user-select: none; } .pysell-ques"
HTML += b"tion { position: relative; /* required for feedback overlays"
HTML += b" */ color: black; background-color: white; border-top-style:"
HTML += b" solid; border-bottom-style: solid; border-width: 3px; borde"
HTML += b"r-color: black; padding: 4px; box-sizing: border-box; margin"
HTML += b"-top: 32px; margin-bottom: 32px; -webkit-box-shadow: 0px 0px"
HTML += b" 6px 3px #e8e8e8; box-shadow: 0px 0px 6px 3px #e8e8e8; overf"
HTML += b"low-x: auto; overflow-y: visible; } .pysell-button-group { d"
HTML += b"isplay: flex; align-items: center; justify-content: center; "
HTML += b"text-align: center; margin-left: auto; margin-right: auto; }"
HTML += b" @media (min-width: 800px) { .pysell-question { border-radiu"
HTML += b"s: 6px; padding: 16px; margin: 16px; border-left-style: soli"
HTML += b"d; border-right-style: solid; } } .pysell-question-feedback "
HTML += b"{ opacity: 1.8; z-index: 10; display: none; position: absolu"
HTML += b"te; pointer-events: none; left: 0%; top: 0%; width: 100%; he"
HTML += b"ight: 100%; text-align: center; font-size: 4vw; text-shadow:"
HTML += b" 0px 0px 18px rgba(0, 0, 0, 0.15); background-color: rgba(25"
HTML += b"5, 255, 255, 0.95); padding: 10px; justify-content: center; "
HTML += b"align-items: center; } .pysell-question-title { user-select:"
HTML += b' none; font-size: 24pt; } .pysell-code { font-family: "Couri'
HTML += b'er New", Courier, monospace; color: black; background-color:'
HTML += b" rgb(235, 235, 235); padding: 2px 5px; border-radius: 5px; m"
HTML += b'argin: 1px 2px; } .pysell-debug-code { font-family: "Courier'
HTML += b' New", Courier, monospace; padding: 4px; margin-bottom: 5px;'
HTML += b" background-color: black; color: white; border-radius: 5px; "
HTML += b"opacity: 0.85; overflow-x: scroll; } .pysell-debug-info { te"
HTML += b"xt-align: end; font-size: 10pt; margin-top: 2px; color: rgb("
HTML += b"64, 64, 64); } .pysell-input-field { position: relative; wid"
HTML += b"th: 32px; height: 24px; font-size: 14pt; border-style: solid"
HTML += b"; border-color: black; border-radius: 5px; border-width: 0.2"
HTML += b"; padding-left: 5px; padding-right: 5px; outline-color: blac"
HTML += b"k; background-color: transparent; margin: 1px; } .pysell-inp"
HTML += b"ut-field:focus { outline-color: maroon; } .pysell-equation-p"
HTML += b"review { position: absolute; top: 120%; left: 0%; padding-le"
HTML += b"ft: 8px; padding-right: 8px; padding-top: 4px; padding-botto"
HTML += b"m: 4px; background-color: rgb(128, 0, 0); border-radius: 5px"
HTML += b"; font-size: 12pt; color: white; text-align: start; z-index:"
HTML += b" 1000; opacity: 0.95; } .pysell-button { padding-left: 8px; "
HTML += b"padding-right: 8px; padding-top: 5px; padding-bottom: 5px; f"
HTML += b"ont-size: 12pt; background-color: rgb(0, 150, 0); color: whi"
HTML += b"te; border-style: none; border-radius: 4px; height: 36px; cu"
HTML += b"rsor: pointer; } .pysell-start-button { background-color: va"
HTML += b'r(--pysell-green); font-size: "x-large"; } .pysell-matrix-re'
HTML += b"size-button { width: 20px; background-color: black; color: #"
HTML += b"fff; text-align: center; border-radius: 3px; position: absol"
HTML += b"ute; z-index: 1; height: 20px; cursor: pointer; overflow: hi"
HTML += b"dden; font-size: 16px; } .pysell-timer { position: fixed; le"
HTML += b"ft: 0; top: 0; padding: 5px 15px; background-color: rgb(32, "
HTML += b"32, 32); color: white; opacity: 0.4; font-size: 32pt; z-inde"
HTML += b"x: 1000; border-bottom-right-radius: 10px; text-align: cente"
HTML += b'r; font-family: "Courier New", Courier, monospace; } .pysell'
HTML += b"-eval { text-align: center; background-color: black; color: "
HTML += b"white; padding: 10px; } @media (min-width: 800px) { .pysell-"
HTML += b"eval { border-radius: 10px; } } .pysell-timer-info { font-si"
HTML += b"ze: x-large; text-align: center; background-color: black; co"
HTML += b"lor: white; padding: 20px 10px; user-select: none; } @media "
HTML += b"(min-width: 800px) { .pysell-timer-info { border-radius: 6px"
HTML += b'; } } </style> </head> <body> <div id="timer"></div> <div id'
HTML += b'="header"></div> <br /> <div class="contents"> <div id="time'
HTML += b'r-info"></div> <div id="questions"></div> <div id="timer-foo'
HTML += b'ter"></div> <div id="timer-eval"></div> </div> <br /><br /><'
HTML += b'br /><br /> <div class="footer"> <div class="contents"> <spa'
HTML += b'n id="date"></span> &mdash; This quiz was developed using py'
HTML += b"SELL, a Python-based Simple E-Learning Language &mdash; <a h"
HTML += b'ref="https://pysell.org" style="color: var(--grey)" >https:/'
HTML += b'/pysell.org</a > <br /> <div style="width: 100%; display: fl'
HTML += b'ex; justify-content: center"> <img style="max-width: 48px; p'
HTML += b'adding: 16px 0px" src="data:image/svg+xml;base64,PD94bWwgdmV'
HTML += b"yc2lvbj0iMS4wIiBlbmNvZGluZz0iVVRGLTgiPz4KPCEtLSBDcmVhdGVkIHd"
HTML += b"pdGggSW5rc2NhcGUgKGh0dHA6Ly93d3cuaW5rc2NhcGUub3JnLykgLS0+Cjx"
HTML += b"zdmcgd2lkdGg9IjEwMG1tIiBoZWlnaHQ9IjEwMG1tIiB2ZXJzaW9uPSIxLjE"
HTML += b"iIHZpZXdCb3g9IjAgMCAxMDAgMTAwIiB4bWxucz0iaHR0cDovL3d3dy53My5"
HTML += b"vcmcvMjAwMC9zdmciIHhtbG5zOnhsaW5rPSJodHRwOi8vd3d3LnczLm9yZy8"
HTML += b"xOTk5L3hsaW5rIj4KIDxkZWZzPgogIDxsaW5lYXJHcmFkaWVudCBpZD0ibGl"
HTML += b"uZWFyR3JhZGllbnQzNjU4IiB4MT0iMjguNTI3IiB4Mj0iMTI4LjUzIiB5MT0"
HTML += b"iNzkuNjQ4IiB5Mj0iNzkuNjQ4IiBncmFkaWVudFRyYW5zZm9ybT0ibWF0cml"
HTML += b"4KDEuMDE2MSAwIDAgMS4wMTYxIC0yOS43OSAtMzAuOTI4KSIgZ3JhZGllbnR"
HTML += b"Vbml0cz0idXNlclNwYWNlT25Vc2UiPgogICA8c3RvcCBzdG9wLWNvbG9yPSI"
HTML += b"jNTkwMDVlIiBvZmZzZXQ9IjAiLz4KICAgPHN0b3Agc3RvcC1jb2xvcj0iI2F"
HTML += b"kMDA3ZiIgb2Zmc2V0PSIxIi8+CiAgPC9saW5lYXJHcmFkaWVudD4KIDwvZGV"
HTML += b"mcz4KIDxyZWN0IHdpZHRoPSIxMDAiIGhlaWdodD0iMTAwIiByeT0iMCIgZml"
HTML += b"sbD0idXJsKCNsaW5lYXJHcmFkaWVudDM2NTgpIi8+CiA8ZyBmaWxsPSIjZmZ"
HTML += b"mIj4KICA8ZyB0cmFuc2Zvcm09Im1hdHJpeCguNDA3NDMgMCAwIC40MDc0MyA"
HTML += b"tNDIuODQyIC0zNi4xMzYpIiBzdHJva2Utd2lkdGg9IjMuNzc5NSIgc3R5bGU"
HTML += b"9InNoYXBlLWluc2lkZTp1cmwoI3JlY3Q5NTItNyk7c2hhcGUtcGFkZGluZzo"
HTML += b"2LjUzMTQ0O3doaXRlLXNwYWNlOnByZSIgYXJpYS1sYWJlbD0iU0VMTCI+CiA"
HTML += b"gIDxwYXRoIGQ9Im0xNzEuMDEgMjM4LjM5cS0yLjExMi0yLjY4OC01LjU2OC0"
HTML += b"0LjIyNC0zLjM2LTEuNjMyLTYuNTI4LTEuNjMyLTEuNjMyIDAtMy4zNiAwLjI"
HTML += b"4OC0xLjYzMiAwLjI4OC0yLjk3NiAxLjE1Mi0xLjM0NCAwLjc2OC0yLjMwNCA"
HTML += b"yLjExMi0wLjg2NCAxLjI0OC0wLjg2NCAzLjI2NCAwIDEuNzI4IDAuNjcyIDI"
HTML += b"uODggMC43NjggMS4xNTIgMi4xMTIgMi4wMTYgMS40NCAwLjg2NCAzLjM2IDE"
HTML += b"uNjMyIDEuOTIgMC42NzIgNC4zMiAxLjQ0IDMuNDU2IDEuMTUyIDcuMiAyLjU"
HTML += b"5MiAzLjc0NCAxLjM0NCA2LjgxNiAzLjY0OHQ1LjA4OCA1Ljc2cTIuMDE2IDM"
HTML += b"uMzYgMi4wMTYgOC40NDggMCA1Ljg1Ni0yLjIwOCAxMC4xNzYtMi4xMTIgNC4"
HTML += b"yMjQtNS43NiA3LjAwOHQtOC4zNTIgNC4xMjgtOS42OTYgMS4zNDRxLTcuMjk"
HTML += b"2IDAtMTQuMTEyLTIuNDk2LTYuODE2LTIuNTkyLTExLjMyOC03LjI5NmwxMC4"
HTML += b"3NTItMTAuOTQ0cTIuNDk2IDMuMDcyIDYuNTI4IDUuMTg0IDQuMTI4IDIuMDE"
HTML += b"2IDguMTYgMi4wMTYgMS44MjQgMCAzLjU1Mi0wLjM4NHQyLjk3Ni0xLjI0OHE"
HTML += b"xLjM0NC0wLjg2NCAyLjExMi0yLjMwNHQwLjc2OC0zLjQ1NnEwLTEuOTItMC4"
HTML += b"5Ni0zLjI2NHQtMi43ODQtMi40cS0xLjcyOC0xLjE1Mi00LjQxNi0yLjAxNi0"
HTML += b"yLjU5Mi0wLjk2LTUuOTUyLTIuMDE2LTMuMjY0LTEuMDU2LTYuNDMyLTIuNDk"
HTML += b"2LTMuMDcyLTEuNDQtNS41NjgtMy42NDgtMi40LTIuMzA0LTMuOTM2LTUuNDc"
HTML += b"yLTEuNDQtMy4yNjQtMS40NC03Ljg3MiAwLTUuNjY0IDIuMzA0LTkuNjk2dDY"
HTML += b"uMDQ4LTYuNjI0IDguNDQ4LTMuNzQ0cTQuNzA0LTEuMjQ4IDkuNTA0LTEuMjQ"
HTML += b"4IDUuNzYgMCAxMS43MTIgMi4xMTIgNi4wNDggMi4xMTIgMTAuNTYgNi4yNHo"
HTML += b"iLz4KICAgPHBhdGggZD0ibTE5MS44NCAyODguN3YtNjcuOTY4aDUyLjE5bC0"
HTML += b"xLjI5ODggMTMuOTJoLTM1LjA1MXYxMi43NjhoMzMuNDE5bC0xLjI5ODggMTM"
HTML += b"uMTUyaC0zMi4xMnYxNC4xMTJoMzEuNTg0bC0xLjI5ODggMTQuMDE2eiIvPgo"
HTML += b"gIDwvZz4KICA8ZyB0cmFuc2Zvcm09Im1hdHJpeCguNDA3NDMgMCAwIC40MDc"
HTML += b"0MyAtNDAuMTY4IC03OC4wODIpIiBzdHJva2Utd2lkdGg9IjMuNzc5NSIgc3R"
HTML += b"5bGU9InNoYXBlLWluc2lkZTp1cmwoI3JlY3Q5NTItOS05KTtzaGFwZS1wYWR"
HTML += b"kaW5nOjYuNTMxNDQ7d2hpdGUtc3BhY2U6cHJlIiBhcmlhLWxhYmVsPSJweSI"
HTML += b"+CiAgIDxwYXRoIGQ9Im0xODcuNDMgMjY0LjZxMCA0Ljk5Mi0xLjUzNiA5LjZ"
HTML += b"0LTQuNTEyIDguMTZxLTIuODggMy40NTYtNy4xMDQgNS41Njh0LTkuNiAyLjE"
HTML += b"xMnEtNC40MTYgMC04LjM1Mi0xLjcyOC0zLjkzNi0xLjgyNC02LjE0NC00Ljg"
HTML += b"5NmgtMC4xOTJ2MjguMzJoLTE1Ljc0NHYtNzAuODQ4aDE0Ljk3NnY1Ljg1Nmg"
HTML += b"wLjI4OHEyLjIwOC0yLjg4IDYuMDQ4LTQuOTkyIDMuOTM2LTIuMjA4IDkuMjE"
HTML += b"2LTIuMjA4IDUuMTg0IDAgOS40MDggMi4wMTZ0Ny4xMDQgNS40NzJxMi45NzY"
HTML += b"gMy40NTYgNC41MTIgOC4wNjQgMS42MzIgNC41MTIgMS42MzIgOS41MDR6bS0"
HTML += b"xNS4yNjQgMHEwLTIuMzA0LTAuNzY4LTQuNTEyLTAuNjcyLTIuMjA4LTIuMTE"
HTML += b"yLTMuODQtMS4zNDQtMS43MjgtMy40NTYtMi43ODR0LTQuODk2LTEuMDU2cS0"
HTML += b"yLjY4OCAwLTQuOCAxLjA1NnQtMy42NDggMi43ODRxLTEuNDQgMS43MjgtMi4"
HTML += b"zMDQgMy45MzYtMC43NjggMi4yMDgtMC43NjggNC41MTJ0MC43NjggNC41MTJ"
HTML += b"xMC44NjQgMi4yMDggMi4zMDQgMy45MzYgMS41MzYgMS43MjggMy42NDggMi4"
HTML += b"3ODR0NC44IDEuMDU2cTIuNzg0IDAgNC44OTYtMS4wNTZ0My40NTYtMi43ODR"
HTML += b"xMS40NC0xLjcyOCAyLjExMi0zLjkzNiAwLjc2OC0yLjMwNCAwLjc2OC00LjY"
HTML += b"wOHoiLz4KICAgPHBhdGggZD0ibTIyNC4yOSAyOTUuOXEtMS40NCAzLjc0NC0"
HTML += b"zLjI2NCA2LjYyNC0xLjcyOCAyLjk3Ni00LjIyNCA0Ljk5Mi0yLjQgMi4xMTI"
HTML += b"tNS43NiAzLjE2OC0zLjI2NCAxLjA1Ni03Ljc3NiAxLjA1Ni0yLjIwOCAwLTQ"
HTML += b"uNjA4LTAuMjg4LTIuMzA0LTAuMjg4LTQuMDMyLTAuNzY4bDEuNzI4LTEzLjI"
HTML += b"0OHExLjE1MiAwLjM4NCAyLjQ5NiAwLjU3NiAxLjQ0IDAuMjg4IDIuNTkyIDA"
HTML += b"uMjg4IDMuNjQ4IDAgNS4yOC0xLjcyOCAxLjYzMi0xLjYzMiAyLjc4NC00Ljc"
HTML += b"wNGwxLjUzNi0zLjkzNi0xOS45NjgtNDcuMDRoMTcuNDcybDEwLjY1NiAzMC4"
HTML += b"3MmgwLjI4OGw5LjUwNC0zMC43MmgxNi43MDR6Ii8+CiAgPC9nPgogIDxwYXR"
HTML += b"oIGQ9Im02OC4wOTYgMTUuNzc1aDcuODAyOWwtOC45ODU0IDY5Ljc5MWgtNy4"
HTML += b"4MDN6IiBzdHJva2Utd2lkdGg9IjEuMTE3NiIvPgogIDxwYXRoIGQ9Im04My4"
HTML += b"4NTMgMTUuNzQ4aDcuODAzbC04Ljk4NTQgNjkuNzkxaC03LjgwM3oiIHN0cm9"
HTML += b'rZS13aWR0aD0iMS4xMTc2Ii8+CiA8L2c+Cjwvc3ZnPgo=" /> </div> <sp'
HTML += b'an id="data-policy"></span> </div> </div>  <script>let debug'
HTML += b" = false; let quizSrc = {};var pysell=(()=>{var H=Object.def"
HTML += b"ineProperty;var pe=Object.getOwnPropertyDescriptor;var de=Ob"
HTML += b"ject.getOwnPropertyNames;var ue=Object.prototype.hasOwnPrope"
HTML += b'rty;var f=(r,e)=>H(r,"name",{value:e,configurable:!0});var m'
HTML += b"e=(r,e)=>{for(var t in e)H(r,t,{get:e[t],enumerable:!0})},fe"
HTML += b'=(r,e,t,s)=>{if(e&&typeof e=="object"||typeof e=="function")'
HTML += b"for(let i of de(e))!ue.call(r,i)&&i!==t&&H(r,i,{get:()=>e[i]"
HTML += b",enumerable:!(s=pe(e,i))||s.enumerable});return r};var ge=r="
HTML += b'>fe(H({},"__esModule",{value:!0}),r);var ke={};me(ke,{init:('
HTML += b')=>be});var F={en:"This page operates entirely in your brows'
HTML += b'er and does not store any data on external servers.",de:"Die'
HTML += b"se Seite wird in Ihrem Browser ausgef\\xFChrt und speichert k"
HTML += b'eine Daten auf Servern.",es:"Esta p\\xE1gina se ejecuta en su'
HTML += b' navegador y no almacena ning\\xFAn dato en los servidores.",'
HTML += b'it:"Questa pagina viene eseguita nel browser e non memorizza'
HTML += b' alcun dato sui server.",fr:"Cette page fonctionne dans votr'
HTML += b"e navigateur et ne stocke aucune donn\\xE9e sur des serveurs."
HTML += b'"},O={en:"* this page to receive a new set of randomized tas'
HTML += b'ks.",de:"Sie k\\xF6nnen diese Seite *, um neue randomisierte '
HTML += b'Aufgaben zu erhalten.",es:"Puedes * esta p\\xE1gina para obte'
HTML += b'ner nuevas tareas aleatorias.",it:"\\xC8 possibile * questa p'
HTML += b'agina per ottenere nuovi compiti randomizzati",fr:"Vous pouv'
HTML += b"ez * cette page pour obtenir de nouvelles t\\xE2ches al\\xE9at"
HTML += b'oires"},K={en:"Refresh",de:"aktualisieren",es:"recargar",it:'
HTML += b'"ricaricare",fr:"recharger"},Z={en:["awesome","great","well '
HTML += b'done","nice","you got it","good"],de:["super","gut gemacht",'
HTML += b'"weiter so","richtig"],es:["impresionante","genial","correct'
HTML += b'o","bien hecho"],it:["fantastico","grande","corretto","ben f'
HTML += b'atto"],fr:["g\\xE9nial","super","correct","bien fait"]},X={en'
HTML += b':["please complete all fields"],de:["bitte alles ausf\\xFClle'
HTML += b'n"],es:["por favor, rellene todo"],it:["compilare tutto"],fr'
HTML += b':["remplis tout s\'il te plait"]},Y={en:["try again","still s'
HTML += b'ome mistakes","wrong answer","no"],de:["leider falsch","nich'
HTML += b't richtig","versuch\'s nochmal"],es:["int\\xE9ntalo de nuevo",'
HTML += b'"todav\\xEDa algunos errores","respuesta incorrecta"],it:["ri'
HTML += b'prova","ancora qualche errore","risposta sbagliata"],fr:["r\\'
HTML += b'xE9essayer","encore des erreurs","mauvaise r\\xE9ponse"]},G={'
HTML += b'en:"point(s)",de:"Punkt(e)",es:"punto(s)",it:"punto/i",fr:"p'
HTML += b'oint(s)"},J={en:"Evaluate now",de:"Jetzt auswerten",es:"Eval'
HTML += b'uar ahora",it:"Valuta ora",fr:"\\xC9valuer maintenant"},$={en'
HTML += b':"Data Policy: This website does not collect, store, or proc'
HTML += b"ess any personal data on external servers. All functionality"
HTML += b" is executed locally in your browser, ensuring complete priv"
HTML += b"acy. No cookies are used, and no data is transmitted to or f"
HTML += b"rom the server. Your activity on this site remains entirely "
HTML += b'private and local to your device.",de:"Datenschutzrichtlinie'
HTML += b": Diese Website sammelt, speichert oder verarbeitet keine pe"
HTML += b"rsonenbezogenen Daten auf externen Servern. Alle Funktionen "
HTML += b"werden lokal in Ihrem Browser ausgef\\xFChrt, um vollst\\xE4nd"
HTML += b"ige Privatsph\\xE4re zu gew\\xE4hrleisten. Es werden keine Coo"
HTML += b"kies verwendet, und es werden keine Daten an den Server gese"
HTML += b"ndet oder von diesem empfangen. Ihre Aktivit\\xE4t auf dieser"
HTML += b" Seite bleibt vollst\\xE4ndig privat und lokal auf Ihrem Ger\\"
HTML += b'xE4t.",es:"Pol\\xEDtica de datos: Este sitio web no recopila,'
HTML += b" almacena ni procesa ning\\xFAn dato personal en servidores e"
HTML += b"xternos. Toda la funcionalidad se ejecuta localmente en su n"
HTML += b"avegador, garantizando una privacidad completa. No se utiliz"
HTML += b"an cookies y no se transmiten datos hacia o desde el servido"
HTML += b"r. Su actividad en este sitio permanece completamente privad"
HTML += b'a y local en su dispositivo.",it:"Politica sui dati: Questo '
HTML += b"sito web non raccoglie, memorizza o elabora alcun dato perso"
HTML += b"nale su server esterni. Tutte le funzionalit\\xE0 vengono ese"
HTML += b"guite localmente nel tuo browser, garantendo una privacy com"
HTML += b"pleta. Non vengono utilizzati cookie e nessun dato viene tra"
HTML += b"smesso da o verso il server. La tua attivit\\xE0 su questo si"
HTML += b"to rimane completamente privata e locale sul tuo dispositivo"
HTML += b'.",fr:"Politique de confidentialit\\xE9: Ce site web ne colle'
HTML += b"cte, ne stocke ni ne traite aucune donn\\xE9e personnelle sur"
HTML += b" des serveurs externes. Toutes les fonctionnalit\\xE9s sont e"
HTML += b"x\\xE9cut\\xE9es localement dans votre navigateur, garantissan"
HTML += b"t une confidentialit\\xE9 totale. Aucun cookie n\\u2019est uti"
HTML += b"lis\\xE9 et aucune donn\\xE9e n\\u2019est transmise vers ou dep"
HTML += b"uis le serveur. Votre activit\\xE9 sur ce site reste enti\\xE8"
HTML += b'rement priv\\xE9e et locale sur votre appareil."},ee={en:"You'
HTML += b" have a limited time to complete this quiz. The countdown, d"
HTML += b"isplayed in minutes, is visible at the top-left of the scree"
HTML += b"n. When you're ready to begin, simply press the Start button"
HTML += b'.",de:"Die Zeit f\\xFCr dieses Quiz ist begrenzt. Der Countdo'
HTML += b"wn, in Minuten angezeigt, l\\xE4uft oben links auf dem Bildsc"
HTML += b'hirm. Mit dem Start-Button beginnt das Quiz.",es:"Tienes un '
HTML += b"tiempo limitado para completar este cuestionario. La cuenta "
HTML += b"regresiva, mostrada en minutos, se encuentra en la parte sup"
HTML += b"erior izquierda de la pantalla. Cuando est\\xE9s listo, simpl"
HTML += b'emente presiona el bot\\xF3n de inicio.",it:"Hai un tempo lim'
HTML += b"itato per completare questo quiz. Il conto alla rovescia, vi"
HTML += b"sualizzato in minuti, \\xE8 visibile in alto a sinistra dello"
HTML += b" schermo. Quando sei pronto, premi semplicemente il pulsante"
HTML += b' Start.",fr:"Vous disposez d\\u2019un temps limit\\xE9 pour co'
HTML += b"mpl\\xE9ter ce quiz. Le compte \\xE0 rebours, affich\\xE9 en mi"
HTML += b"nutes, est visible en haut \\xE0 gauche de l\\u2019\\xE9cran. L"
HTML += b"orsque vous \\xEAtes pr\\xEAt, appuyez simplement sur le bouto"
HTML += b'n D\\xE9marrer."};function x(r=[]){let e=document.createEleme'
HTML += b'nt("div");return e.append(...r),e}f(x,"genDiv");function te('
HTML += b'r=[]){let e=document.createElement("ul");return e.append(...'
HTML += b'r),e}f(te,"genUl");function ie(r){let e=document.createEleme'
HTML += b'nt("li");return e.appendChild(r),e}f(ie,"genLi");function W('
HTML += b'r){let e=document.createElement("input");return e.spellcheck'
HTML += b'=!1,e.type="text",e.classList.add("pysell-input-field"),e.st'
HTML += b'yle.width=r+"px",e}f(W,"genInputField");function se(){let r='
HTML += b'document.createElement("button");return r.type="button",r.cl'
HTML += b'assList.add("pysell-button"),r}f(se,"genButton");function k('
HTML += b'r,e=[]){let t=document.createElement("span");return e.length'
HTML += b'>0?t.append(...e):t.innerHTML=r,t}f(k,"genSpan");function N('
HTML += b"r,e,t=!1){katex.render(e,r,{throwOnError:!1,displayMode:t,ma"
HTML += b'cros:{"\\\\RR":"\\\\mathbb{R}","\\\\NN":"\\\\mathbb{N}","\\\\QQ":"\\\\ma'
HTML += b'thbb{Q}","\\\\ZZ":"\\\\mathbb{Z}","\\\\CC":"\\\\mathbb{C}"}})}f(N,"u'
HTML += b'pdateMathElement");function T(r,e=!1){let t=document.createE'
HTML += b'lement("span");return N(t,r,e),t}f(T,"genMathSpan");function'
HTML += b" ne(r,e){let t=Array(e.length+1).fill(null).map(()=>Array(r."
HTML += b"length+1).fill(null));for(let s=0;s<=r.length;s+=1)t[0][s]=s"
HTML += b";for(let s=0;s<=e.length;s+=1)t[s][0]=s;for(let s=1;s<=e.len"
HTML += b"gth;s+=1)for(let i=1;i<=r.length;i+=1){let o=r[i-1]===e[s-1]"
HTML += b"?0:1;t[s][i]=Math.min(t[s][i-1]+1,t[s-1][i]+1,t[s-1][i-1]+o)"
HTML += b'}return t[e.length][r.length]}f(ne,"levenshteinDistance");va'
HTML += b'r re=\'<svg xmlns="http://www.w3.org/2000/svg" height="28" vi'
HTML += b'ewBox="0 0 448 512"><path fill="black" d="M384 80c8.8 0 16 7'
HTML += b".2 16 16V416c0 8.8-7.2 16-16 16H64c-8.8 0-16-7.2-16-16V96c0-"
HTML += b"8.8 7.2-16 16-16H384zM64 32C28.7 32 0 60.7 0 96V416c0 35.3 2"
HTML += b"8.7 64 64 64H384c35.3 0 64-28.7 64-64V96c0-35.3-28.7-64-64-6"
HTML += b'4H64z"/></svg>\',ae=\'<svg xmlns="http://www.w3.org/2000/svg" '
HTML += b'height="28" viewBox="0 0 448 512"><path fill="black" d="M64 '
HTML += b"80c-8.8 0-16 7.2-16 16V416c0 8.8 7.2 16 16 16H384c8.8 0 16-7"
HTML += b".2 16-16V96c0-8.8-7.2-16-16-16H64zM0 96C0 60.7 28.7 32 64 32"
HTML += b"H384c35.3 0 64 28.7 64 64V416c0 35.3-28.7 64-64 64H64c-35.3 "
HTML += b"0-64-28.7-64-64V96zM337 209L209 337c-9.4 9.4-24.6 9.4-33.9 0"
HTML += b"l-64-64c-9.4-9.4-9.4-24.6 0-33.9s24.6-9.4 33.9 0l47 47L303 1"
HTML += b"75c9.4-9.4 24.6-9.4 33.9 0s9.4 24.6 0 33.9z\"/>',le='<svg xml"
HTML += b'ns="http://www.w3.org/2000/svg" height="28" viewBox="0 0 512'
HTML += b' 512"><path fill="black" d="M464 256A208 208 0 1 0 48 256a20'
HTML += b"8 208 0 1 0 416 0zM0 256a256 256 0 1 1 512 0A256 256 0 1 1 0"
HTML += b' 256z"/></svg>\',oe=\'<svg xmlns="http://www.w3.org/2000/svg" '
HTML += b'height="28" viewBox="0 0 512 512"><path fill="black" d="M256'
HTML += b" 48a208 208 0 1 1 0 416 208 208 0 1 1 0-416zm0 464A256 256 0"
HTML += b" 1 0 256 0a256 256 0 1 0 0 512zM369 209c9.4-9.4 9.4-24.6 0-3"
HTML += b"3.9s-24.6-9.4-33.9 0l-111 111-47-47c-9.4-9.4-24.6-9.4-33.9 0"
HTML += b's-9.4 24.6 0 33.9l64 64c9.4 9.4 24.6 9.4 33.9 0L369 209z"/><'
HTML += b'/svg>\',D=\'<svg xmlns="http://www.w3.org/2000/svg" width="50"'
HTML += b' height="25" viewBox="0 0 384 512" fill="white"><path d="M73'
HTML += b" 39c-14.8-9.1-33.4-9.4-48.5-.9S0 62.6 0 80V432c0 17.4 9.4 33"
HTML += b".4 24.5 41.9s33.7 8.1 48.5-.9L361 297c14.3-8.7 23-24.2 23-41"
HTML += b"s-8.7-32.2-23-41L73 39z\"/></svg>',Q='<svg xmlns=\"http://www."
HTML += b'w3.org/2000/svg" width="50" height="25" viewBox="0 0 512 512'
HTML += b'" fill="white"><path d="M0 224c0 17.7 14.3 32 32 32s32-14.3 '
HTML += b"32-32c0-53 43-96 96-96H320v32c0 12.9 7.8 24.6 19.8 29.6s25.7"
HTML += b" 2.2 34.9-6.9l64-64c12.5-12.5 12.5-32.8 0-45.3l-64-64c-9.2-9"
HTML += b".2-22.9-11.9-34.9-6.9S320 19.1 320 32V64H160C71.6 64 0 135.6"
HTML += b" 0 224zm512 64c0-17.7-14.3-32-32-32s-32 14.3-32 32c0 53-43 9"
HTML += b"6-96 96H192V352c0-12.9-7.8-24.6-19.8-29.6s-25.7-2.2-34.9 6.9"
HTML += b"l-64 64c-12.5 12.5-12.5 32.8 0 45.3l64 64c9.2 9.2 22.9 11.9 "
HTML += b"34.9 6.9s19.8-16.6 19.8-29.6V448H352c88.4 0 160-71.6 160-160"
HTML += b"z\"/></svg>';function P(r,e=!1){let t=new Array(r);for(let s="
HTML += b"0;s<r;s++)t[s]=s;if(e)for(let s=0;s<r;s++){let i=Math.floor("
HTML += b"Math.random()*r),o=Math.floor(Math.random()*r),l=t[i];t[i]=t"
HTML += b'[o],t[o]=l}return t}f(P,"range");function _(r,e,t=-1){if(t<0'
HTML += b"&&(t=r.length),t==1){e.push([...r]);return}for(let s=0;s<t;s"
HTML += b"++){_(r,e,t-1);let i=t%2==0?s:0,o=r[i];r[i]=r[t-1],r[t-1]=o}"
HTML += b'}f(_,"heapsAlgorithm");var L=class r{static{f(this,"Matrix")'
HTML += b"}constructor(e,t){this.m=e,this.n=t,this.v=new Array(e*t).fi"
HTML += b'll("0")}getElement(e,t){return e<0||e>=this.m||t<0||t>=this.'
HTML += b'n?"":this.v[e*this.n+t]}resize(e,t,s){if(e<1||e>50||t<1||t>5'
HTML += b"0)return!1;let i=new r(e,t);i.v.fill(s);for(let o=0;o<i.m;o+"
HTML += b"+)for(let l=0;l<i.n;l++)i.v[o*i.n+l]=this.getElement(o,l);re"
HTML += b"turn this.fromMatrix(i),!0}fromMatrix(e){this.m=e.m,this.n=e"
HTML += b'.n,this.v=[...e.v]}fromString(e){this.m=e.split("],").length'
HTML += b',this.v=e.replaceAll("[","").replaceAll("]","").split(",").m'
HTML += b"ap(t=>t.trim()),this.n=this.v.length/this.m}getMaxCellStrlen"
HTML += b"(){let e=0;for(let t of this.v)t.length>e&&(e=t.length);retu"
HTML += b'rn e}toTeXString(e=!1,t=!0){let s="";t?s+=e?"\\\\left[\\\\begin{'
HTML += b'array}":"\\\\begin{bmatrix}":s+=e?"\\\\left(\\\\begin{array}":"\\\\b'
HTML += b'egin{pmatrix}",e&&(s+="{"+"c".repeat(this.n-1)+"|c}");for(le'
HTML += b't i=0;i<this.m;i++){for(let o=0;o<this.n;o++){o>0&&(s+="&");'
HTML += b"let l=this.getElement(i,o);try{l=b.parse(l).toTexString()}ca"
HTML += b'tch{}s+=l}s+="\\\\\\\\"}return t?s+=e?"\\\\end{array}\\\\right]":"\\\\'
HTML += b'end{bmatrix}":s+=e?"\\\\end{array}\\\\right)":"\\\\end{pmatrix}",s'
HTML += b'}},b=class r{static{f(this,"Term")}constructor(){this.root=n'
HTML += b'ull,this.src="",this.token="",this.skippedWhiteSpace=!1,this'
HTML += b".pos=0}clone(){let e=new r;return e.root=this.root.clone(),e"
HTML += b'}getVars(e,t="",s=null){if(s==null&&(s=this.root),s.op.start'
HTML += b'sWith("var:")){let i=s.op.substring(4);(t.length==0||t.lengt'
HTML += b"h>0&&i.startsWith(t))&&e.add(i)}for(let i of s.c)this.getVar"
HTML += b"s(e,t,i)}setVars(e,t=null){t==null&&(t=this.root);for(let s "
HTML += b'of t.c)this.setVars(e,s);if(t.op.startsWith("var:")){let s=t'
HTML += b".op.substring(4);if(s in e){let i=e[s].clone();t.op=i.op,t.c"
HTML += b"=i.c,t.re=i.re,t.im=i.im}}}renameVar(e,t,s=null){s==null&&(s"
HTML += b"=this.root);for(let i of s.c)this.renameVar(e,t,i);s.op.star"
HTML += b'tsWith("var:")&&s.op.substring(4)===e&&(s.op="var:"+t)}eval('
HTML += b"e,t=null){let i=a.const(),o=0,l=0,h=null;switch(t==null&&(t="
HTML += b'this.root),t.op){case"const":i=t;break;case"+":case"-":case"'
HTML += b'*":case"/":case"^":{let n=this.eval(e,t.c[0]),c=this.eval(e,'
HTML += b't.c[1]);switch(t.op){case"+":i.re=n.re+c.re,i.im=n.im+c.im;b'
HTML += b'reak;case"-":i.re=n.re-c.re,i.im=n.im-c.im;break;case"*":i.r'
HTML += b'e=n.re*c.re-n.im*c.im,i.im=n.re*c.im+n.im*c.re;break;case"/"'
HTML += b":o=c.re*c.re+c.im*c.im,i.re=(n.re*c.re+n.im*c.im)/o,i.im=(n."
HTML += b'im*c.re-n.re*c.im)/o;break;case"^":h=new a("exp",[new a("*",'
HTML += b'[c,new a("ln",[n])])]),i=this.eval(e,h);break}break}case".-"'
HTML += b':case"abs":case"acos":case"acosh":case"asin":case"asinh":cas'
HTML += b'e"atan":case"atanh":case"ceil":case"cos":case"cosh":case"cot'
HTML += b'":case"exp":case"floor":case"ln":case"log":case"log10":case"'
HTML += b'log2":case"round":case"sin":case"sinc":case"sinh":case"sqrt"'
HTML += b':case"tan":case"tanh":{let n=this.eval(e,t.c[0]);switch(t.op'
HTML += b'){case".-":i.re=-n.re,i.im=-n.im;break;case"abs":i.re=Math.s'
HTML += b'qrt(n.re*n.re+n.im*n.im),i.im=0;break;case"acos":h=new a("*"'
HTML += b',[a.const(0,-1),new a("ln",[new a("+",[a.const(0,1),new a("s'
HTML += b'qrt",[new a("-",[a.const(1,0),new a("*",[n,n])])])])])]),i=t'
HTML += b'his.eval(e,h);break;case"acosh":h=new a("*",[n,new a("sqrt",'
HTML += b'[new a("-",[new a("*",[n,n]),a.const(1,0)])])]),i=this.eval('
HTML += b'e,h);break;case"asin":h=new a("*",[a.const(0,-1),new a("ln",'
HTML += b'[new a("+",[new a("*",[a.const(0,1),n]),new a("sqrt",[new a('
HTML += b'"-",[a.const(1,0),new a("*",[n,n])])])])])]),i=this.eval(e,h'
HTML += b');break;case"asinh":h=new a("*",[n,new a("sqrt",[new a("+",['
HTML += b'new a("*",[n,n]),a.const(1,0)])])]),i=this.eval(e,h);break;c'
HTML += b'ase"atan":h=new a("*",[a.const(0,.5),new a("ln",[new a("/",['
HTML += b'new a("-",[a.const(0,1),new a("*",[a.const(0,1),n])]),new a('
HTML += b'"+",[a.const(0,1),new a("*",[a.const(0,1),n])])])])]),i=this'
HTML += b'.eval(e,h);break;case"atanh":h=new a("*",[a.const(.5,0),new '
HTML += b'a("ln",[new a("/",[new a("+",[a.const(1,0),n]),new a("-",[a.'
HTML += b'const(1,0),n])])])]),i=this.eval(e,h);break;case"ceil":i.re='
HTML += b'Math.ceil(n.re),i.im=Math.ceil(n.im);break;case"cos":i.re=Ma'
HTML += b"th.cos(n.re)*Math.cosh(n.im),i.im=-Math.sin(n.re)*Math.sinh("
HTML += b'n.im);break;case"cosh":h=new a("*",[a.const(.5,0),new a("+",'
HTML += b'[new a("exp",[n]),new a("exp",[new a(".-",[n])])])]),i=this.'
HTML += b'eval(e,h);break;case"cot":o=Math.sin(n.re)*Math.sin(n.re)+Ma'
HTML += b"th.sinh(n.im)*Math.sinh(n.im),i.re=Math.sin(n.re)*Math.cos(n"
HTML += b'.re)/o,i.im=-(Math.sinh(n.im)*Math.cosh(n.im))/o;break;case"'
HTML += b'exp":i.re=Math.exp(n.re)*Math.cos(n.im),i.im=Math.exp(n.re)*'
HTML += b'Math.sin(n.im);break;case"floor":i.re=Math.floor(n.re),i.im='
HTML += b'Math.floor(n.im);break;case"ln":case"log":i.re=Math.log(Math'
HTML += b".sqrt(n.re*n.re+n.im*n.im)),o=Math.abs(n.im)<1e-9?0:n.im,i.i"
HTML += b'm=Math.atan2(o,n.re);break;case"log10":h=new a("/",[new a("l'
HTML += b'n",[n]),new a("ln",[a.const(10)])]),i=this.eval(e,h);break;c'
HTML += b'ase"log2":h=new a("/",[new a("ln",[n]),new a("ln",[a.const(2'
HTML += b')])]),i=this.eval(e,h);break;case"round":i.re=Math.round(n.r'
HTML += b'e),i.im=Math.round(n.im);break;case"sin":i.re=Math.sin(n.re)'
HTML += b"*Math.cosh(n.im),i.im=Math.cos(n.re)*Math.sinh(n.im);break;c"
HTML += b'ase"sinc":h=new a("/",[new a("sin",[n]),n]),i=this.eval(e,h)'
HTML += b';break;case"sinh":h=new a("*",[a.const(.5,0),new a("-",[new '
HTML += b'a("exp",[n]),new a("exp",[new a(".-",[n])])])]),i=this.eval('
HTML += b'e,h);break;case"sqrt":h=new a("^",[n,a.const(.5)]),i=this.ev'
HTML += b'al(e,h);break;case"tan":o=Math.cos(n.re)*Math.cos(n.re)+Math'
HTML += b".sinh(n.im)*Math.sinh(n.im),i.re=Math.sin(n.re)*Math.cos(n.r"
HTML += b'e)/o,i.im=Math.sinh(n.im)*Math.cosh(n.im)/o;break;case"tanh"'
HTML += b':h=new a("/",[new a("-",[new a("exp",[n]),new a("exp",[new a'
HTML += b'(".-",[n])])]),new a("+",[new a("exp",[n]),new a("exp",[new '
HTML += b'a(".-",[n])])])]),i=this.eval(e,h);break}break}default:if(t.'
HTML += b'op.startsWith("var:")){let n=t.op.substring(4);if(n==="pi")r'
HTML += b'eturn a.const(Math.PI);if(n==="e")return a.const(Math.E);if('
HTML += b'n==="i")return a.const(0,1);if(n==="true")return a.const(1);'
HTML += b'if(n==="false")return a.const(0);if(n in e)return e[n];throw'
HTML += b' new Error("eval-error: unknown variable \'"+n+"\'")}else thro'
HTML += b'w new Error("UNIMPLEMENTED eval \'"+t.op+"\'")}return i}static'
HTML += b' parse(e){let t=new r;if(t.src=e,t.token="",t.skippedWhiteSp'
HTML += b'ace=!1,t.pos=0,t.next(),t.root=t.parseExpr(!1),t.token!=="")'
HTML += b'throw new Error("remaining tokens: "+t.token+"...");return t'
HTML += b"}parseExpr(e){return this.parseAdd(e)}parseAdd(e){let t=this"
HTML += b'.parseMul(e);for(;["+","-"].includes(this.token)&&!(e&&this.'
HTML += b"skippedWhiteSpace);){let s=this.token;this.next(),t=new a(s,"
HTML += b"[t,this.parseMul(e)])}return t}parseMul(e){let t=this.parseP"
HTML += b'ow(e);for(;!(e&&this.skippedWhiteSpace);){let s="*";if(["*",'
HTML += b'"/"].includes(this.token))s=this.token,this.next();else if(!'
HTML += b'e&&this.token==="(")s="*";else if(this.token.length>0&&(this'
HTML += b'.isAlpha(this.token[0])||this.isNum(this.token[0])))s="*";el'
HTML += b"se break;t=new a(s,[t,this.parsePow(e)])}return t}parsePow(e"
HTML += b'){let t=this.parseUnary(e);for(;["^"].includes(this.token)&&'
HTML += b"!(e&&this.skippedWhiteSpace);){let s=this.token;this.next(),"
HTML += b"t=new a(s,[t,this.parseUnary(e)])}return t}parseUnary(e){ret"
HTML += b'urn this.token==="-"?(this.next(),new a(".-",[this.parseMul('
HTML += b"e)])):this.parseInfix(e)}parseInfix(e){if(this.token.length="
HTML += b'=0)throw new Error("expected unary");if(this.isNum(this.toke'
HTML += b'n[0])){let t=this.token;return this.next(),this.token==="."&'
HTML += b'&(t+=".",this.next(),this.token.length>0&&(t+=this.token,thi'
HTML += b's.next())),new a("const",[],parseFloat(t))}else if(this.fun1'
HTML += b"().length>0){let t=this.fun1();this.next(t.length);let s=nul"
HTML += b'l;if(this.token==="(")if(this.next(),s=this.parseExpr(e),thi'
HTML += b's.token+="",this.token===")")this.next();else throw Error("e'
HTML += b"xpected ')'\");else s=this.parseMul(!0);return new a(t,[s])}e"
HTML += b'lse if(this.token==="("){this.next();let t=this.parseExpr(e)'
HTML += b';if(this.token+="",this.token===")")this.next();else throw E'
HTML += b"rror(\"expected ')'\");return t.explicitParentheses=!0,t}else "
HTML += b'if(this.token==="|"){this.next();let t=this.parseExpr(e);if('
HTML += b'this.token+="",this.token==="|")this.next();else throw Error'
HTML += b'("expected \'|\'");return new a("abs",[t])}else if(this.isAlph'
HTML += b'a(this.token[0])){let t="";return this.token.startsWith("pi"'
HTML += b')?t="pi":this.token.startsWith("true")?t="true":this.token.s'
HTML += b'tartsWith("false")?t="false":this.token.startsWith("C1")?t="'
HTML += b'C1":this.token.startsWith("C2")?t="C2":t=this.token[0],t==="'
HTML += b'I"&&(t="i"),this.next(t.length),new a("var:"+t,[])}else thro'
HTML += b'w new Error("expected unary")}static compare(e,t,s={}){let l'
HTML += b"=new Set;e.getVars(l),t.getVars(l);for(let h=0;h<10;h++){let"
HTML += b" n={};for(let g of l)g in s?n[g]=s[g]:n[g]=a.const(Math.rand"
HTML += b"om(),Math.random());let c=e.eval(n),p=t.eval(n),m=c.re-p.re,"
HTML += b"u=c.im-p.im;if(Math.sqrt(m*m+u*u)>1e-9)return!1}return!0}fun"
HTML += b'1(){let e=["abs","acos","acosh","asin","asinh","atan","atanh'
HTML += b'","ceil","cos","cosh","cot","exp","floor","ln","log","log10"'
HTML += b',"log2","round","sin","sinc","sinh","sqrt","tan","tanh"];for'
HTML += b"(let t of e)if(this.token.toLowerCase().startsWith(t))return"
HTML += b' t;return""}next(e=-1){if(e>0&&this.token.length>e){this.tok'
HTML += b"en=this.token.substring(e),this.skippedWhiteSpace=!1;return}"
HTML += b'this.token="";let t=!1,s=this.src.length;for(this.skippedWhi'
HTML += b"teSpace=!1;this.pos<s&&`\t\n `.includes(this.src[this.pos]);)t"
HTML += b"his.skippedWhiteSpace=!0,this.pos++;for(;!t&&this.pos<s;){le"
HTML += b"t i=this.src[this.pos];if(this.token.length>0&&(this.isNum(t"
HTML += b"his.token[0])&&this.isAlpha(i)||this.isAlpha(this.token[0])&"
HTML += b'&this.isNum(i))&&this.token!="C")return;if(`^%#*$()[]{},.:;+'
HTML += b"-*/_!<>=?|\t\n `.includes(i)){if(this.token.length>0)return;t="
HTML += b"!0}`\t\n `.includes(i)==!1&&(this.token+=i),this.pos++}}isNum("
HTML += b"e){return e.charCodeAt(0)>=48&&e.charCodeAt(0)<=57}isAlpha(e"
HTML += b"){return e.charCodeAt(0)>=65&&e.charCodeAt(0)<=90||e.charCod"
HTML += b'eAt(0)>=97&&e.charCodeAt(0)<=122||e==="_"}toString(){return '
HTML += b'this.root==null?"":this.root.toString()}toTexString(){return'
HTML += b' this.root==null?"":this.root.toTexString()}},a=class r{stat'
HTML += b'ic{f(this,"TermNode")}constructor(e,t,s=0,i=0){this.op=e,thi'
HTML += b"s.c=t,this.re=s,this.im=i,this.explicitParentheses=!1}clone("
HTML += b"){let e=new r(this.op,this.c.map(t=>t.clone()),this.re,this."
HTML += b"im);return e.explicitParentheses=this.explicitParentheses,e}"
HTML += b'static const(e=0,t=0){return new r("const",[],e,t)}compare(e'
HTML += b",t=0,s=1e-9){let i=this.re-e,o=this.im-t;return Math.sqrt(i*"
HTML += b'i+o*o)<s}toString(){let e="";if(this.op==="const"){let t=Mat'
HTML += b"h.abs(this.re)>1e-14,s=Math.abs(this.im)>1e-14;t&&s&&this.im"
HTML += b'>=0?e="("+this.re+"+"+this.im+"i)":t&&s&&this.im<0?e="("+thi'
HTML += b's.re+"-"+-this.im+"i)":t&&this.re>0?e=""+this.re:t&&this.re<'
HTML += b'0?e="("+this.re+")":s?e="("+this.im+"i)":e="0"}else this.op.'
HTML += b'startsWith("var")?e=this.op.split(":")[1]:this.c.length==1?e'
HTML += b'=(this.op===".-"?"-":this.op)+"("+this.c.toString()+")":e="('
HTML += b'"+this.c.map(t=>t.toString()).join(this.op)+")";return e}toT'
HTML += b'exString(e=!1){let s="";switch(this.op){case"const":{let i=M'
HTML += b'ath.abs(this.re)>1e-9,o=Math.abs(this.im)>1e-9,l=i?""+this.r'
HTML += b'e:"",h=o?""+this.im+"i":"";h==="1i"?h="i":h==="-1i"&&(h="-i"'
HTML += b'),!i&&!o?s="0":(o&&this.im>=0&&i&&(h="+"+h),s=l+h);break}cas'
HTML += b'e".-":s="-"+this.c[0].toTexString();break;case"+":case"-":ca'
HTML += b'se"*":case"^":{let i=this.c[0].toTexString(),o=this.c[1].toT'
HTML += b'exString(),l=this.op==="*"?"\\\\cdot ":this.op;s="{"+i+"}"+l+"'
HTML += b'{"+o+"}";break}case"/":{let i=this.c[0].toTexString(!0),o=th'
HTML += b'is.c[1].toTexString(!0);s="\\\\frac{"+i+"}{"+o+"}";break}case"'
HTML += b'floor":{let i=this.c[0].toTexString(!0);s+="\\\\"+this.op+"\\\\l'
HTML += b'eft\\\\lfloor"+i+"\\\\right\\\\rfloor";break}case"ceil":{let i=thi'
HTML += b's.c[0].toTexString(!0);s+="\\\\"+this.op+"\\\\left\\\\lceil"+i+"\\\\'
HTML += b'right\\\\rceil";break}case"round":{let i=this.c[0].toTexString'
HTML += b'(!0);s+="\\\\"+this.op+"\\\\left["+i+"\\\\right]";break}case"acos"'
HTML += b':case"acosh":case"asin":case"asinh":case"atan":case"atanh":c'
HTML += b'ase"cos":case"cosh":case"cot":case"exp":case"ln":case"log":c'
HTML += b'ase"log10":case"log2":case"sin":case"sinc":case"sinh":case"t'
HTML += b'an":case"tanh":{let i=this.c[0].toTexString(!0);s+="\\\\"+this'
HTML += b'.op+"\\\\left("+i+"\\\\right)";break}case"sqrt":{let i=this.c[0]'
HTML += b'.toTexString(!0);s+="\\\\"+this.op+"{"+i+"}";break}case"abs":{'
HTML += b'let i=this.c[0].toTexString(!0);s+="\\\\left|"+i+"\\\\right|";br'
HTML += b'eak}default:if(this.op.startsWith("var:")){let i=this.op.sub'
HTML += b'string(4);switch(i){case"pi":i="\\\\pi";break}s=" "+i+" "}else'
HTML += b'{let i="warning: Node.toString(..):";i+=" unimplemented oper'
HTML += b'ator \'"+this.op+"\'",console.log(i),s=this.op,this.c.length>0'
HTML += b'&&(s+="\\\\left({"+this.c.map(o=>o.toTexString(!0)).join(",")+'
HTML += b'"}\\\\right)")}}return!e&&this.explicitParentheses&&(s="\\\\left'
HTML += b'({"+s+"}\\\\right)"),s}};function he(r,e){let t=1e-9;if(b.comp'
HTML += b"are(r,e))return!0;r=r.clone(),e=e.clone(),U(r.root),U(e.root"
HTML += b");let s=new Set;r.getVars(s),e.getVars(s);let i=[],o=[];for("
HTML += b'let n of s.keys())n.startsWith("C")?i.push(n):o.push(n);let '
HTML += b'l=i.length;for(let n=0;n<l;n++){let c=i[n];r.renameVar(c,"_C'
HTML += b'"+n),e.renameVar(c,"_C"+n)}for(let n=0;n<l;n++)r.renameVar("'
HTML += b'_C"+n,"C"+n),e.renameVar("_C"+n,"C"+n);i=[];for(let n=0;n<l;'
HTML += b'n++)i.push("C"+n);let h=[];_(P(l),h);for(let n of h){let c=r'
HTML += b'.clone(),p=e.clone();for(let u=0;u<l;u++)p.renameVar("C"+u,"'
HTML += b'__C"+n[u]);for(let u=0;u<l;u++)p.renameVar("__C"+u,"C"+u);le'
HTML += b't m=!0;for(let u=0;u<l;u++){let d="C"+u,g={};g[d]=new a("*",'
HTML += b'[new a("var:C"+u,[]),new a("var:K",[])]),p.setVars(g);let v='
HTML += b"{};v[d]=a.const(Math.random(),Math.random());for(let C=0;C<l"
HTML += b';C++)u!=C&&(v["C"+C]=a.const(0,0));let M=new a("abs",[new a('
HTML += b'"-",[c.root,p.root])]),E=new b;E.root=M;for(let C of o)v[C]='
HTML += b'a.const(Math.random(),Math.random());let y=ve(E,"K",v)[0];p.'
HTML += b"setVars({K:a.const(y,0)}),v={};for(let C=0;C<l;C++)u!=C&&(v["
HTML += b'"C"+C]=a.const(0,0));if(b.compare(c,p,v)==!1){m=!1;break}}if'
HTML += b'(m&&b.compare(c,p))return!0}return!1}f(he,"compareODE");func'
HTML += b"tion ve(r,e,t){let s=1e-11,i=1e3,o=0,l=0,h=1,n=888;for(;o<i;"
HTML += b"){t[e]=a.const(l);let p=r.eval(t).re;t[e]=a.const(l+h);let m"
HTML += b"=r.eval(t).re;t[e]=a.const(l-h);let u=r.eval(t).re,d=0;if(m<"
HTML += b"p&&(p=m,d=1),u<p&&(p=u,d=-1),d==1&&(l+=h),d==-1&&(l-=h),p<s)"
HTML += b"break;(d==0||d!=n)&&(h/=2),n=d,o++}t[e]=a.const(l);let c=r.e"
HTML += b'val(t).re;return[l,c]}f(ve,"minimize");function U(r){for(let'
HTML += b' e of r.c)U(e);switch(r.op){case"+":case"-":case"*":case"/":'
HTML += b'case"^":{let e=[r.c[0].op,r.c[1].op],t=[e[0]==="const",e[1]='
HTML += b'=="const"],s=[e[0].startsWith("var:C"),e[1].startsWith("var:'
HTML += b'C")];s[0]&&t[1]?(r.op=r.c[0].op,r.c=[]):s[1]&&t[0]?(r.op=r.c'
HTML += b"[1].op,r.c=[]):s[0]&&s[1]&&e[0]==e[1]&&(r.op=r.c[0].op,r.c=["
HTML += b']);break}case".-":case"abs":case"sin":case"sinc":case"cos":c'
HTML += b'ase"tan":case"cot":case"exp":case"ln":case"log":case"sqrt":r'
HTML += b'.c[0].op.startsWith("var:C")&&(r.op=r.c[0].op,r.c=[]);break}'
HTML += b'}f(U,"prepareODEconstantComparison");var A=class{static{f(th'
HTML += b'is,"GapInput")}constructor(e,t,s,i){this.question=t,this.inp'
HTML += b'utId=s,s.length==0&&(this.inputId=s="gap-"+t.gapIdx,t.types['
HTML += b'this.inputId]="string",t.expected[this.inputId]=i,t.gapIdx++'
HTML += b'),s in t.student||(t.student[s]="");let o=i.split("|"),l=0;f'
HTML += b"or(let p=0;p<o.length;p++){let m=o[p];m.length>l&&(l=m.lengt"
HTML += b'h)}let h=k("");e.appendChild(h);let n=Math.max(l*15,24),c=W('
HTML += b'n);if(t.gapInputs[this.inputId]=c,c.addEventListener("keyup"'
HTML += b",()=>{t.editingEnabled!=!1&&(this.question.editedQuestion(),"
HTML += b"c.value=c.value.toUpperCase(),this.question.student[this.inp"
HTML += b"utId]=c.value.trim())}),h.appendChild(c),this.question.showS"
HTML += b"olution&&(this.question.student[this.inputId]=c.value=o[0],o"
HTML += b'.length>1)){let p=k("["+o.join("|")+"]");p.style.fontSize="s'
HTML += b'mall",p.style.textDecoration="underline",h.appendChild(p)}}}'
HTML += b',z=class{static{f(this,"TermInput")}constructor(e,t,s,i,o,l,'
HTML += b'h=!1){s in t.student||(t.student[s]=""),this.question=t,this'
HTML += b'.inputId=s,this.outerSpan=k(""),this.outerSpan.style.positio'
HTML += b'n="relative",e.appendChild(this.outerSpan),this.inputElement'
HTML += b"=W(Math.max(i*12,48)),this.outerSpan.appendChild(this.inputE"
HTML += b"lement),this.equationPreviewDiv=x(),this.equationPreviewDiv."
HTML += b'classList.add("pysell-equation-preview"),this.equationPrevie'
HTML += b'wDiv.style.display="none",this.outerSpan.appendChild(this.eq'
HTML += b'uationPreviewDiv),this.inputElement.addEventListener("click"'
HTML += b",()=>{if(t.editingEnabled==!1){this.inputElement.blur();retu"
HTML += b"rn}this.question.editedQuestion(),this.edited()}),this.input"
HTML += b'Element.addEventListener("keyup",()=>{t.editingEnabled!=!1&&'
HTML += b"(this.question.editedQuestion(),this.edited())}),this.inputE"
HTML += b'lement.addEventListener("focus",()=>{t.editingEnabled!=!1}),'
HTML += b'this.inputElement.addEventListener("focusout",()=>{this.equa'
HTML += b'tionPreviewDiv.innerHTML="",this.equationPreviewDiv.style.di'
HTML += b'splay="none"}),this.inputElement.addEventListener("keydown",'
HTML += b"n=>{if(t.editingEnabled==!1){n.preventDefault();return}let c"
HTML += b'="abcdefghijklmnopqrstuvwxyz";c+="ABCDEFGHIJKLMNOPQRSTUVWXYZ'
HTML += b'",c+="0123456789",c+="+-*/^(). <>=|",l&&(c="-0123456789"),n.'
HTML += b"key.length<3&&c.includes(n.key)==!1&&n.preventDefault();let "
HTML += b"p=this.inputElement.value.length*12;this.inputElement.offset"
HTML += b'Width<p&&(this.inputElement.style.width=""+p+"px")}),(h||thi'
HTML += b"s.question.showSolution)&&(t.student[s]=this.inputElement.va"
HTML += b'lue=o)}edited(){let e=this.inputElement.value.trim(),t="",s='
HTML += b'!1;try{let i=b.parse(e);s=i.root.op==="const",t=i.toTexStrin'
HTML += b"g(),this.inputElement.style.color=this.question.quiz.darkMod"
HTML += b'e?"var(--pysell-white)":"var(--pysell-black)",this.equationP'
HTML += b'reviewDiv.style.backgroundColor="var(--pysell-green)"}catch{'
HTML += b't=e.replaceAll("^","\\\\hat{~}").replaceAll("_","\\\\_"),this.in'
HTML += b'putElement.style.color="maroon",this.equationPreviewDiv.styl'
HTML += b'e.backgroundColor="maroon"}N(this.equationPreviewDiv,t,!0),t'
HTML += b'his.equationPreviewDiv.style.display=e.length>0&&!s?"block":'
HTML += b'"none",this.question.student[this.inputId]=e}},B=class{stati'
HTML += b'c{f(this,"MatrixInput")}constructor(e,t,s,i){this.parent=e,t'
HTML += b"his.question=t,this.inputId=s,this.matExpected=new L(0,0),th"
HTML += b"is.matExpected.fromString(i),this.matStudent=new L(this.matE"
HTML += b"xpected.m==1?1:3,this.matExpected.n==1?1:3),t.showSolution&&"
HTML += b"this.matStudent.fromMatrix(this.matExpected),this.genMatrixD"
HTML += b'om(!0)}genMatrixDom(e){let t=x();this.parent.innerHTML="",th'
HTML += b'is.parent.appendChild(t),t.style.position="relative",t.style'
HTML += b'.display="inline-block";let s=document.createElement("table"'
HTML += b');s.style.borderCollapse="collapse",t.appendChild(s);let i=t'
HTML += b"his.matExpected.getMaxCellStrlen();for(let d=0;d<this.matStu"
HTML += b'dent.m;d++){let g=document.createElement("tr");g.style.borde'
HTML += b'rCollapse="collapse",g.style.borderStyle="none",s.appendChil'
HTML += b"d(g),d==0&&g.appendChild(this.generateMatrixParenthesis(!0,t"
HTML += b"his.matStudent.m));for(let v=0;v<this.matStudent.n;v++){let "
HTML += b'M=d*this.matStudent.n+v,E=document.createElement("td");E.sty'
HTML += b'le.borderCollapse="collapse",g.appendChild(E);let y=this.inp'
HTML += b'utId+"-"+M;new z(E,this.question,y,i,this.matStudent.v[M],!1'
HTML += b",!e)}d==0&&g.appendChild(this.generateMatrixParenthesis(!1,t"
HTML += b'his.matStudent.m))}let o=["+","-","+","-"],l=[0,0,1,-1],h=[1'
HTML += b",-1,0,0],n=[0,22,888,888],c=[888,888,-23,-23],p=[-22,-22,0,2"
HTML += b"2],m=[this.matExpected.n!=1,this.matExpected.n!=1,this.matEx"
HTML += b"pected.m!=1,this.matExpected.m!=1],u=[this.matStudent.n>=10,"
HTML += b"this.matStudent.n<=1,this.matStudent.m>=10,this.matStudent.m"
HTML += b"<=1];for(let d=0;d<4;d++){if(m[d]==!1)continue;let g=k(o[d])"
HTML += b';n[d]!=888&&(g.style.top=""+n[d]+"px"),c[d]!=888&&(g.style.b'
HTML += b'ottom=""+c[d]+"px"),p[d]!=888&&(g.style.right=""+p[d]+"px"),'
HTML += b'g.classList.add("pysell-matrix-resize-button"),t.appendChild'
HTML += b'(g),u[d]?g.style.opacity="0.5":g.addEventListener("click",()'
HTML += b"=>{for(let v=0;v<this.matStudent.m;v++)for(let M=0;M<this.ma"
HTML += b'tStudent.n;M++){let E=v*this.matStudent.n+M,y=this.inputId+"'
HTML += b'-"+E,S=this.question.student[y];this.matStudent.v[E]=S,delet'
HTML += b"e this.question.student[y]}this.matStudent.resize(this.matSt"
HTML += b'udent.m+l[d],this.matStudent.n+h[d],""),this.genMatrixDom(!1'
HTML += b")})}}generateMatrixParenthesis(e,t){let s=document.createEle"
HTML += b'ment("td");s.style.width="3px";for(let i of["Top",e?"Left":"'
HTML += b'Right","Bottom"])s.style["border"+i+"Width"]="2px",s.style["'
HTML += b'border"+i+"Style"]="solid";return this.question.language=="d'
HTML += b'e"&&(e?s.style.borderTopLeftRadius="5px":s.style.borderTopRi'
HTML += b'ghtRadius="5px",e?s.style.borderBottomLeftRadius="5px":s.sty'
HTML += b'le.borderBottomRightRadius="5px"),s.rowSpan=t,s}};var w={ini'
HTML += b't:0,errors:1,passed:2,incomplete:3},q=class{static{f(this,"Q'
HTML += b'uestion")}constructor(e,t,s,i,o){this.quiz=e,this.state=w.in'
HTML += b"it,this.language=i,this.src=s,this.debug=o,this.instanceOrde"
HTML += b"r=P(s.instances.length,!0),this.instanceIdx=0,this.choiceIdx"
HTML += b"=0,this.includesSingleChoice=!1,this.gapIdx=0,this.expected="
HTML += b"{},this.types={},this.student={},this.gapInputs={},this.pare"
HTML += b"ntDiv=t,this.questionDiv=null,this.feedbackPopupDiv=null,thi"
HTML += b"s.titleDiv=null,this.checkAndRepeatBtn=null,this.showSolutio"
HTML += b"n=!1,this.feedbackSpan=null,this.numCorrect=0,this.numChecke"
HTML += b"d=0,this.hasCheckButton=!0,this.editingEnabled=!0}reset(){th"
HTML += b"is.gapIdx=0,this.choiceIdx=0,this.instanceIdx=(this.instance"
HTML += b"Idx+1)%this.src.instances.length}getCurrentInstance(){let e="
HTML += b"this.instanceOrder[this.instanceIdx];return this.src.instanc"
HTML += b"es[e]}editedQuestion(){this.state=w.init,this.updateVisualQu"
HTML += b'estionState();let e=this.quiz.darkMode?"var(--pysell-white)"'
HTML += b':"var(--pysell-black)";this.questionDiv.style.color=e,this.c'
HTML += b'heckAndRepeatBtn.innerHTML=this.quiz.darkMode?D.replace("whi'
HTML += b'te","black"):D,this.checkAndRepeatBtn.style.display="block",'
HTML += b"this.checkAndRepeatBtn.style.color=e}updateVisualQuestionSta"
HTML += b'te(){let e=this.quiz.darkMode?"var(--pysell-white)":"var(--p'
HTML += b'ysell-black)",t="transparent";switch(this.state){case w.init'
HTML += b':e=this.quiz.darkMode?"var(--pysell-white)":"var(--pysell-bl'
HTML += b'ack)";break;case w.passed:e="var(--pysell-green)",t="rgba(0,'
HTML += b'150,0, 0.035)";break;case w.incomplete:case w.errors:e="var('
HTML += b'--pysell-red)",t="rgba(150,0,0, 0.035)",this.includesSingleC'
HTML += b"hoice==!1&&this.numChecked>=5&&(this.feedbackSpan.innerHTML="
HTML += b'"&nbsp;&nbsp;"+this.numCorrect+" / "+this.numChecked);break}'
HTML += b"this.questionDiv.style.backgroundColor=t,this.questionDiv.st"
HTML += b"yle.borderColor=e}populateDom(e=!1){if(this.parentDiv.innerH"
HTML += b'TML="",this.questionDiv=x(),this.parentDiv.appendChild(this.'
HTML += b'questionDiv),this.questionDiv.classList.add("pysell-question'
HTML += b'"),this.questionDiv.style.borderColor=this.quiz.darkMode?"va'
HTML += b'r(--pysell-white)":"var(--pysell-black)",this.feedbackPopupD'
HTML += b'iv=x(),this.feedbackPopupDiv.classList.add("pysell-question-'
HTML += b'feedback"),this.questionDiv.appendChild(this.feedbackPopupDi'
HTML += b'v),this.feedbackPopupDiv.innerHTML="awesome",this.debug&&"sr'
HTML += b'c_line"in this.src){let i=x();i.classList.add("pysell-debug-'
HTML += b'info"),i.innerHTML="Source code: lines "+this.src.src_line+"'
HTML += b'..",this.questionDiv.appendChild(i)}if(this.titleDiv=x(),thi'
HTML += b"s.questionDiv.appendChild(this.titleDiv),this.titleDiv.class"
HTML += b'List.add("pysell-question-title"),this.titleDiv.style.color='
HTML += b'this.quiz.darkMode?"var(--pysell-white)":"var(--pysell-black'
HTML += b')",this.titleDiv.innerHTML=this.src.title,this.src.error.len'
HTML += b"gth>0){let i=k(this.src.error);this.questionDiv.appendChild("
HTML += b'i),i.style.color="red";return}let t=this.getCurrentInstance('
HTML += b');if(t!=null&&"__svg_image"in t){let i=t.__svg_image.v,o=x()'
HTML += b";this.questionDiv.appendChild(o);let l=document.createElemen"
HTML += b't("img");o.appendChild(l),l.classList.add("pysell-img"),l.sr'
HTML += b'c="data:image/svg+xml;base64,"+i}for(let i of this.src.text.'
HTML += b"c)this.questionDiv.appendChild(this.generateText(i));let s=x"
HTML += b'();if(s.innerHTML="",s.classList.add("pysell-button-group"),'
HTML += b"this.questionDiv.appendChild(s),this.hasCheckButton=Object.k"
HTML += b"eys(this.expected).length>0,this.hasCheckButton&&(this.check"
HTML += b"AndRepeatBtn=se(),s.appendChild(this.checkAndRepeatBtn),this"
HTML += b'.checkAndRepeatBtn.innerHTML=this.quiz.darkMode?D.replace("w'
HTML += b'hite","black"):D,this.checkAndRepeatBtn.style.backgroundColo'
HTML += b'r=this.quiz.darkMode?"var(--pysell-white)":"var(--pysell-bla'
HTML += b'ck)",e&&(this.checkAndRepeatBtn.style.height="32px",this.che'
HTML += b'ckAndRepeatBtn.style.visibility="hidden")),this.feedbackSpan'
HTML += b'=k(""),this.feedbackSpan.style.userSelect="none",s.appendChi'
HTML += b"ld(this.feedbackSpan),this.debug){if(this.src.variables.leng"
HTML += b'th>0){let l=x();l.classList.add("pysell-debug-info"),l.inner'
HTML += b'HTML="Variables generated by Python Code",this.questionDiv.a'
HTML += b'ppendChild(l);let h=x();h.classList.add("pysell-debug-code")'
HTML += b",this.questionDiv.appendChild(h);let n=this.getCurrentInstan"
HTML += b'ce(),c="",p=[...this.src.variables];p.sort();for(let m of p)'
HTML += b'{let u=n[m].t,d=n[m].v;switch(u){case"vector":d="["+d+"]";br'
HTML += b'eak;case"set":d="{"+d+"}";break}c+=u+" "+m+" = "+d+"<br/>"}h'
HTML += b'.innerHTML=c}let i=["python_src_html","text_src_html"],o=["P'
HTML += b'ython Source Code","Text Source Code"];for(let l=0;l<i.lengt'
HTML += b"h;l++){let h=i[l];if(h in this.src&&this.src[h].length>0){le"
HTML += b't n=x();n.classList.add("pysell-debug-info"),n.innerHTML=o[l'
HTML += b"],this.questionDiv.appendChild(n);let c=x();c.classList.add("
HTML += b'"pysell-debug-code"),this.questionDiv.append(c),c.innerHTML='
HTML += b"this.src[h]}}}this.hasCheckButton&&this.checkAndRepeatBtn.ad"
HTML += b'dEventListener("click",()=>{this.state==w.passed?(this.state'
HTML += b"=w.init,this.editingEnabled=!0,this.reset(),this.populateDom"
HTML += b'()):V(this)})}generateMathString(e){let t="";switch(e.t){cas'
HTML += b'e"math":case"display-math":for(let s of e.c){let i=this.gene'
HTML += b'rateMathString(s);s.t==="var"&&t.includes("!PM")&&(i.startsW'
HTML += b'ith("{-")?(i="{"+i.substring(2),t=t.replaceAll("!PM","-")):t'
HTML += b'=t.replaceAll("!PM","+")),t+=i}break;case"text":return e.d;c'
HTML += b'ase"plus_minus":{t+=" !PM ";break}case"var":{let s=this.getC'
HTML += b'urrentInstance(),i=s[e.d].t,o=s[e.d].v;switch(i){case"vector'
HTML += b'":return"\\\\left["+o+"\\\\right]";case"set":return"\\\\left\\\\{"+o'
HTML += b'+"\\\\right\\\\}";case"complex":{let l=o.split(","),h=parseFloat'
HTML += b"(l[0]),n=parseFloat(l[1]);return a.const(h,n).toTexString()}"
HTML += b'case"matrix":{let l=new L(0,0);return l.fromString(o),t=l.to'
HTML += b'TeXString(e.d.includes("augmented"),this.language!="de"),t}c'
HTML += b'ase"term":{try{t=b.parse(o).toTexString()}catch{}break}defau'
HTML += b'lt:t=o}}}return e.t==="plus_minus"?t:"{"+t+"}"}generateText('
HTML += b'e,t=!1){switch(e.t){case"paragraph":case"span":{let s=docume'
HTML += b'nt.createElement(e.t=="span"||t?"span":"p");for(let i of e.c'
HTML += b")s.appendChild(this.generateText(i));return s.style.userSele"
HTML += b'ct="none",s}case"text":return k(e.d);case"code":{let s=k(e.d'
HTML += b');return s.classList.add("pysell-code"),s}case"italic":case"'
HTML += b'bold":{let s=k("");return s.append(...e.c.map(i=>this.genera'
HTML += b'teText(i))),e.t==="bold"?s.style.fontWeight="bold":s.style.f'
HTML += b'ontStyle="italic",s}case"math":case"display-math":{let s=thi'
HTML += b's.generateMathString(e);return T(s,e.t==="display-math")}cas'
HTML += b'e"string_var":{let s=k(""),i=this.getCurrentInstance(),o=i[e'
HTML += b'.d].t,l=i[e.d].v;return o==="string"?s.innerHTML=l:(s.innerH'
HTML += b'TML="EXPECTED VARIABLE OF TYPE STRING",s.style.color="red"),'
HTML += b's}case"gap":{let s=k("");return new A(s,this,"",e.d),s}case"'
HTML += b'input":case"input2":{let s=e.t==="input2",i=k("");i.style.ve'
HTML += b'rticalAlign="text-bottom";let o=e.d,l=this.getCurrentInstanc'
HTML += b"e()[o];if(this.expected[o]=l.v,this.types[o]=l.t,!s)switch(l"
HTML += b'.t){case"set":i.append(T("\\\\{"),k(" "));break;case"vector":i'
HTML += b'.append(T("["),k(" "));break}if(l.t==="string")new A(i,this,'
HTML += b'o,this.expected[o]);else if(l.t==="vector"||l.t==="set"){let'
HTML += b' h=l.v.split(","),n=h.length;for(let c=0;c<n;c++){c>0&&i.app'
HTML += b'endChild(k(" , "));let p=o+"-"+c;new z(i,this,p,h[c].length,'
HTML += b'h[c],!1)}}else if(l.t==="matrix"){let h=x();i.appendChild(h)'
HTML += b',new B(h,this,o,l.v)}else if(l.t==="complex"){let h=l.v.spli'
HTML += b't(",");new z(i,this,o+"-0",h[0].length,h[0],!1),i.append(k("'
HTML += b' "),T("+"),k(" ")),new z(i,this,o+"-1",h[1].length,h[1],!1),'
HTML += b'i.append(k(" "),T("i"))}else{let h=l.t==="int";new z(i,this,'
HTML += b'o,l.v.length,l.v,h)}if(!s)switch(l.t){case"set":i.append(k("'
HTML += b' "),T("\\\\}"));break;case"vector":i.append(k(" "),T("]"));bre'
HTML += b'ak}return i}case"itemize":return te(e.c.map(s=>ie(this.gener'
HTML += b'ateText(s))));case"single-choice":case"multi-choice":{let s='
HTML += b'e.t=="multi-choice";s||(this.includesSingleChoice=!0);let i='
HTML += b'document.createElement("table");i.style.border="none",i.styl'
HTML += b'e.borderCollapse="collapse";let o=e.c.length,l=this.debug==!'
HTML += b"1,h=P(o,l),n=s?ae:oe,c=s?re:le;this.quiz.darkMode&&(n=n.repl"
HTML += b'ace("black","white"),c=c.replace("black","white"));let p=[],'
HTML += b'm=[];for(let u=0;u<o;u++){let d=h[u],g=e.c[d],v="mc-"+this.c'
HTML += b'hoiceIdx+"-"+d;m.push(v);let M=g.c[0].t=="bool"?g.c[0].d:thi'
HTML += b"s.getCurrentInstance()[g.c[0].d].v;this.expected[v]=M,this.t"
HTML += b'ypes[v]="bool",this.student[v]=this.showSolution?M:"false";l'
HTML += b'et E=this.generateText(g.c[1],!0),y=document.createElement("'
HTML += b'tr");i.appendChild(y),y.style.cursor="pointer",y.style.borde'
HTML += b'rStyle="none";let S=document.createElement("td");S.style.wid'
HTML += b'th="40px",p.push(S),y.appendChild(S),S.innerHTML=this.studen'
HTML += b't[v]=="true"?n:c;let C=document.createElement("td");y.append'
HTML += b'Child(C),C.appendChild(E),s?y.addEventListener("click",()=>{'
HTML += b"this.editingEnabled!=!1&&(this.editedQuestion(),this.student"
HTML += b'[v]=this.student[v]==="true"?"false":"true",this.student[v]='
HTML += b'=="true"?S.innerHTML=n:S.innerHTML=c)}):y.addEventListener("'
HTML += b'click",()=>{if(this.editingEnabled!=!1){this.editedQuestion('
HTML += b');for(let I of m)this.student[I]="false";this.student[v]="tr'
HTML += b'ue";for(let I=0;I<m.length;I++){let j=h[I];p[j].innerHTML=th'
HTML += b'is.student[m[j]]=="true"?n:c}}})}return this.choiceIdx++,i}c'
HTML += b'ase"image":{let s=x(),o=e.d.split("."),l=o[o.length-1],h=e.c'
HTML += b'[0].d,n=e.c[1].d,c=document.createElement("img");s.appendChi'
HTML += b'ld(c),c.classList.add("pysell-img"),c.style.width=h+"%";let '
HTML += b'p={svg:"svg+xml",png:"png",jpg:"jpeg"};return c.src="data:im'
HTML += b'age/"+p[l]+";base64,"+n,s}default:{let s=k("UNIMPLEMENTED("+'
HTML += b'e.t+")");return s.style.color="red",s}}}};function V(r){r.fe'
HTML += b'edbackSpan.innerHTML="",r.numChecked=0,r.numCorrect=0;let e='
HTML += b"!0;for(let i in r.expected){let o=r.types[i],l=r.student[i],"
HTML += b'h=r.expected[i];switch(l!=null&&l.length==0&&(e=!1),o){case"'
HTML += b'bool":r.numChecked++,l.toLowerCase()===h.toLowerCase()&&r.nu'
HTML += b'mCorrect++;break;case"string":{r.numChecked++;let n=r.gapInp'
HTML += b"uts[i],c=l.trim().toUpperCase(),p=h.trim().toUpperCase().spl"
HTML += b'it("|"),m=!1;for(let u of p)if(ne(c,u)<=1){m=!0,r.numCorrect'
HTML += b"++,r.gapInputs[i].value=u,r.student[i]=u;break}n.style.color"
HTML += b'=m?"black":"white",n.style.backgroundColor=m?"transparent":"'
HTML += b'maroon";break}case"int":r.numChecked++,Math.abs(parseFloat(l'
HTML += b')-parseFloat(h))<1e-9&&r.numCorrect++;break;case"float":case'
HTML += b'"term":{r.numChecked++;try{let n=b.parse(h),c=b.parse(l),p=!'
HTML += b"1;r.src.is_ode?p=he(n,c):p=b.compare(n,c),p&&r.numCorrect++}"
HTML += b'catch(n){r.debug&&(console.log("term invalid"),console.log(n'
HTML += b'))}break}case"vector":case"complex":case"set":{let n=h.split'
HTML += b'(",");r.numChecked+=n.length;let c=[];for(let p=0;p<n.length'
HTML += b';p++){let m=r.student[i+"-"+p];m.length==0&&(e=!1),c.push(m)'
HTML += b'}if(o==="set")for(let p=0;p<n.length;p++)try{let m=b.parse(n'
HTML += b"[p]);for(let u=0;u<c.length;u++){let d=b.parse(c[u]);if(b.co"
HTML += b"mpare(m,d)){r.numCorrect++;break}}}catch(m){r.debug&&console"
HTML += b".log(m)}else for(let p=0;p<n.length;p++)try{let m=b.parse(c["
HTML += b"p]),u=b.parse(n[p]);b.compare(m,u)&&r.numCorrect++}catch(m){"
HTML += b'r.debug&&console.log(m)}break}case"matrix":{let n=new L(0,0)'
HTML += b";n.fromString(h),r.numChecked+=n.m*n.n;for(let c=0;c<n.m;c++"
HTML += b')for(let p=0;p<n.n;p++){let m=c*n.n+p;l=r.student[i+"-"+m],l'
HTML += b"!=null&&l.length==0&&(e=!1);let u=n.v[m];try{let d=b.parse(u"
HTML += b"),g=b.parse(l);b.compare(d,g)&&r.numCorrect++}catch(d){r.deb"
HTML += b'ug&&console.log(d)}}break}default:r.feedbackSpan.innerHTML="'
HTML += b'UNIMPLEMENTED EVAL OF TYPE "+o}}e==!1?r.state=w.incomplete:r'
HTML += b".state=r.numCorrect==r.numChecked?w.passed:w.errors,r.update"
HTML += b"VisualQuestionState();let t=[];switch(r.state){case w.passed"
HTML += b":t=Z[r.language];break;case w.incomplete:t=X[r.language];bre"
HTML += b"ak;case w.errors:t=Y[r.language];break}let s=t[Math.floor(Ma"
HTML += b"th.random()*t.length)];r.feedbackPopupDiv.innerHTML=s,r.feed"
HTML += b'backPopupDiv.style.color=r.state===w.passed?"var(--pysell-gr'
HTML += b'een)":"var(--pysell-red)",r.feedbackPopupDiv.style.display="'
HTML += b'flex",setTimeout(()=>{r.feedbackPopupDiv.style.display="none'
HTML += b'"},1e3),r.editingEnabled=!0,r.state===w.passed?(r.editingEna'
HTML += b"bled=!1,r.src.instances.length>1?r.checkAndRepeatBtn.innerHT"
HTML += b'ML=r.quiz.darkMode?Q.replace("white","black"):Q:r.checkAndRe'
HTML += b'peatBtn.style.visibility="hidden"):r.checkAndRepeatBtn!=null'
HTML += b'&&(r.checkAndRepeatBtn.innerHTML=r.quiz.darkMode?D.replace("'
HTML += b'white","black"):D)}f(V,"evalQuestion");var R=class{static{f('
HTML += b'this,"Quiz")}constructor(e,t,s,i=!1,o=!0){if(this.quizSrc=e,'
HTML += b'this.htmlElements=t,["en","de","es","it","fr"].includes(this'
HTML += b'.quizSrc.lang)==!1&&(this.quizSrc.lang="en"),this.debug=s,th'
HTML += b"is.darkMode=i,this.questionNumbering=o,this.questions=[],thi"
HTML += b"s.timeLeft=e.timer,this.timeLimited=e.timer>0,this.fillPageM"
HTML += b"etadata(),this.timeLimited){let l=t.timerInfo;l.classList.ad"
HTML += b'd("pysell-timer-info");let h=document.createElement("span");'
HTML += b"h.innerHTML=ee[this.quizSrc.lang],l.appendChild(h),l.appendC"
HTML += b'hild(document.createElement("br")),l.appendChild(document.cr'
HTML += b'eateElement("br"));let n=document.createElement("button");n.'
HTML += b'classList.add("pysell-button pysell-start-button"),n.innerHT'
HTML += b'ML="Start",n.addEventListener("click",()=>{l.style.display="'
HTML += b'none",this.generateQuestions(),this.runTimer()}),l.appendChi'
HTML += b'ld(n)}else this.generateQuestions()}fillPageMetadata(){if("d'
HTML += b'ate"in this.htmlElements){let e=this.htmlElements.date;e.inn'
HTML += b'erHTML=this.quizSrc.date}if("header"in this.htmlElements){le'
HTML += b't e=this.htmlElements.header,t=document.createElement("h1");'
HTML += b"t.innerHTML=this.quizSrc.title,e.appendChild(t);let s=docume"
HTML += b'nt.createElement("div");s.style.marginTop="15px",e.appendChi'
HTML += b'ld(s);let i=document.createElement("div");i.classList.add("p'
HTML += b'ysell-author"),i.innerHTML=this.quizSrc.author,e.appendChild'
HTML += b'(i);let o=document.createElement("p");if(o.classList.add("py'
HTML += b'sell-course-info"),e.appendChild(o),this.quizSrc.info.length'
HTML += b">0)o.innerHTML=this.quizSrc.info;else{o.innerHTML=F[this.qui"
HTML += b'zSrc.lang];let l=\'<span onclick="location.reload()" style="t'
HTML += b"ext-decoration: none; font-weight: bold; cursor: pointer\">'+"
HTML += b'K[this.quizSrc.lang]+"</span>",h=document.createElement("p")'
HTML += b';h.classList.add("pysell-course-info"),e.appendChild(h),h.in'
HTML += b'nerHTML=O[this.quizSrc.lang].replace("*",l)}if(this.debug){l'
HTML += b'et l=document.createElement("h1");l.classList.add("pysell-de'
HTML += b'bug-code"),l.innerHTML="DEBUG VERSION",e.appendChild(l)}}}ge'
HTML += b"nerateQuestions(){let e=1;for(let t of this.quizSrc.question"
HTML += b's){let s=t.title;this.questionNumbering&&(s=""+e+". "+s),t.t'
HTML += b"itle=s;let i=x();this.htmlElements.questions.appendChild(i);"
HTML += b"let o=new q(this,i,t,this.quizSrc.lang,this.debug);o.showSol"
HTML += b"ution=this.debug,this.questions.push(o),o.populateDom(this.t"
HTML += b"imeLimited),this.debug&&t.error.length==0&&o.hasCheckButton&"
HTML += b"&o.checkAndRepeatBtn.click(),e++}}runTimer(){let e=this.html"
HTML += b'Elements.timerFooter;e.style.textAlign="center";let t=docume'
HTML += b'nt.createElement("button");t.classList.add("pysell-button"),'
HTML += b't.style.backgroundColor="var(--pysell-green)",t.innerHTML=J['
HTML += b'this.quizSrc.lang],t.addEventListener("click",()=>{this.time'
HTML += b"Left=1}),e.appendChild(t);let s=this.htmlElements.timer;s.cl"
HTML += b'assList.add("pysell-timer"),s.innerHTML=ce(this.timeLeft);le'
HTML += b"t i=setInterval(()=>{this.timeLeft--,s.innerHTML=ce(this.tim"
HTML += b"eLeft),this.timeLeft<=0&&this.stopTimer(i)},1e3)}stopTimer(e"
HTML += b'){let t=this.htmlElements.timerFooter;t.style.display="none"'
HTML += b",clearInterval(e);let s=0,i=0;for(let h of this.questions){l"
HTML += b"et n=h.src.points;i+=n,V(h),h.state===w.passed&&(s+=n),h.edi"
HTML += b"tingEnabled=!1}let o=this.htmlElements.timerEval;o.classList"
HTML += b'.add("pysell-eval");let l=document.createElement("h1");o.app'
HTML += b'endChild(l),l.innerHTML=i==0?"":""+s+" / "+i+" "+G[this.quiz'
HTML += b'Src.lang]+" <br/><br/>"+Math.round(s/i*100)+" %"}};function '
HTML += b'ce(r){let e=Math.floor(r/60),t=r%60;return e+":"+(""+t).padS'
HTML += b'tart(2,"0")}f(ce,"formatTime");function be(r,e){let t={date:'
HTML += b'document.getElementById("date"),header:document.getElementBy'
HTML += b'Id("header"),questions:document.getElementById("questions"),'
HTML += b'timer:document.getElementById("timer"),timerInfo:document.ge'
HTML += b'tElementById("timer-info"),timerFooter:document.getElementBy'
HTML += b'Id("timer-footer"),timerEval:document.getElementById("timer-'
HTML += b'eval")};new R(r,t,e),document.getElementById("data-policy").'
HTML += b'innerHTML=$[r.lang]}f(be,"init");return ge(ke);})();pysell.i'
HTML += b"nit(quizSrc,debug);</script></body> </html> "
HTML = HTML.decode("utf-8")
# @end(html)


def main(args):
    """the main function"""

    silent_mode = "-S" in args

    if silent_mode is False:
        print("---------------------------------------------------------------------")
        print("pySELL by Andreas Schwenk - Licensed under GPLv3 - https://pysell.org")
        print("---------------------------------------------------------------------")

    # get input and output path
    if len(args) < 2:
        print("USAGE: pysell [-J] [-S] INPUT_PATH.txt")
        print("   option -J enables to output a JSON file for debugging purposes")
        print("   option -S enables silent mode, i.e. prevents info logs")
        print("EXAMPLE: pysell my-quiz.txt")
        print(
            "   compiles quiz definition in file 'my-quiz.txt' to file 'my-quiz.html'"
        )
        sys.exit(-1)
    write_explicit_json_file = "-J" in args
    input_path = args[-1]
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
        f.write(
            HTML.replace(
                "let quizSrc = {};",
                "/*@PYSELL_JSON@*/let quizSrc = " + output_json + ";/*@PYSELL_JSON@*/",
            )
        )

    # exit normally
    return


if __name__ == "__main__":
    main(sys.argv)
    sys.exit(0)
