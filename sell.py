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
            # Split text by "\n" and remove empty lines.
            # Keep the trailing "\n" in each line, also keep preceding white spaces
            text = self.data
            lines = [line + "\n" for line in text.split("\n") if line.strip() != ""]
            # as first character, add the type of the line
            tmp = []
            is_code = False
            for line in lines:
                if line.startswith("```"):
                    is_code = not is_code
                    continue
                t = ""
                if is_code:
                    t = "c"
                else:
                    line = line.lstrip()
                    t = line[0] if line[0] in "[(-!" else "p"
                tmp.append(t + line)
            lines = tmp
            # join lines that have the same type (except for trailing "\\")
            tmp = []
            last = ""
            for line in lines:
                if (
                    len(last) > 0
                    and line[0] == last[0]
                    and (not last.endswith("\\\\\n"))
                ):
                    tmp[-1] += line[1:]
                else:
                    tmp.append(line)
                last = line
            lines = tmp
            # replace trailing "\\\\\n" by "\n"
            tmp = []
            for line in lines:
                if line.endswith("\\\\\n"):
                    tmp.append(line[:-3].rstrip() + "\n")
                else:
                    tmp.append(line)
            lines = tmp
            # create children
            self.children = []
            types = {
                "p": "paragraph",
                "c": "code-block",
                "(": "single-choice",
                "[": "multi-choice",
                "-": "itemize",
                "!": "command",
            }
            for line in lines:
                t = types[line[0]]
                txt = line[1:]
                self.children.append(TextNode(t, txt))
            # parse children
            for child in self.children:
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

        elif self.type == "code-block":
            # do nothing
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


