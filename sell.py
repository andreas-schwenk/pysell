#!/usr/bin/env python3

# pylint: disable=too-many-lines

"""
======= pySELL =================================================================
        
        A Python based Simple E-Learning Language 
        for the simple creation of interactive courses

LICENSE GPLv3

AUTHOR  Andreas Schwenk <mailto:contact@compiler-construction.com>

DOCS    Refer to https://github.com/andreas-schwenk/pysell and read the
        descriptions at the end of the page

INSTALL Run 'pip install pysell', or use the stand-alone implementation sell.py

CMD     pysell [-J] PATH
        
        -J          is optional and generates a JSON output file for debugging        
   
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
HTML += b'" ></script> <style> :root { --grey: #5a5a5a; --green: rgb(2'
HTML += b'4, 82, 1); --red: rgb(123, 0, 0); } html, body { font-family'
HTML += b': Arial, Helvetica, sans-serif; margin: 0; padding: 0; backg'
HTML += b'round-color: white; } .contents { max-width: 800px; margin-l'
HTML += b'eft: auto; margin-right: auto; padding: 0; } h1 { text-align'
HTML += b': center; font-size: 28pt; word-wrap: break-word; margin-bot'
HTML += b'tom: 10px; user-select: none; } img { width: 100%; display: '
HTML += b'block; margin-left: auto; margin-right: auto; user-select: n'
HTML += b'one; } .author { text-align: center; font-size: 16pt; margin'
HTML += b'-bottom: 24px; user-select: none; } .courseInfo { text-align'
HTML += b': center; user-select: none; } .footer { position: relative;'
HTML += b' bottom: 0; font-size: small; text-align: center; line-heigh'
HTML += b't: 1.8; color: var(--grey); /*background-color: #2c2c2c;*/ m'
HTML += b'argin: 0; padding: 10px 10px; user-select: none; } .question'
HTML += b' { position: relative; /* required for feedback overlays */ '
HTML += b'color: black; background-color: white; border-top-style: sol'
HTML += b'id; border-bottom-style: solid; border-width: 3px; border-co'
HTML += b'lor: black; padding: 4px; margin-top: 32px; margin-bottom: 3'
HTML += b'2px; -webkit-box-shadow: 0px 0px 6px 3px #e8e8e8; box-shadow'
HTML += b': 0px 0px 6px 3px #e8e8e8; overflow-x: auto; overflow-y: hid'
HTML += b'den; } .button-group { display: flex; align-items: center; j'
HTML += b'ustify-content: center; text-align: center; margin-left: aut'
HTML += b'o; margin-right: auto; }  @media (min-width: 800px) { .quest'
HTML += b'ion { border-radius: 6px; padding: 16px; margin: 16px; borde'
HTML += b'r-left-style: solid; border-right-style: solid; } }  .questi'
HTML += b'onFeedback { opacity: 1.8; z-index: 10; display: none; posit'
HTML += b'ion: absolute; pointer-events: none; left: 0%; top: 0%; widt'
HTML += b'h: 100%; height: 100%; text-align: center; font-size: 4vw; t'
HTML += b'ext-shadow: 0px 0px 18px rgba(0, 0, 0, 0.15); background-col'
HTML += b'or: rgba(255, 255, 255, 0.95); padding: 10px; justify-conten'
HTML += b't: center; align-items: center; /*padding-top: 20px; padding'
HTML += b'-bottom: 20px;*/ /*border-style: solid; border-width: 4px; b'
HTML += b'order-color: rgb(200, 200, 200); border-radius: 16px; -webki'
HTML += b't-box-shadow: 0px 0px 18px 5px rgba(0, 0, 0, 0.66); box-shad'
HTML += b'ow: 0px 0px 18px 5px rgba(0, 0, 0, 0.66);*/ } .questionTitle'
HTML += b' { user-select: none; font-size: 24pt; } .code { font-family'
HTML += b': "Courier New", Courier, monospace; color: black; backgroun'
HTML += b'd-color: rgb(235, 235, 235); padding: 2px 5px; border-radius'
HTML += b': 5px; margin: 1px 2px; } .debugCode { font-family: "Courier'
HTML += b' New", Courier, monospace; padding: 4px; margin-bottom: 5px;'
HTML += b' background-color: black; color: white; border-radius: 5px; '
HTML += b'opacity: 0.85; overflow-x: scroll; } .debugInfo { text-align'
HTML += b': end; font-size: 10pt; margin-top: 2px; color: rgb(64, 64, '
HTML += b'64); } ul { user-select: none; margin-top: 0; margin-left: 0'
HTML += b'px; padding-left: 20px; } .inputField { position: relative; '
HTML += b'width: 32px; height: 24px; font-size: 14pt; border-style: so'
HTML += b'lid; border-color: black; border-radius: 5px; border-width: '
HTML += b'0.2; padding-left: 5px; padding-right: 5px; outline-color: b'
HTML += b'lack; background-color: transparent; margin: 1px; } .inputFi'
HTML += b'eld:focus { outline-color: maroon; } .equationPreview { posi'
HTML += b'tion: absolute; top: 120%; left: 0%; padding-left: 8px; padd'
HTML += b'ing-right: 8px; padding-top: 4px; padding-bottom: 4px; backg'
HTML += b'round-color: rgb(128, 0, 0); border-radius: 5px; font-size: '
HTML += b'12pt; color: white; text-align: start; z-index: 100; opacity'
HTML += b': 0.95; } .button { padding-left: 8px; padding-right: 8px; p'
HTML += b'adding-top: 5px; padding-bottom: 5px; font-size: 12pt; backg'
HTML += b'round-color: rgb(0, 150, 0); color: white; border-style: non'
HTML += b'e; border-radius: 4px; height: 36px; cursor: pointer; } .mat'
HTML += b'rixResizeButton { width: 20px; background-color: black; colo'
HTML += b'r: #fff; text-align: center; border-radius: 3px; position: a'
HTML += b'bsolute; z-index: 1; height: 20px; cursor: pointer; margin-b'
HTML += b'ottom: 3px; } a { color: black; text-decoration: underline; '
HTML += b'} .timer { display: none; position: fixed; left: 0; top: 0; '
HTML += b'padding: 5px 15px; background-color: rgb(32, 32, 32); color:'
HTML += b' white; opacity: 0.4; font-size: 32pt; z-index: 1000; /*marg'
HTML += b'in: 2px; border-radius: 10px;*/ border-bottom-right-radius: '
HTML += b'10px; text-align: center; font-family: "Courier New", Courie'
HTML += b'r, monospace; } .evalBtn { text-align: center; } .eval { tex'
HTML += b't-align: center; background-color: black; color: white; padd'
HTML += b'ing: 10px; } @media (min-width: 800px) { .eval { border-radi'
HTML += b'us: 10px; } } .timerInfo { font-size: x-large; text-align: c'
HTML += b'enter; background-color: black; color: white; padding: 20px '
HTML += b'10px; user-select: none; } @media (min-width: 800px) { .time'
HTML += b'rInfo { border-radius: 6px; } } </style> </head> <body> <div'
HTML += b' id="timer" class="timer">99:99</div> <h1 id="title"></h1> <'
HTML += b'div style="margin-top: 15px"></div> <div class="author" id="'
HTML += b'author"></div> <p id="courseInfo1" class="courseInfo"></p> <'
HTML += b'p id="courseInfo2" class="courseInfo"></p> <h1 id="debug" cl'
HTML += b'ass="debugCode" style="display: none">DEBUG VERSION</h1>  <b'
HTML += b'r />  <div class="contents"> <div id="timer-info" class="tim'
HTML += b'erInfo" style="display: none"> <span id="timer-info-text"></'
HTML += b'span> <br /><br /> <button id="start-btn" class="button" sty'
HTML += b'le="background-color: var(--green); font-size: x-large" > St'
HTML += b'art </button> </div>  <div id="questions"></div>  <div id="s'
HTML += b'top-now" class="evalBtn" style="display: none"> <button id="'
HTML += b'stop-now-btn" class="button" style="background-color: var(--'
HTML += b'green)" > jetzt auswerten </button> </div> <br /> <div id="q'
HTML += b'uestions-eval" class="eval" style="display: none"> <h1 id="q'
HTML += b'uestions-eval-percentage">0 %</h1> </div> </div>  <br /><br '
HTML += b'/><br /><br />  <div class="footer"> <div class="contents"> '
HTML += b'<span id="date"></span> &mdash; This quiz was developed usin'
HTML += b'g pySELL, a Python-based Simple E-Learning Language &mdash; '
HTML += b'<a href="https://pysell.org" style="color: var(--grey)" >htt'
HTML += b'ps://pysell.org</a > <br /> <span style="width: 64px"> <img '
HTML += b'style="max-width: 48px; padding: 16px 0px" src="data:image/s'
HTML += b'vg+xml;base64,PD94bWwgdmVyc2lvbj0iMS4wIiBlbmNvZGluZz0iVVRGLT'
HTML += b'giPz4KPCEtLSBDcmVhdGVkIHdpdGggSW5rc2NhcGUgKGh0dHA6Ly93d3cuaW'
HTML += b'5rc2NhcGUub3JnLykgLS0+Cjxzdmcgd2lkdGg9IjEwMG1tIiBoZWlnaHQ9Ij'
HTML += b'EwMG1tIiB2ZXJzaW9uPSIxLjEiIHZpZXdCb3g9IjAgMCAxMDAgMTAwIiB4bW'
HTML += b'xucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHhtbG5zOnhsaW5rPS'
HTML += b'JodHRwOi8vd3d3LnczLm9yZy8xOTk5L3hsaW5rIj4KIDxkZWZzPgogIDxsaW'
HTML += b'5lYXJHcmFkaWVudCBpZD0ibGluZWFyR3JhZGllbnQzNjU4IiB4MT0iMjguNT'
HTML += b'I3IiB4Mj0iMTI4LjUzIiB5MT0iNzkuNjQ4IiB5Mj0iNzkuNjQ4IiBncmFkaW'
HTML += b'VudFRyYW5zZm9ybT0ibWF0cml4KDEuMDE2MSAwIDAgMS4wMTYxIC0yOS43OS'
HTML += b'AtMzAuOTI4KSIgZ3JhZGllbnRVbml0cz0idXNlclNwYWNlT25Vc2UiPgogIC'
HTML += b'A8c3RvcCBzdG9wLWNvbG9yPSIjNTkwMDVlIiBvZmZzZXQ9IjAiLz4KICAgPH'
HTML += b'N0b3Agc3RvcC1jb2xvcj0iI2FkMDA3ZiIgb2Zmc2V0PSIxIi8+CiAgPC9saW'
HTML += b'5lYXJHcmFkaWVudD4KIDwvZGVmcz4KIDxyZWN0IHdpZHRoPSIxMDAiIGhlaW'
HTML += b'dodD0iMTAwIiByeT0iMCIgZmlsbD0idXJsKCNsaW5lYXJHcmFkaWVudDM2NT'
HTML += b'gpIi8+CiA8ZyBmaWxsPSIjZmZmIj4KICA8ZyB0cmFuc2Zvcm09Im1hdHJpeC'
HTML += b'guNDA3NDMgMCAwIC40MDc0MyAtNDIuODQyIC0zNi4xMzYpIiBzdHJva2Utd2'
HTML += b'lkdGg9IjMuNzc5NSIgc3R5bGU9InNoYXBlLWluc2lkZTp1cmwoI3JlY3Q5NT'
HTML += b'ItNyk7c2hhcGUtcGFkZGluZzo2LjUzMTQ0O3doaXRlLXNwYWNlOnByZSIgYX'
HTML += b'JpYS1sYWJlbD0iU0VMTCI+CiAgIDxwYXRoIGQ9Im0xNzEuMDEgMjM4LjM5cS'
HTML += b'0yLjExMi0yLjY4OC01LjU2OC00LjIyNC0zLjM2LTEuNjMyLTYuNTI4LTEuNj'
HTML += b'MyLTEuNjMyIDAtMy4zNiAwLjI4OC0xLjYzMiAwLjI4OC0yLjk3NiAxLjE1Mi'
HTML += b'0xLjM0NCAwLjc2OC0yLjMwNCAyLjExMi0wLjg2NCAxLjI0OC0wLjg2NCAzLj'
HTML += b'I2NCAwIDEuNzI4IDAuNjcyIDIuODggMC43NjggMS4xNTIgMi4xMTIgMi4wMT'
HTML += b'YgMS40NCAwLjg2NCAzLjM2IDEuNjMyIDEuOTIgMC42NzIgNC4zMiAxLjQ0ID'
HTML += b'MuNDU2IDEuMTUyIDcuMiAyLjU5MiAzLjc0NCAxLjM0NCA2LjgxNiAzLjY0OH'
HTML += b'Q1LjA4OCA1Ljc2cTIuMDE2IDMuMzYgMi4wMTYgOC40NDggMCA1Ljg1Ni0yLj'
HTML += b'IwOCAxMC4xNzYtMi4xMTIgNC4yMjQtNS43NiA3LjAwOHQtOC4zNTIgNC4xMj'
HTML += b'gtOS42OTYgMS4zNDRxLTcuMjk2IDAtMTQuMTEyLTIuNDk2LTYuODE2LTIuNT'
HTML += b'kyLTExLjMyOC03LjI5NmwxMC43NTItMTAuOTQ0cTIuNDk2IDMuMDcyIDYuNT'
HTML += b'I4IDUuMTg0IDQuMTI4IDIuMDE2IDguMTYgMi4wMTYgMS44MjQgMCAzLjU1Mi'
HTML += b'0wLjM4NHQyLjk3Ni0xLjI0OHExLjM0NC0wLjg2NCAyLjExMi0yLjMwNHQwLj'
HTML += b'c2OC0zLjQ1NnEwLTEuOTItMC45Ni0zLjI2NHQtMi43ODQtMi40cS0xLjcyOC'
HTML += b'0xLjE1Mi00LjQxNi0yLjAxNi0yLjU5Mi0wLjk2LTUuOTUyLTIuMDE2LTMuMj'
HTML += b'Y0LTEuMDU2LTYuNDMyLTIuNDk2LTMuMDcyLTEuNDQtNS41NjgtMy42NDgtMi'
HTML += b'40LTIuMzA0LTMuOTM2LTUuNDcyLTEuNDQtMy4yNjQtMS40NC03Ljg3MiAwLT'
HTML += b'UuNjY0IDIuMzA0LTkuNjk2dDYuMDQ4LTYuNjI0IDguNDQ4LTMuNzQ0cTQuNz'
HTML += b'A0LTEuMjQ4IDkuNTA0LTEuMjQ4IDUuNzYgMCAxMS43MTIgMi4xMTIgNi4wND'
HTML += b'ggMi4xMTIgMTAuNTYgNi4yNHoiLz4KICAgPHBhdGggZD0ibTE5MS44NCAyOD'
HTML += b'guN3YtNjcuOTY4aDUyLjE5bC0xLjI5ODggMTMuOTJoLTM1LjA1MXYxMi43Nj'
HTML += b'hoMzMuNDE5bC0xLjI5ODggMTMuMTUyaC0zMi4xMnYxNC4xMTJoMzEuNTg0bC'
HTML += b'0xLjI5ODggMTQuMDE2eiIvPgogIDwvZz4KICA8ZyB0cmFuc2Zvcm09Im1hdH'
HTML += b'JpeCguNDA3NDMgMCAwIC40MDc0MyAtNDAuMTY4IC03OC4wODIpIiBzdHJva2'
HTML += b'Utd2lkdGg9IjMuNzc5NSIgc3R5bGU9InNoYXBlLWluc2lkZTp1cmwoI3JlY3'
HTML += b'Q5NTItOS05KTtzaGFwZS1wYWRkaW5nOjYuNTMxNDQ7d2hpdGUtc3BhY2U6cH'
HTML += b'JlIiBhcmlhLWxhYmVsPSJweSI+CiAgIDxwYXRoIGQ9Im0xODcuNDMgMjY0Lj'
HTML += b'ZxMCA0Ljk5Mi0xLjUzNiA5LjZ0LTQuNTEyIDguMTZxLTIuODggMy40NTYtNy'
HTML += b'4xMDQgNS41Njh0LTkuNiAyLjExMnEtNC40MTYgMC04LjM1Mi0xLjcyOC0zLj'
HTML += b'kzNi0xLjgyNC02LjE0NC00Ljg5NmgtMC4xOTJ2MjguMzJoLTE1Ljc0NHYtNz'
HTML += b'AuODQ4aDE0Ljk3NnY1Ljg1NmgwLjI4OHEyLjIwOC0yLjg4IDYuMDQ4LTQuOT'
HTML += b'kyIDMuOTM2LTIuMjA4IDkuMjE2LTIuMjA4IDUuMTg0IDAgOS40MDggMi4wMT'
HTML += b'Z0Ny4xMDQgNS40NzJxMi45NzYgMy40NTYgNC41MTIgOC4wNjQgMS42MzIgNC'
HTML += b'41MTIgMS42MzIgOS41MDR6bS0xNS4yNjQgMHEwLTIuMzA0LTAuNzY4LTQuNT'
HTML += b'EyLTAuNjcyLTIuMjA4LTIuMTEyLTMuODQtMS4zNDQtMS43MjgtMy40NTYtMi'
HTML += b'43ODR0LTQuODk2LTEuMDU2cS0yLjY4OCAwLTQuOCAxLjA1NnQtMy42NDggMi'
HTML += b'43ODRxLTEuNDQgMS43MjgtMi4zMDQgMy45MzYtMC43NjggMi4yMDgtMC43Nj'
HTML += b'ggNC41MTJ0MC43NjggNC41MTJxMC44NjQgMi4yMDggMi4zMDQgMy45MzYgMS'
HTML += b'41MzYgMS43MjggMy42NDggMi43ODR0NC44IDEuMDU2cTIuNzg0IDAgNC44OT'
HTML += b'YtMS4wNTZ0My40NTYtMi43ODRxMS40NC0xLjcyOCAyLjExMi0zLjkzNiAwLj'
HTML += b'c2OC0yLjMwNCAwLjc2OC00LjYwOHoiLz4KICAgPHBhdGggZD0ibTIyNC4yOS'
HTML += b'AyOTUuOXEtMS40NCAzLjc0NC0zLjI2NCA2LjYyNC0xLjcyOCAyLjk3Ni00Lj'
HTML += b'IyNCA0Ljk5Mi0yLjQgMi4xMTItNS43NiAzLjE2OC0zLjI2NCAxLjA1Ni03Lj'
HTML += b'c3NiAxLjA1Ni0yLjIwOCAwLTQuNjA4LTAuMjg4LTIuMzA0LTAuMjg4LTQuMD'
HTML += b'MyLTAuNzY4bDEuNzI4LTEzLjI0OHExLjE1MiAwLjM4NCAyLjQ5NiAwLjU3Ni'
HTML += b'AxLjQ0IDAuMjg4IDIuNTkyIDAuMjg4IDMuNjQ4IDAgNS4yOC0xLjcyOCAxLj'
HTML += b'YzMi0xLjYzMiAyLjc4NC00LjcwNGwxLjUzNi0zLjkzNi0xOS45NjgtNDcuMD'
HTML += b'RoMTcuNDcybDEwLjY1NiAzMC43MmgwLjI4OGw5LjUwNC0zMC43MmgxNi43MD'
HTML += b'R6Ii8+CiAgPC9nPgogIDxwYXRoIGQ9Im02OC4wOTYgMTUuNzc1aDcuODAyOW'
HTML += b'wtOC45ODU0IDY5Ljc5MWgtNy44MDN6IiBzdHJva2Utd2lkdGg9IjEuMTE3Ni'
HTML += b'IvPgogIDxwYXRoIGQ9Im04My44NTMgMTUuNzQ4aDcuODAzbC04Ljk4NTQgNj'
HTML += b'kuNzkxaC03LjgwM3oiIHN0cm9rZS13aWR0aD0iMS4xMTc2Ii8+CiA8L2c+Cj'
HTML += b'wvc3ZnPgo=" /> </span> <span id="data-policy"></span> </div>'
HTML += b' </div>  <script>let debug = false; let quizSrc = {};var pys'
HTML += b'ell=(()=>{var A=Object.defineProperty;var pe=Object.getOwnPr'
HTML += b'opertyDescriptor;var ue=Object.getOwnPropertyNames;var de=Ob'
HTML += b'ject.prototype.hasOwnProperty;var f=(r,e)=>A(r,"name",{value'
HTML += b':e,configurable:!0});var me=(r,e)=>{for(var t in e)A(r,t,{ge'
HTML += b't:e[t],enumerable:!0})},fe=(r,e,t,s)=>{if(e&&typeof e=="obje'
HTML += b'ct"||typeof e=="function")for(let i of ue(e))!de.call(r,i)&&'
HTML += b'i!==t&&A(r,i,{get:()=>e[i],enumerable:!(s=pe(e,i))||s.enumer'
HTML += b'able});return r};var ge=r=>fe(A({},"__esModule",{value:!0}),'
HTML += b'r);var ke={};me(ke,{Quiz:()=>q,init:()=>be});function w(r=[]'
HTML += b'){let e=document.createElement("div");return e.append(...r),'
HTML += b'e}f(w,"genDiv");function j(r=[]){let e=document.createElemen'
HTML += b't("ul");return e.append(...r),e}f(j,"genUl");function O(r){l'
HTML += b'et e=document.createElement("li");return e.appendChild(r),e}'
HTML += b'f(O,"genLi");function W(r){let e=document.createElement("inp'
HTML += b'ut");return e.spellcheck=!1,e.type="text",e.classList.add("i'
HTML += b'nputField"),e.style.width=r+"px",e}f(W,"genInputField");func'
HTML += b'tion F(){let r=document.createElement("button");return r.typ'
HTML += b'e="button",r.classList.add("button"),r}f(F,"genButton");func'
HTML += b'tion k(r,e=[]){let t=document.createElement("span");return e'
HTML += b'.length>0?t.append(...e):t.innerHTML=r,t}f(k,"genSpan");func'
HTML += b'tion Q(r,e,t=!1){katex.render(e,r,{throwOnError:!1,displayMo'
HTML += b'de:t,macros:{"\\\\RR":"\\\\mathbb{R}","\\\\NN":"\\\\mathbb{N}","\\\\QQ'
HTML += b'":"\\\\mathbb{Q}","\\\\ZZ":"\\\\mathbb{Z}","\\\\CC":"\\\\mathbb{C}"}})'
HTML += b'}f(Q,"updateMathElement");function L(r,e=!1){let t=document.'
HTML += b'createElement("span");return Q(t,r,e),t}f(L,"genMathSpan");f'
HTML += b'unction K(r,e){let t=Array(e.length+1).fill(null).map(()=>Ar'
HTML += b'ray(r.length+1).fill(null));for(let s=0;s<=r.length;s+=1)t[0'
HTML += b'][s]=s;for(let s=0;s<=e.length;s+=1)t[s][0]=s;for(let s=1;s<'
HTML += b'=e.length;s+=1)for(let i=1;i<=r.length;i+=1){let l=r[i-1]==='
HTML += b'e[s-1]?0:1;t[s][i]=Math.min(t[s][i-1]+1,t[s-1][i]+1,t[s-1][i'
HTML += b'-1]+l)}return t[e.length][r.length]}f(K,"levenshteinDistance'
HTML += b'");var Z=\'<svg xmlns="http://www.w3.org/2000/svg" height="28'
HTML += b'" viewBox="0 0 448 512"><path d="M384 80c8.8 0 16 7.2 16 16V'
HTML += b'416c0 8.8-7.2 16-16 16H64c-8.8 0-16-7.2-16-16V96c0-8.8 7.2-1'
HTML += b'6 16-16H384zM64 32C28.7 32 0 60.7 0 96V416c0 35.3 28.7 64 64'
HTML += b' 64H384c35.3 0 64-28.7 64-64V96c0-35.3-28.7-64-64-64H64z"/><'
HTML += b'/svg>\',X=\'<svg xmlns="http://www.w3.org/2000/svg" height="28'
HTML += b'" viewBox="0 0 448 512"><path d="M64 80c-8.8 0-16 7.2-16 16V'
HTML += b'416c0 8.8 7.2 16 16 16H384c8.8 0 16-7.2 16-16V96c0-8.8-7.2-1'
HTML += b'6-16-16H64zM0 96C0 60.7 28.7 32 64 32H384c35.3 0 64 28.7 64 '
HTML += b'64V416c0 35.3-28.7 64-64 64H64c-35.3 0-64-28.7-64-64V96zM337'
HTML += b' 209L209 337c-9.4 9.4-24.6 9.4-33.9 0l-64-64c-9.4-9.4-9.4-24'
HTML += b'.6 0-33.9s24.6-9.4 33.9 0l47 47L303 175c9.4-9.4 24.6-9.4 33.'
HTML += b'9 0s9.4 24.6 0 33.9z"/>\',Y=\'<svg xmlns="http://www.w3.org/20'
HTML += b'00/svg" height="28" viewBox="0 0 512 512"><path d="M464 256A'
HTML += b'208 208 0 1 0 48 256a208 208 0 1 0 416 0zM0 256a256 256 0 1 '
HTML += b'1 512 0A256 256 0 1 1 0 256z"/></svg>\',G=\'<svg xmlns="http:/'
HTML += b'/www.w3.org/2000/svg" height="28" viewBox="0 0 512 512"><pat'
HTML += b'h d="M256 48a208 208 0 1 1 0 416 208 208 0 1 1 0-416zm0 464A'
HTML += b'256 256 0 1 0 256 0a256 256 0 1 0 0 512zM369 209c9.4-9.4 9.4'
HTML += b'-24.6 0-33.9s-24.6-9.4-33.9 0l-111 111-47-47c-9.4-9.4-24.6-9'
HTML += b'.4-33.9 0s-9.4 24.6 0 33.9l64 64c9.4 9.4 24.6 9.4 33.9 0L369'
HTML += b' 209z"/></svg>\',P=\'<svg xmlns="http://www.w3.org/2000/svg" w'
HTML += b'idth="50" height="25" viewBox="0 0 384 512" fill="white"><pa'
HTML += b'th d="M73 39c-14.8-9.1-33.4-9.4-48.5-.9S0 62.6 0 80V432c0 17'
HTML += b'.4 9.4 33.4 24.5 41.9s33.7 8.1 48.5-.9L361 297c14.3-8.7 23-2'
HTML += b'4.2 23-41s-8.7-32.2-23-41L73 39z"/></svg>\',J=\'<svg xmlns="ht'
HTML += b'tp://www.w3.org/2000/svg" width="50" height="25" viewBox="0 '
HTML += b'0 512 512" fill="white"><path d="M0 224c0 17.7 14.3 32 32 32'
HTML += b's32-14.3 32-32c0-53 43-96 96-96H320v32c0 12.9 7.8 24.6 19.8 '
HTML += b'29.6s25.7 2.2 34.9-6.9l64-64c12.5-12.5 12.5-32.8 0-45.3l-64-'
HTML += b'64c-9.2-9.2-22.9-11.9-34.9-6.9S320 19.1 320 32V64H160C71.6 6'
HTML += b'4 0 135.6 0 224zm512 64c0-17.7-14.3-32-32-32s-32 14.3-32 32c'
HTML += b'0 53-43 96-96 96H192V352c0-12.9-7.8-24.6-19.8-29.6s-25.7-2.2'
HTML += b'-34.9 6.9l-64 64c-12.5 12.5-12.5 32.8 0 45.3l64 64c9.2 9.2 2'
HTML += b'2.9 11.9 34.9 6.9s19.8-16.6 19.8-29.6V448H352c88.4 0 160-71.'
HTML += b'6 160-160z"/></svg>\';var $={en:"This page operates entirely '
HTML += b'in your browser and does not store any data on external serv'
HTML += b'ers.",de:"Diese Seite wird in Ihrem Browser ausgef\\xFChrt un'
HTML += b'd speichert keine Daten auf Servern.",es:"Esta p\\xE1gina se '
HTML += b'ejecuta en su navegador y no almacena ning\\xFAn dato en los '
HTML += b'servidores.",it:"Questa pagina viene eseguita nel browser e '
HTML += b'non memorizza alcun dato sui server.",fr:"Cette page fonctio'
HTML += b'nne dans votre navigateur et ne stocke aucune donn\\xE9e sur '
HTML += b'des serveurs."},ee={en:"* this page to receive a new set of '
HTML += b'randomized tasks.",de:"Sie k\\xF6nnen diese Seite *, um neue '
HTML += b'randomisierte Aufgaben zu erhalten.",es:"Puedes * esta p\\xE1'
HTML += b'gina para obtener nuevas tareas aleatorias.",it:"\\xC8 possib'
HTML += b'ile * questa pagina per ottenere nuovi compiti randomizzati"'
HTML += b',fr:"Vous pouvez * cette page pour obtenir de nouvelles t\\xE'
HTML += b'2ches al\\xE9atoires"},te={en:"Refresh",de:"aktualisieren",es'
HTML += b':"recargar",it:"ricaricare",fr:"recharger"},ie={en:["awesome'
HTML += b'","great","well done","nice","you got it","good"],de:["super'
HTML += b'","gut gemacht","weiter so","richtig"],es:["impresionante","'
HTML += b'genial","correcto","bien hecho"],it:["fantastico","grande","'
HTML += b'corretto","ben fatto"],fr:["g\\xE9nial","super","correct","bi'
HTML += b'en fait"]},se={en:["please complete all fields"],de:["bitte '
HTML += b'alles ausf\\xFCllen"],es:["por favor, rellene todo"],it:["com'
HTML += b'pilare tutto"],fr:["remplis tout s\'il te plait"]},ne={en:["t'
HTML += b'ry again","still some mistakes","wrong answer","no"],de:["le'
HTML += b'ider falsch","nicht richtig","versuch\'s nochmal"],es:["int\\x'
HTML += b'E9ntalo de nuevo","todav\\xEDa algunos errores","respuesta in'
HTML += b'correcta"],it:["riprova","ancora qualche errore","risposta s'
HTML += b'bagliata"],fr:["r\\xE9essayer","encore des erreurs","mauvaise'
HTML += b' r\\xE9ponse"]},re={en:"point(s)",de:"Punkt(e)",es:"punto(s)"'
HTML += b',it:"punto/i",fr:"point(s)"},ae={en:"Evaluate now",de:"Jetzt'
HTML += b' auswerten",es:"Evaluar ahora",it:"Valuta ora",fr:"\\xC9value'
HTML += b'r maintenant"},le={en:"Data Policy: This website does not co'
HTML += b'llect, store, or process any personal data on external serve'
HTML += b'rs. All functionality is executed locally in your browser, e'
HTML += b'nsuring complete privacy. No cookies are used, and no data i'
HTML += b's transmitted to or from the server. Your activity on this s'
HTML += b'ite remains entirely private and local to your device.",de:"'
HTML += b'Datenschutzrichtlinie: Diese Website sammelt, speichert oder'
HTML += b' verarbeitet keine personenbezogenen Daten auf externen Serv'
HTML += b'ern. Alle Funktionen werden lokal in Ihrem Browser ausgef\\xF'
HTML += b'Chrt, um vollst\\xE4ndige Privatsph\\xE4re zu gew\\xE4hrleisten'
HTML += b'. Es werden keine Cookies verwendet, und es werden keine Dat'
HTML += b'en an den Server gesendet oder von diesem empfangen. Ihre Ak'
HTML += b'tivit\\xE4t auf dieser Seite bleibt vollst\\xE4ndig privat und'
HTML += b' lokal auf Ihrem Ger\\xE4t.",es:"Pol\\xEDtica de datos: Este s'
HTML += b'itio web no recopila, almacena ni procesa ning\\xFAn dato per'
HTML += b'sonal en servidores externos. Toda la funcionalidad se ejecu'
HTML += b'ta localmente en su navegador, garantizando una privacidad c'
HTML += b'ompleta. No se utilizan cookies y no se transmiten datos hac'
HTML += b'ia o desde el servidor. Su actividad en este sitio permanece'
HTML += b' completamente privada y local en su dispositivo.",it:"Polit'
HTML += b'ica sui dati: Questo sito web non raccoglie, memorizza o ela'
HTML += b'bora alcun dato personale su server esterni. Tutte le funzio'
HTML += b'nalit\\xE0 vengono eseguite localmente nel tuo browser, garan'
HTML += b'tendo una privacy completa. Non vengono utilizzati cookie e '
HTML += b'nessun dato viene trasmesso da o verso il server. La tua att'
HTML += b'ivit\\xE0 su questo sito rimane completamente privata e local'
HTML += b'e sul tuo dispositivo.",fr:"Politique de confidentialit\\xE9:'
HTML += b' Ce site web ne collecte, ne stocke ni ne traite aucune donn'
HTML += b'\\xE9e personnelle sur des serveurs externes. Toutes les fonc'
HTML += b'tionnalit\\xE9s sont ex\\xE9cut\\xE9es localement dans votre na'
HTML += b'vigateur, garantissant une confidentialit\\xE9 totale. Aucun '
HTML += b'cookie n\\u2019est utilis\\xE9 et aucune donn\\xE9e n\\u2019est '
HTML += b'transmise vers ou depuis le serveur. Votre activit\\xE9 sur c'
HTML += b'e site reste enti\\xE8rement priv\\xE9e et locale sur votre ap'
HTML += b'pareil."},oe={en:"You have a limited time to complete this q'
HTML += b'uiz. The countdown, displayed in minutes, is visible at the '
HTML += b"top-left of the screen. When you're ready to begin, simply p"
HTML += b'ress the Start button.",de:"Die Zeit f\\xFCr dieses Quiz ist '
HTML += b'begrenzt. Der Countdown, in Minuten angezeigt, l\\xE4uft oben'
HTML += b' links auf dem Bildschirm. Mit dem Start-Button beginnt das '
HTML += b'Quiz.",es:"Tienes un tiempo limitado para completar este cue'
HTML += b'stionario. La cuenta regresiva, mostrada en minutos, se encu'
HTML += b'entra en la parte superior izquierda de la pantalla. Cuando '
HTML += b'est\\xE9s listo, simplemente presiona el bot\\xF3n de inicio."'
HTML += b',it:"Hai un tempo limitato per completare questo quiz. Il co'
HTML += b'nto alla rovescia, visualizzato in minuti, \\xE8 visibile in '
HTML += b'alto a sinistra dello schermo. Quando sei pronto, premi semp'
HTML += b'licemente il pulsante Start.",fr:"Vous disposez d\\u2019un te'
HTML += b'mps limit\\xE9 pour compl\\xE9ter ce quiz. Le compte \\xE0 rebo'
HTML += b'urs, affich\\xE9 en minutes, est visible en haut \\xE0 gauche '
HTML += b'de l\\u2019\\xE9cran. Lorsque vous \\xEAtes pr\\xEAt, appuyez si'
HTML += b'mplement sur le bouton D\\xE9marrer."};function z(r,e=!1){let'
HTML += b' t=new Array(r);for(let s=0;s<r;s++)t[s]=s;if(e)for(let s=0;'
HTML += b's<r;s++){let i=Math.floor(Math.random()*r),l=Math.floor(Math'
HTML += b'.random()*r),o=t[i];t[i]=t[l],t[l]=o}return t}f(z,"range");f'
HTML += b'unction N(r,e,t=-1){if(t<0&&(t=r.length),t==1){e.push([...r]'
HTML += b');return}for(let s=0;s<t;s++){N(r,e,t-1);let i=t%2==0?s:0,l='
HTML += b'r[i];r[i]=r[t-1],r[t-1]=l}}f(N,"heapsAlgorithm");var E=class'
HTML += b' r{static{f(this,"Matrix")}constructor(e,t){this.m=e,this.n='
HTML += b't,this.v=new Array(e*t).fill("0")}getElement(e,t){return e<0'
HTML += b'||e>=this.m||t<0||t>=this.n?"":this.v[e*this.n+t]}resize(e,t'
HTML += b',s){if(e<1||e>50||t<1||t>50)return!1;let i=new r(e,t);i.v.fi'
HTML += b'll(s);for(let l=0;l<i.m;l++)for(let o=0;o<i.n;o++)i.v[l*i.n+'
HTML += b'o]=this.getElement(l,o);return this.fromMatrix(i),!0}fromMat'
HTML += b'rix(e){this.m=e.m,this.n=e.n,this.v=[...e.v]}fromString(e){t'
HTML += b'his.m=e.split("],").length,this.v=e.replaceAll("[","").repla'
HTML += b'ceAll("]","").split(",").map(t=>t.trim()),this.n=this.v.leng'
HTML += b'th/this.m}getMaxCellStrlen(){let e=0;for(let t of this.v)t.l'
HTML += b'ength>e&&(e=t.length);return e}toTeXString(e=!1,t=!0){let s='
HTML += b'"";t?s+=e?"\\\\left[\\\\begin{array}":"\\\\begin{bmatrix}":s+=e?"\\'
HTML += b'\\left(\\\\begin{array}":"\\\\begin{pmatrix}",e&&(s+="{"+"c".repe'
HTML += b'at(this.n-1)+"|c}");for(let i=0;i<this.m;i++){for(let l=0;l<'
HTML += b'this.n;l++){l>0&&(s+="&");let o=this.getElement(i,l);try{o=b'
HTML += b'.parse(o).toTexString()}catch{}s+=o}s+="\\\\\\\\"}return t?s+=e?'
HTML += b'"\\\\end{array}\\\\right]":"\\\\end{bmatrix}":s+=e?"\\\\end{array}\\\\'
HTML += b'right)":"\\\\end{pmatrix}",s}},b=class r{static{f(this,"Term")'
HTML += b'}constructor(){this.root=null,this.src="",this.token="",this'
HTML += b'.skippedWhiteSpace=!1,this.pos=0}clone(){let e=new r;return '
HTML += b'e.root=this.root.clone(),e}getVars(e,t="",s=null){if(s==null'
HTML += b'&&(s=this.root),s.op.startsWith("var:")){let i=s.op.substrin'
HTML += b'g(4);(t.length==0||t.length>0&&i.startsWith(t))&&e.add(i)}fo'
HTML += b'r(let i of s.c)this.getVars(e,t,i)}setVars(e,t=null){t==null'
HTML += b'&&(t=this.root);for(let s of t.c)this.setVars(e,s);if(t.op.s'
HTML += b'tartsWith("var:")){let s=t.op.substring(4);if(s in e){let i='
HTML += b'e[s].clone();t.op=i.op,t.c=i.c,t.re=i.re,t.im=i.im}}}renameV'
HTML += b'ar(e,t,s=null){s==null&&(s=this.root);for(let i of s.c)this.'
HTML += b'renameVar(e,t,i);s.op.startsWith("var:")&&s.op.substring(4)='
HTML += b'==e&&(s.op="var:"+t)}eval(e,t=null){let i=a.const(),l=0,o=0,'
HTML += b'c=null;switch(t==null&&(t=this.root),t.op){case"const":i=t;b'
HTML += b'reak;case"+":case"-":case"*":case"/":case"^":{let n=this.eva'
HTML += b'l(e,t.c[0]),h=this.eval(e,t.c[1]);switch(t.op){case"+":i.re='
HTML += b'n.re+h.re,i.im=n.im+h.im;break;case"-":i.re=n.re-h.re,i.im=n'
HTML += b'.im-h.im;break;case"*":i.re=n.re*h.re-n.im*h.im,i.im=n.re*h.'
HTML += b'im+n.im*h.re;break;case"/":l=h.re*h.re+h.im*h.im,i.re=(n.re*'
HTML += b'h.re+n.im*h.im)/l,i.im=(n.im*h.re-n.re*h.im)/l;break;case"^"'
HTML += b':c=new a("exp",[new a("*",[h,new a("ln",[n])])]),i=this.eval'
HTML += b'(e,c);break}break}case".-":case"abs":case"acos":case"acosh":'
HTML += b'case"asin":case"asinh":case"atan":case"atanh":case"ceil":cas'
HTML += b'e"cos":case"cosh":case"cot":case"exp":case"floor":case"ln":c'
HTML += b'ase"log":case"log10":case"log2":case"round":case"sin":case"s'
HTML += b'inc":case"sinh":case"sqrt":case"tan":case"tanh":{let n=this.'
HTML += b'eval(e,t.c[0]);switch(t.op){case".-":i.re=-n.re,i.im=-n.im;b'
HTML += b'reak;case"abs":i.re=Math.sqrt(n.re*n.re+n.im*n.im),i.im=0;br'
HTML += b'eak;case"acos":c=new a("*",[a.const(0,-1),new a("ln",[new a('
HTML += b'"+",[a.const(0,1),new a("sqrt",[new a("-",[a.const(1,0),new '
HTML += b'a("*",[n,n])])])])])]),i=this.eval(e,c);break;case"acosh":c='
HTML += b'new a("*",[n,new a("sqrt",[new a("-",[new a("*",[n,n]),a.con'
HTML += b'st(1,0)])])]),i=this.eval(e,c);break;case"asin":c=new a("*",'
HTML += b'[a.const(0,-1),new a("ln",[new a("+",[new a("*",[a.const(0,1'
HTML += b'),n]),new a("sqrt",[new a("-",[a.const(1,0),new a("*",[n,n])'
HTML += b'])])])])]),i=this.eval(e,c);break;case"asinh":c=new a("*",[n'
HTML += b',new a("sqrt",[new a("+",[new a("*",[n,n]),a.const(1,0)])])]'
HTML += b'),i=this.eval(e,c);break;case"atan":c=new a("*",[a.const(0,.'
HTML += b'5),new a("ln",[new a("/",[new a("-",[a.const(0,1),new a("*",'
HTML += b'[a.const(0,1),n])]),new a("+",[a.const(0,1),new a("*",[a.con'
HTML += b'st(0,1),n])])])])]),i=this.eval(e,c);break;case"atanh":c=new'
HTML += b' a("*",[a.const(.5,0),new a("ln",[new a("/",[new a("+",[a.co'
HTML += b'nst(1,0),n]),new a("-",[a.const(1,0),n])])])]),i=this.eval(e'
HTML += b',c);break;case"ceil":i.re=Math.ceil(n.re),i.im=Math.ceil(n.i'
HTML += b'm);break;case"cos":i.re=Math.cos(n.re)*Math.cosh(n.im),i.im='
HTML += b'-Math.sin(n.re)*Math.sinh(n.im);break;case"cosh":c=new a("*"'
HTML += b',[a.const(.5,0),new a("+",[new a("exp",[n]),new a("exp",[new'
HTML += b' a(".-",[n])])])]),i=this.eval(e,c);break;case"cot":l=Math.s'
HTML += b'in(n.re)*Math.sin(n.re)+Math.sinh(n.im)*Math.sinh(n.im),i.re'
HTML += b'=Math.sin(n.re)*Math.cos(n.re)/l,i.im=-(Math.sinh(n.im)*Math'
HTML += b'.cosh(n.im))/l;break;case"exp":i.re=Math.exp(n.re)*Math.cos('
HTML += b'n.im),i.im=Math.exp(n.re)*Math.sin(n.im);break;case"floor":i'
HTML += b'.re=Math.floor(n.re),i.im=Math.floor(n.im);break;case"ln":ca'
HTML += b'se"log":i.re=Math.log(Math.sqrt(n.re*n.re+n.im*n.im)),l=Math'
HTML += b'.abs(n.im)<1e-9?0:n.im,i.im=Math.atan2(l,n.re);break;case"lo'
HTML += b'g10":c=new a("/",[new a("ln",[n]),new a("ln",[a.const(10)])]'
HTML += b'),i=this.eval(e,c);break;case"log2":c=new a("/",[new a("ln",'
HTML += b'[n]),new a("ln",[a.const(2)])]),i=this.eval(e,c);break;case"'
HTML += b'round":i.re=Math.round(n.re),i.im=Math.round(n.im);break;cas'
HTML += b'e"sin":i.re=Math.sin(n.re)*Math.cosh(n.im),i.im=Math.cos(n.r'
HTML += b'e)*Math.sinh(n.im);break;case"sinc":c=new a("/",[new a("sin"'
HTML += b',[n]),n]),i=this.eval(e,c);break;case"sinh":c=new a("*",[a.c'
HTML += b'onst(.5,0),new a("-",[new a("exp",[n]),new a("exp",[new a(".'
HTML += b'-",[n])])])]),i=this.eval(e,c);break;case"sqrt":c=new a("^",'
HTML += b'[n,a.const(.5)]),i=this.eval(e,c);break;case"tan":l=Math.cos'
HTML += b'(n.re)*Math.cos(n.re)+Math.sinh(n.im)*Math.sinh(n.im),i.re=M'
HTML += b'ath.sin(n.re)*Math.cos(n.re)/l,i.im=Math.sinh(n.im)*Math.cos'
HTML += b'h(n.im)/l;break;case"tanh":c=new a("/",[new a("-",[new a("ex'
HTML += b'p",[n]),new a("exp",[new a(".-",[n])])]),new a("+",[new a("e'
HTML += b'xp",[n]),new a("exp",[new a(".-",[n])])])]),i=this.eval(e,c)'
HTML += b';break}break}default:if(t.op.startsWith("var:")){let n=t.op.'
HTML += b'substring(4);if(n==="pi")return a.const(Math.PI);if(n==="e")'
HTML += b'return a.const(Math.E);if(n==="i")return a.const(0,1);if(n=='
HTML += b'="true")return a.const(1);if(n==="false")return a.const(0);i'
HTML += b'f(n in e)return e[n];throw new Error("eval-error: unknown va'
HTML += b'riable \'"+n+"\'")}else throw new Error("UNIMPLEMENTED eval \'"'
HTML += b'+t.op+"\'")}return i}static parse(e){let t=new r;if(t.src=e,t'
HTML += b'.token="",t.skippedWhiteSpace=!1,t.pos=0,t.next(),t.root=t.p'
HTML += b'arseExpr(!1),t.token!=="")throw new Error("remaining tokens:'
HTML += b' "+t.token+"...");return t}parseExpr(e){return this.parseAdd'
HTML += b'(e)}parseAdd(e){let t=this.parseMul(e);for(;["+","-"].includ'
HTML += b'es(this.token)&&!(e&&this.skippedWhiteSpace);){let s=this.to'
HTML += b'ken;this.next(),t=new a(s,[t,this.parseMul(e)])}return t}par'
HTML += b'seMul(e){let t=this.parsePow(e);for(;!(e&&this.skippedWhiteS'
HTML += b'pace);){let s="*";if(["*","/"].includes(this.token))s=this.t'
HTML += b'oken,this.next();else if(!e&&this.token==="(")s="*";else if('
HTML += b'this.token.length>0&&(this.isAlpha(this.token[0])||this.isNu'
HTML += b'm(this.token[0])))s="*";else break;t=new a(s,[t,this.parsePo'
HTML += b'w(e)])}return t}parsePow(e){let t=this.parseUnary(e);for(;["'
HTML += b'^"].includes(this.token)&&!(e&&this.skippedWhiteSpace);){let'
HTML += b' s=this.token;this.next(),t=new a(s,[t,this.parseUnary(e)])}'
HTML += b'return t}parseUnary(e){return this.token==="-"?(this.next(),'
HTML += b'new a(".-",[this.parseMul(e)])):this.parseInfix(e)}parseInfi'
HTML += b'x(e){if(this.token.length==0)throw new Error("expected unary'
HTML += b'");if(this.isNum(this.token[0])){let t=this.token;return thi'
HTML += b's.next(),this.token==="."&&(t+=".",this.next(),this.token.le'
HTML += b'ngth>0&&(t+=this.token,this.next())),new a("const",[],parseF'
HTML += b'loat(t))}else if(this.fun1().length>0){let t=this.fun1();thi'
HTML += b's.next(t.length);let s=null;if(this.token==="(")if(this.next'
HTML += b'(),s=this.parseExpr(e),this.token+="",this.token===")")this.'
HTML += b'next();else throw Error("expected \')\'");else s=this.parseMul'
HTML += b'(!0);return new a(t,[s])}else if(this.token==="("){this.next'
HTML += b'();let t=this.parseExpr(e);if(this.token+="",this.token===")'
HTML += b'")this.next();else throw Error("expected \')\'");return t.expl'
HTML += b'icitParentheses=!0,t}else if(this.token==="|"){this.next();l'
HTML += b'et t=this.parseExpr(e);if(this.token+="",this.token==="|")th'
HTML += b'is.next();else throw Error("expected \'|\'");return new a("abs'
HTML += b'",[t])}else if(this.isAlpha(this.token[0])){let t="";return '
HTML += b'this.token.startsWith("pi")?t="pi":this.token.startsWith("tr'
HTML += b'ue")?t="true":this.token.startsWith("false")?t="false":this.'
HTML += b'token.startsWith("C1")?t="C1":this.token.startsWith("C2")?t='
HTML += b'"C2":t=this.token[0],t==="I"&&(t="i"),this.next(t.length),ne'
HTML += b'w a("var:"+t,[])}else throw new Error("expected unary")}stat'
HTML += b'ic compare(e,t,s={}){let o=new Set;e.getVars(o),t.getVars(o)'
HTML += b';for(let c=0;c<10;c++){let n={};for(let g of o)g in s?n[g]=s'
HTML += b'[g]:n[g]=a.const(Math.random(),Math.random());let h=e.eval(n'
HTML += b'),p=t.eval(n),m=h.re-p.re,d=h.im-p.im;if(Math.sqrt(m*m+d*d)>'
HTML += b'1e-9)return!1}return!0}fun1(){let e=["abs","acos","acosh","a'
HTML += b'sin","asinh","atan","atanh","ceil","cos","cosh","cot","exp",'
HTML += b'"floor","ln","log","log10","log2","round","sin","sinc","sinh'
HTML += b'","sqrt","tan","tanh"];for(let t of e)if(this.token.toLowerC'
HTML += b'ase().startsWith(t))return t;return""}next(e=-1){if(e>0&&thi'
HTML += b's.token.length>e){this.token=this.token.substring(e),this.sk'
HTML += b'ippedWhiteSpace=!1;return}this.token="";let t=!1,s=this.src.'
HTML += b'length;for(this.skippedWhiteSpace=!1;this.pos<s&&`\t\n `.inclu'
HTML += b'des(this.src[this.pos]);)this.skippedWhiteSpace=!0,this.pos+'
HTML += b'+;for(;!t&&this.pos<s;){let i=this.src[this.pos];if(this.tok'
HTML += b'en.length>0&&(this.isNum(this.token[0])&&this.isAlpha(i)||th'
HTML += b'is.isAlpha(this.token[0])&&this.isNum(i))&&this.token!="C")r'
HTML += b'eturn;if(`^%#*$()[]{},.:;+-*/_!<>=?|\t\n `.includes(i)){if(thi'
HTML += b's.token.length>0)return;t=!0}`\t\n `.includes(i)==!1&&(this.to'
HTML += b'ken+=i),this.pos++}}isNum(e){return e.charCodeAt(0)>=48&&e.c'
HTML += b'harCodeAt(0)<=57}isAlpha(e){return e.charCodeAt(0)>=65&&e.ch'
HTML += b'arCodeAt(0)<=90||e.charCodeAt(0)>=97&&e.charCodeAt(0)<=122||'
HTML += b'e==="_"}toString(){return this.root==null?"":this.root.toStr'
HTML += b'ing()}toTexString(){return this.root==null?"":this.root.toTe'
HTML += b'xString()}},a=class r{static{f(this,"TermNode")}constructor('
HTML += b'e,t,s=0,i=0){this.op=e,this.c=t,this.re=s,this.im=i,this.exp'
HTML += b'licitParentheses=!1}clone(){let e=new r(this.op,this.c.map(t'
HTML += b'=>t.clone()),this.re,this.im);return e.explicitParentheses=t'
HTML += b'his.explicitParentheses,e}static const(e=0,t=0){return new r'
HTML += b'("const",[],e,t)}compare(e,t=0,s=1e-9){let i=this.re-e,l=thi'
HTML += b's.im-t;return Math.sqrt(i*i+l*l)<s}toString(){let e="";if(th'
HTML += b'is.op==="const"){let t=Math.abs(this.re)>1e-14,s=Math.abs(th'
HTML += b'is.im)>1e-14;t&&s&&this.im>=0?e="("+this.re+"+"+this.im+"i)"'
HTML += b':t&&s&&this.im<0?e="("+this.re+"-"+-this.im+"i)":t&&this.re>'
HTML += b'0?e=""+this.re:t&&this.re<0?e="("+this.re+")":s?e="("+this.i'
HTML += b'm+"i)":e="0"}else this.op.startsWith("var")?e=this.op.split('
HTML += b'":")[1]:this.c.length==1?e=(this.op===".-"?"-":this.op)+"("+'
HTML += b'this.c.toString()+")":e="("+this.c.map(t=>t.toString()).join'
HTML += b'(this.op)+")";return e}toTexString(e=!1){let s="";switch(thi'
HTML += b's.op){case"const":{let i=Math.abs(this.re)>1e-9,l=Math.abs(t'
HTML += b'his.im)>1e-9,o=i?""+this.re:"",c=l?""+this.im+"i":"";c==="1i'
HTML += b'"?c="i":c==="-1i"&&(c="-i"),!i&&!l?s="0":(l&&this.im>=0&&i&&'
HTML += b'(c="+"+c),s=o+c);break}case".-":s="-"+this.c[0].toTexString('
HTML += b');break;case"+":case"-":case"*":case"^":{let i=this.c[0].toT'
HTML += b'exString(),l=this.c[1].toTexString(),o=this.op==="*"?"\\\\cdot'
HTML += b' ":this.op;s="{"+i+"}"+o+"{"+l+"}";break}case"/":{let i=this'
HTML += b'.c[0].toTexString(!0),l=this.c[1].toTexString(!0);s="\\\\frac{'
HTML += b'"+i+"}{"+l+"}";break}case"floor":{let i=this.c[0].toTexStrin'
HTML += b'g(!0);s+="\\\\"+this.op+"\\\\left\\\\lfloor"+i+"\\\\right\\\\rfloor";b'
HTML += b'reak}case"ceil":{let i=this.c[0].toTexString(!0);s+="\\\\"+thi'
HTML += b's.op+"\\\\left\\\\lceil"+i+"\\\\right\\\\rceil";break}case"round":{l'
HTML += b'et i=this.c[0].toTexString(!0);s+="\\\\"+this.op+"\\\\left["+i+"'
HTML += b'\\\\right]";break}case"acos":case"acosh":case"asin":case"asinh'
HTML += b'":case"atan":case"atanh":case"cos":case"cosh":case"cot":case'
HTML += b'"exp":case"ln":case"log":case"log10":case"log2":case"sin":ca'
HTML += b'se"sinc":case"sinh":case"tan":case"tanh":{let i=this.c[0].to'
HTML += b'TexString(!0);s+="\\\\"+this.op+"\\\\left("+i+"\\\\right)";break}c'
HTML += b'ase"sqrt":{let i=this.c[0].toTexString(!0);s+="\\\\"+this.op+"'
HTML += b'{"+i+"}";break}case"abs":{let i=this.c[0].toTexString(!0);s+'
HTML += b'="\\\\left|"+i+"\\\\right|";break}default:if(this.op.startsWith('
HTML += b'"var:")){let i=this.op.substring(4);switch(i){case"pi":i="\\\\'
HTML += b'pi";break}s=" "+i+" "}else{let i="warning: Node.toString(..)'
HTML += b':";i+=" unimplemented operator \'"+this.op+"\'",console.log(i)'
HTML += b',s=this.op,this.c.length>0&&(s+="\\\\left({"+this.c.map(l=>l.t'
HTML += b'oTexString(!0)).join(",")+"}\\\\right)")}}return!e&&this.expli'
HTML += b'citParentheses&&(s="\\\\left({"+s+"}\\\\right)"),s}};function ce'
HTML += b'(r,e){let t=1e-9;if(b.compare(r,e))return!0;r=r.clone(),e=e.'
HTML += b'clone(),_(r.root),_(e.root);let s=new Set;r.getVars(s),e.get'
HTML += b'Vars(s);let i=[],l=[];for(let n of s.keys())n.startsWith("C"'
HTML += b')?i.push(n):l.push(n);let o=i.length;for(let n=0;n<o;n++){le'
HTML += b't h=i[n];r.renameVar(h,"_C"+n),e.renameVar(h,"_C"+n)}for(let'
HTML += b' n=0;n<o;n++)r.renameVar("_C"+n,"C"+n),e.renameVar("_C"+n,"C'
HTML += b'"+n);i=[];for(let n=0;n<o;n++)i.push("C"+n);let c=[];N(z(o),'
HTML += b'c);for(let n of c){let h=r.clone(),p=e.clone();for(let d=0;d'
HTML += b'<o;d++)p.renameVar("C"+d,"__C"+n[d]);for(let d=0;d<o;d++)p.r'
HTML += b'enameVar("__C"+d,"C"+d);let m=!0;for(let d=0;d<o;d++){let u='
HTML += b'"C"+d,g={};g[u]=new a("*",[new a("var:C"+d,[]),new a("var:K"'
HTML += b',[])]),p.setVars(g);let v={};v[u]=a.const(Math.random(),Math'
HTML += b'.random());for(let y=0;y<o;y++)d!=y&&(v["C"+y]=a.const(0,0))'
HTML += b';let M=new a("abs",[new a("-",[h.root,p.root])]),S=new b;S.r'
HTML += b'oot=M;for(let y of l)v[y]=a.const(Math.random(),Math.random('
HTML += b'));let C=ve(S,"K",v)[0];p.setVars({K:a.const(C,0)}),v={};for'
HTML += b'(let y=0;y<o;y++)d!=y&&(v["C"+y]=a.const(0,0));if(b.compare('
HTML += b'h,p,v)==!1){m=!1;break}}if(m&&b.compare(h,p))return!0}return'
HTML += b'!1}f(ce,"compareODE");function ve(r,e,t){let s=1e-11,i=1e3,l'
HTML += b'=0,o=0,c=1,n=888;for(;l<i;){t[e]=a.const(o);let p=r.eval(t).'
HTML += b're;t[e]=a.const(o+c);let m=r.eval(t).re;t[e]=a.const(o-c);le'
HTML += b't d=r.eval(t).re,u=0;if(m<p&&(p=m,u=1),d<p&&(p=d,u=-1),u==1&'
HTML += b'&(o+=c),u==-1&&(o-=c),p<s)break;(u==0||u!=n)&&(c/=2),n=u,l++'
HTML += b'}t[e]=a.const(o);let h=r.eval(t).re;return[o,h]}f(ve,"minimi'
HTML += b'ze");function _(r){for(let e of r.c)_(e);switch(r.op){case"+'
HTML += b'":case"-":case"*":case"/":case"^":{let e=[r.c[0].op,r.c[1].o'
HTML += b'p],t=[e[0]==="const",e[1]==="const"],s=[e[0].startsWith("var'
HTML += b':C"),e[1].startsWith("var:C")];s[0]&&t[1]?(r.op=r.c[0].op,r.'
HTML += b'c=[]):s[1]&&t[0]?(r.op=r.c[1].op,r.c=[]):s[0]&&s[1]&&e[0]==e'
HTML += b'[1]&&(r.op=r.c[0].op,r.c=[]);break}case".-":case"abs":case"s'
HTML += b'in":case"sinc":case"cos":case"tan":case"cot":case"exp":case"'
HTML += b'ln":case"log":case"sqrt":r.c[0].op.startsWith("var:C")&&(r.o'
HTML += b'p=r.c[0].op,r.c=[]);break}}f(_,"prepareODEconstantComparison'
HTML += b'");var B=class{static{f(this,"GapInput")}constructor(e,t,s,i'
HTML += b'){this.question=t,this.inputId=s,s.length==0&&(this.inputId='
HTML += b's="gap-"+t.gapIdx,t.types[this.inputId]="string",t.expected['
HTML += b'this.inputId]=i,t.gapIdx++),s in t.student||(t.student[s]=""'
HTML += b');let l=i.split("|"),o=0;for(let p=0;p<l.length;p++){let m=l'
HTML += b'[p];m.length>o&&(o=m.length)}let c=k("");e.appendChild(c);le'
HTML += b't n=Math.max(o*15,24),h=W(n);if(t.gapInputs[this.inputId]=h,'
HTML += b'h.addEventListener("keyup",()=>{t.editingEnabled!=!1&&(this.'
HTML += b'question.editedQuestion(),h.value=h.value.toUpperCase(),this'
HTML += b'.question.student[this.inputId]=h.value.trim())}),c.appendCh'
HTML += b'ild(h),this.question.showSolution&&(this.question.student[th'
HTML += b'is.inputId]=h.value=l[0],l.length>1)){let p=k("["+l.join("|"'
HTML += b')+"]");p.style.fontSize="small",p.style.textDecoration="unde'
HTML += b'rline",c.appendChild(p)}}},I=class{static{f(this,"TermInput"'
HTML += b')}constructor(e,t,s,i,l,o,c=!1){s in t.student||(t.student[s'
HTML += b']=""),this.question=t,this.inputId=s,this.outerSpan=k(""),th'
HTML += b'is.outerSpan.style.position="relative",e.appendChild(this.ou'
HTML += b'terSpan),this.inputElement=W(Math.max(i*12,48)),this.outerSp'
HTML += b'an.appendChild(this.inputElement),this.equationPreviewDiv=w('
HTML += b'),this.equationPreviewDiv.classList.add("equationPreview"),t'
HTML += b'his.equationPreviewDiv.style.display="none",this.outerSpan.a'
HTML += b'ppendChild(this.equationPreviewDiv),this.inputElement.addEve'
HTML += b'ntListener("click",()=>{t.editingEnabled!=!1&&(this.question'
HTML += b'.editedQuestion(),this.edited())}),this.inputElement.addEven'
HTML += b'tListener("keyup",()=>{t.editingEnabled!=!1&&(this.question.'
HTML += b'editedQuestion(),this.edited())}),this.inputElement.addEvent'
HTML += b'Listener("focus",()=>{t.editingEnabled!=!1}),this.inputEleme'
HTML += b'nt.addEventListener("focusout",()=>{this.equationPreviewDiv.'
HTML += b'innerHTML="",this.equationPreviewDiv.style.display="none"}),'
HTML += b'this.inputElement.addEventListener("keydown",n=>{if(t.editin'
HTML += b'gEnabled==!1){n.preventDefault();return}let h="abcdefghijklm'
HTML += b'nopqrstuvwxyz";h+="ABCDEFGHIJKLMNOPQRSTUVWXYZ",h+="012345678'
HTML += b'9",h+="+-*/^(). <>=|",o&&(h="-0123456789"),n.key.length<3&&h'
HTML += b'.includes(n.key)==!1&&n.preventDefault();let p=this.inputEle'
HTML += b'ment.value.length*12;this.inputElement.offsetWidth<p&&(this.'
HTML += b'inputElement.style.width=""+p+"px")}),(c||this.question.show'
HTML += b'Solution)&&(t.student[s]=this.inputElement.value=l)}edited()'
HTML += b'{let e=this.inputElement.value.trim(),t="",s=!1;try{let i=b.'
HTML += b'parse(e);s=i.root.op==="const",t=i.toTexString(),this.inputE'
HTML += b'lement.style.color="black",this.equationPreviewDiv.style.bac'
HTML += b'kgroundColor="green"}catch{t=e.replaceAll("^","\\\\hat{~}").re'
HTML += b'placeAll("_","\\\\_"),this.inputElement.style.color="maroon",t'
HTML += b'his.equationPreviewDiv.style.backgroundColor="maroon"}Q(this'
HTML += b'.equationPreviewDiv,t,!0),this.equationPreviewDiv.style.disp'
HTML += b'lay=e.length>0&&!s?"block":"none",this.question.student[this'
HTML += b'.inputId]=e}},H=class{static{f(this,"MatrixInput")}construct'
HTML += b'or(e,t,s,i){this.parent=e,this.question=t,this.inputId=s,thi'
HTML += b's.matExpected=new E(0,0),this.matExpected.fromString(i),this'
HTML += b'.matStudent=new E(this.matExpected.m==1?1:3,this.matExpected'
HTML += b'.n==1?1:3),t.showSolution&&this.matStudent.fromMatrix(this.m'
HTML += b'atExpected),this.genMatrixDom(!0)}genMatrixDom(e){let t=w();'
HTML += b'this.parent.innerHTML="",this.parent.appendChild(t),t.style.'
HTML += b'position="relative",t.style.display="inline-block";let s=doc'
HTML += b'ument.createElement("table");t.appendChild(s);let i=this.mat'
HTML += b'Expected.getMaxCellStrlen();for(let u=0;u<this.matStudent.m;'
HTML += b'u++){let g=document.createElement("tr");s.appendChild(g),u=='
HTML += b'0&&g.appendChild(this.generateMatrixParenthesis(!0,this.matS'
HTML += b'tudent.m));for(let v=0;v<this.matStudent.n;v++){let M=u*this'
HTML += b'.matStudent.n+v,S=document.createElement("td");g.appendChild'
HTML += b'(S);let C=this.inputId+"-"+M;new I(S,this.question,C,i,this.'
HTML += b'matStudent.v[M],!1,!e)}u==0&&g.appendChild(this.generateMatr'
HTML += b'ixParenthesis(!1,this.matStudent.m))}let l=["+","-","+","-"]'
HTML += b',o=[0,0,1,-1],c=[1,-1,0,0],n=[0,22,888,888],h=[888,888,-22,-'
HTML += b'22],p=[-22,-22,0,22],m=[this.matExpected.n!=1,this.matExpect'
HTML += b'ed.n!=1,this.matExpected.m!=1,this.matExpected.m!=1],d=[this'
HTML += b'.matStudent.n>=10,this.matStudent.n<=1,this.matStudent.m>=10'
HTML += b',this.matStudent.m<=1];for(let u=0;u<4;u++){if(m[u]==!1)cont'
HTML += b'inue;let g=k(l[u]);n[u]!=888&&(g.style.top=""+n[u]+"px"),h[u'
HTML += b']!=888&&(g.style.bottom=""+h[u]+"px"),p[u]!=888&&(g.style.ri'
HTML += b'ght=""+p[u]+"px"),g.classList.add("matrixResizeButton"),t.ap'
HTML += b'pendChild(g),d[u]?g.style.opacity="0.5":g.addEventListener("'
HTML += b'click",()=>{for(let v=0;v<this.matStudent.m;v++)for(let M=0;'
HTML += b'M<this.matStudent.n;M++){let S=v*this.matStudent.n+M,C=this.'
HTML += b'inputId+"-"+S,T=this.question.student[C];this.matStudent.v[S'
HTML += b']=T,delete this.question.student[C]}this.matStudent.resize(t'
HTML += b'his.matStudent.m+o[u],this.matStudent.n+c[u],""),this.genMat'
HTML += b'rixDom(!1)})}}generateMatrixParenthesis(e,t){let s=document.'
HTML += b'createElement("td");s.style.width="3px";for(let i of["Top",e'
HTML += b'?"Left":"Right","Bottom"])s.style["border"+i+"Width"]="2px",'
HTML += b's.style["border"+i+"Style"]="solid";return this.question.lan'
HTML += b'guage=="de"&&(e?s.style.borderTopLeftRadius="5px":s.style.bo'
HTML += b'rderTopRightRadius="5px",e?s.style.borderBottomLeftRadius="5'
HTML += b'px":s.style.borderBottomRightRadius="5px"),s.rowSpan=t,s}};v'
HTML += b'ar x={init:0,errors:1,passed:2,incomplete:3},V=class{static{'
HTML += b'f(this,"Question")}constructor(e,t,s,i){this.state=x.init,th'
HTML += b'is.language=s,this.src=t,this.debug=i,this.instanceOrder=z(t'
HTML += b'.instances.length,!0),this.instanceIdx=0,this.choiceIdx=0,th'
HTML += b'is.includesSingleChoice=!1,this.gapIdx=0,this.expected={},th'
HTML += b'is.types={},this.student={},this.gapInputs={},this.parentDiv'
HTML += b'=e,this.questionDiv=null,this.feedbackPopupDiv=null,this.tit'
HTML += b'leDiv=null,this.checkAndRepeatBtn=null,this.showSolution=!1,'
HTML += b'this.feedbackSpan=null,this.numCorrect=0,this.numChecked=0,t'
HTML += b'his.hasCheckButton=!0,this.editingEnabled=!0}reset(){this.ga'
HTML += b'pIdx=0,this.choiceIdx=0,this.instanceIdx=(this.instanceIdx+1'
HTML += b')%this.src.instances.length}getCurrentInstance(){let e=this.'
HTML += b'instanceOrder[this.instanceIdx];return this.src.instances[e]'
HTML += b'}editedQuestion(){this.state=x.init,this.updateVisualQuestio'
HTML += b'nState(),this.questionDiv.style.color="black",this.checkAndR'
HTML += b'epeatBtn.innerHTML=P,this.checkAndRepeatBtn.style.display="b'
HTML += b'lock",this.checkAndRepeatBtn.style.color="black"}updateVisua'
HTML += b'lQuestionState(){let e="black",t="transparent";switch(this.s'
HTML += b'tate){case x.init:e="black";break;case x.passed:e="var(--gre'
HTML += b'en)",t="rgba(0,150,0, 0.035)";break;case x.incomplete:case x'
HTML += b'.errors:e="var(--red)",t="rgba(150,0,0, 0.035)",this.include'
HTML += b'sSingleChoice==!1&&this.numChecked>=5&&(this.feedbackSpan.in'
HTML += b'nerHTML="&nbsp;&nbsp;"+this.numCorrect+" / "+this.numChecked'
HTML += b');break}this.questionDiv.style.backgroundColor=t,this.questi'
HTML += b'onDiv.style.borderColor=e}populateDom(e=!1){if(this.parentDi'
HTML += b'v.innerHTML="",this.questionDiv=w(),this.parentDiv.appendChi'
HTML += b'ld(this.questionDiv),this.questionDiv.classList.add("questio'
HTML += b'n"),this.feedbackPopupDiv=w(),this.feedbackPopupDiv.classLis'
HTML += b't.add("questionFeedback"),this.questionDiv.appendChild(this.'
HTML += b'feedbackPopupDiv),this.feedbackPopupDiv.innerHTML="awesome",'
HTML += b'this.debug&&"src_line"in this.src){let i=w();i.classList.add'
HTML += b'("debugInfo"),i.innerHTML="Source code: lines "+this.src.src'
HTML += b'_line+"..",this.questionDiv.appendChild(i)}if(this.titleDiv='
HTML += b'w(),this.questionDiv.appendChild(this.titleDiv),this.titleDi'
HTML += b'v.classList.add("questionTitle"),this.titleDiv.innerHTML=thi'
HTML += b's.src.title,this.src.error.length>0){let i=k(this.src.error)'
HTML += b';this.questionDiv.appendChild(i),i.style.color="red";return}'
HTML += b'let t=this.getCurrentInstance();if(t!=null&&"__svg_image"in '
HTML += b't){let i=t.__svg_image.v,l=w();this.questionDiv.appendChild('
HTML += b'l);let o=document.createElement("img");l.appendChild(o),o.cl'
HTML += b'assList.add("img"),o.src="data:image/svg+xml;base64,"+i}for('
HTML += b'let i of this.src.text.c)this.questionDiv.appendChild(this.g'
HTML += b'enerateText(i));let s=w();if(s.innerHTML="",s.classList.add('
HTML += b'"button-group"),this.questionDiv.appendChild(s),this.hasChec'
HTML += b'kButton=Object.keys(this.expected).length>0,this.hasCheckBut'
HTML += b'ton&&(this.checkAndRepeatBtn=F(),s.appendChild(this.checkAnd'
HTML += b'RepeatBtn),this.checkAndRepeatBtn.innerHTML=P,this.checkAndR'
HTML += b'epeatBtn.style.backgroundColor="black",e&&(this.checkAndRepe'
HTML += b'atBtn.style.height="0",this.checkAndRepeatBtn.style.visibili'
HTML += b'ty="hidden")),this.feedbackSpan=k(""),this.feedbackSpan.styl'
HTML += b'e.userSelect="none",s.appendChild(this.feedbackSpan),this.de'
HTML += b'bug){if(this.src.variables.length>0){let o=w();o.classList.a'
HTML += b'dd("debugInfo"),o.innerHTML="Variables generated by Python C'
HTML += b'ode",this.questionDiv.appendChild(o);let c=w();c.classList.a'
HTML += b'dd("debugCode"),this.questionDiv.appendChild(c);let n=this.g'
HTML += b'etCurrentInstance(),h="",p=[...this.src.variables];p.sort();'
HTML += b'for(let m of p){let d=n[m].t,u=n[m].v;switch(d){case"vector"'
HTML += b':u="["+u+"]";break;case"set":u="{"+u+"}";break}h+=d+" "+m+" '
HTML += b'= "+u+"<br/>"}c.innerHTML=h}let i=["python_src_html","text_s'
HTML += b'rc_html"],l=["Python Source Code","Text Source Code"];for(le'
HTML += b't o=0;o<i.length;o++){let c=i[o];if(c in this.src&&this.src['
HTML += b'c].length>0){let n=w();n.classList.add("debugInfo"),n.innerH'
HTML += b'TML=l[o],this.questionDiv.appendChild(n);let h=w();h.classLi'
HTML += b'st.add("debugCode"),this.questionDiv.append(h),h.innerHTML=t'
HTML += b'his.src[c]}}}this.hasCheckButton&&this.checkAndRepeatBtn.add'
HTML += b'EventListener("click",()=>{this.state==x.passed?(this.state='
HTML += b'x.init,this.editingEnabled=!0,this.reset(),this.populateDom('
HTML += b')):R(this)})}generateMathString(e){let t="";switch(e.t){case'
HTML += b'"math":case"display-math":for(let s of e.c){let i=this.gener'
HTML += b'ateMathString(s);s.t==="var"&&t.includes("!PM")&&(i.startsWi'
HTML += b'th("{-")?(i="{"+i.substring(2),t=t.replaceAll("!PM","-")):t='
HTML += b't.replaceAll("!PM","+")),t+=i}break;case"text":return e.d;ca'
HTML += b'se"plus_minus":{t+=" !PM ";break}case"var":{let s=this.getCu'
HTML += b'rrentInstance(),i=s[e.d].t,l=s[e.d].v;switch(i){case"vector"'
HTML += b':return"\\\\left["+l+"\\\\right]";case"set":return"\\\\left\\\\{"+l+'
HTML += b'"\\\\right\\\\}";case"complex":{let o=l.split(","),c=parseFloat('
HTML += b'o[0]),n=parseFloat(o[1]);return a.const(c,n).toTexString()}c'
HTML += b'ase"matrix":{let o=new E(0,0);return o.fromString(l),t=o.toT'
HTML += b'eXString(e.d.includes("augmented"),this.language!="de"),t}ca'
HTML += b'se"term":{try{t=b.parse(l).toTexString()}catch{}break}defaul'
HTML += b't:t=l}}}return e.t==="plus_minus"?t:"{"+t+"}"}generateText(e'
HTML += b',t=!1){switch(e.t){case"paragraph":case"span":{let s=documen'
HTML += b't.createElement(e.t=="span"||t?"span":"p");for(let i of e.c)'
HTML += b's.appendChild(this.generateText(i));return s.style.userSelec'
HTML += b't="none",s}case"text":return k(e.d);case"code":{let s=k(e.d)'
HTML += b';return s.classList.add("code"),s}case"italic":case"bold":{l'
HTML += b'et s=k("");return s.append(...e.c.map(i=>this.generateText(i'
HTML += b'))),e.t==="bold"?s.style.fontWeight="bold":s.style.fontStyle'
HTML += b'="italic",s}case"math":case"display-math":{let s=this.genera'
HTML += b'teMathString(e);return L(s,e.t==="display-math")}case"string'
HTML += b'_var":{let s=k(""),i=this.getCurrentInstance(),l=i[e.d].t,o='
HTML += b'i[e.d].v;return l==="string"?s.innerHTML=o:(s.innerHTML="EXP'
HTML += b'ECTED VARIABLE OF TYPE STRING",s.style.color="red"),s}case"g'
HTML += b'ap":{let s=k("");return new B(s,this,"",e.d),s}case"input":c'
HTML += b'ase"input2":{let s=e.t==="input2",i=k("");i.style.verticalAl'
HTML += b'ign="text-bottom";let l=e.d,o=this.getCurrentInstance()[l];i'
HTML += b'f(this.expected[l]=o.v,this.types[l]=o.t,!s)switch(o.t){case'
HTML += b'"set":i.append(L("\\\\{"),k(" "));break;case"vector":i.append('
HTML += b'L("["),k(" "));break}if(o.t==="string")new B(i,this,l,this.e'
HTML += b'xpected[l]);else if(o.t==="vector"||o.t==="set"){let c=o.v.s'
HTML += b'plit(","),n=c.length;for(let h=0;h<n;h++){h>0&&i.appendChild'
HTML += b'(k(" , "));let p=l+"-"+h;new I(i,this,p,c[h].length,c[h],!1)'
HTML += b'}}else if(o.t==="matrix"){let c=w();i.appendChild(c),new H(c'
HTML += b',this,l,o.v)}else if(o.t==="complex"){let c=o.v.split(",");n'
HTML += b'ew I(i,this,l+"-0",c[0].length,c[0],!1),i.append(k(" "),L("+'
HTML += b'"),k(" ")),new I(i,this,l+"-1",c[1].length,c[1],!1),i.append'
HTML += b'(k(" "),L("i"))}else{let c=o.t==="int";new I(i,this,l,o.v.le'
HTML += b'ngth,o.v,c)}if(!s)switch(o.t){case"set":i.append(k(" "),L("\\'
HTML += b'\\}"));break;case"vector":i.append(k(" "),L("]"));break}retur'
HTML += b'n i}case"itemize":return j(e.c.map(s=>O(this.generateText(s)'
HTML += b')));case"single-choice":case"multi-choice":{let s=e.t=="mult'
HTML += b'i-choice";s||(this.includesSingleChoice=!0);let i=document.c'
HTML += b'reateElement("table"),l=e.c.length,o=this.debug==!1,c=z(l,o)'
HTML += b',n=s?X:G,h=s?Z:Y,p=[],m=[];for(let d=0;d<l;d++){let u=c[d],g'
HTML += b'=e.c[u],v="mc-"+this.choiceIdx+"-"+u;m.push(v);let M=g.c[0].'
HTML += b't=="bool"?g.c[0].d:this.getCurrentInstance()[g.c[0].d].v;thi'
HTML += b's.expected[v]=M,this.types[v]="bool",this.student[v]=this.sh'
HTML += b'owSolution?M:"false";let S=this.generateText(g.c[1],!0),C=do'
HTML += b'cument.createElement("tr");i.appendChild(C),C.style.cursor="'
HTML += b'pointer";let T=document.createElement("td");p.push(T),C.appe'
HTML += b'ndChild(T),T.innerHTML=this.student[v]=="true"?n:h;let y=doc'
HTML += b'ument.createElement("td");C.appendChild(y),y.appendChild(S),'
HTML += b's?C.addEventListener("click",()=>{this.editingEnabled!=!1&&('
HTML += b'this.editedQuestion(),this.student[v]=this.student[v]==="tru'
HTML += b'e"?"false":"true",this.student[v]==="true"?T.innerHTML=n:T.i'
HTML += b'nnerHTML=h)}):C.addEventListener("click",()=>{if(this.editin'
HTML += b'gEnabled!=!1){this.editedQuestion();for(let D of m)this.stud'
HTML += b'ent[D]="false";this.student[v]="true";for(let D=0;D<m.length'
HTML += b';D++){let U=c[D];p[U].innerHTML=this.student[m[U]]=="true"?n'
HTML += b':h}}})}return this.choiceIdx++,i}case"image":{let s=w(),l=e.'
HTML += b'd.split("."),o=l[l.length-1],c=e.c[0].d,n=e.c[1].d,h=documen'
HTML += b't.createElement("img");s.appendChild(h),h.classList.add("img'
HTML += b'"),h.style.width=c+"%";let p={svg:"svg+xml",png:"png",jpg:"j'
HTML += b'peg"};return h.src="data:image/"+p[o]+";base64,"+n,s}default'
HTML += b':{let s=k("UNIMPLEMENTED("+e.t+")");return s.style.color="re'
HTML += b'd",s}}}};function R(r){r.feedbackSpan.innerHTML="",r.numChec'
HTML += b'ked=0,r.numCorrect=0;let e=!0;for(let i in r.expected){let l'
HTML += b'=r.types[i],o=r.student[i],c=r.expected[i];switch(o!=null&&o'
HTML += b'.length==0&&(e=!1),l){case"bool":r.numChecked++,o.toLowerCas'
HTML += b'e()===c.toLowerCase()&&r.numCorrect++;break;case"string":{r.'
HTML += b'numChecked++;let n=r.gapInputs[i],h=o.trim().toUpperCase(),p'
HTML += b'=c.trim().toUpperCase().split("|"),m=!1;for(let d of p)if(K('
HTML += b'h,d)<=1){m=!0,r.numCorrect++,r.gapInputs[i].value=d,r.studen'
HTML += b't[i]=d;break}n.style.color=m?"black":"white",n.style.backgro'
HTML += b'undColor=m?"transparent":"maroon";break}case"int":r.numCheck'
HTML += b'ed++,Math.abs(parseFloat(o)-parseFloat(c))<1e-9&&r.numCorrec'
HTML += b't++;break;case"float":case"term":{r.numChecked++;try{let n=b'
HTML += b'.parse(c),h=b.parse(o),p=!1;r.src.is_ode?p=ce(n,h):p=b.compa'
HTML += b're(n,h),p&&r.numCorrect++}catch(n){r.debug&&(console.log("te'
HTML += b'rm invalid"),console.log(n))}break}case"vector":case"complex'
HTML += b'":case"set":{let n=c.split(",");r.numChecked+=n.length;let h'
HTML += b'=[];for(let p=0;p<n.length;p++){let m=r.student[i+"-"+p];m.l'
HTML += b'ength==0&&(e=!1),h.push(m)}if(l==="set")for(let p=0;p<n.leng'
HTML += b'th;p++)try{let m=b.parse(n[p]);for(let d=0;d<h.length;d++){l'
HTML += b'et u=b.parse(h[d]);if(b.compare(m,u)){r.numCorrect++;break}}'
HTML += b'}catch(m){r.debug&&console.log(m)}else for(let p=0;p<n.lengt'
HTML += b'h;p++)try{let m=b.parse(h[p]),d=b.parse(n[p]);b.compare(m,d)'
HTML += b'&&r.numCorrect++}catch(m){r.debug&&console.log(m)}break}case'
HTML += b'"matrix":{let n=new E(0,0);n.fromString(c),r.numChecked+=n.m'
HTML += b'*n.n;for(let h=0;h<n.m;h++)for(let p=0;p<n.n;p++){let m=h*n.'
HTML += b'n+p;o=r.student[i+"-"+m],o!=null&&o.length==0&&(e=!1);let d='
HTML += b'n.v[m];try{let u=b.parse(d),g=b.parse(o);b.compare(u,g)&&r.n'
HTML += b'umCorrect++}catch(u){r.debug&&console.log(u)}}break}default:'
HTML += b'r.feedbackSpan.innerHTML="UNIMPLEMENTED EVAL OF TYPE "+l}}e='
HTML += b'=!1?r.state=x.incomplete:r.state=r.numCorrect==r.numChecked?'
HTML += b'x.passed:x.errors,r.updateVisualQuestionState();let t=[];swi'
HTML += b'tch(r.state){case x.passed:t=ie[r.language];break;case x.inc'
HTML += b'omplete:t=se[r.language];break;case x.errors:t=ne[r.language'
HTML += b'];break}let s=t[Math.floor(Math.random()*t.length)];r.feedba'
HTML += b'ckPopupDiv.innerHTML=s,r.feedbackPopupDiv.style.color=r.stat'
HTML += b'e===x.passed?"var(--green)":"var(--red)",r.feedbackPopupDiv.'
HTML += b'style.display="flex",setTimeout(()=>{r.feedbackPopupDiv.styl'
HTML += b'e.display="none"},1e3),r.editingEnabled=!0,r.state===x.passe'
HTML += b'd?(r.editingEnabled=!1,r.src.instances.length>1?r.checkAndRe'
HTML += b'peatBtn.innerHTML=J:r.checkAndRepeatBtn.style.visibility="hi'
HTML += b'dden"):r.checkAndRepeatBtn!=null&&(r.checkAndRepeatBtn.inner'
HTML += b'HTML=P)}f(R,"evalQuestion");function be(r,e){new q(r,e)}f(be'
HTML += b',"init");var q=class{static{f(this,"Quiz")}constructor(e,t){'
HTML += b'this.quizSrc=e,["en","de","es","it","fr"].includes(this.quiz'
HTML += b'Src.lang)==!1&&(this.quizSrc.lang="en"),this.debug=t,this.de'
HTML += b'bug&&(document.getElementById("debug").style.display="block"'
HTML += b'),this.questions=[],this.timeLeft=e.timer,this.timeLimited=e'
HTML += b'.timer>0,this.fillPageMetadata(),this.timeLimited?(document.'
HTML += b'getElementById("timer-info").style.display="block",document.'
HTML += b'getElementById("timer-info-text").innerHTML=oe[this.quizSrc.'
HTML += b'lang],document.getElementById("start-btn").addEventListener('
HTML += b'"click",()=>{document.getElementById("timer-info").style.dis'
HTML += b'play="none",this.generateQuestions(),this.runTimer()})):this'
HTML += b'.generateQuestions()}fillPageMetadata(){if(document.getEleme'
HTML += b'ntById("date").innerHTML=this.quizSrc.date,document.getEleme'
HTML += b'ntById("title").innerHTML=this.quizSrc.title,document.getEle'
HTML += b'mentById("author").innerHTML=this.quizSrc.author,this.quizSr'
HTML += b'c.info.length>0)document.getElementById("courseInfo1").inner'
HTML += b'HTML=this.quizSrc.info;else{document.getElementById("courseI'
HTML += b'nfo1").innerHTML=$[this.quizSrc.lang];let e=\'<span onclick="'
HTML += b'location.reload()" style="text-decoration: none; font-weight'
HTML += b': bold; cursor: pointer">\'+te[this.quizSrc.lang]+"</span>";d'
HTML += b'ocument.getElementById("courseInfo2").innerHTML=ee[this.quiz'
HTML += b'Src.lang].replace("*",e)}document.getElementById("data-polic'
HTML += b'y").innerHTML=le[this.quizSrc.lang]}generateQuestions(){let '
HTML += b'e=document.getElementById("questions"),t=1;for(let s of this'
HTML += b'.quizSrc.questions){s.title=""+t+". "+s.title;let i=w();e.ap'
HTML += b'pendChild(i);let l=new V(i,s,this.quizSrc.lang,this.debug);l'
HTML += b'.showSolution=this.debug,this.questions.push(l),l.populateDo'
HTML += b'm(this.timeLimited),this.debug&&s.error.length==0&&l.hasChec'
HTML += b'kButton&&l.checkAndRepeatBtn.click(),t++}}runTimer(){documen'
HTML += b't.getElementById("stop-now").style.display="block",document.'
HTML += b'getElementById("stop-now-btn").innerHTML=ae[this.quizSrc.lan'
HTML += b'g],document.getElementById("stop-now-btn").addEventListener('
HTML += b'"click",()=>{this.timeLeft=1});let e=document.getElementById'
HTML += b'("timer");e.style.display="block",e.innerHTML=he(this.timeLe'
HTML += b'ft);let t=setInterval(()=>{this.timeLeft--,e.innerHTML=he(th'
HTML += b'is.timeLeft),this.timeLeft<=0&&this.stopTimer(t)},1e3)}stopT'
HTML += b'imer(e){document.getElementById("stop-now").style.display="n'
HTML += b'one",clearInterval(e);let t=0,s=0;for(let l of this.question'
HTML += b's){let o=l.src.points;s+=o,R(l),l.state===x.passed&&(t+=o),l'
HTML += b'.editingEnabled=!1}document.getElementById("questions-eval")'
HTML += b'.style.display="block";let i=document.getElementById("questi'
HTML += b'ons-eval-percentage");i.innerHTML=s==0?"":""+t+" / "+s+" "+r'
HTML += b'e[this.quizSrc.lang]+" <br/><br/>"+Math.round(t/s*100)+" %"}'
HTML += b'};function he(r){let e=Math.floor(r/60),t=r%60;return e+":"+'
HTML += b'(""+t).padStart(2,"0")}f(he,"formatTime");return ge(ke);})()'
HTML += b';pysell.init(quizSrc,debug);</script></body> </html> '
HTML = HTML.decode('utf-8')
# @end(html)


def main():
    """the main function"""

    print("---------------------------------------------------------------------")
    print("pySELL by Andreas Schwenk - Licensed under GPLv3 - https://pysell.org")
    print("---------------------------------------------------------------------")

    # get input and output path
    if len(sys.argv) < 2:
        print("USAGE: pysell [-J] INPUT_PATH.txt")
        print("   option -J enables to output a JSON file for debugging purposes")
        print("EXAMPLE: pysell my-quiz.txt")
        print(
            "   compiles quiz definition in file 'my-quiz.txt' to file 'my-quiz.html'"
        )
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
        f.write(
            HTML.replace(
                "let quizSrc = {};",
                "/*@PYSELL_JSON@*/let quizSrc = " + output_json + ";/*@PYSELL_JSON@*/",
            )
        )

    # exit normally
    sys.exit(0)


if __name__ == "__main__":
    main()