# pylint: disable-next=too-many-branches,too-many-locals
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
        line = line.split("##")[0]  # remove comments
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
                    question.text_src += line_not_stripped.rstrip() + "\n"
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
HTML += b'" ></script> <style> :root { --pysell-black: #000000; --pyse'
HTML += b'll-white: #ffffff; --pysell-grey: #5a5a5a; --pysell-green: r'
HTML += b'gb(24, 82, 1); --pysell-red: rgb(123, 0, 0); } html, body { '
HTML += b'font-family: Arial, Helvetica, sans-serif; margin: 0; paddin'
HTML += b'g: 0; background-color: white; } /* TODO: .pysell-ul as div '
HTML += b'element */ ul { user-select: none; margin-top: 0; margin-lef'
HTML += b't: 0px; padding-left: 20px; } a { color: black; text-decorat'
HTML += b'ion: underline; } h1 { text-align: center; font-size: 28pt; '
HTML += b'word-wrap: break-word; margin-bottom: 10px; user-select: non'
HTML += b'e; }  .contents { max-width: 800px; margin-left: auto; margi'
HTML += b'n-right: auto; padding: 0; } .footer { position: relative; b'
HTML += b'ottom: 0; font-size: small; text-align: center; line-height:'
HTML += b' 1.8; color: var(--pysell-grey); margin: 0; padding: 10px 10'
HTML += b'px; user-select: none; }  .pysell-img { width: 100%; display'
HTML += b': block; margin-left: auto; margin-right: auto; user-select:'
HTML += b' none; } .pysell-author { text-align: center; font-size: 16p'
HTML += b't; margin-bottom: 24px; user-select: none; } .pysell-course-'
HTML += b'info { text-align: center; user-select: none; } .pysell-ques'
HTML += b'tion { position: relative; /* required for feedback overlays'
HTML += b' */ color: black; background-color: white; border-top-style:'
HTML += b' solid; border-bottom-style: solid; border-width: 3px; borde'
HTML += b'r-color: black; padding: 4px; box-sizing: border-box; margin'
HTML += b'-top: 32px; margin-bottom: 32px; -webkit-box-shadow: 0px 0px'
HTML += b' 6px 3px #e8e8e8; box-shadow: 0px 0px 6px 3px #e8e8e8; overf'
HTML += b'low-x: auto; overflow-y: visible; } .pysell-button-group { d'
HTML += b'isplay: flex; align-items: center; justify-content: center; '
HTML += b'text-align: center; margin-left: auto; margin-right: auto; }'
HTML += b' @media (min-width: 800px) { .pysell-question { border-radiu'
HTML += b's: 6px; padding: 16px; margin: 16px; border-left-style: soli'
HTML += b'd; border-right-style: solid; } } .pysell-question-feedback '
HTML += b'{ opacity: 1.8; z-index: 10; display: none; position: absolu'
HTML += b'te; pointer-events: none; left: 0%; top: 0%; width: 100%; he'
HTML += b'ight: 100%; text-align: center; font-size: 4vw; text-shadow:'
HTML += b' 0px 0px 18px rgba(0, 0, 0, 0.15); background-color: rgba(25'
HTML += b'5, 255, 255, 0.95); padding: 10px; justify-content: center; '
HTML += b'align-items: center; } .pysell-question-title { user-select:'
HTML += b' none; font-size: 24pt; } .pysell-code { font-family: "Couri'
HTML += b'er New", Courier, monospace; color: black; background-color:'
HTML += b' rgb(235, 235, 235); padding: 2px 5px; border-radius: 5px; m'
HTML += b'argin: 1px 2px; } .pysell-code-block { font-family: "Courier'
HTML += b' New", Courier, monospace; color: black; background-color: r'
HTML += b'gb(235, 235, 235); padding: 2px 5px; border-radius: 5px; mar'
HTML += b'gin: 2px 2px 10px 2px; } .pysell-debug-code { font-family: "'
HTML += b'Courier New", Courier, monospace; padding: 4px; margin-botto'
HTML += b'm: 5px; background-color: black; color: white; border-radius'
HTML += b': 5px; opacity: 0.85; overflow-x: scroll; } .pysell-debug-in'
HTML += b'fo { text-align: end; font-size: 10pt; margin-top: 2px; colo'
HTML += b'r: rgb(64, 64, 64); } .pysell-input-field { position: relati'
HTML += b've; width: 32px; height: 24px; font-size: 14pt; border-style'
HTML += b': solid; border-color: black; border-radius: 5px; border-wid'
HTML += b'th: 0.2; padding-left: 5px; padding-right: 5px; outline-colo'
HTML += b'r: black; background-color: transparent; margin: 1px; } .pys'
HTML += b'ell-input-field:focus { outline-color: maroon; } .pysell-equ'
HTML += b'ation-preview { position: absolute; top: 120%; left: 0%; pad'
HTML += b'ding-left: 8px; padding-right: 8px; padding-top: 4px; paddin'
HTML += b'g-bottom: 4px; background-color: rgb(128, 0, 0); border-radi'
HTML += b'us: 5px; font-size: 12pt; color: white; text-align: start; z'
HTML += b'-index: 1000; opacity: 0.95; } .pysell-button { padding-left'
HTML += b': 8px; padding-right: 8px; padding-top: 5px; padding-bottom:'
HTML += b' 5px; font-size: 12pt; background-color: rgb(0, 150, 0); col'
HTML += b'or: white; border-style: none; border-radius: 4px; height: 3'
HTML += b'6px; cursor: pointer; } .pysell-start-button { background-co'
HTML += b'lor: var(--pysell-green); font-size: "x-large"; } .pysell-ma'
HTML += b'trix-resize-button { width: 20px; background-color: black; c'
HTML += b'olor: #fff; text-align: center; border-radius: 3px; position'
HTML += b': absolute; z-index: 1; height: 20px; cursor: pointer; overf'
HTML += b'low: hidden; font-size: 16px; } .pysell-timer { position: fi'
HTML += b'xed; left: 0; top: 0; padding: 5px 15px; background-color: r'
HTML += b'gb(32, 32, 32); color: white; opacity: 0.4; font-size: 32pt;'
HTML += b' z-index: 1000; border-bottom-right-radius: 10px; text-align'
HTML += b': center; font-family: "Courier New", Courier, monospace; } '
HTML += b'.pysell-eval { text-align: center; background-color: black; '
HTML += b'color: white; padding: 10px; } @media (min-width: 800px) { .'
HTML += b'pysell-eval { border-radius: 10px; } } .pysell-timer-info { '
HTML += b'font-size: x-large; text-align: center; background-color: bl'
HTML += b'ack; color: white; padding: 20px 10px; user-select: none; } '
HTML += b'@media (min-width: 800px) { .pysell-timer-info { border-radi'
HTML += b'us: 6px; } } </style> </head> <body> <div id="timer"></div> '
HTML += b'<div id="header"></div> <br /> <div class="contents"> <div i'
HTML += b'd="timer-info"></div> <div id="questions"></div> <div id="ti'
HTML += b'mer-footer"></div> <div id="timer-eval"></div> </div> <br />'
HTML += b'<br /><br /><br /> <div class="footer"> <div class="contents'
HTML += b'"> <span id="date"></span> &mdash; This quiz was developed u'
HTML += b'sing pySELL, a Python-based Simple E-Learning Language &mdas'
HTML += b'h; <a href="https://pysell.org" style="color: var(--grey)" >'
HTML += b'https://pysell.org</a > <br /> <div style="width: 100%; disp'
HTML += b'lay: flex; justify-content: center"> <img style="max-width: '
HTML += b'48px; padding: 16px 0px" src="data:image/svg+xml;base64,PD94'
HTML += b'bWwgdmVyc2lvbj0iMS4wIiBlbmNvZGluZz0iVVRGLTgiPz4KPCEtLSBDcmVh'
HTML += b'dGVkIHdpdGggSW5rc2NhcGUgKGh0dHA6Ly93d3cuaW5rc2NhcGUub3JnLykg'
HTML += b'LS0+Cjxzdmcgd2lkdGg9IjEwMG1tIiBoZWlnaHQ9IjEwMG1tIiB2ZXJzaW9u'
HTML += b'PSIxLjEiIHZpZXdCb3g9IjAgMCAxMDAgMTAwIiB4bWxucz0iaHR0cDovL3d3'
HTML += b'dy53My5vcmcvMjAwMC9zdmciIHhtbG5zOnhsaW5rPSJodHRwOi8vd3d3Lncz'
HTML += b'Lm9yZy8xOTk5L3hsaW5rIj4KIDxkZWZzPgogIDxsaW5lYXJHcmFkaWVudCBp'
HTML += b'ZD0ibGluZWFyR3JhZGllbnQzNjU4IiB4MT0iMjguNTI3IiB4Mj0iMTI4LjUz'
HTML += b'IiB5MT0iNzkuNjQ4IiB5Mj0iNzkuNjQ4IiBncmFkaWVudFRyYW5zZm9ybT0i'
HTML += b'bWF0cml4KDEuMDE2MSAwIDAgMS4wMTYxIC0yOS43OSAtMzAuOTI4KSIgZ3Jh'
HTML += b'ZGllbnRVbml0cz0idXNlclNwYWNlT25Vc2UiPgogICA8c3RvcCBzdG9wLWNv'
HTML += b'bG9yPSIjNTkwMDVlIiBvZmZzZXQ9IjAiLz4KICAgPHN0b3Agc3RvcC1jb2xv'
HTML += b'cj0iI2FkMDA3ZiIgb2Zmc2V0PSIxIi8+CiAgPC9saW5lYXJHcmFkaWVudD4K'
HTML += b'IDwvZGVmcz4KIDxyZWN0IHdpZHRoPSIxMDAiIGhlaWdodD0iMTAwIiByeT0i'
HTML += b'MCIgZmlsbD0idXJsKCNsaW5lYXJHcmFkaWVudDM2NTgpIi8+CiA8ZyBmaWxs'
HTML += b'PSIjZmZmIj4KICA8ZyB0cmFuc2Zvcm09Im1hdHJpeCguNDA3NDMgMCAwIC40'
HTML += b'MDc0MyAtNDIuODQyIC0zNi4xMzYpIiBzdHJva2Utd2lkdGg9IjMuNzc5NSIg'
HTML += b'c3R5bGU9InNoYXBlLWluc2lkZTp1cmwoI3JlY3Q5NTItNyk7c2hhcGUtcGFk'
HTML += b'ZGluZzo2LjUzMTQ0O3doaXRlLXNwYWNlOnByZSIgYXJpYS1sYWJlbD0iU0VM'
HTML += b'TCI+CiAgIDxwYXRoIGQ9Im0xNzEuMDEgMjM4LjM5cS0yLjExMi0yLjY4OC01'
HTML += b'LjU2OC00LjIyNC0zLjM2LTEuNjMyLTYuNTI4LTEuNjMyLTEuNjMyIDAtMy4z'
HTML += b'NiAwLjI4OC0xLjYzMiAwLjI4OC0yLjk3NiAxLjE1Mi0xLjM0NCAwLjc2OC0y'
HTML += b'LjMwNCAyLjExMi0wLjg2NCAxLjI0OC0wLjg2NCAzLjI2NCAwIDEuNzI4IDAu'
HTML += b'NjcyIDIuODggMC43NjggMS4xNTIgMi4xMTIgMi4wMTYgMS40NCAwLjg2NCAz'
HTML += b'LjM2IDEuNjMyIDEuOTIgMC42NzIgNC4zMiAxLjQ0IDMuNDU2IDEuMTUyIDcu'
HTML += b'MiAyLjU5MiAzLjc0NCAxLjM0NCA2LjgxNiAzLjY0OHQ1LjA4OCA1Ljc2cTIu'
HTML += b'MDE2IDMuMzYgMi4wMTYgOC40NDggMCA1Ljg1Ni0yLjIwOCAxMC4xNzYtMi4x'
HTML += b'MTIgNC4yMjQtNS43NiA3LjAwOHQtOC4zNTIgNC4xMjgtOS42OTYgMS4zNDRx'
HTML += b'LTcuMjk2IDAtMTQuMTEyLTIuNDk2LTYuODE2LTIuNTkyLTExLjMyOC03LjI5'
HTML += b'NmwxMC43NTItMTAuOTQ0cTIuNDk2IDMuMDcyIDYuNTI4IDUuMTg0IDQuMTI4'
HTML += b'IDIuMDE2IDguMTYgMi4wMTYgMS44MjQgMCAzLjU1Mi0wLjM4NHQyLjk3Ni0x'
HTML += b'LjI0OHExLjM0NC0wLjg2NCAyLjExMi0yLjMwNHQwLjc2OC0zLjQ1NnEwLTEu'
HTML += b'OTItMC45Ni0zLjI2NHQtMi43ODQtMi40cS0xLjcyOC0xLjE1Mi00LjQxNi0y'
HTML += b'LjAxNi0yLjU5Mi0wLjk2LTUuOTUyLTIuMDE2LTMuMjY0LTEuMDU2LTYuNDMy'
HTML += b'LTIuNDk2LTMuMDcyLTEuNDQtNS41NjgtMy42NDgtMi40LTIuMzA0LTMuOTM2'
HTML += b'LTUuNDcyLTEuNDQtMy4yNjQtMS40NC03Ljg3MiAwLTUuNjY0IDIuMzA0LTku'
HTML += b'Njk2dDYuMDQ4LTYuNjI0IDguNDQ4LTMuNzQ0cTQuNzA0LTEuMjQ4IDkuNTA0'
HTML += b'LTEuMjQ4IDUuNzYgMCAxMS43MTIgMi4xMTIgNi4wNDggMi4xMTIgMTAuNTYg'
HTML += b'Ni4yNHoiLz4KICAgPHBhdGggZD0ibTE5MS44NCAyODguN3YtNjcuOTY4aDUy'
HTML += b'LjE5bC0xLjI5ODggMTMuOTJoLTM1LjA1MXYxMi43NjhoMzMuNDE5bC0xLjI5'
HTML += b'ODggMTMuMTUyaC0zMi4xMnYxNC4xMTJoMzEuNTg0bC0xLjI5ODggMTQuMDE2'
HTML += b'eiIvPgogIDwvZz4KICA8ZyB0cmFuc2Zvcm09Im1hdHJpeCguNDA3NDMgMCAw'
HTML += b'IC40MDc0MyAtNDAuMTY4IC03OC4wODIpIiBzdHJva2Utd2lkdGg9IjMuNzc5'
HTML += b'NSIgc3R5bGU9InNoYXBlLWluc2lkZTp1cmwoI3JlY3Q5NTItOS05KTtzaGFw'
HTML += b'ZS1wYWRkaW5nOjYuNTMxNDQ7d2hpdGUtc3BhY2U6cHJlIiBhcmlhLWxhYmVs'
HTML += b'PSJweSI+CiAgIDxwYXRoIGQ9Im0xODcuNDMgMjY0LjZxMCA0Ljk5Mi0xLjUz'
HTML += b'NiA5LjZ0LTQuNTEyIDguMTZxLTIuODggMy40NTYtNy4xMDQgNS41Njh0LTku'
HTML += b'NiAyLjExMnEtNC40MTYgMC04LjM1Mi0xLjcyOC0zLjkzNi0xLjgyNC02LjE0'
HTML += b'NC00Ljg5NmgtMC4xOTJ2MjguMzJoLTE1Ljc0NHYtNzAuODQ4aDE0Ljk3NnY1'
HTML += b'Ljg1NmgwLjI4OHEyLjIwOC0yLjg4IDYuMDQ4LTQuOTkyIDMuOTM2LTIuMjA4'
HTML += b'IDkuMjE2LTIuMjA4IDUuMTg0IDAgOS40MDggMi4wMTZ0Ny4xMDQgNS40NzJx'
HTML += b'Mi45NzYgMy40NTYgNC41MTIgOC4wNjQgMS42MzIgNC41MTIgMS42MzIgOS41'
HTML += b'MDR6bS0xNS4yNjQgMHEwLTIuMzA0LTAuNzY4LTQuNTEyLTAuNjcyLTIuMjA4'
HTML += b'LTIuMTEyLTMuODQtMS4zNDQtMS43MjgtMy40NTYtMi43ODR0LTQuODk2LTEu'
HTML += b'MDU2cS0yLjY4OCAwLTQuOCAxLjA1NnQtMy42NDggMi43ODRxLTEuNDQgMS43'
HTML += b'MjgtMi4zMDQgMy45MzYtMC43NjggMi4yMDgtMC43NjggNC41MTJ0MC43Njgg'
HTML += b'NC41MTJxMC44NjQgMi4yMDggMi4zMDQgMy45MzYgMS41MzYgMS43MjggMy42'
HTML += b'NDggMi43ODR0NC44IDEuMDU2cTIuNzg0IDAgNC44OTYtMS4wNTZ0My40NTYt'
HTML += b'Mi43ODRxMS40NC0xLjcyOCAyLjExMi0zLjkzNiAwLjc2OC0yLjMwNCAwLjc2'
HTML += b'OC00LjYwOHoiLz4KICAgPHBhdGggZD0ibTIyNC4yOSAyOTUuOXEtMS40NCAz'
HTML += b'Ljc0NC0zLjI2NCA2LjYyNC0xLjcyOCAyLjk3Ni00LjIyNCA0Ljk5Mi0yLjQg'
HTML += b'Mi4xMTItNS43NiAzLjE2OC0zLjI2NCAxLjA1Ni03Ljc3NiAxLjA1Ni0yLjIw'
HTML += b'OCAwLTQuNjA4LTAuMjg4LTIuMzA0LTAuMjg4LTQuMDMyLTAuNzY4bDEuNzI4'
HTML += b'LTEzLjI0OHExLjE1MiAwLjM4NCAyLjQ5NiAwLjU3NiAxLjQ0IDAuMjg4IDIu'
HTML += b'NTkyIDAuMjg4IDMuNjQ4IDAgNS4yOC0xLjcyOCAxLjYzMi0xLjYzMiAyLjc4'
HTML += b'NC00LjcwNGwxLjUzNi0zLjkzNi0xOS45NjgtNDcuMDRoMTcuNDcybDEwLjY1'
HTML += b'NiAzMC43MmgwLjI4OGw5LjUwNC0zMC43MmgxNi43MDR6Ii8+CiAgPC9nPgog'
HTML += b'IDxwYXRoIGQ9Im02OC4wOTYgMTUuNzc1aDcuODAyOWwtOC45ODU0IDY5Ljc5'
HTML += b'MWgtNy44MDN6IiBzdHJva2Utd2lkdGg9IjEuMTE3NiIvPgogIDxwYXRoIGQ9'
HTML += b'Im04My44NTMgMTUuNzQ4aDcuODAzbC04Ljk4NTQgNjkuNzkxaC03LjgwM3oi'
HTML += b'IHN0cm9rZS13aWR0aD0iMS4xMTc2Ii8+CiA8L2c+Cjwvc3ZnPgo=" /> </d'
HTML += b'iv> <span id="data-policy"></span> </div> </div>  <script>le'
HTML += b't debug = false; let quizSrc = {};var pysell=(()=>{var H=Obj'
HTML += b'ect.defineProperty;var pe=Object.getOwnPropertyDescriptor;va'
HTML += b'r de=Object.getOwnPropertyNames;var ue=Object.prototype.hasO'
HTML += b'wnProperty;var f=(r,e)=>H(r,"name",{value:e,configurable:!0}'
HTML += b');var me=(r,e)=>{for(var t in e)H(r,t,{get:e[t],enumerable:!'
HTML += b'0})},fe=(r,e,t,s)=>{if(e&&typeof e=="object"||typeof e=="fun'
HTML += b'ction")for(let i of de(e))!ue.call(r,i)&&i!==t&&H(r,i,{get:('
HTML += b')=>e[i],enumerable:!(s=pe(e,i))||s.enumerable});return r};va'
HTML += b'r ge=r=>fe(H({},"__esModule",{value:!0}),r);var ke={};me(ke,'
HTML += b'{init:()=>be});var F={en:"This page operates entirely in you'
HTML += b'r browser and does not store any data on external servers.",'
HTML += b'de:"Diese Seite wird in Ihrem Browser ausgef\\xFChrt und spei'
HTML += b'chert keine Daten auf Servern.",es:"Esta p\\xE1gina se ejecut'
HTML += b'a en su navegador y no almacena ning\\xFAn dato en los servid'
HTML += b'ores.",it:"Questa pagina viene eseguita nel browser e non me'
HTML += b'morizza alcun dato sui server.",fr:"Cette page fonctionne da'
HTML += b'ns votre navigateur et ne stocke aucune donn\\xE9e sur des se'
HTML += b'rveurs."},O={en:"* this page to receive a new set of randomi'
HTML += b'zed tasks.",de:"Sie k\\xF6nnen diese Seite *, um neue randomi'
HTML += b'sierte Aufgaben zu erhalten.",es:"Puedes * esta p\\xE1gina pa'
HTML += b'ra obtener nuevas tareas aleatorias.",it:"\\xC8 possibile * q'
HTML += b'uesta pagina per ottenere nuovi compiti randomizzati",fr:"Vo'
HTML += b'us pouvez * cette page pour obtenir de nouvelles t\\xE2ches a'
HTML += b'l\\xE9atoires"},K={en:"Refresh",de:"aktualisieren",es:"recarg'
HTML += b'ar",it:"ricaricare",fr:"recharger"},Z={en:["awesome","great"'
HTML += b',"well done","nice","you got it","good"],de:["super","gut ge'
HTML += b'macht","weiter so","richtig"],es:["impresionante","genial","'
HTML += b'correcto","bien hecho"],it:["fantastico","grande","corretto"'
HTML += b',"ben fatto"],fr:["g\\xE9nial","super","correct","bien fait"]'
HTML += b'},X={en:["please complete all fields"],de:["bitte alles ausf'
HTML += b'\\xFCllen"],es:["por favor, rellene todo"],it:["compilare tut'
HTML += b'to"],fr:["remplis tout s\'il te plait"]},Y={en:["try again","'
HTML += b'still some mistakes","wrong answer","no"],de:["leider falsch'
HTML += b'","nicht richtig","versuch\'s nochmal"],es:["int\\xE9ntalo de '
HTML += b'nuevo","todav\\xEDa algunos errores","respuesta incorrecta"],'
HTML += b'it:["riprova","ancora qualche errore","risposta sbagliata"],'
HTML += b'fr:["r\\xE9essayer","encore des erreurs","mauvaise r\\xE9ponse'
HTML += b'"]},G={en:"point(s)",de:"Punkt(e)",es:"punto(s)",it:"punto/i'
HTML += b'",fr:"point(s)"},J={en:"Evaluate now",de:"Jetzt auswerten",e'
HTML += b's:"Evaluar ahora",it:"Valuta ora",fr:"\\xC9valuer maintenant"'
HTML += b'},$={en:"Data Policy: This website does not collect, store, '
HTML += b'or process any personal data on external servers. All functi'
HTML += b'onality is executed locally in your browser, ensuring comple'
HTML += b'te privacy. No cookies are used, and no data is transmitted '
HTML += b'to or from the server. Your activity on this site remains en'
HTML += b'tirely private and local to your device.",de:"Datenschutzric'
HTML += b'htlinie: Diese Website sammelt, speichert oder verarbeitet k'
HTML += b'eine personenbezogenen Daten auf externen Servern. Alle Funk'
HTML += b'tionen werden lokal in Ihrem Browser ausgef\\xFChrt, um volls'
HTML += b't\\xE4ndige Privatsph\\xE4re zu gew\\xE4hrleisten. Es werden ke'
HTML += b'ine Cookies verwendet, und es werden keine Daten an den Serv'
HTML += b'er gesendet oder von diesem empfangen. Ihre Aktivit\\xE4t auf'
HTML += b' dieser Seite bleibt vollst\\xE4ndig privat und lokal auf Ihr'
HTML += b'em Ger\\xE4t.",es:"Pol\\xEDtica de datos: Este sitio web no re'
HTML += b'copila, almacena ni procesa ning\\xFAn dato personal en servi'
HTML += b'dores externos. Toda la funcionalidad se ejecuta localmente '
HTML += b'en su navegador, garantizando una privacidad completa. No se'
HTML += b' utilizan cookies y no se transmiten datos hacia o desde el '
HTML += b'servidor. Su actividad en este sitio permanece completamente'
HTML += b' privada y local en su dispositivo.",it:"Politica sui dati: '
HTML += b'Questo sito web non raccoglie, memorizza o elabora alcun dat'
HTML += b'o personale su server esterni. Tutte le funzionalit\\xE0 veng'
HTML += b'ono eseguite localmente nel tuo browser, garantendo una priv'
HTML += b'acy completa. Non vengono utilizzati cookie e nessun dato vi'
HTML += b'ene trasmesso da o verso il server. La tua attivit\\xE0 su qu'
HTML += b'esto sito rimane completamente privata e locale sul tuo disp'
HTML += b'ositivo.",fr:"Politique de confidentialit\\xE9: Ce site web n'
HTML += b'e collecte, ne stocke ni ne traite aucune donn\\xE9e personne'
HTML += b'lle sur des serveurs externes. Toutes les fonctionnalit\\xE9s'
HTML += b' sont ex\\xE9cut\\xE9es localement dans votre navigateur, gara'
HTML += b'ntissant une confidentialit\\xE9 totale. Aucun cookie n\\u2019'
HTML += b'est utilis\\xE9 et aucune donn\\xE9e n\\u2019est transmise vers'
HTML += b' ou depuis le serveur. Votre activit\\xE9 sur ce site reste e'
HTML += b'nti\\xE8rement priv\\xE9e et locale sur votre appareil."},ee={'
HTML += b'en:"You have a limited time to complete this quiz. The count'
HTML += b'down, displayed in minutes, is visible at the top-left of th'
HTML += b"e screen. When you're ready to begin, simply press the Start"
HTML += b' button.",de:"Die Zeit f\\xFCr dieses Quiz ist begrenzt. Der '
HTML += b'Countdown, in Minuten angezeigt, l\\xE4uft oben links auf dem'
HTML += b' Bildschirm. Mit dem Start-Button beginnt das Quiz.",es:"Tie'
HTML += b'nes un tiempo limitado para completar este cuestionario. La '
HTML += b'cuenta regresiva, mostrada en minutos, se encuentra en la pa'
HTML += b'rte superior izquierda de la pantalla. Cuando est\\xE9s listo'
HTML += b', simplemente presiona el bot\\xF3n de inicio.",it:"Hai un te'
HTML += b'mpo limitato per completare questo quiz. Il conto alla roves'
HTML += b'cia, visualizzato in minuti, \\xE8 visibile in alto a sinistr'
HTML += b'a dello schermo. Quando sei pronto, premi semplicemente il p'
HTML += b'ulsante Start.",fr:"Vous disposez d\\u2019un temps limit\\xE9 '
HTML += b'pour compl\\xE9ter ce quiz. Le compte \\xE0 rebours, affich\\xE'
HTML += b'9 en minutes, est visible en haut \\xE0 gauche de l\\u2019\\xE9'
HTML += b'cran. Lorsque vous \\xEAtes pr\\xEAt, appuyez simplement sur l'
HTML += b'e bouton D\\xE9marrer."};function w(r=[]){let e=document.crea'
HTML += b'teElement("div");return e.append(...r),e}f(w,"genDiv");funct'
HTML += b'ion te(r=[]){let e=document.createElement("ul");return e.app'
HTML += b'end(...r),e}f(te,"genUl");function ie(r){let e=document.crea'
HTML += b'teElement("li");return e.appendChild(r),e}f(ie,"genLi");func'
HTML += b'tion W(r){let e=document.createElement("input");return e.spe'
HTML += b'llcheck=!1,e.type="text",e.classList.add("pysell-input-field'
HTML += b'"),e.style.width=r+"px",e}f(W,"genInputField");function se()'
HTML += b'{let r=document.createElement("button");return r.type="butto'
HTML += b'n",r.classList.add("pysell-button"),r}f(se,"genButton");func'
HTML += b'tion k(r,e=[]){let t=document.createElement("span");return e'
HTML += b'.length>0?t.append(...e):t.innerHTML=r,t}f(k,"genSpan");func'
HTML += b'tion N(r,e,t=!1){katex.render(e,r,{throwOnError:!1,displayMo'
HTML += b'de:t,macros:{"\\\\RR":"\\\\mathbb{R}","\\\\NN":"\\\\mathbb{N}","\\\\QQ'
HTML += b'":"\\\\mathbb{Q}","\\\\ZZ":"\\\\mathbb{Z}","\\\\CC":"\\\\mathbb{C}"}})'
HTML += b'}f(N,"updateMathElement");function T(r,e=!1){let t=document.'
HTML += b'createElement("span");return N(t,r,e),t}f(T,"genMathSpan");f'
HTML += b'unction ne(r,e){let t=Array(e.length+1).fill(null).map(()=>A'
HTML += b'rray(r.length+1).fill(null));for(let s=0;s<=r.length;s+=1)t['
HTML += b'0][s]=s;for(let s=0;s<=e.length;s+=1)t[s][0]=s;for(let s=1;s'
HTML += b'<=e.length;s+=1)for(let i=1;i<=r.length;i+=1){let o=r[i-1]=='
HTML += b'=e[s-1]?0:1;t[s][i]=Math.min(t[s][i-1]+1,t[s-1][i]+1,t[s-1]['
HTML += b'i-1]+o)}return t[e.length][r.length]}f(ne,"levenshteinDistan'
HTML += b'ce");var re=\'<svg xmlns="http://www.w3.org/2000/svg" height='
HTML += b'"28" viewBox="0 0 448 512"><path fill="black" d="M384 80c8.8'
HTML += b' 0 16 7.2 16 16V416c0 8.8-7.2 16-16 16H64c-8.8 0-16-7.2-16-1'
HTML += b'6V96c0-8.8 7.2-16 16-16H384zM64 32C28.7 32 0 60.7 0 96V416c0'
HTML += b' 35.3 28.7 64 64 64H384c35.3 0 64-28.7 64-64V96c0-35.3-28.7-'
HTML += b'64-64-64H64z"/></svg>\',ae=\'<svg xmlns="http://www.w3.org/200'
HTML += b'0/svg" height="28" viewBox="0 0 448 512"><path fill="black" '
HTML += b'd="M64 80c-8.8 0-16 7.2-16 16V416c0 8.8 7.2 16 16 16H384c8.8'
HTML += b' 0 16-7.2 16-16V96c0-8.8-7.2-16-16-16H64zM0 96C0 60.7 28.7 3'
HTML += b'2 64 32H384c35.3 0 64 28.7 64 64V416c0 35.3-28.7 64-64 64H64'
HTML += b'c-35.3 0-64-28.7-64-64V96zM337 209L209 337c-9.4 9.4-24.6 9.4'
HTML += b'-33.9 0l-64-64c-9.4-9.4-9.4-24.6 0-33.9s24.6-9.4 33.9 0l47 4'
HTML += b'7L303 175c9.4-9.4 24.6-9.4 33.9 0s9.4 24.6 0 33.9z"/>\',le=\'<'
HTML += b'svg xmlns="http://www.w3.org/2000/svg" height="28" viewBox="'
HTML += b'0 0 512 512"><path fill="black" d="M464 256A208 208 0 1 0 48'
HTML += b' 256a208 208 0 1 0 416 0zM0 256a256 256 0 1 1 512 0A256 256 '
HTML += b'0 1 1 0 256z"/></svg>\',oe=\'<svg xmlns="http://www.w3.org/200'
HTML += b'0/svg" height="28" viewBox="0 0 512 512"><path fill="black" '
HTML += b'd="M256 48a208 208 0 1 1 0 416 208 208 0 1 1 0-416zm0 464A25'
HTML += b'6 256 0 1 0 256 0a256 256 0 1 0 0 512zM369 209c9.4-9.4 9.4-2'
HTML += b'4.6 0-33.9s-24.6-9.4-33.9 0l-111 111-47-47c-9.4-9.4-24.6-9.4'
HTML += b'-33.9 0s-9.4 24.6 0 33.9l64 64c9.4 9.4 24.6 9.4 33.9 0L369 2'
HTML += b'09z"/></svg>\',D=\'<svg xmlns="http://www.w3.org/2000/svg" wid'
HTML += b'th="50" height="25" viewBox="0 0 384 512" fill="white"><path'
HTML += b' d="M73 39c-14.8-9.1-33.4-9.4-48.5-.9S0 62.6 0 80V432c0 17.4'
HTML += b' 9.4 33.4 24.5 41.9s33.7 8.1 48.5-.9L361 297c14.3-8.7 23-24.'
HTML += b'2 23-41s-8.7-32.2-23-41L73 39z"/></svg>\',Q=\'<svg xmlns="http'
HTML += b'://www.w3.org/2000/svg" width="50" height="25" viewBox="0 0 '
HTML += b'512 512" fill="white"><path d="M0 224c0 17.7 14.3 32 32 32s3'
HTML += b'2-14.3 32-32c0-53 43-96 96-96H320v32c0 12.9 7.8 24.6 19.8 29'
HTML += b'.6s25.7 2.2 34.9-6.9l64-64c12.5-12.5 12.5-32.8 0-45.3l-64-64'
HTML += b'c-9.2-9.2-22.9-11.9-34.9-6.9S320 19.1 320 32V64H160C71.6 64 '
HTML += b'0 135.6 0 224zm512 64c0-17.7-14.3-32-32-32s-32 14.3-32 32c0 '
HTML += b'53-43 96-96 96H192V352c0-12.9-7.8-24.6-19.8-29.6s-25.7-2.2-3'
HTML += b'4.9 6.9l-64 64c-12.5 12.5-12.5 32.8 0 45.3l64 64c9.2 9.2 22.'
HTML += b'9 11.9 34.9 6.9s19.8-16.6 19.8-29.6V448H352c88.4 0 160-71.6 '
HTML += b'160-160z"/></svg>\';function P(r,e=!1){let t=new Array(r);for'
HTML += b'(let s=0;s<r;s++)t[s]=s;if(e)for(let s=0;s<r;s++){let i=Math'
HTML += b'.floor(Math.random()*r),o=Math.floor(Math.random()*r),l=t[i]'
HTML += b';t[i]=t[o],t[o]=l}return t}f(P,"range");function _(r,e,t=-1)'
HTML += b'{if(t<0&&(t=r.length),t==1){e.push([...r]);return}for(let s='
HTML += b'0;s<t;s++){_(r,e,t-1);let i=t%2==0?s:0,o=r[i];r[i]=r[t-1],r['
HTML += b't-1]=o}}f(_,"heapsAlgorithm");var L=class r{static{f(this,"M'
HTML += b'atrix")}constructor(e,t){this.m=e,this.n=t,this.v=new Array('
HTML += b'e*t).fill("0")}getElement(e,t){return e<0||e>=this.m||t<0||t'
HTML += b'>=this.n?"":this.v[e*this.n+t]}resize(e,t,s){if(e<1||e>50||t'
HTML += b'<1||t>50)return!1;let i=new r(e,t);i.v.fill(s);for(let o=0;o'
HTML += b'<i.m;o++)for(let l=0;l<i.n;l++)i.v[o*i.n+l]=this.getElement('
HTML += b'o,l);return this.fromMatrix(i),!0}fromMatrix(e){this.m=e.m,t'
HTML += b'his.n=e.n,this.v=[...e.v]}fromString(e){this.m=e.split("],")'
HTML += b'.length,this.v=e.replaceAll("[","").replaceAll("]","").split'
HTML += b'(",").map(t=>t.trim()),this.n=this.v.length/this.m}getMaxCel'
HTML += b'lStrlen(){let e=0;for(let t of this.v)t.length>e&&(e=t.lengt'
HTML += b'h);return e}toTeXString(e=!1,t=!0){let s="";t?s+=e?"\\\\left[\\'
HTML += b'\\begin{array}":"\\\\begin{bmatrix}":s+=e?"\\\\left(\\\\begin{array'
HTML += b'}":"\\\\begin{pmatrix}",e&&(s+="{"+"c".repeat(this.n-1)+"|c}")'
HTML += b';for(let i=0;i<this.m;i++){for(let o=0;o<this.n;o++){o>0&&(s'
HTML += b'+="&");let l=this.getElement(i,o);try{l=b.parse(l).toTexStri'
HTML += b'ng()}catch{}s+=l}s+="\\\\\\\\"}return t?s+=e?"\\\\end{array}\\\\righ'
HTML += b't]":"\\\\end{bmatrix}":s+=e?"\\\\end{array}\\\\right)":"\\\\end{pmat'
HTML += b'rix}",s}},b=class r{static{f(this,"Term")}constructor(){this'
HTML += b'.root=null,this.src="",this.token="",this.skippedWhiteSpace='
HTML += b'!1,this.pos=0}clone(){let e=new r;return e.root=this.root.cl'
HTML += b'one(),e}getVars(e,t="",s=null){if(s==null&&(s=this.root),s.o'
HTML += b'p.startsWith("var:")){let i=s.op.substring(4);(t.length==0||'
HTML += b't.length>0&&i.startsWith(t))&&e.add(i)}for(let i of s.c)this'
HTML += b'.getVars(e,t,i)}setVars(e,t=null){t==null&&(t=this.root);for'
HTML += b'(let s of t.c)this.setVars(e,s);if(t.op.startsWith("var:")){'
HTML += b'let s=t.op.substring(4);if(s in e){let i=e[s].clone();t.op=i'
HTML += b'.op,t.c=i.c,t.re=i.re,t.im=i.im}}}renameVar(e,t,s=null){s==n'
HTML += b'ull&&(s=this.root);for(let i of s.c)this.renameVar(e,t,i);s.'
HTML += b'op.startsWith("var:")&&s.op.substring(4)===e&&(s.op="var:"+t'
HTML += b')}eval(e,t=null){let i=a.const(),o=0,l=0,h=null;switch(t==nu'
HTML += b'll&&(t=this.root),t.op){case"const":i=t;break;case"+":case"-'
HTML += b'":case"*":case"/":case"^":{let n=this.eval(e,t.c[0]),c=this.'
HTML += b'eval(e,t.c[1]);switch(t.op){case"+":i.re=n.re+c.re,i.im=n.im'
HTML += b'+c.im;break;case"-":i.re=n.re-c.re,i.im=n.im-c.im;break;case'
HTML += b'"*":i.re=n.re*c.re-n.im*c.im,i.im=n.re*c.im+n.im*c.re;break;'
HTML += b'case"/":o=c.re*c.re+c.im*c.im,i.re=(n.re*c.re+n.im*c.im)/o,i'
HTML += b'.im=(n.im*c.re-n.re*c.im)/o;break;case"^":h=new a("exp",[new'
HTML += b' a("*",[c,new a("ln",[n])])]),i=this.eval(e,h);break}break}c'
HTML += b'ase".-":case"abs":case"acos":case"acosh":case"asin":case"asi'
HTML += b'nh":case"atan":case"atanh":case"ceil":case"cos":case"cosh":c'
HTML += b'ase"cot":case"exp":case"floor":case"ln":case"log":case"log10'
HTML += b'":case"log2":case"round":case"sin":case"sinc":case"sinh":cas'
HTML += b'e"sqrt":case"tan":case"tanh":{let n=this.eval(e,t.c[0]);swit'
HTML += b'ch(t.op){case".-":i.re=-n.re,i.im=-n.im;break;case"abs":i.re'
HTML += b'=Math.sqrt(n.re*n.re+n.im*n.im),i.im=0;break;case"acos":h=ne'
HTML += b'w a("*",[a.const(0,-1),new a("ln",[new a("+",[a.const(0,1),n'
HTML += b'ew a("sqrt",[new a("-",[a.const(1,0),new a("*",[n,n])])])])]'
HTML += b')]),i=this.eval(e,h);break;case"acosh":h=new a("*",[n,new a('
HTML += b'"sqrt",[new a("-",[new a("*",[n,n]),a.const(1,0)])])]),i=thi'
HTML += b's.eval(e,h);break;case"asin":h=new a("*",[a.const(0,-1),new '
HTML += b'a("ln",[new a("+",[new a("*",[a.const(0,1),n]),new a("sqrt",'
HTML += b'[new a("-",[a.const(1,0),new a("*",[n,n])])])])])]),i=this.e'
HTML += b'val(e,h);break;case"asinh":h=new a("*",[n,new a("sqrt",[new '
HTML += b'a("+",[new a("*",[n,n]),a.const(1,0)])])]),i=this.eval(e,h);'
HTML += b'break;case"atan":h=new a("*",[a.const(0,.5),new a("ln",[new '
HTML += b'a("/",[new a("-",[a.const(0,1),new a("*",[a.const(0,1),n])])'
HTML += b',new a("+",[a.const(0,1),new a("*",[a.const(0,1),n])])])])])'
HTML += b',i=this.eval(e,h);break;case"atanh":h=new a("*",[a.const(.5,'
HTML += b'0),new a("ln",[new a("/",[new a("+",[a.const(1,0),n]),new a('
HTML += b'"-",[a.const(1,0),n])])])]),i=this.eval(e,h);break;case"ceil'
HTML += b'":i.re=Math.ceil(n.re),i.im=Math.ceil(n.im);break;case"cos":'
HTML += b'i.re=Math.cos(n.re)*Math.cosh(n.im),i.im=-Math.sin(n.re)*Mat'
HTML += b'h.sinh(n.im);break;case"cosh":h=new a("*",[a.const(.5,0),new'
HTML += b' a("+",[new a("exp",[n]),new a("exp",[new a(".-",[n])])])]),'
HTML += b'i=this.eval(e,h);break;case"cot":o=Math.sin(n.re)*Math.sin(n'
HTML += b'.re)+Math.sinh(n.im)*Math.sinh(n.im),i.re=Math.sin(n.re)*Mat'
HTML += b'h.cos(n.re)/o,i.im=-(Math.sinh(n.im)*Math.cosh(n.im))/o;brea'
HTML += b'k;case"exp":i.re=Math.exp(n.re)*Math.cos(n.im),i.im=Math.exp'
HTML += b'(n.re)*Math.sin(n.im);break;case"floor":i.re=Math.floor(n.re'
HTML += b'),i.im=Math.floor(n.im);break;case"ln":case"log":i.re=Math.l'
HTML += b'og(Math.sqrt(n.re*n.re+n.im*n.im)),o=Math.abs(n.im)<1e-9?0:n'
HTML += b'.im,i.im=Math.atan2(o,n.re);break;case"log10":h=new a("/",[n'
HTML += b'ew a("ln",[n]),new a("ln",[a.const(10)])]),i=this.eval(e,h);'
HTML += b'break;case"log2":h=new a("/",[new a("ln",[n]),new a("ln",[a.'
HTML += b'const(2)])]),i=this.eval(e,h);break;case"round":i.re=Math.ro'
HTML += b'und(n.re),i.im=Math.round(n.im);break;case"sin":i.re=Math.si'
HTML += b'n(n.re)*Math.cosh(n.im),i.im=Math.cos(n.re)*Math.sinh(n.im);'
HTML += b'break;case"sinc":h=new a("/",[new a("sin",[n]),n]),i=this.ev'
HTML += b'al(e,h);break;case"sinh":h=new a("*",[a.const(.5,0),new a("-'
HTML += b'",[new a("exp",[n]),new a("exp",[new a(".-",[n])])])]),i=thi'
HTML += b's.eval(e,h);break;case"sqrt":h=new a("^",[n,a.const(.5)]),i='
HTML += b'this.eval(e,h);break;case"tan":o=Math.cos(n.re)*Math.cos(n.r'
HTML += b'e)+Math.sinh(n.im)*Math.sinh(n.im),i.re=Math.sin(n.re)*Math.'
HTML += b'cos(n.re)/o,i.im=Math.sinh(n.im)*Math.cosh(n.im)/o;break;cas'
HTML += b'e"tanh":h=new a("/",[new a("-",[new a("exp",[n]),new a("exp"'
HTML += b',[new a(".-",[n])])]),new a("+",[new a("exp",[n]),new a("exp'
HTML += b'",[new a(".-",[n])])])]),i=this.eval(e,h);break}break}defaul'
HTML += b't:if(t.op.startsWith("var:")){let n=t.op.substring(4);if(n=='
HTML += b'="pi")return a.const(Math.PI);if(n==="e")return a.const(Math'
HTML += b'.E);if(n==="i")return a.const(0,1);if(n==="true")return a.co'
HTML += b'nst(1);if(n==="false")return a.const(0);if(n in e)return e[n'
HTML += b'];throw new Error("eval-error: unknown variable \'"+n+"\'")}el'
HTML += b'se throw new Error("UNIMPLEMENTED eval \'"+t.op+"\'")}return i'
HTML += b'}static parse(e){let t=new r;if(t.src=e,t.token="",t.skipped'
HTML += b'WhiteSpace=!1,t.pos=0,t.next(),t.root=t.parseExpr(!1),t.toke'
HTML += b'n!=="")throw new Error("remaining tokens: "+t.token+"...");r'
HTML += b'eturn t}parseExpr(e){return this.parseAdd(e)}parseAdd(e){let'
HTML += b' t=this.parseMul(e);for(;["+","-"].includes(this.token)&&!(e'
HTML += b'&&this.skippedWhiteSpace);){let s=this.token;this.next(),t=n'
HTML += b'ew a(s,[t,this.parseMul(e)])}return t}parseMul(e){let t=this'
HTML += b'.parsePow(e);for(;!(e&&this.skippedWhiteSpace);){let s="*";i'
HTML += b'f(["*","/"].includes(this.token))s=this.token,this.next();el'
HTML += b'se if(!e&&this.token==="(")s="*";else if(this.token.length>0'
HTML += b'&&(this.isAlpha(this.token[0])||this.isNum(this.token[0])))s'
HTML += b'="*";else break;t=new a(s,[t,this.parsePow(e)])}return t}par'
HTML += b'sePow(e){let t=this.parseUnary(e);for(;["^"].includes(this.t'
HTML += b'oken)&&!(e&&this.skippedWhiteSpace);){let s=this.token;this.'
HTML += b'next(),t=new a(s,[t,this.parseUnary(e)])}return t}parseUnary'
HTML += b'(e){return this.token==="-"?(this.next(),new a(".-",[this.pa'
HTML += b'rseMul(e)])):this.parseInfix(e)}parseInfix(e){if(this.token.'
HTML += b'length==0)throw new Error("expected unary");if(this.isNum(th'
HTML += b'is.token[0])){let t=this.token;return this.next(),this.token'
HTML += b'==="."&&(t+=".",this.next(),this.token.length>0&&(t+=this.to'
HTML += b'ken,this.next())),new a("const",[],parseFloat(t))}else if(th'
HTML += b'is.fun1().length>0){let t=this.fun1();this.next(t.length);le'
HTML += b't s=null;if(this.token==="(")if(this.next(),s=this.parseExpr'
HTML += b'(e),this.token+="",this.token===")")this.next();else throw E'
HTML += b'rror("expected \')\'");else s=this.parseMul(!0);return new a(t'
HTML += b',[s])}else if(this.token==="("){this.next();let t=this.parse'
HTML += b'Expr(e);if(this.token+="",this.token===")")this.next();else '
HTML += b'throw Error("expected \')\'");return t.explicitParentheses=!0,'
HTML += b't}else if(this.token==="|"){this.next();let t=this.parseExpr'
HTML += b'(e);if(this.token+="",this.token==="|")this.next();else thro'
HTML += b'w Error("expected \'|\'");return new a("abs",[t])}else if(this'
HTML += b'.isAlpha(this.token[0])){let t="";return this.token.startsWi'
HTML += b'th("pi")?t="pi":this.token.startsWith("true")?t="true":this.'
HTML += b'token.startsWith("false")?t="false":this.token.startsWith("C'
HTML += b'1")?t="C1":this.token.startsWith("C2")?t="C2":t=this.token[0'
HTML += b'],t==="I"&&(t="i"),this.next(t.length),new a("var:"+t,[])}el'
HTML += b'se throw new Error("expected unary")}static compare(e,t,s={}'
HTML += b'){let l=new Set;e.getVars(l),t.getVars(l);for(let h=0;h<10;h'
HTML += b'++){let n={};for(let g of l)g in s?n[g]=s[g]:n[g]=a.const(Ma'
HTML += b'th.random(),Math.random());let c=e.eval(n),p=t.eval(n),m=c.r'
HTML += b'e-p.re,u=c.im-p.im;if(Math.sqrt(m*m+u*u)>1e-9)return!1}retur'
HTML += b'n!0}fun1(){let e=["abs","acos","acosh","asin","asinh","atan"'
HTML += b',"atanh","ceil","cos","cosh","cot","exp","floor","ln","log",'
HTML += b'"log10","log2","round","sin","sinc","sinh","sqrt","tan","tan'
HTML += b'h"];for(let t of e)if(this.token.toLowerCase().startsWith(t)'
HTML += b')return t;return""}next(e=-1){if(e>0&&this.token.length>e){t'
HTML += b'his.token=this.token.substring(e),this.skippedWhiteSpace=!1;'
HTML += b'return}this.token="";let t=!1,s=this.src.length;for(this.ski'
HTML += b'ppedWhiteSpace=!1;this.pos<s&&`\t\n `.includes(this.src[this.p'
HTML += b'os]);)this.skippedWhiteSpace=!0,this.pos++;for(;!t&&this.pos'
HTML += b'<s;){let i=this.src[this.pos];if(this.token.length>0&&(this.'
HTML += b'isNum(this.token[0])&&this.isAlpha(i)||this.isAlpha(this.tok'
HTML += b'en[0])&&this.isNum(i))&&this.token!="C")return;if(`^%#*$()[]'
HTML += b'{},.:;+-*/_!<>=?|\t\n `.includes(i)){if(this.token.length>0)re'
HTML += b'turn;t=!0}`\t\n `.includes(i)==!1&&(this.token+=i),this.pos++}'
HTML += b'}isNum(e){return e.charCodeAt(0)>=48&&e.charCodeAt(0)<=57}is'
HTML += b'Alpha(e){return e.charCodeAt(0)>=65&&e.charCodeAt(0)<=90||e.'
HTML += b'charCodeAt(0)>=97&&e.charCodeAt(0)<=122||e==="_"}toString(){'
HTML += b'return this.root==null?"":this.root.toString()}toTexString()'
HTML += b'{return this.root==null?"":this.root.toTexString()}},a=class'
HTML += b' r{static{f(this,"TermNode")}constructor(e,t,s=0,i=0){this.o'
HTML += b'p=e,this.c=t,this.re=s,this.im=i,this.explicitParentheses=!1'
HTML += b'}clone(){let e=new r(this.op,this.c.map(t=>t.clone()),this.r'
HTML += b'e,this.im);return e.explicitParentheses=this.explicitParenth'
HTML += b'eses,e}static const(e=0,t=0){return new r("const",[],e,t)}co'
HTML += b'mpare(e,t=0,s=1e-9){let i=this.re-e,o=this.im-t;return Math.'
HTML += b'sqrt(i*i+o*o)<s}toString(){let e="";if(this.op==="const"){le'
HTML += b't t=Math.abs(this.re)>1e-14,s=Math.abs(this.im)>1e-14;t&&s&&'
HTML += b'this.im>=0?e="("+this.re+"+"+this.im+"i)":t&&s&&this.im<0?e='
HTML += b'"("+this.re+"-"+-this.im+"i)":t&&this.re>0?e=""+this.re:t&&t'
HTML += b'his.re<0?e="("+this.re+")":s?e="("+this.im+"i)":e="0"}else t'
HTML += b'his.op.startsWith("var")?e=this.op.split(":")[1]:this.c.leng'
HTML += b'th==1?e=(this.op===".-"?"-":this.op)+"("+this.c.toString()+"'
HTML += b')":e="("+this.c.map(t=>t.toString()).join(this.op)+")";retur'
HTML += b'n e}toTexString(e=!1){let s="";switch(this.op){case"const":{'
HTML += b'let i=Math.abs(this.re)>1e-9,o=Math.abs(this.im)>1e-9,l=i?""'
HTML += b'+this.re:"",h=o?""+this.im+"i":"";h==="1i"?h="i":h==="-1i"&&'
HTML += b'(h="-i"),!i&&!o?s="0":(o&&this.im>=0&&i&&(h="+"+h),s=l+h);br'
HTML += b'eak}case".-":s="-"+this.c[0].toTexString();break;case"+":cas'
HTML += b'e"-":case"*":case"^":{let i=this.c[0].toTexString(),o=this.c'
HTML += b'[1].toTexString(),l=this.op==="*"?"\\\\cdot ":this.op;s="{"+i+'
HTML += b'"}"+l+"{"+o+"}";break}case"/":{let i=this.c[0].toTexString(!'
HTML += b'0),o=this.c[1].toTexString(!0);s="\\\\frac{"+i+"}{"+o+"}";brea'
HTML += b'k}case"floor":{let i=this.c[0].toTexString(!0);s+="\\\\"+this.'
HTML += b'op+"\\\\left\\\\lfloor"+i+"\\\\right\\\\rfloor";break}case"ceil":{le'
HTML += b't i=this.c[0].toTexString(!0);s+="\\\\"+this.op+"\\\\left\\\\lceil'
HTML += b'"+i+"\\\\right\\\\rceil";break}case"round":{let i=this.c[0].toTe'
HTML += b'xString(!0);s+="\\\\"+this.op+"\\\\left["+i+"\\\\right]";break}cas'
HTML += b'e"acos":case"acosh":case"asin":case"asinh":case"atan":case"a'
HTML += b'tanh":case"cos":case"cosh":case"cot":case"exp":case"ln":case'
HTML += b'"log":case"log10":case"log2":case"sin":case"sinc":case"sinh"'
HTML += b':case"tan":case"tanh":{let i=this.c[0].toTexString(!0);s+="\\'
HTML += b'\\"+this.op+"\\\\left("+i+"\\\\right)";break}case"sqrt":{let i=th'
HTML += b'is.c[0].toTexString(!0);s+="\\\\"+this.op+"{"+i+"}";break}case'
HTML += b'"abs":{let i=this.c[0].toTexString(!0);s+="\\\\left|"+i+"\\\\rig'
HTML += b'ht|";break}default:if(this.op.startsWith("var:")){let i=this'
HTML += b'.op.substring(4);switch(i){case"pi":i="\\\\pi";break}s=" "+i+"'
HTML += b' "}else{let i="warning: Node.toString(..):";i+=" unimplement'
HTML += b'ed operator \'"+this.op+"\'",console.log(i),s=this.op,this.c.l'
HTML += b'ength>0&&(s+="\\\\left({"+this.c.map(o=>o.toTexString(!0)).joi'
HTML += b'n(",")+"}\\\\right)")}}return!e&&this.explicitParentheses&&(s='
HTML += b'"\\\\left({"+s+"}\\\\right)"),s}};function he(r,e){let t=1e-9;if'
HTML += b'(b.compare(r,e))return!0;r=r.clone(),e=e.clone(),U(r.root),U'
HTML += b'(e.root);let s=new Set;r.getVars(s),e.getVars(s);let i=[],o='
HTML += b'[];for(let n of s.keys())n.startsWith("C")?i.push(n):o.push('
HTML += b'n);let l=i.length;for(let n=0;n<l;n++){let c=i[n];r.renameVa'
HTML += b'r(c,"_C"+n),e.renameVar(c,"_C"+n)}for(let n=0;n<l;n++)r.rena'
HTML += b'meVar("_C"+n,"C"+n),e.renameVar("_C"+n,"C"+n);i=[];for(let n'
HTML += b'=0;n<l;n++)i.push("C"+n);let h=[];_(P(l),h);for(let n of h){'
HTML += b'let c=r.clone(),p=e.clone();for(let u=0;u<l;u++)p.renameVar('
HTML += b'"C"+u,"__C"+n[u]);for(let u=0;u<l;u++)p.renameVar("__C"+u,"C'
HTML += b'"+u);let m=!0;for(let u=0;u<l;u++){let d="C"+u,g={};g[d]=new'
HTML += b' a("*",[new a("var:C"+u,[]),new a("var:K",[])]),p.setVars(g)'
HTML += b';let v={};v[d]=a.const(Math.random(),Math.random());for(let '
HTML += b'C=0;C<l;C++)u!=C&&(v["C"+C]=a.const(0,0));let M=new a("abs",'
HTML += b'[new a("-",[c.root,p.root])]),E=new b;E.root=M;for(let C of '
HTML += b'o)v[C]=a.const(Math.random(),Math.random());let y=ve(E,"K",v'
HTML += b')[0];p.setVars({K:a.const(y,0)}),v={};for(let C=0;C<l;C++)u!'
HTML += b'=C&&(v["C"+C]=a.const(0,0));if(b.compare(c,p,v)==!1){m=!1;br'
HTML += b'eak}}if(m&&b.compare(c,p))return!0}return!1}f(he,"compareODE'
HTML += b'");function ve(r,e,t){let s=1e-11,i=1e3,o=0,l=0,h=1,n=888;fo'
HTML += b'r(;o<i;){t[e]=a.const(l);let p=r.eval(t).re;t[e]=a.const(l+h'
HTML += b');let m=r.eval(t).re;t[e]=a.const(l-h);let u=r.eval(t).re,d='
HTML += b'0;if(m<p&&(p=m,d=1),u<p&&(p=u,d=-1),d==1&&(l+=h),d==-1&&(l-='
HTML += b'h),p<s)break;(d==0||d!=n)&&(h/=2),n=d,o++}t[e]=a.const(l);le'
HTML += b't c=r.eval(t).re;return[l,c]}f(ve,"minimize");function U(r){'
HTML += b'for(let e of r.c)U(e);switch(r.op){case"+":case"-":case"*":c'
HTML += b'ase"/":case"^":{let e=[r.c[0].op,r.c[1].op],t=[e[0]==="const'
HTML += b'",e[1]==="const"],s=[e[0].startsWith("var:C"),e[1].startsWit'
HTML += b'h("var:C")];s[0]&&t[1]?(r.op=r.c[0].op,r.c=[]):s[1]&&t[0]?(r'
HTML += b'.op=r.c[1].op,r.c=[]):s[0]&&s[1]&&e[0]==e[1]&&(r.op=r.c[0].o'
HTML += b'p,r.c=[]);break}case".-":case"abs":case"sin":case"sinc":case'
HTML += b'"cos":case"tan":case"cot":case"exp":case"ln":case"log":case"'
HTML += b'sqrt":r.c[0].op.startsWith("var:C")&&(r.op=r.c[0].op,r.c=[])'
HTML += b';break}}f(U,"prepareODEconstantComparison");var A=class{stat'
HTML += b'ic{f(this,"GapInput")}constructor(e,t,s,i){this.question=t,t'
HTML += b'his.inputId=s,s.length==0&&(this.inputId=s="gap-"+t.gapIdx,t'
HTML += b'.types[this.inputId]="string",t.expected[this.inputId]=i,t.g'
HTML += b'apIdx++),s in t.student||(t.student[s]="");let o=i.split("|"'
HTML += b'),l=0;for(let p=0;p<o.length;p++){let m=o[p];m.length>l&&(l='
HTML += b'm.length)}let h=k("");e.appendChild(h);let n=Math.max(l*15,2'
HTML += b'4),c=W(n);if(t.gapInputs[this.inputId]=c,c.addEventListener('
HTML += b'"keyup",()=>{t.editingEnabled!=!1&&(this.question.editedQues'
HTML += b'tion(),c.value=c.value.toUpperCase(),this.question.student[t'
HTML += b'his.inputId]=c.value.trim())}),h.appendChild(c),this.questio'
HTML += b'n.showSolution&&(this.question.student[this.inputId]=c.value'
HTML += b'=o[0],o.length>1)){let p=k("["+o.join("|")+"]");p.style.font'
HTML += b'Size="small",p.style.textDecoration="underline",h.appendChil'
HTML += b'd(p)}}},z=class{static{f(this,"TermInput")}constructor(e,t,s'
HTML += b',i,o,l,h=!1){s in t.student||(t.student[s]=""),this.question'
HTML += b'=t,this.inputId=s,this.outerSpan=k(""),this.outerSpan.style.'
HTML += b'position="relative",e.appendChild(this.outerSpan),this.input'
HTML += b'Element=W(Math.max(i*12,48)),this.outerSpan.appendChild(this'
HTML += b'.inputElement),this.equationPreviewDiv=w(),this.equationPrev'
HTML += b'iewDiv.classList.add("pysell-equation-preview"),this.equatio'
HTML += b'nPreviewDiv.style.display="none",this.outerSpan.appendChild('
HTML += b'this.equationPreviewDiv),this.inputElement.addEventListener('
HTML += b'"click",()=>{if(t.editingEnabled==!1){this.inputElement.blur'
HTML += b'();return}this.question.editedQuestion(),this.edited()}),thi'
HTML += b's.inputElement.addEventListener("keyup",()=>{t.editingEnable'
HTML += b'd!=!1&&(this.question.editedQuestion(),this.edited())}),this'
HTML += b'.inputElement.addEventListener("focus",()=>{t.editingEnabled'
HTML += b'!=!1}),this.inputElement.addEventListener("focusout",()=>{th'
HTML += b'is.equationPreviewDiv.innerHTML="",this.equationPreviewDiv.s'
HTML += b'tyle.display="none"}),this.inputElement.addEventListener("ke'
HTML += b'ydown",n=>{if(t.editingEnabled==!1){n.preventDefault();retur'
HTML += b'n}let c="abcdefghijklmnopqrstuvwxyz";c+="ABCDEFGHIJKLMNOPQRS'
HTML += b'TUVWXYZ",c+="0123456789",c+="+-*/^(). <>=|",l&&(c="-01234567'
HTML += b'89"),n.key.length<3&&c.includes(n.key)==!1&&n.preventDefault'
HTML += b'();let p=this.inputElement.value.length*12;this.inputElement'
HTML += b'.offsetWidth<p&&(this.inputElement.style.width=""+p+"px")}),'
HTML += b'(h||this.question.showSolution)&&(t.student[s]=this.inputEle'
HTML += b'ment.value=o)}edited(){let e=this.inputElement.value.trim(),'
HTML += b't="",s=!1;try{let i=b.parse(e);s=i.root.op==="const",t=i.toT'
HTML += b'exString(),this.inputElement.style.color=this.question.quiz.'
HTML += b'darkMode?"var(--pysell-white)":"var(--pysell-black)",this.eq'
HTML += b'uationPreviewDiv.style.backgroundColor="var(--pysell-green)"'
HTML += b'}catch{t=e.replaceAll("^","\\\\hat{~}").replaceAll("_","\\\\_"),'
HTML += b'this.inputElement.style.color="maroon",this.equationPreviewD'
HTML += b'iv.style.backgroundColor="maroon"}N(this.equationPreviewDiv,'
HTML += b't,!0),this.equationPreviewDiv.style.display=e.length>0&&!s?"'
HTML += b'block":"none",this.question.student[this.inputId]=e}},B=clas'
HTML += b's{static{f(this,"MatrixInput")}constructor(e,t,s,i){this.par'
HTML += b'ent=e,this.question=t,this.inputId=s,this.matExpected=new L('
HTML += b'0,0),this.matExpected.fromString(i),this.matStudent=new L(th'
HTML += b'is.matExpected.m==1?1:3,this.matExpected.n==1?1:3),t.showSol'
HTML += b'ution&&this.matStudent.fromMatrix(this.matExpected),this.gen'
HTML += b'MatrixDom(!0)}genMatrixDom(e){let t=w();this.parent.innerHTM'
HTML += b'L="",this.parent.appendChild(t),t.style.position="relative",'
HTML += b't.style.display="inline-block";let s=document.createElement('
HTML += b'"table");s.style.borderCollapse="collapse",t.appendChild(s);'
HTML += b'let i=this.matExpected.getMaxCellStrlen();for(let d=0;d<this'
HTML += b'.matStudent.m;d++){let g=document.createElement("tr");g.styl'
HTML += b'e.borderCollapse="collapse",g.style.borderStyle="none",s.app'
HTML += b'endChild(g),d==0&&g.appendChild(this.generateMatrixParenthes'
HTML += b'is(!0,this.matStudent.m));for(let v=0;v<this.matStudent.n;v+'
HTML += b'+){let M=d*this.matStudent.n+v,E=document.createElement("td"'
HTML += b');E.style.borderCollapse="collapse",g.appendChild(E);let y=t'
HTML += b'his.inputId+"-"+M;new z(E,this.question,y,i,this.matStudent.'
HTML += b'v[M],!1,!e)}d==0&&g.appendChild(this.generateMatrixParenthes'
HTML += b'is(!1,this.matStudent.m))}let o=["+","-","+","-"],l=[0,0,1,-'
HTML += b'1],h=[1,-1,0,0],n=[0,22,888,888],c=[888,888,-23,-23],p=[-22,'
HTML += b'-22,0,22],m=[this.matExpected.n!=1,this.matExpected.n!=1,thi'
HTML += b's.matExpected.m!=1,this.matExpected.m!=1],u=[this.matStudent'
HTML += b'.n>=10,this.matStudent.n<=1,this.matStudent.m>=10,this.matSt'
HTML += b'udent.m<=1];for(let d=0;d<4;d++){if(m[d]==!1)continue;let g='
HTML += b'k(o[d]);n[d]!=888&&(g.style.top=""+n[d]+"px"),c[d]!=888&&(g.'
HTML += b'style.bottom=""+c[d]+"px"),p[d]!=888&&(g.style.right=""+p[d]'
HTML += b'+"px"),g.classList.add("pysell-matrix-resize-button"),t.appe'
HTML += b'ndChild(g),u[d]?g.style.opacity="0.5":g.addEventListener("cl'
HTML += b'ick",()=>{for(let v=0;v<this.matStudent.m;v++)for(let M=0;M<'
HTML += b'this.matStudent.n;M++){let E=v*this.matStudent.n+M,y=this.in'
HTML += b'putId+"-"+E,S=this.question.student[y];this.matStudent.v[E]='
HTML += b'S,delete this.question.student[y]}this.matStudent.resize(thi'
HTML += b's.matStudent.m+l[d],this.matStudent.n+h[d],""),this.genMatri'
HTML += b'xDom(!1)})}}generateMatrixParenthesis(e,t){let s=document.cr'
HTML += b'eateElement("td");s.style.width="3px";for(let i of["Top",e?"'
HTML += b'Left":"Right","Bottom"])s.style["border"+i+"Width"]="2px",s.'
HTML += b'style["border"+i+"Style"]="solid";return this.question.langu'
HTML += b'age=="de"&&(e?s.style.borderTopLeftRadius="5px":s.style.bord'
HTML += b'erTopRightRadius="5px",e?s.style.borderBottomLeftRadius="5px'
HTML += b'":s.style.borderBottomRightRadius="5px"),s.rowSpan=t,s}};var'
HTML += b' x={init:0,errors:1,passed:2,incomplete:3},q=class{static{f('
HTML += b'this,"Question")}constructor(e,t,s,i,o){this.quiz=e,this.sta'
HTML += b'te=x.init,this.language=i,this.src=s,this.debug=o,this.insta'
HTML += b'nceOrder=P(s.instances.length,!0),this.instanceIdx=0,this.ch'
HTML += b'oiceIdx=0,this.includesSingleChoice=!1,this.gapIdx=0,this.ex'
HTML += b'pected={},this.types={},this.student={},this.gapInputs={},th'
HTML += b'is.parentDiv=t,this.questionDiv=null,this.feedbackPopupDiv=n'
HTML += b'ull,this.titleDiv=null,this.checkAndRepeatBtn=null,this.show'
HTML += b'Solution=!1,this.feedbackSpan=null,this.numCorrect=0,this.nu'
HTML += b'mChecked=0,this.hasCheckButton=!0,this.editingEnabled=!0}res'
HTML += b'et(){this.gapIdx=0,this.choiceIdx=0,this.instanceIdx=(this.i'
HTML += b'nstanceIdx+1)%this.src.instances.length}getCurrentInstance()'
HTML += b'{let e=this.instanceOrder[this.instanceIdx];return this.src.'
HTML += b'instances[e]}editedQuestion(){this.state=x.init,this.updateV'
HTML += b'isualQuestionState();let e=this.quiz.darkMode?"var(--pysell-'
HTML += b'white)":"var(--pysell-black)";this.questionDiv.style.color=e'
HTML += b',this.checkAndRepeatBtn.innerHTML=this.quiz.darkMode?D.repla'
HTML += b'ce("white","black"):D,this.checkAndRepeatBtn.style.display="'
HTML += b'block",this.checkAndRepeatBtn.style.color=e}updateVisualQues'
HTML += b'tionState(){let e=this.quiz.darkMode?"var(--pysell-white)":"'
HTML += b'var(--pysell-black)",t="transparent";switch(this.state){case'
HTML += b' x.init:e=this.quiz.darkMode?"var(--pysell-white)":"var(--py'
HTML += b'sell-black)";break;case x.passed:e="var(--pysell-green)",t="'
HTML += b'rgba(0,150,0, 0.035)";break;case x.incomplete:case x.errors:'
HTML += b'e="var(--pysell-red)",t="rgba(150,0,0, 0.035)",this.includes'
HTML += b'SingleChoice==!1&&this.numChecked>=5&&(this.feedbackSpan.inn'
HTML += b'erHTML="&nbsp;&nbsp;"+this.numCorrect+" / "+this.numChecked)'
HTML += b';break}this.questionDiv.style.backgroundColor=t,this.questio'
HTML += b'nDiv.style.borderColor=e}populateDom(e=!1){if(this.parentDiv'
HTML += b'.innerHTML="",this.questionDiv=w(),this.parentDiv.appendChil'
HTML += b'd(this.questionDiv),this.questionDiv.classList.add("pysell-q'
HTML += b'uestion"),this.questionDiv.style.borderColor=this.quiz.darkM'
HTML += b'ode?"var(--pysell-white)":"var(--pysell-black)",this.feedbac'
HTML += b'kPopupDiv=w(),this.feedbackPopupDiv.classList.add("pysell-qu'
HTML += b'estion-feedback"),this.questionDiv.appendChild(this.feedback'
HTML += b'PopupDiv),this.feedbackPopupDiv.innerHTML="awesome",this.deb'
HTML += b'ug&&"src_line"in this.src){let i=w();i.classList.add("pysell'
HTML += b'-debug-info"),i.innerHTML="Source code: lines "+this.src.src'
HTML += b'_line+"..",this.questionDiv.appendChild(i)}if(this.titleDiv='
HTML += b'w(),this.questionDiv.appendChild(this.titleDiv),this.titleDi'
HTML += b'v.classList.add("pysell-question-title"),this.titleDiv.style'
HTML += b'.color=this.quiz.darkMode?"var(--pysell-white)":"var(--pysel'
HTML += b'l-black)",this.titleDiv.innerHTML=this.src.title,this.src.er'
HTML += b'ror.length>0){let i=k(this.src.error);this.questionDiv.appen'
HTML += b'dChild(i),i.style.color="red";return}let t=this.getCurrentIn'
HTML += b'stance();if(t!=null&&"__svg_image"in t){let i=t.__svg_image.'
HTML += b'v,o=w();this.questionDiv.appendChild(o);let l=document.creat'
HTML += b'eElement("img");o.appendChild(l),l.classList.add("pysell-img'
HTML += b'"),l.src="data:image/svg+xml;base64,"+i}for(let i of this.sr'
HTML += b'c.text.c)this.questionDiv.appendChild(this.generateText(i));'
HTML += b'let s=w();if(s.innerHTML="",s.classList.add("pysell-button-g'
HTML += b'roup"),this.questionDiv.appendChild(s),this.hasCheckButton=O'
HTML += b'bject.keys(this.expected).length>0,this.hasCheckButton&&(thi'
HTML += b's.checkAndRepeatBtn=se(),s.appendChild(this.checkAndRepeatBt'
HTML += b'n),this.checkAndRepeatBtn.innerHTML=this.quiz.darkMode?D.rep'
HTML += b'lace("white","black"):D,this.checkAndRepeatBtn.style.backgro'
HTML += b'undColor=this.quiz.darkMode?"var(--pysell-white)":"var(--pys'
HTML += b'ell-black)",e&&(this.checkAndRepeatBtn.style.height="32px",t'
HTML += b'his.checkAndRepeatBtn.style.visibility="hidden")),this.feedb'
HTML += b'ackSpan=k(""),this.feedbackSpan.style.userSelect="none",s.ap'
HTML += b'pendChild(this.feedbackSpan),this.debug){if(this.src.variabl'
HTML += b'es.length>0){let l=w();l.classList.add("pysell-debug-info"),'
HTML += b'l.innerHTML="Variables generated by Python Code",this.questi'
HTML += b'onDiv.appendChild(l);let h=w();h.classList.add("pysell-debug'
HTML += b'-code"),this.questionDiv.appendChild(h);let n=this.getCurren'
HTML += b'tInstance(),c="",p=[...this.src.variables];p.sort();for(let '
HTML += b'm of p){let u=n[m].t,d=n[m].v;switch(u){case"vector":d="["+d'
HTML += b'+"]";break;case"set":d="{"+d+"}";break}c+=u+" "+m+" = "+d+"<'
HTML += b'br/>"}h.innerHTML=c}let i=["python_src_html","text_src_html"'
HTML += b'],o=["Python Source Code","Text Source Code"];for(let l=0;l<'
HTML += b'i.length;l++){let h=i[l];if(h in this.src&&this.src[h].lengt'
HTML += b'h>0){let n=w();n.classList.add("pysell-debug-info"),n.innerH'
HTML += b'TML=o[l],this.questionDiv.appendChild(n);let c=w();c.classLi'
HTML += b'st.add("pysell-debug-code"),this.questionDiv.append(c),c.inn'
HTML += b'erHTML=this.src[h]}}}this.hasCheckButton&&this.checkAndRepea'
HTML += b'tBtn.addEventListener("click",()=>{this.state==x.passed?(thi'
HTML += b's.state=x.init,this.editingEnabled=!0,this.reset(),this.popu'
HTML += b'lateDom()):V(this)})}generateMathString(e){let t="";switch(e'
HTML += b'.t){case"math":case"display-math":for(let s of e.c){let i=th'
HTML += b'is.generateMathString(s);s.t==="var"&&t.includes("!PM")&&(i.'
HTML += b'startsWith("{-")?(i="{"+i.substring(2),t=t.replaceAll("!PM",'
HTML += b'"-")):t=t.replaceAll("!PM","+")),t+=i}break;case"text":retur'
HTML += b'n e.d;case"plus_minus":{t+=" !PM ";break}case"var":{let s=th'
HTML += b'is.getCurrentInstance(),i=s[e.d].t,o=s[e.d].v;switch(i){case'
HTML += b'"vector":return"\\\\left["+o+"\\\\right]";case"set":return"\\\\lef'
HTML += b't\\\\{"+o+"\\\\right\\\\}";case"complex":{let l=o.split(","),h=par'
HTML += b'seFloat(l[0]),n=parseFloat(l[1]);return a.const(h,n).toTexSt'
HTML += b'ring()}case"matrix":{let l=new L(0,0);return l.fromString(o)'
HTML += b',t=l.toTeXString(e.d.includes("augmented"),this.language!="d'
HTML += b'e"),t}case"term":{try{t=b.parse(o).toTexString()}catch{}brea'
HTML += b'k}default:t=o}}}return e.t==="plus_minus"?t:"{"+t+"}"}genera'
HTML += b'teText(e,t=!1){switch(e.t){case"paragraph":case"span":{let s'
HTML += b'=document.createElement(e.t=="span"||t?"span":"p");for(let i'
HTML += b' of e.c)s.appendChild(this.generateText(i));return s.style.u'
HTML += b'serSelect="none",s}case"text":return k(e.d);case"code":{let '
HTML += b's=k(e.d);return s.classList.add("pysell-code"),s}case"code-b'
HTML += b'lock":{let s=w();return s.classList.add("pysell-code-block")'
HTML += b',s.innerHTML=e.d.replaceAll(`\n`,"<br/>").replaceAll(" ","&nb'
HTML += b'sp;"),s}case"italic":case"bold":{let s=k("");return s.append'
HTML += b'(...e.c.map(i=>this.generateText(i))),e.t==="bold"?s.style.f'
HTML += b'ontWeight="bold":s.style.fontStyle="italic",s}case"math":cas'
HTML += b'e"display-math":{let s=this.generateMathString(e);return T(s'
HTML += b',e.t==="display-math")}case"string_var":{let s=k(""),i=this.'
HTML += b'getCurrentInstance(),o=i[e.d].t,l=i[e.d].v;return o==="strin'
HTML += b'g"?s.innerHTML=l:(s.innerHTML="EXPECTED VARIABLE OF TYPE STR'
HTML += b'ING",s.style.color="red"),s}case"gap":{let s=k("");return ne'
HTML += b'w A(s,this,"",e.d),s}case"input":case"input2":{let s=e.t==="'
HTML += b'input2",i=k("");i.style.verticalAlign="text-bottom";let o=e.'
HTML += b'd,l=this.getCurrentInstance()[o];if(this.expected[o]=l.v,thi'
HTML += b's.types[o]=l.t,!s)switch(l.t){case"set":i.append(T("\\\\{"),k('
HTML += b'" "));break;case"vector":i.append(T("["),k(" "));break}if(l.'
HTML += b't==="string")new A(i,this,o,this.expected[o]);else if(l.t==='
HTML += b'"vector"||l.t==="set"){let h=l.v.split(","),n=h.length;for(l'
HTML += b'et c=0;c<n;c++){c>0&&i.appendChild(k(" , "));let p=o+"-"+c;n'
HTML += b'ew z(i,this,p,h[c].length,h[c],!1)}}else if(l.t==="matrix"){'
HTML += b'let h=w();i.appendChild(h),new B(h,this,o,l.v)}else if(l.t=='
HTML += b'="complex"){let h=l.v.split(",");new z(i,this,o+"-0",h[0].le'
HTML += b'ngth,h[0],!1),i.append(k(" "),T("+"),k(" ")),new z(i,this,o+'
HTML += b'"-1",h[1].length,h[1],!1),i.append(k(" "),T("i"))}else{let h'
HTML += b'=l.t==="int";new z(i,this,o,l.v.length,l.v,h)}if(!s)switch(l'
HTML += b'.t){case"set":i.append(k(" "),T("\\\\}"));break;case"vector":i'
HTML += b'.append(k(" "),T("]"));break}return i}case"itemize":return t'
HTML += b'e(e.c.map(s=>ie(this.generateText(s))));case"single-choice":'
HTML += b'case"multi-choice":{let s=e.t=="multi-choice";s||(this.inclu'
HTML += b'desSingleChoice=!0);let i=document.createElement("table");i.'
HTML += b'style.border="none",i.style.borderCollapse="collapse";let o='
HTML += b'e.c.length,l=this.debug==!1,h=P(o,l),n=s?ae:oe,c=s?re:le;thi'
HTML += b's.quiz.darkMode&&(n=n.replace("black","white"),c=c.replace("'
HTML += b'black","white"));let p=[],m=[];for(let u=0;u<o;u++){let d=h['
HTML += b'u],g=e.c[d],v="mc-"+this.choiceIdx+"-"+d;m.push(v);let M=g.c'
HTML += b'[0].t=="bool"?g.c[0].d:this.getCurrentInstance()[g.c[0].d].v'
HTML += b';this.expected[v]=M,this.types[v]="bool",this.student[v]=thi'
HTML += b's.showSolution?M:"false";let E=this.generateText(g.c[1],!0),'
HTML += b'y=document.createElement("tr");i.appendChild(y),y.style.curs'
HTML += b'or="pointer",y.style.borderStyle="none";let S=document.creat'
HTML += b'eElement("td");S.style.width="40px",p.push(S),y.appendChild('
HTML += b'S),S.innerHTML=this.student[v]=="true"?n:c;let C=document.cr'
HTML += b'eateElement("td");y.appendChild(C),C.appendChild(E),s?y.addE'
HTML += b'ventListener("click",()=>{this.editingEnabled!=!1&&(this.edi'
HTML += b'tedQuestion(),this.student[v]=this.student[v]==="true"?"fals'
HTML += b'e":"true",this.student[v]==="true"?S.innerHTML=n:S.innerHTML'
HTML += b'=c)}):y.addEventListener("click",()=>{if(this.editingEnabled'
HTML += b'!=!1){this.editedQuestion();for(let I of m)this.student[I]="'
HTML += b'false";this.student[v]="true";for(let I=0;I<m.length;I++){le'
HTML += b't j=h[I];p[j].innerHTML=this.student[m[j]]=="true"?n:c}}})}r'
HTML += b'eturn this.choiceIdx++,i}case"image":{let s=w(),o=e.d.split('
HTML += b'"."),l=o[o.length-1],h=e.c[0].d,n=e.c[1].d,c=document.create'
HTML += b'Element("img");s.appendChild(c),c.classList.add("pysell-img"'
HTML += b'),c.style.width=h+"%";let p={svg:"svg+xml",png:"png",jpg:"jp'
HTML += b'eg"};return c.src="data:image/"+p[l]+";base64,"+n,s}default:'
HTML += b'{let s=k("UNIMPLEMENTED("+e.t+")");return s.style.color="red'
HTML += b'",s}}}};function V(r){r.feedbackSpan.innerHTML="",r.numCheck'
HTML += b'ed=0,r.numCorrect=0;let e=!0;for(let i in r.expected){let o='
HTML += b'r.types[i],l=r.student[i],h=r.expected[i];switch(l!=null&&l.'
HTML += b'length==0&&(e=!1),o){case"bool":r.numChecked++,l.toLowerCase'
HTML += b'()===h.toLowerCase()&&r.numCorrect++;break;case"string":{r.n'
HTML += b'umChecked++;let n=r.gapInputs[i],c=l.trim().toUpperCase(),p='
HTML += b'h.trim().toUpperCase().split("|"),m=!1;for(let u of p)if(ne('
HTML += b'c,u)<=1){m=!0,r.numCorrect++,r.gapInputs[i].value=u,r.studen'
HTML += b't[i]=u;break}n.style.color=m?"black":"white",n.style.backgro'
HTML += b'undColor=m?"transparent":"maroon";break}case"int":r.numCheck'
HTML += b'ed++,Math.abs(parseFloat(l)-parseFloat(h))<1e-9&&r.numCorrec'
HTML += b't++;break;case"float":case"term":{r.numChecked++;try{let n=b'
HTML += b'.parse(h),c=b.parse(l),p=!1;r.src.is_ode?p=he(n,c):p=b.compa'
HTML += b're(n,c),p&&r.numCorrect++}catch(n){r.debug&&(console.log("te'
HTML += b'rm invalid"),console.log(n))}break}case"vector":case"complex'
HTML += b'":case"set":{let n=h.split(",");r.numChecked+=n.length;let c'
HTML += b'=[];for(let p=0;p<n.length;p++){let m=r.student[i+"-"+p];m.l'
HTML += b'ength==0&&(e=!1),c.push(m)}if(o==="set")for(let p=0;p<n.leng'
HTML += b'th;p++)try{let m=b.parse(n[p]);for(let u=0;u<c.length;u++){l'
HTML += b'et d=b.parse(c[u]);if(b.compare(m,d)){r.numCorrect++;break}}'
HTML += b'}catch(m){r.debug&&console.log(m)}else for(let p=0;p<n.lengt'
HTML += b'h;p++)try{let m=b.parse(c[p]),u=b.parse(n[p]);b.compare(m,u)'
HTML += b'&&r.numCorrect++}catch(m){r.debug&&console.log(m)}break}case'
HTML += b'"matrix":{let n=new L(0,0);n.fromString(h),r.numChecked+=n.m'
HTML += b'*n.n;for(let c=0;c<n.m;c++)for(let p=0;p<n.n;p++){let m=c*n.'
HTML += b'n+p;l=r.student[i+"-"+m],l!=null&&l.length==0&&(e=!1);let u='
HTML += b'n.v[m];try{let d=b.parse(u),g=b.parse(l);b.compare(d,g)&&r.n'
HTML += b'umCorrect++}catch(d){r.debug&&console.log(d)}}break}default:'
HTML += b'r.feedbackSpan.innerHTML="UNIMPLEMENTED EVAL OF TYPE "+o}}e='
HTML += b'=!1?r.state=x.incomplete:r.state=r.numCorrect==r.numChecked?'
HTML += b'x.passed:x.errors,r.updateVisualQuestionState();let t=[];swi'
HTML += b'tch(r.state){case x.passed:t=Z[r.language];break;case x.inco'
HTML += b'mplete:t=X[r.language];break;case x.errors:t=Y[r.language];b'
HTML += b'reak}let s=t[Math.floor(Math.random()*t.length)];r.feedbackP'
HTML += b'opupDiv.innerHTML=s,r.feedbackPopupDiv.style.color=r.state=='
HTML += b'=x.passed?"var(--pysell-green)":"var(--pysell-red)",r.feedba'
HTML += b'ckPopupDiv.style.display="flex",setTimeout(()=>{r.feedbackPo'
HTML += b'pupDiv.style.display="none"},1e3),r.editingEnabled=!0,r.stat'
HTML += b'e===x.passed?(r.editingEnabled=!1,r.src.instances.length>1?r'
HTML += b'.checkAndRepeatBtn.innerHTML=r.quiz.darkMode?Q.replace("whit'
HTML += b'e","black"):Q:r.checkAndRepeatBtn.style.visibility="hidden")'
HTML += b':r.checkAndRepeatBtn!=null&&(r.checkAndRepeatBtn.innerHTML=r'
HTML += b'.quiz.darkMode?D.replace("white","black"):D)}f(V,"evalQuesti'
HTML += b'on");var R=class{static{f(this,"Quiz")}constructor(e,t,s,i=!'
HTML += b'1,o=!0){if(this.quizSrc=e,this.htmlElements=t,["en","de","es'
HTML += b'","it","fr"].includes(this.quizSrc.lang)==!1&&(this.quizSrc.'
HTML += b'lang="en"),this.debug=s,this.darkMode=i,this.questionNumberi'
HTML += b'ng=o,this.questions=[],this.timeLeft=e.timer,this.timeLimite'
HTML += b'd=e.timer>0,this.fillPageMetadata(),this.timeLimited){let l='
HTML += b't.timerInfo;l.classList.add("pysell-timer-info");let h=docum'
HTML += b'ent.createElement("span");h.innerHTML=ee[this.quizSrc.lang],'
HTML += b'l.appendChild(h),l.appendChild(document.createElement("br"))'
HTML += b',l.appendChild(document.createElement("br"));let n=document.'
HTML += b'createElement("button");n.classList.add("pysell-button pysel'
HTML += b'l-start-button"),n.innerHTML="Start",n.addEventListener("cli'
HTML += b'ck",()=>{l.style.display="none",this.generateQuestions(),thi'
HTML += b's.runTimer()}),l.appendChild(n)}else this.generateQuestions('
HTML += b')}fillPageMetadata(){if("date"in this.htmlElements){let e=th'
HTML += b'is.htmlElements.date;e.innerHTML=this.quizSrc.date}if("heade'
HTML += b'r"in this.htmlElements){let e=this.htmlElements.header,t=doc'
HTML += b'ument.createElement("h1");t.innerHTML=this.quizSrc.title.spl'
HTML += b'it(" -- ").join("<br/>"),e.appendChild(t);let s=document.cre'
HTML += b'ateElement("div");s.style.marginTop="15px",e.appendChild(s);'
HTML += b'let i=document.createElement("div");i.classList.add("pysell-'
HTML += b'author"),i.innerHTML=this.quizSrc.author,e.appendChild(i);le'
HTML += b't o=document.createElement("p");if(o.classList.add("pysell-c'
HTML += b'ourse-info"),e.appendChild(o),this.quizSrc.info.length>0)o.i'
HTML += b'nnerHTML=this.quizSrc.info;else{o.innerHTML=F[this.quizSrc.l'
HTML += b'ang];let l=\'<span onclick="location.reload()" style="text-de'
HTML += b'coration: none; font-weight: bold; cursor: pointer">\'+K[this'
HTML += b'.quizSrc.lang]+"</span>",h=document.createElement("p");h.cla'
HTML += b'ssList.add("pysell-course-info"),e.appendChild(h),h.innerHTM'
HTML += b'L=O[this.quizSrc.lang].replace("*",l)}if(this.debug){let l=d'
HTML += b'ocument.createElement("h1");l.classList.add("pysell-debug-co'
HTML += b'de"),l.innerHTML="DEBUG VERSION",e.appendChild(l)}}}generate'
HTML += b'Questions(){let e=1;for(let t of this.quizSrc.questions){let'
HTML += b' s=t.title;this.questionNumbering&&(s=""+e+". "+s),t.title=s'
HTML += b';let i=w();this.htmlElements.questions.appendChild(i);let o='
HTML += b'new q(this,i,t,this.quizSrc.lang,this.debug);o.showSolution='
HTML += b'this.debug,this.questions.push(o),o.populateDom(this.timeLim'
HTML += b'ited),this.debug&&t.error.length==0&&o.hasCheckButton&&o.che'
HTML += b'ckAndRepeatBtn.click(),e++}}runTimer(){let e=this.htmlElemen'
HTML += b'ts.timerFooter;e.style.textAlign="center";let t=document.cre'
HTML += b'ateElement("button");t.classList.add("pysell-button"),t.styl'
HTML += b'e.backgroundColor="var(--pysell-green)",t.innerHTML=J[this.q'
HTML += b'uizSrc.lang],t.addEventListener("click",()=>{this.timeLeft=1'
HTML += b'}),e.appendChild(t);let s=this.htmlElements.timer;s.classLis'
HTML += b't.add("pysell-timer"),s.innerHTML=ce(this.timeLeft);let i=se'
HTML += b'tInterval(()=>{this.timeLeft--,s.innerHTML=ce(this.timeLeft)'
HTML += b',this.timeLeft<=0&&this.stopTimer(i)},1e3)}stopTimer(e){let '
HTML += b't=this.htmlElements.timerFooter;t.style.display="none",clear'
HTML += b'Interval(e);let s=0,i=0;for(let h of this.questions){let n=h'
HTML += b'.src.points;i+=n,V(h),h.state===x.passed&&(s+=n),h.editingEn'
HTML += b'abled=!1}let o=this.htmlElements.timerEval;o.classList.add("'
HTML += b'pysell-eval");let l=document.createElement("h1");o.appendChi'
HTML += b'ld(l),l.innerHTML=i==0?"":""+s+" / "+i+" "+G[this.quizSrc.la'
HTML += b'ng]+" <br/><br/>"+Math.round(s/i*100)+" %"}};function ce(r){'
HTML += b'let e=Math.floor(r/60),t=r%60;return e+":"+(""+t).padStart(2'
HTML += b',"0")}f(ce,"formatTime");function be(r,e){let t={date:docume'
HTML += b'nt.getElementById("date"),header:document.getElementById("he'
HTML += b'ader"),questions:document.getElementById("questions"),timer:'
HTML += b'document.getElementById("timer"),timerInfo:document.getEleme'
HTML += b'ntById("timer-info"),timerFooter:document.getElementById("ti'
HTML += b'mer-footer"),timerEval:document.getElementById("timer-eval")'
HTML += b'};new R(r,t,e),document.getElementById("data-policy").innerH'
HTML += b'TML=$[r.lang]}f(be,"init");return ge(ke);})();pysell.init(qu'
HTML += b'izSrc,debug);</script></body> </html> '
HTML = HTML.decode('utf-8')
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
