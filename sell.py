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
HTML += b' id="timer" class="timer">02:34</div> <h1 id="title"></h1> <'
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
HTML += b'green)" > jetzt auswerten (TODO: translate) </button> </div>'
HTML += b' <br /> <div id="questions-eval" class="eval" style="display'
HTML += b': none"> <h1 id="questions-eval-percentage">0 %</h1> </div> '
HTML += b'</div>  <br /><br /><br /><br />  <div class="footer"> <div '
HTML += b'class="contents"> <span id="date"></span> &mdash; This quiz '
HTML += b'was developed using pySELL, a Python-based Simple E-Learning'
HTML += b' Language &mdash; <a href="https://pysell.org" style="color:'
HTML += b' var(--grey)" >https://pysell.org</a > <br /> <span style="w'
HTML += b'idth: 64px"> <img style="max-width: 48px; padding: 16px 0px"'
HTML += b' src="data:image/svg+xml;base64,PD94bWwgdmVyc2lvbj0iMS4wIiBl'
HTML += b'bmNvZGluZz0iVVRGLTgiPz4KPCEtLSBDcmVhdGVkIHdpdGggSW5rc2NhcGUg'
HTML += b'KGh0dHA6Ly93d3cuaW5rc2NhcGUub3JnLykgLS0+Cjxzdmcgd2lkdGg9IjEw'
HTML += b'MG1tIiBoZWlnaHQ9IjEwMG1tIiB2ZXJzaW9uPSIxLjEiIHZpZXdCb3g9IjAg'
HTML += b'MCAxMDAgMTAwIiB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmci'
HTML += b'IHhtbG5zOnhsaW5rPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5L3hsaW5rIj4K'
HTML += b'IDxkZWZzPgogIDxsaW5lYXJHcmFkaWVudCBpZD0ibGluZWFyR3JhZGllbnQz'
HTML += b'NjU4IiB4MT0iMjguNTI3IiB4Mj0iMTI4LjUzIiB5MT0iNzkuNjQ4IiB5Mj0i'
HTML += b'NzkuNjQ4IiBncmFkaWVudFRyYW5zZm9ybT0ibWF0cml4KDEuMDE2MSAwIDAg'
HTML += b'MS4wMTYxIC0yOS43OSAtMzAuOTI4KSIgZ3JhZGllbnRVbml0cz0idXNlclNw'
HTML += b'YWNlT25Vc2UiPgogICA8c3RvcCBzdG9wLWNvbG9yPSIjNTkwMDVlIiBvZmZz'
HTML += b'ZXQ9IjAiLz4KICAgPHN0b3Agc3RvcC1jb2xvcj0iI2FkMDA3ZiIgb2Zmc2V0'
HTML += b'PSIxIi8+CiAgPC9saW5lYXJHcmFkaWVudD4KIDwvZGVmcz4KIDxyZWN0IHdp'
HTML += b'ZHRoPSIxMDAiIGhlaWdodD0iMTAwIiByeT0iMCIgZmlsbD0idXJsKCNsaW5l'
HTML += b'YXJHcmFkaWVudDM2NTgpIi8+CiA8ZyBmaWxsPSIjZmZmIj4KICA8ZyB0cmFu'
HTML += b'c2Zvcm09Im1hdHJpeCguNDA3NDMgMCAwIC40MDc0MyAtNDIuODQyIC0zNi4x'
HTML += b'MzYpIiBzdHJva2Utd2lkdGg9IjMuNzc5NSIgc3R5bGU9InNoYXBlLWluc2lk'
HTML += b'ZTp1cmwoI3JlY3Q5NTItNyk7c2hhcGUtcGFkZGluZzo2LjUzMTQ0O3doaXRl'
HTML += b'LXNwYWNlOnByZSIgYXJpYS1sYWJlbD0iU0VMTCI+CiAgIDxwYXRoIGQ9Im0x'
HTML += b'NzEuMDEgMjM4LjM5cS0yLjExMi0yLjY4OC01LjU2OC00LjIyNC0zLjM2LTEu'
HTML += b'NjMyLTYuNTI4LTEuNjMyLTEuNjMyIDAtMy4zNiAwLjI4OC0xLjYzMiAwLjI4'
HTML += b'OC0yLjk3NiAxLjE1Mi0xLjM0NCAwLjc2OC0yLjMwNCAyLjExMi0wLjg2NCAx'
HTML += b'LjI0OC0wLjg2NCAzLjI2NCAwIDEuNzI4IDAuNjcyIDIuODggMC43NjggMS4x'
HTML += b'NTIgMi4xMTIgMi4wMTYgMS40NCAwLjg2NCAzLjM2IDEuNjMyIDEuOTIgMC42'
HTML += b'NzIgNC4zMiAxLjQ0IDMuNDU2IDEuMTUyIDcuMiAyLjU5MiAzLjc0NCAxLjM0'
HTML += b'NCA2LjgxNiAzLjY0OHQ1LjA4OCA1Ljc2cTIuMDE2IDMuMzYgMi4wMTYgOC40'
HTML += b'NDggMCA1Ljg1Ni0yLjIwOCAxMC4xNzYtMi4xMTIgNC4yMjQtNS43NiA3LjAw'
HTML += b'OHQtOC4zNTIgNC4xMjgtOS42OTYgMS4zNDRxLTcuMjk2IDAtMTQuMTEyLTIu'
HTML += b'NDk2LTYuODE2LTIuNTkyLTExLjMyOC03LjI5NmwxMC43NTItMTAuOTQ0cTIu'
HTML += b'NDk2IDMuMDcyIDYuNTI4IDUuMTg0IDQuMTI4IDIuMDE2IDguMTYgMi4wMTYg'
HTML += b'MS44MjQgMCAzLjU1Mi0wLjM4NHQyLjk3Ni0xLjI0OHExLjM0NC0wLjg2NCAy'
HTML += b'LjExMi0yLjMwNHQwLjc2OC0zLjQ1NnEwLTEuOTItMC45Ni0zLjI2NHQtMi43'
HTML += b'ODQtMi40cS0xLjcyOC0xLjE1Mi00LjQxNi0yLjAxNi0yLjU5Mi0wLjk2LTUu'
HTML += b'OTUyLTIuMDE2LTMuMjY0LTEuMDU2LTYuNDMyLTIuNDk2LTMuMDcyLTEuNDQt'
HTML += b'NS41NjgtMy42NDgtMi40LTIuMzA0LTMuOTM2LTUuNDcyLTEuNDQtMy4yNjQt'
HTML += b'MS40NC03Ljg3MiAwLTUuNjY0IDIuMzA0LTkuNjk2dDYuMDQ4LTYuNjI0IDgu'
HTML += b'NDQ4LTMuNzQ0cTQuNzA0LTEuMjQ4IDkuNTA0LTEuMjQ4IDUuNzYgMCAxMS43'
HTML += b'MTIgMi4xMTIgNi4wNDggMi4xMTIgMTAuNTYgNi4yNHoiLz4KICAgPHBhdGgg'
HTML += b'ZD0ibTE5MS44NCAyODguN3YtNjcuOTY4aDUyLjE5bC0xLjI5ODggMTMuOTJo'
HTML += b'LTM1LjA1MXYxMi43NjhoMzMuNDE5bC0xLjI5ODggMTMuMTUyaC0zMi4xMnYx'
HTML += b'NC4xMTJoMzEuNTg0bC0xLjI5ODggMTQuMDE2eiIvPgogIDwvZz4KICA8ZyB0'
HTML += b'cmFuc2Zvcm09Im1hdHJpeCguNDA3NDMgMCAwIC40MDc0MyAtNDAuMTY4IC03'
HTML += b'OC4wODIpIiBzdHJva2Utd2lkdGg9IjMuNzc5NSIgc3R5bGU9InNoYXBlLWlu'
HTML += b'c2lkZTp1cmwoI3JlY3Q5NTItOS05KTtzaGFwZS1wYWRkaW5nOjYuNTMxNDQ7'
HTML += b'd2hpdGUtc3BhY2U6cHJlIiBhcmlhLWxhYmVsPSJweSI+CiAgIDxwYXRoIGQ9'
HTML += b'Im0xODcuNDMgMjY0LjZxMCA0Ljk5Mi0xLjUzNiA5LjZ0LTQuNTEyIDguMTZx'
HTML += b'LTIuODggMy40NTYtNy4xMDQgNS41Njh0LTkuNiAyLjExMnEtNC40MTYgMC04'
HTML += b'LjM1Mi0xLjcyOC0zLjkzNi0xLjgyNC02LjE0NC00Ljg5NmgtMC4xOTJ2Mjgu'
HTML += b'MzJoLTE1Ljc0NHYtNzAuODQ4aDE0Ljk3NnY1Ljg1NmgwLjI4OHEyLjIwOC0y'
HTML += b'Ljg4IDYuMDQ4LTQuOTkyIDMuOTM2LTIuMjA4IDkuMjE2LTIuMjA4IDUuMTg0'
HTML += b'IDAgOS40MDggMi4wMTZ0Ny4xMDQgNS40NzJxMi45NzYgMy40NTYgNC41MTIg'
HTML += b'OC4wNjQgMS42MzIgNC41MTIgMS42MzIgOS41MDR6bS0xNS4yNjQgMHEwLTIu'
HTML += b'MzA0LTAuNzY4LTQuNTEyLTAuNjcyLTIuMjA4LTIuMTEyLTMuODQtMS4zNDQt'
HTML += b'MS43MjgtMy40NTYtMi43ODR0LTQuODk2LTEuMDU2cS0yLjY4OCAwLTQuOCAx'
HTML += b'LjA1NnQtMy42NDggMi43ODRxLTEuNDQgMS43MjgtMi4zMDQgMy45MzYtMC43'
HTML += b'NjggMi4yMDgtMC43NjggNC41MTJ0MC43NjggNC41MTJxMC44NjQgMi4yMDgg'
HTML += b'Mi4zMDQgMy45MzYgMS41MzYgMS43MjggMy42NDggMi43ODR0NC44IDEuMDU2'
HTML += b'cTIuNzg0IDAgNC44OTYtMS4wNTZ0My40NTYtMi43ODRxMS40NC0xLjcyOCAy'
HTML += b'LjExMi0zLjkzNiAwLjc2OC0yLjMwNCAwLjc2OC00LjYwOHoiLz4KICAgPHBh'
HTML += b'dGggZD0ibTIyNC4yOSAyOTUuOXEtMS40NCAzLjc0NC0zLjI2NCA2LjYyNC0x'
HTML += b'LjcyOCAyLjk3Ni00LjIyNCA0Ljk5Mi0yLjQgMi4xMTItNS43NiAzLjE2OC0z'
HTML += b'LjI2NCAxLjA1Ni03Ljc3NiAxLjA1Ni0yLjIwOCAwLTQuNjA4LTAuMjg4LTIu'
HTML += b'MzA0LTAuMjg4LTQuMDMyLTAuNzY4bDEuNzI4LTEzLjI0OHExLjE1MiAwLjM4'
HTML += b'NCAyLjQ5NiAwLjU3NiAxLjQ0IDAuMjg4IDIuNTkyIDAuMjg4IDMuNjQ4IDAg'
HTML += b'NS4yOC0xLjcyOCAxLjYzMi0xLjYzMiAyLjc4NC00LjcwNGwxLjUzNi0zLjkz'
HTML += b'Ni0xOS45NjgtNDcuMDRoMTcuNDcybDEwLjY1NiAzMC43MmgwLjI4OGw5LjUw'
HTML += b'NC0zMC43MmgxNi43MDR6Ii8+CiAgPC9nPgogIDxwYXRoIGQ9Im02OC4wOTYg'
HTML += b'MTUuNzc1aDcuODAyOWwtOC45ODU0IDY5Ljc5MWgtNy44MDN6IiBzdHJva2Ut'
HTML += b'd2lkdGg9IjEuMTE3NiIvPgogIDxwYXRoIGQ9Im04My44NTMgMTUuNzQ4aDcu'
HTML += b'ODAzbC04Ljk4NTQgNjkuNzkxaC03LjgwM3oiIHN0cm9rZS13aWR0aD0iMS4x'
HTML += b'MTc2Ii8+CiA8L2c+Cjwvc3ZnPgo=" /> </span> <span id="data-poli'
HTML += b'cy"></span> </div> </div>  <script>let debug = false; let qu'
HTML += b'izSrc = {};var pysell=(()=>{var A=Object.defineProperty;var '
HTML += b'pe=Object.getOwnPropertyDescriptor;var ue=Object.getOwnPrope'
HTML += b'rtyNames;var de=Object.prototype.hasOwnProperty;var f=(r,e)='
HTML += b'>A(r,"name",{value:e,configurable:!0});var me=(r,e)=>{for(va'
HTML += b'r t in e)A(r,t,{get:e[t],enumerable:!0})},fe=(r,e,t,s)=>{if('
HTML += b'e&&typeof e=="object"||typeof e=="function")for(let i of ue('
HTML += b'e))!de.call(r,i)&&i!==t&&A(r,i,{get:()=>e[i],enumerable:!(s='
HTML += b'pe(e,i))||s.enumerable});return r};var ge=r=>fe(A({},"__esMo'
HTML += b'dule",{value:!0}),r);var ke={};me(ke,{Quiz:()=>q,init:()=>be'
HTML += b'});function w(r=[]){let e=document.createElement("div");retu'
HTML += b'rn e.append(...r),e}f(w,"genDiv");function j(r=[]){let e=doc'
HTML += b'ument.createElement("ul");return e.append(...r),e}f(j,"genUl'
HTML += b'");function O(r){let e=document.createElement("li");return e'
HTML += b'.appendChild(r),e}f(O,"genLi");function W(r){let e=document.'
HTML += b'createElement("input");return e.spellcheck=!1,e.type="text",'
HTML += b'e.classList.add("inputField"),e.style.width=r+"px",e}f(W,"ge'
HTML += b'nInputField");function F(){let r=document.createElement("but'
HTML += b'ton");return r.type="button",r.classList.add("button"),r}f(F'
HTML += b',"genButton");function k(r,e=[]){let t=document.createElemen'
HTML += b't("span");return e.length>0?t.append(...e):t.innerHTML=r,t}f'
HTML += b'(k,"genSpan");function Q(r,e,t=!1){katex.render(e,r,{throwOn'
HTML += b'Error:!1,displayMode:t,macros:{"\\\\RR":"\\\\mathbb{R}","\\\\NN":"'
HTML += b'\\\\mathbb{N}","\\\\QQ":"\\\\mathbb{Q}","\\\\ZZ":"\\\\mathbb{Z}","\\\\CC'
HTML += b'":"\\\\mathbb{C}"}})}f(Q,"updateMathElement");function L(r,e=!'
HTML += b'1){let t=document.createElement("span");return Q(t,r,e),t}f('
HTML += b'L,"genMathSpan");function K(r,e){let t=Array(e.length+1).fil'
HTML += b'l(null).map(()=>Array(r.length+1).fill(null));for(let s=0;s<'
HTML += b'=r.length;s+=1)t[0][s]=s;for(let s=0;s<=e.length;s+=1)t[s][0'
HTML += b']=s;for(let s=1;s<=e.length;s+=1)for(let i=1;i<=r.length;i+='
HTML += b'1){let l=r[i-1]===e[s-1]?0:1;t[s][i]=Math.min(t[s][i-1]+1,t['
HTML += b's-1][i]+1,t[s-1][i-1]+l)}return t[e.length][r.length]}f(K,"l'
HTML += b'evenshteinDistance");var Z=\'<svg xmlns="http://www.w3.org/20'
HTML += b'00/svg" height="28" viewBox="0 0 448 512"><path d="M384 80c8'
HTML += b'.8 0 16 7.2 16 16V416c0 8.8-7.2 16-16 16H64c-8.8 0-16-7.2-16'
HTML += b'-16V96c0-8.8 7.2-16 16-16H384zM64 32C28.7 32 0 60.7 0 96V416'
HTML += b'c0 35.3 28.7 64 64 64H384c35.3 0 64-28.7 64-64V96c0-35.3-28.'
HTML += b'7-64-64-64H64z"/></svg>\',X=\'<svg xmlns="http://www.w3.org/20'
HTML += b'00/svg" height="28" viewBox="0 0 448 512"><path d="M64 80c-8'
HTML += b'.8 0-16 7.2-16 16V416c0 8.8 7.2 16 16 16H384c8.8 0 16-7.2 16'
HTML += b'-16V96c0-8.8-7.2-16-16-16H64zM0 96C0 60.7 28.7 32 64 32H384c'
HTML += b'35.3 0 64 28.7 64 64V416c0 35.3-28.7 64-64 64H64c-35.3 0-64-'
HTML += b'28.7-64-64V96zM337 209L209 337c-9.4 9.4-24.6 9.4-33.9 0l-64-'
HTML += b'64c-9.4-9.4-9.4-24.6 0-33.9s24.6-9.4 33.9 0l47 47L303 175c9.'
HTML += b'4-9.4 24.6-9.4 33.9 0s9.4 24.6 0 33.9z"/>\',Y=\'<svg xmlns="ht'
HTML += b'tp://www.w3.org/2000/svg" height="28" viewBox="0 0 512 512">'
HTML += b'<path d="M464 256A208 208 0 1 0 48 256a208 208 0 1 0 416 0zM'
HTML += b'0 256a256 256 0 1 1 512 0A256 256 0 1 1 0 256z"/></svg>\',G=\''
HTML += b'<svg xmlns="http://www.w3.org/2000/svg" height="28" viewBox='
HTML += b'"0 0 512 512"><path d="M256 48a208 208 0 1 1 0 416 208 208 0'
HTML += b' 1 1 0-416zm0 464A256 256 0 1 0 256 0a256 256 0 1 0 0 512zM3'
HTML += b'69 209c9.4-9.4 9.4-24.6 0-33.9s-24.6-9.4-33.9 0l-111 111-47-'
HTML += b'47c-9.4-9.4-24.6-9.4-33.9 0s-9.4 24.6 0 33.9l64 64c9.4 9.4 2'
HTML += b'4.6 9.4 33.9 0L369 209z"/></svg>\',P=\'<svg xmlns="http://www.'
HTML += b'w3.org/2000/svg" width="50" height="25" viewBox="0 0 384 512'
HTML += b'" fill="white"><path d="M73 39c-14.8-9.1-33.4-9.4-48.5-.9S0 '
HTML += b'62.6 0 80V432c0 17.4 9.4 33.4 24.5 41.9s33.7 8.1 48.5-.9L361'
HTML += b' 297c14.3-8.7 23-24.2 23-41s-8.7-32.2-23-41L73 39z"/></svg>\''
HTML += b',J=\'<svg xmlns="http://www.w3.org/2000/svg" width="50" heigh'
HTML += b't="25" viewBox="0 0 512 512" fill="white"><path d="M0 224c0 '
HTML += b'17.7 14.3 32 32 32s32-14.3 32-32c0-53 43-96 96-96H320v32c0 1'
HTML += b'2.9 7.8 24.6 19.8 29.6s25.7 2.2 34.9-6.9l64-64c12.5-12.5 12.'
HTML += b'5-32.8 0-45.3l-64-64c-9.2-9.2-22.9-11.9-34.9-6.9S320 19.1 32'
HTML += b'0 32V64H160C71.6 64 0 135.6 0 224zm512 64c0-17.7-14.3-32-32-'
HTML += b'32s-32 14.3-32 32c0 53-43 96-96 96H192V352c0-12.9-7.8-24.6-1'
HTML += b'9.8-29.6s-25.7-2.2-34.9 6.9l-64 64c-12.5 12.5-12.5 32.8 0 45'
HTML += b'.3l64 64c9.2 9.2 22.9 11.9 34.9 6.9s19.8-16.6 19.8-29.6V448H'
HTML += b'352c88.4 0 160-71.6 160-160z"/></svg>\';var $={en:"This page '
HTML += b'operates entirely in your browser and does not store any dat'
HTML += b'a on external servers.",de:"Diese Seite wird in Ihrem Browse'
HTML += b'r ausgef\\xFChrt und speichert keine Daten auf Servern.",es:"'
HTML += b'Esta p\\xE1gina se ejecuta en su navegador y no almacena ning'
HTML += b'\\xFAn dato en los servidores.",it:"Questa pagina viene esegu'
HTML += b'ita nel browser e non memorizza alcun dato sui server.",fr:"'
HTML += b'Cette page fonctionne dans votre navigateur et ne stocke auc'
HTML += b'une donn\\xE9e sur des serveurs."},ee={en:"* this page to rec'
HTML += b'eive a new set of randomized tasks.",de:"Sie k\\xF6nnen diese'
HTML += b' Seite *, um neue randomisierte Aufgaben zu erhalten.",es:"P'
HTML += b'uedes * esta p\\xE1gina para obtener nuevas tareas aleatorias'
HTML += b'.",it:"\\xC8 possibile * questa pagina per ottenere nuovi com'
HTML += b'piti randomizzati",fr:"Vous pouvez * cette page pour obtenir'
HTML += b' de nouvelles t\\xE2ches al\\xE9atoires"},te={en:"Refresh",de:'
HTML += b'"aktualisieren",es:"recargar",it:"ricaricare",fr:"recharger"'
HTML += b'},ie={en:["awesome","great","well done","nice","you got it",'
HTML += b'"good"],de:["super","gut gemacht","weiter so","richtig"],es:'
HTML += b'["impresionante","genial","correcto","bien hecho"],it:["fant'
HTML += b'astico","grande","corretto","ben fatto"],fr:["g\\xE9nial","su'
HTML += b'per","correct","bien fait"]},se={en:["please complete all fi'
HTML += b'elds"],de:["bitte alles ausf\\xFCllen"],es:["por favor, relle'
HTML += b'ne todo"],it:["compilare tutto"],fr:["remplis tout s\'il te p'
HTML += b'lait"]},ne={en:["try again","still some mistakes","wrong ans'
HTML += b'wer","no"],de:["leider falsch","nicht richtig","versuch\'s no'
HTML += b'chmal"],es:["int\\xE9ntalo de nuevo","todav\\xEDa algunos erro'
HTML += b'res","respuesta incorrecta"],it:["riprova","ancora qualche e'
HTML += b'rrore","risposta sbagliata"],fr:["r\\xE9essayer","encore des '
HTML += b'erreurs","mauvaise r\\xE9ponse"]},re={en:"point(s)",de:"Punkt'
HTML += b'(e)",es:"punto(s)",it:"punto/i",fr:"point(s)"},ae={en:"Evalu'
HTML += b'ate now",de:"Jetzt auswerten",es:"Evaluar ahora",it:"Valuta '
HTML += b'ora",fr:"\\xC9valuer maintenant"},le={en:"Data Policy: This w'
HTML += b'ebsite does not collect, store, or process any personal data'
HTML += b' on external servers. All functionality is executed locally '
HTML += b'in your browser, ensuring complete privacy. No cookies are u'
HTML += b'sed, and no data is transmitted to or from the server. Your '
HTML += b'activity on this site remains entirely private and local to '
HTML += b'your device.",de:"Datenschutzrichtlinie: Diese Website samme'
HTML += b'lt, speichert oder verarbeitet keine personenbezogenen Daten'
HTML += b' auf externen Servern. Alle Funktionen werden lokal in Ihrem'
HTML += b' Browser ausgef\\xFChrt, um vollst\\xE4ndige Privatsph\\xE4re z'
HTML += b'u gew\\xE4hrleisten. Es werden keine Cookies verwendet, und e'
HTML += b's werden keine Daten an den Server gesendet oder von diesem '
HTML += b'empfangen. Ihre Aktivit\\xE4t auf dieser Seite bleibt vollst\\'
HTML += b'xE4ndig privat und lokal auf Ihrem Ger\\xE4t.",es:"Pol\\xEDtic'
HTML += b'a de datos: Este sitio web no recopila, almacena ni procesa '
HTML += b'ning\\xFAn dato personal en servidores externos. Toda la func'
HTML += b'ionalidad se ejecuta localmente en su navegador, garantizand'
HTML += b'o una privacidad completa. No se utilizan cookies y no se tr'
HTML += b'ansmiten datos hacia o desde el servidor. Su actividad en es'
HTML += b'te sitio permanece completamente privada y local en su dispo'
HTML += b'sitivo.",it:"Politica sui dati: Questo sito web non raccogli'
HTML += b'e, memorizza o elabora alcun dato personale su server estern'
HTML += b'i. Tutte le funzionalit\\xE0 vengono eseguite localmente nel '
HTML += b'tuo browser, garantendo una privacy completa. Non vengono ut'
HTML += b'ilizzati cookie e nessun dato viene trasmesso da o verso il '
HTML += b'server. La tua attivit\\xE0 su questo sito rimane completamen'
HTML += b'te privata e locale sul tuo dispositivo.",fr:"Politique de c'
HTML += b'onfidentialit\\xE9: Ce site web ne collecte, ne stocke ni ne '
HTML += b'traite aucune donn\\xE9e personnelle sur des serveurs externe'
HTML += b's. Toutes les fonctionnalit\\xE9s sont ex\\xE9cut\\xE9es locale'
HTML += b'ment dans votre navigateur, garantissant une confidentialit\\'
HTML += b'xE9 totale. Aucun cookie n\\u2019est utilis\\xE9 et aucune don'
HTML += b'n\\xE9e n\\u2019est transmise vers ou depuis le serveur. Votre'
HTML += b' activit\\xE9 sur ce site reste enti\\xE8rement priv\\xE9e et l'
HTML += b'ocale sur votre appareil."},oe={en:"You have a limited time '
HTML += b'to complete this quiz. The countdown, displayed in minutes, '
HTML += b"is visible at the top-left of the screen. When you're ready "
HTML += b'to begin, simply press the Start button.",de:"Die Zeit f\\xFC'
HTML += b'r dieses Quiz ist begrenzt. Der Countdown, in Minuten angeze'
HTML += b'igt, l\\xE4uft oben links auf dem Bildschirm. Mit dem Start-B'
HTML += b'utton beginnt das Quiz.",es:"Tienes un tiempo limitado para '
HTML += b'completar este cuestionario. La cuenta regresiva, mostrada e'
HTML += b'n minutos, se encuentra en la parte superior izquierda de la'
HTML += b' pantalla. Cuando est\\xE9s listo, simplemente presiona el bo'
HTML += b't\\xF3n de inicio.",it:"Hai un tempo limitato per completare '
HTML += b'questo quiz. Il conto alla rovescia, visualizzato in minuti,'
HTML += b' \\xE8 visibile in alto a sinistra dello schermo. Quando sei '
HTML += b'pronto, premi semplicemente il pulsante Start.",fr:"Vous dis'
HTML += b'posez d\\u2019un temps limit\\xE9 pour compl\\xE9ter ce quiz. L'
HTML += b'e compte \\xE0 rebours, affich\\xE9 en minutes, est visible en'
HTML += b' haut \\xE0 gauche de l\\u2019\\xE9cran. Lorsque vous \\xEAtes p'
HTML += b'r\\xEAt, appuyez simplement sur le bouton D\\xE9marrer."};func'
HTML += b'tion z(r,e=!1){let t=new Array(r);for(let s=0;s<r;s++)t[s]=s'
HTML += b';if(e)for(let s=0;s<r;s++){let i=Math.floor(Math.random()*r)'
HTML += b',l=Math.floor(Math.random()*r),o=t[i];t[i]=t[l],t[l]=o}retur'
HTML += b'n t}f(z,"range");function N(r,e,t=-1){if(t<0&&(t=r.length),t'
HTML += b'==1){e.push([...r]);return}for(let s=0;s<t;s++){N(r,e,t-1);l'
HTML += b'et i=t%2==0?s:0,l=r[i];r[i]=r[t-1],r[t-1]=l}}f(N,"heapsAlgor'
HTML += b'ithm");var E=class r{static{f(this,"Matrix")}constructor(e,t'
HTML += b'){this.m=e,this.n=t,this.v=new Array(e*t).fill("0")}getEleme'
HTML += b'nt(e,t){return e<0||e>=this.m||t<0||t>=this.n?"":this.v[e*th'
HTML += b'is.n+t]}resize(e,t,s){if(e<1||e>50||t<1||t>50)return!1;let i'
HTML += b'=new r(e,t);i.v.fill(s);for(let l=0;l<i.m;l++)for(let o=0;o<'
HTML += b'i.n;o++)i.v[l*i.n+o]=this.getElement(l,o);return this.fromMa'
HTML += b'trix(i),!0}fromMatrix(e){this.m=e.m,this.n=e.n,this.v=[...e.'
HTML += b'v]}fromString(e){this.m=e.split("],").length,this.v=e.replac'
HTML += b'eAll("[","").replaceAll("]","").split(",").map(t=>t.trim()),'
HTML += b'this.n=this.v.length/this.m}getMaxCellStrlen(){let e=0;for(l'
HTML += b'et t of this.v)t.length>e&&(e=t.length);return e}toTeXString'
HTML += b'(e=!1,t=!0){let s="";t?s+=e?"\\\\left[\\\\begin{array}":"\\\\begin'
HTML += b'{bmatrix}":s+=e?"\\\\left(\\\\begin{array}":"\\\\begin{pmatrix}",e'
HTML += b'&&(s+="{"+"c".repeat(this.n-1)+"|c}");for(let i=0;i<this.m;i'
HTML += b'++){for(let l=0;l<this.n;l++){l>0&&(s+="&");let o=this.getEl'
HTML += b'ement(i,l);try{o=b.parse(o).toTexString()}catch{}s+=o}s+="\\\\'
HTML += b'\\\\"}return t?s+=e?"\\\\end{array}\\\\right]":"\\\\end{bmatrix}":s+'
HTML += b'=e?"\\\\end{array}\\\\right)":"\\\\end{pmatrix}",s}},b=class r{sta'
HTML += b'tic{f(this,"Term")}constructor(){this.root=null,this.src="",'
HTML += b'this.token="",this.skippedWhiteSpace=!1,this.pos=0}clone(){l'
HTML += b'et e=new r;return e.root=this.root.clone(),e}getVars(e,t="",'
HTML += b's=null){if(s==null&&(s=this.root),s.op.startsWith("var:")){l'
HTML += b'et i=s.op.substring(4);(t.length==0||t.length>0&&i.startsWit'
HTML += b'h(t))&&e.add(i)}for(let i of s.c)this.getVars(e,t,i)}setVars'
HTML += b'(e,t=null){t==null&&(t=this.root);for(let s of t.c)this.setV'
HTML += b'ars(e,s);if(t.op.startsWith("var:")){let s=t.op.substring(4)'
HTML += b';if(s in e){let i=e[s].clone();t.op=i.op,t.c=i.c,t.re=i.re,t'
HTML += b'.im=i.im}}}renameVar(e,t,s=null){s==null&&(s=this.root);for('
HTML += b'let i of s.c)this.renameVar(e,t,i);s.op.startsWith("var:")&&'
HTML += b's.op.substring(4)===e&&(s.op="var:"+t)}eval(e,t=null){let i='
HTML += b'a.const(),l=0,o=0,c=null;switch(t==null&&(t=this.root),t.op)'
HTML += b'{case"const":i=t;break;case"+":case"-":case"*":case"/":case"'
HTML += b'^":{let n=this.eval(e,t.c[0]),h=this.eval(e,t.c[1]);switch(t'
HTML += b'.op){case"+":i.re=n.re+h.re,i.im=n.im+h.im;break;case"-":i.r'
HTML += b'e=n.re-h.re,i.im=n.im-h.im;break;case"*":i.re=n.re*h.re-n.im'
HTML += b'*h.im,i.im=n.re*h.im+n.im*h.re;break;case"/":l=h.re*h.re+h.i'
HTML += b'm*h.im,i.re=(n.re*h.re+n.im*h.im)/l,i.im=(n.im*h.re-n.re*h.i'
HTML += b'm)/l;break;case"^":c=new a("exp",[new a("*",[h,new a("ln",[n'
HTML += b'])])]),i=this.eval(e,c);break}break}case".-":case"abs":case"'
HTML += b'acos":case"acosh":case"asin":case"asinh":case"atan":case"ata'
HTML += b'nh":case"ceil":case"cos":case"cosh":case"cot":case"exp":case'
HTML += b'"floor":case"ln":case"log":case"log10":case"log2":case"round'
HTML += b'":case"sin":case"sinc":case"sinh":case"sqrt":case"tan":case"'
HTML += b'tanh":{let n=this.eval(e,t.c[0]);switch(t.op){case".-":i.re='
HTML += b'-n.re,i.im=-n.im;break;case"abs":i.re=Math.sqrt(n.re*n.re+n.'
HTML += b'im*n.im),i.im=0;break;case"acos":c=new a("*",[a.const(0,-1),'
HTML += b'new a("ln",[new a("+",[a.const(0,1),new a("sqrt",[new a("-",'
HTML += b'[a.const(1,0),new a("*",[n,n])])])])])]),i=this.eval(e,c);br'
HTML += b'eak;case"acosh":c=new a("*",[n,new a("sqrt",[new a("-",[new '
HTML += b'a("*",[n,n]),a.const(1,0)])])]),i=this.eval(e,c);break;case"'
HTML += b'asin":c=new a("*",[a.const(0,-1),new a("ln",[new a("+",[new '
HTML += b'a("*",[a.const(0,1),n]),new a("sqrt",[new a("-",[a.const(1,0'
HTML += b'),new a("*",[n,n])])])])])]),i=this.eval(e,c);break;case"asi'
HTML += b'nh":c=new a("*",[n,new a("sqrt",[new a("+",[new a("*",[n,n])'
HTML += b',a.const(1,0)])])]),i=this.eval(e,c);break;case"atan":c=new '
HTML += b'a("*",[a.const(0,.5),new a("ln",[new a("/",[new a("-",[a.con'
HTML += b'st(0,1),new a("*",[a.const(0,1),n])]),new a("+",[a.const(0,1'
HTML += b'),new a("*",[a.const(0,1),n])])])])]),i=this.eval(e,c);break'
HTML += b';case"atanh":c=new a("*",[a.const(.5,0),new a("ln",[new a("/'
HTML += b'",[new a("+",[a.const(1,0),n]),new a("-",[a.const(1,0),n])])'
HTML += b'])]),i=this.eval(e,c);break;case"ceil":i.re=Math.ceil(n.re),'
HTML += b'i.im=Math.ceil(n.im);break;case"cos":i.re=Math.cos(n.re)*Mat'
HTML += b'h.cosh(n.im),i.im=-Math.sin(n.re)*Math.sinh(n.im);break;case'
HTML += b'"cosh":c=new a("*",[a.const(.5,0),new a("+",[new a("exp",[n]'
HTML += b'),new a("exp",[new a(".-",[n])])])]),i=this.eval(e,c);break;'
HTML += b'case"cot":l=Math.sin(n.re)*Math.sin(n.re)+Math.sinh(n.im)*Ma'
HTML += b'th.sinh(n.im),i.re=Math.sin(n.re)*Math.cos(n.re)/l,i.im=-(Ma'
HTML += b'th.sinh(n.im)*Math.cosh(n.im))/l;break;case"exp":i.re=Math.e'
HTML += b'xp(n.re)*Math.cos(n.im),i.im=Math.exp(n.re)*Math.sin(n.im);b'
HTML += b'reak;case"floor":i.re=Math.floor(n.re),i.im=Math.floor(n.im)'
HTML += b';break;case"ln":case"log":i.re=Math.log(Math.sqrt(n.re*n.re+'
HTML += b'n.im*n.im)),l=Math.abs(n.im)<1e-9?0:n.im,i.im=Math.atan2(l,n'
HTML += b'.re);break;case"log10":c=new a("/",[new a("ln",[n]),new a("l'
HTML += b'n",[a.const(10)])]),i=this.eval(e,c);break;case"log2":c=new '
HTML += b'a("/",[new a("ln",[n]),new a("ln",[a.const(2)])]),i=this.eva'
HTML += b'l(e,c);break;case"round":i.re=Math.round(n.re),i.im=Math.rou'
HTML += b'nd(n.im);break;case"sin":i.re=Math.sin(n.re)*Math.cosh(n.im)'
HTML += b',i.im=Math.cos(n.re)*Math.sinh(n.im);break;case"sinc":c=new '
HTML += b'a("/",[new a("sin",[n]),n]),i=this.eval(e,c);break;case"sinh'
HTML += b'":c=new a("*",[a.const(.5,0),new a("-",[new a("exp",[n]),new'
HTML += b' a("exp",[new a(".-",[n])])])]),i=this.eval(e,c);break;case"'
HTML += b'sqrt":c=new a("^",[n,a.const(.5)]),i=this.eval(e,c);break;ca'
HTML += b'se"tan":l=Math.cos(n.re)*Math.cos(n.re)+Math.sinh(n.im)*Math'
HTML += b'.sinh(n.im),i.re=Math.sin(n.re)*Math.cos(n.re)/l,i.im=Math.s'
HTML += b'inh(n.im)*Math.cosh(n.im)/l;break;case"tanh":c=new a("/",[ne'
HTML += b'w a("-",[new a("exp",[n]),new a("exp",[new a(".-",[n])])]),n'
HTML += b'ew a("+",[new a("exp",[n]),new a("exp",[new a(".-",[n])])])]'
HTML += b'),i=this.eval(e,c);break}break}default:if(t.op.startsWith("v'
HTML += b'ar:")){let n=t.op.substring(4);if(n==="pi")return a.const(Ma'
HTML += b'th.PI);if(n==="e")return a.const(Math.E);if(n==="i")return a'
HTML += b'.const(0,1);if(n==="true")return a.const(1);if(n==="false")r'
HTML += b'eturn a.const(0);if(n in e)return e[n];throw new Error("eval'
HTML += b'-error: unknown variable \'"+n+"\'")}else throw new Error("UNI'
HTML += b'MPLEMENTED eval \'"+t.op+"\'")}return i}static parse(e){let t='
HTML += b'new r;if(t.src=e,t.token="",t.skippedWhiteSpace=!1,t.pos=0,t'
HTML += b'.next(),t.root=t.parseExpr(!1),t.token!=="")throw new Error('
HTML += b'"remaining tokens: "+t.token+"...");return t}parseExpr(e){re'
HTML += b'turn this.parseAdd(e)}parseAdd(e){let t=this.parseMul(e);for'
HTML += b'(;["+","-"].includes(this.token)&&!(e&&this.skippedWhiteSpac'
HTML += b'e);){let s=this.token;this.next(),t=new a(s,[t,this.parseMul'
HTML += b'(e)])}return t}parseMul(e){let t=this.parsePow(e);for(;!(e&&'
HTML += b'this.skippedWhiteSpace);){let s="*";if(["*","/"].includes(th'
HTML += b'is.token))s=this.token,this.next();else if(!e&&this.token==='
HTML += b'"(")s="*";else if(this.token.length>0&&(this.isAlpha(this.to'
HTML += b'ken[0])||this.isNum(this.token[0])))s="*";else break;t=new a'
HTML += b'(s,[t,this.parsePow(e)])}return t}parsePow(e){let t=this.par'
HTML += b'seUnary(e);for(;["^"].includes(this.token)&&!(e&&this.skippe'
HTML += b'dWhiteSpace);){let s=this.token;this.next(),t=new a(s,[t,thi'
HTML += b's.parseUnary(e)])}return t}parseUnary(e){return this.token=='
HTML += b'="-"?(this.next(),new a(".-",[this.parseMul(e)])):this.parse'
HTML += b'Infix(e)}parseInfix(e){if(this.token.length==0)throw new Err'
HTML += b'or("expected unary");if(this.isNum(this.token[0])){let t=thi'
HTML += b's.token;return this.next(),this.token==="."&&(t+=".",this.ne'
HTML += b'xt(),this.token.length>0&&(t+=this.token,this.next())),new a'
HTML += b'("const",[],parseFloat(t))}else if(this.fun1().length>0){let'
HTML += b' t=this.fun1();this.next(t.length);let s=null;if(this.token='
HTML += b'=="(")if(this.next(),s=this.parseExpr(e),this.token+="",this'
HTML += b'.token===")")this.next();else throw Error("expected \')\'");el'
HTML += b'se s=this.parseMul(!0);return new a(t,[s])}else if(this.toke'
HTML += b'n==="("){this.next();let t=this.parseExpr(e);if(this.token+='
HTML += b'"",this.token===")")this.next();else throw Error("expected \''
HTML += b')\'");return t.explicitParentheses=!0,t}else if(this.token==='
HTML += b'"|"){this.next();let t=this.parseExpr(e);if(this.token+="",t'
HTML += b'his.token==="|")this.next();else throw Error("expected \'|\'")'
HTML += b';return new a("abs",[t])}else if(this.isAlpha(this.token[0])'
HTML += b'){let t="";return this.token.startsWith("pi")?t="pi":this.to'
HTML += b'ken.startsWith("true")?t="true":this.token.startsWith("false'
HTML += b'")?t="false":this.token.startsWith("C1")?t="C1":this.token.s'
HTML += b'tartsWith("C2")?t="C2":t=this.token[0],t==="I"&&(t="i"),this'
HTML += b'.next(t.length),new a("var:"+t,[])}else throw new Error("exp'
HTML += b'ected unary")}static compare(e,t,s={}){let o=new Set;e.getVa'
HTML += b'rs(o),t.getVars(o);for(let c=0;c<10;c++){let n={};for(let g '
HTML += b'of o)g in s?n[g]=s[g]:n[g]=a.const(Math.random(),Math.random'
HTML += b'());let h=e.eval(n),p=t.eval(n),m=h.re-p.re,d=h.im-p.im;if(M'
HTML += b'ath.sqrt(m*m+d*d)>1e-9)return!1}return!0}fun1(){let e=["abs"'
HTML += b',"acos","acosh","asin","asinh","atan","atanh","ceil","cos","'
HTML += b'cosh","cot","exp","floor","ln","log","log10","log2","round",'
HTML += b'"sin","sinc","sinh","sqrt","tan","tanh"];for(let t of e)if(t'
HTML += b'his.token.toLowerCase().startsWith(t))return t;return""}next'
HTML += b'(e=-1){if(e>0&&this.token.length>e){this.token=this.token.su'
HTML += b'bstring(e),this.skippedWhiteSpace=!1;return}this.token="";le'
HTML += b't t=!1,s=this.src.length;for(this.skippedWhiteSpace=!1;this.'
HTML += b'pos<s&&`\t\n `.includes(this.src[this.pos]);)this.skippedWhite'
HTML += b'Space=!0,this.pos++;for(;!t&&this.pos<s;){let i=this.src[thi'
HTML += b's.pos];if(this.token.length>0&&(this.isNum(this.token[0])&&t'
HTML += b'his.isAlpha(i)||this.isAlpha(this.token[0])&&this.isNum(i))&'
HTML += b'&this.token!="C")return;if(`^%#*$()[]{},.:;+-*/_!<>=?|\t\n `.i'
HTML += b'ncludes(i)){if(this.token.length>0)return;t=!0}`\t\n `.include'
HTML += b's(i)==!1&&(this.token+=i),this.pos++}}isNum(e){return e.char'
HTML += b'CodeAt(0)>=48&&e.charCodeAt(0)<=57}isAlpha(e){return e.charC'
HTML += b'odeAt(0)>=65&&e.charCodeAt(0)<=90||e.charCodeAt(0)>=97&&e.ch'
HTML += b'arCodeAt(0)<=122||e==="_"}toString(){return this.root==null?'
HTML += b'"":this.root.toString()}toTexString(){return this.root==null'
HTML += b'?"":this.root.toTexString()}},a=class r{static{f(this,"TermN'
HTML += b'ode")}constructor(e,t,s=0,i=0){this.op=e,this.c=t,this.re=s,'
HTML += b'this.im=i,this.explicitParentheses=!1}clone(){let e=new r(th'
HTML += b'is.op,this.c.map(t=>t.clone()),this.re,this.im);return e.exp'
HTML += b'licitParentheses=this.explicitParentheses,e}static const(e=0'
HTML += b',t=0){return new r("const",[],e,t)}compare(e,t=0,s=1e-9){let'
HTML += b' i=this.re-e,l=this.im-t;return Math.sqrt(i*i+l*l)<s}toStrin'
HTML += b'g(){let e="";if(this.op==="const"){let t=Math.abs(this.re)>1'
HTML += b'e-14,s=Math.abs(this.im)>1e-14;t&&s&&this.im>=0?e="("+this.r'
HTML += b'e+"+"+this.im+"i)":t&&s&&this.im<0?e="("+this.re+"-"+-this.i'
HTML += b'm+"i)":t&&this.re>0?e=""+this.re:t&&this.re<0?e="("+this.re+'
HTML += b'")":s?e="("+this.im+"i)":e="0"}else this.op.startsWith("var"'
HTML += b')?e=this.op.split(":")[1]:this.c.length==1?e=(this.op===".-"'
HTML += b'?"-":this.op)+"("+this.c.toString()+")":e="("+this.c.map(t=>'
HTML += b't.toString()).join(this.op)+")";return e}toTexString(e=!1){l'
HTML += b'et s="";switch(this.op){case"const":{let i=Math.abs(this.re)'
HTML += b'>1e-9,l=Math.abs(this.im)>1e-9,o=i?""+this.re:"",c=l?""+this'
HTML += b'.im+"i":"";c==="1i"?c="i":c==="-1i"&&(c="-i"),!i&&!l?s="0":('
HTML += b'l&&this.im>=0&&i&&(c="+"+c),s=o+c);break}case".-":s="-"+this'
HTML += b'.c[0].toTexString();break;case"+":case"-":case"*":case"^":{l'
HTML += b'et i=this.c[0].toTexString(),l=this.c[1].toTexString(),o=thi'
HTML += b's.op==="*"?"\\\\cdot ":this.op;s="{"+i+"}"+o+"{"+l+"}";break}c'
HTML += b'ase"/":{let i=this.c[0].toTexString(!0),l=this.c[1].toTexStr'
HTML += b'ing(!0);s="\\\\frac{"+i+"}{"+l+"}";break}case"floor":{let i=th'
HTML += b'is.c[0].toTexString(!0);s+="\\\\"+this.op+"\\\\left\\\\lfloor"+i+"'
HTML += b'\\\\right\\\\rfloor";break}case"ceil":{let i=this.c[0].toTexStri'
HTML += b'ng(!0);s+="\\\\"+this.op+"\\\\left\\\\lceil"+i+"\\\\right\\\\rceil";br'
HTML += b'eak}case"round":{let i=this.c[0].toTexString(!0);s+="\\\\"+thi'
HTML += b's.op+"\\\\left["+i+"\\\\right]";break}case"acos":case"acosh":cas'
HTML += b'e"asin":case"asinh":case"atan":case"atanh":case"cos":case"co'
HTML += b'sh":case"cot":case"exp":case"ln":case"log":case"log10":case"'
HTML += b'log2":case"sin":case"sinc":case"sinh":case"tan":case"tanh":{'
HTML += b'let i=this.c[0].toTexString(!0);s+="\\\\"+this.op+"\\\\left("+i+'
HTML += b'"\\\\right)";break}case"sqrt":{let i=this.c[0].toTexString(!0)'
HTML += b';s+="\\\\"+this.op+"{"+i+"}";break}case"abs":{let i=this.c[0].'
HTML += b'toTexString(!0);s+="\\\\left|"+i+"\\\\right|";break}default:if(t'
HTML += b'his.op.startsWith("var:")){let i=this.op.substring(4);switch'
HTML += b'(i){case"pi":i="\\\\pi";break}s=" "+i+" "}else{let i="warning:'
HTML += b' Node.toString(..):";i+=" unimplemented operator \'"+this.op+'
HTML += b'"\'",console.log(i),s=this.op,this.c.length>0&&(s+="\\\\left({"'
HTML += b'+this.c.map(l=>l.toTexString(!0)).join(",")+"}\\\\right)")}}re'
HTML += b'turn!e&&this.explicitParentheses&&(s="\\\\left({"+s+"}\\\\right)'
HTML += b'"),s}};function ce(r,e){let t=1e-9;if(b.compare(r,e))return!'
HTML += b'0;r=r.clone(),e=e.clone(),_(r.root),_(e.root);let s=new Set;'
HTML += b'r.getVars(s),e.getVars(s);let i=[],l=[];for(let n of s.keys('
HTML += b'))n.startsWith("C")?i.push(n):l.push(n);let o=i.length;for(l'
HTML += b'et n=0;n<o;n++){let h=i[n];r.renameVar(h,"_C"+n),e.renameVar'
HTML += b'(h,"_C"+n)}for(let n=0;n<o;n++)r.renameVar("_C"+n,"C"+n),e.r'
HTML += b'enameVar("_C"+n,"C"+n);i=[];for(let n=0;n<o;n++)i.push("C"+n'
HTML += b');let c=[];N(z(o),c);for(let n of c){let h=r.clone(),p=e.clo'
HTML += b'ne();for(let d=0;d<o;d++)p.renameVar("C"+d,"__C"+n[d]);for(l'
HTML += b'et d=0;d<o;d++)p.renameVar("__C"+d,"C"+d);let m=!0;for(let d'
HTML += b'=0;d<o;d++){let u="C"+d,g={};g[u]=new a("*",[new a("var:C"+d'
HTML += b',[]),new a("var:K",[])]),p.setVars(g);let v={};v[u]=a.const('
HTML += b'Math.random(),Math.random());for(let y=0;y<o;y++)d!=y&&(v["C'
HTML += b'"+y]=a.const(0,0));let M=new a("abs",[new a("-",[h.root,p.ro'
HTML += b'ot])]),S=new b;S.root=M;for(let y of l)v[y]=a.const(Math.ran'
HTML += b'dom(),Math.random());let C=ve(S,"K",v)[0];p.setVars({K:a.con'
HTML += b'st(C,0)}),v={};for(let y=0;y<o;y++)d!=y&&(v["C"+y]=a.const(0'
HTML += b',0));if(b.compare(h,p,v)==!1){m=!1;break}}if(m&&b.compare(h,'
HTML += b'p))return!0}return!1}f(ce,"compareODE");function ve(r,e,t){l'
HTML += b'et s=1e-11,i=1e3,l=0,o=0,c=1,n=888;for(;l<i;){t[e]=a.const(o'
HTML += b');let p=r.eval(t).re;t[e]=a.const(o+c);let m=r.eval(t).re;t['
HTML += b'e]=a.const(o-c);let d=r.eval(t).re,u=0;if(m<p&&(p=m,u=1),d<p'
HTML += b'&&(p=d,u=-1),u==1&&(o+=c),u==-1&&(o-=c),p<s)break;(u==0||u!='
HTML += b'n)&&(c/=2),n=u,l++}t[e]=a.const(o);let h=r.eval(t).re;return'
HTML += b'[o,h]}f(ve,"minimize");function _(r){for(let e of r.c)_(e);s'
HTML += b'witch(r.op){case"+":case"-":case"*":case"/":case"^":{let e=['
HTML += b'r.c[0].op,r.c[1].op],t=[e[0]==="const",e[1]==="const"],s=[e['
HTML += b'0].startsWith("var:C"),e[1].startsWith("var:C")];s[0]&&t[1]?'
HTML += b'(r.op=r.c[0].op,r.c=[]):s[1]&&t[0]?(r.op=r.c[1].op,r.c=[]):s'
HTML += b'[0]&&s[1]&&e[0]==e[1]&&(r.op=r.c[0].op,r.c=[]);break}case".-'
HTML += b'":case"abs":case"sin":case"sinc":case"cos":case"tan":case"co'
HTML += b't":case"exp":case"ln":case"log":case"sqrt":r.c[0].op.startsW'
HTML += b'ith("var:C")&&(r.op=r.c[0].op,r.c=[]);break}}f(_,"prepareODE'
HTML += b'constantComparison");var B=class{static{f(this,"GapInput")}c'
HTML += b'onstructor(e,t,s,i){this.question=t,this.inputId=s,s.length='
HTML += b'=0&&(this.inputId=s="gap-"+t.gapIdx,t.types[this.inputId]="s'
HTML += b'tring",t.expected[this.inputId]=i,t.gapIdx++),s in t.student'
HTML += b'||(t.student[s]="");let l=i.split("|"),o=0;for(let p=0;p<l.l'
HTML += b'ength;p++){let m=l[p];m.length>o&&(o=m.length)}let c=k("");e'
HTML += b'.appendChild(c);let n=Math.max(o*15,24),h=W(n);if(t.gapInput'
HTML += b's[this.inputId]=h,h.addEventListener("keyup",()=>{t.editingE'
HTML += b'nabled!=!1&&(this.question.editedQuestion(),h.value=h.value.'
HTML += b'toUpperCase(),this.question.student[this.inputId]=h.value.tr'
HTML += b'im())}),c.appendChild(h),this.question.showSolution&&(this.q'
HTML += b'uestion.student[this.inputId]=h.value=l[0],l.length>1)){let '
HTML += b'p=k("["+l.join("|")+"]");p.style.fontSize="small",p.style.te'
HTML += b'xtDecoration="underline",c.appendChild(p)}}},I=class{static{'
HTML += b'f(this,"TermInput")}constructor(e,t,s,i,l,o,c=!1){s in t.stu'
HTML += b'dent||(t.student[s]=""),this.question=t,this.inputId=s,this.'
HTML += b'outerSpan=k(""),this.outerSpan.style.position="relative",e.a'
HTML += b'ppendChild(this.outerSpan),this.inputElement=W(Math.max(i*12'
HTML += b',48)),this.outerSpan.appendChild(this.inputElement),this.equ'
HTML += b'ationPreviewDiv=w(),this.equationPreviewDiv.classList.add("e'
HTML += b'quationPreview"),this.equationPreviewDiv.style.display="none'
HTML += b'",this.outerSpan.appendChild(this.equationPreviewDiv),this.i'
HTML += b'nputElement.addEventListener("click",()=>{t.editingEnabled!='
HTML += b'!1&&(this.question.editedQuestion(),this.edited())}),this.in'
HTML += b'putElement.addEventListener("keyup",()=>{t.editingEnabled!=!'
HTML += b'1&&(this.question.editedQuestion(),this.edited())}),this.inp'
HTML += b'utElement.addEventListener("focus",()=>{t.editingEnabled!=!1'
HTML += b'}),this.inputElement.addEventListener("focusout",()=>{this.e'
HTML += b'quationPreviewDiv.innerHTML="",this.equationPreviewDiv.style'
HTML += b'.display="none"}),this.inputElement.addEventListener("keydow'
HTML += b'n",n=>{if(t.editingEnabled==!1){n.preventDefault();return}le'
HTML += b't h="abcdefghijklmnopqrstuvwxyz";h+="ABCDEFGHIJKLMNOPQRSTUVW'
HTML += b'XYZ",h+="0123456789",h+="+-*/^(). <>=|",o&&(h="-0123456789")'
HTML += b',n.key.length<3&&h.includes(n.key)==!1&&n.preventDefault();l'
HTML += b'et p=this.inputElement.value.length*12;this.inputElement.off'
HTML += b'setWidth<p&&(this.inputElement.style.width=""+p+"px")}),(c||'
HTML += b'this.question.showSolution)&&(t.student[s]=this.inputElement'
HTML += b'.value=l)}edited(){let e=this.inputElement.value.trim(),t=""'
HTML += b',s=!1;try{let i=b.parse(e);s=i.root.op==="const",t=i.toTexSt'
HTML += b'ring(),this.inputElement.style.color="black",this.equationPr'
HTML += b'eviewDiv.style.backgroundColor="green"}catch{t=e.replaceAll('
HTML += b'"^","\\\\hat{~}").replaceAll("_","\\\\_"),this.inputElement.styl'
HTML += b'e.color="maroon",this.equationPreviewDiv.style.backgroundCol'
HTML += b'or="maroon"}Q(this.equationPreviewDiv,t,!0),this.equationPre'
HTML += b'viewDiv.style.display=e.length>0&&!s?"block":"none",this.que'
HTML += b'stion.student[this.inputId]=e}},H=class{static{f(this,"Matri'
HTML += b'xInput")}constructor(e,t,s,i){this.parent=e,this.question=t,'
HTML += b'this.inputId=s,this.matExpected=new E(0,0),this.matExpected.'
HTML += b'fromString(i),this.matStudent=new E(this.matExpected.m==1?1:'
HTML += b'3,this.matExpected.n==1?1:3),t.showSolution&&this.matStudent'
HTML += b'.fromMatrix(this.matExpected),this.genMatrixDom(!0)}genMatri'
HTML += b'xDom(e){let t=w();this.parent.innerHTML="",this.parent.appen'
HTML += b'dChild(t),t.style.position="relative",t.style.display="inlin'
HTML += b'e-block";let s=document.createElement("table");t.appendChild'
HTML += b'(s);let i=this.matExpected.getMaxCellStrlen();for(let u=0;u<'
HTML += b'this.matStudent.m;u++){let g=document.createElement("tr");s.'
HTML += b'appendChild(g),u==0&&g.appendChild(this.generateMatrixParent'
HTML += b'hesis(!0,this.matStudent.m));for(let v=0;v<this.matStudent.n'
HTML += b';v++){let M=u*this.matStudent.n+v,S=document.createElement("'
HTML += b'td");g.appendChild(S);let C=this.inputId+"-"+M;new I(S,this.'
HTML += b'question,C,i,this.matStudent.v[M],!1,!e)}u==0&&g.appendChild'
HTML += b'(this.generateMatrixParenthesis(!1,this.matStudent.m))}let l'
HTML += b'=["+","-","+","-"],o=[0,0,1,-1],c=[1,-1,0,0],n=[0,22,888,888'
HTML += b'],h=[888,888,-22,-22],p=[-22,-22,0,22],m=[this.matExpected.n'
HTML += b'!=1,this.matExpected.n!=1,this.matExpected.m!=1,this.matExpe'
HTML += b'cted.m!=1],d=[this.matStudent.n>=10,this.matStudent.n<=1,thi'
HTML += b's.matStudent.m>=10,this.matStudent.m<=1];for(let u=0;u<4;u++'
HTML += b'){if(m[u]==!1)continue;let g=k(l[u]);n[u]!=888&&(g.style.top'
HTML += b'=""+n[u]+"px"),h[u]!=888&&(g.style.bottom=""+h[u]+"px"),p[u]'
HTML += b'!=888&&(g.style.right=""+p[u]+"px"),g.classList.add("matrixR'
HTML += b'esizeButton"),t.appendChild(g),d[u]?g.style.opacity="0.5":g.'
HTML += b'addEventListener("click",()=>{for(let v=0;v<this.matStudent.'
HTML += b'm;v++)for(let M=0;M<this.matStudent.n;M++){let S=v*this.matS'
HTML += b'tudent.n+M,C=this.inputId+"-"+S,T=this.question.student[C];t'
HTML += b'his.matStudent.v[S]=T,delete this.question.student[C]}this.m'
HTML += b'atStudent.resize(this.matStudent.m+o[u],this.matStudent.n+c['
HTML += b'u],""),this.genMatrixDom(!1)})}}generateMatrixParenthesis(e,'
HTML += b't){let s=document.createElement("td");s.style.width="3px";fo'
HTML += b'r(let i of["Top",e?"Left":"Right","Bottom"])s.style["border"'
HTML += b'+i+"Width"]="2px",s.style["border"+i+"Style"]="solid";return'
HTML += b' this.question.language=="de"&&(e?s.style.borderTopLeftRadiu'
HTML += b's="5px":s.style.borderTopRightRadius="5px",e?s.style.borderB'
HTML += b'ottomLeftRadius="5px":s.style.borderBottomRightRadius="5px")'
HTML += b',s.rowSpan=t,s}};var x={init:0,errors:1,passed:2,incomplete:'
HTML += b'3},V=class{static{f(this,"Question")}constructor(e,t,s,i){th'
HTML += b'is.state=x.init,this.language=s,this.src=t,this.debug=i,this'
HTML += b'.instanceOrder=z(t.instances.length,!0),this.instanceIdx=0,t'
HTML += b'his.choiceIdx=0,this.includesSingleChoice=!1,this.gapIdx=0,t'
HTML += b'his.expected={},this.types={},this.student={},this.gapInputs'
HTML += b'={},this.parentDiv=e,this.questionDiv=null,this.feedbackPopu'
HTML += b'pDiv=null,this.titleDiv=null,this.checkAndRepeatBtn=null,thi'
HTML += b's.showSolution=!1,this.feedbackSpan=null,this.numCorrect=0,t'
HTML += b'his.numChecked=0,this.hasCheckButton=!0,this.editingEnabled='
HTML += b'!0}reset(){this.gapIdx=0,this.choiceIdx=0,this.instanceIdx=('
HTML += b'this.instanceIdx+1)%this.src.instances.length}getCurrentInst'
HTML += b'ance(){let e=this.instanceOrder[this.instanceIdx];return thi'
HTML += b's.src.instances[e]}editedQuestion(){this.state=x.init,this.u'
HTML += b'pdateVisualQuestionState(),this.questionDiv.style.color="bla'
HTML += b'ck",this.checkAndRepeatBtn.innerHTML=P,this.checkAndRepeatBt'
HTML += b'n.style.display="block",this.checkAndRepeatBtn.style.color="'
HTML += b'black"}updateVisualQuestionState(){let e="black",t="transpar'
HTML += b'ent";switch(this.state){case x.init:e="black";break;case x.p'
HTML += b'assed:e="var(--green)",t="rgba(0,150,0, 0.035)";break;case x'
HTML += b'.incomplete:case x.errors:e="var(--red)",t="rgba(150,0,0, 0.'
HTML += b'035)",this.includesSingleChoice==!1&&this.numChecked>=5&&(th'
HTML += b'is.feedbackSpan.innerHTML="&nbsp;&nbsp;"+this.numCorrect+" /'
HTML += b' "+this.numChecked);break}this.questionDiv.style.backgroundC'
HTML += b'olor=t,this.questionDiv.style.borderColor=e}populateDom(e=!1'
HTML += b'){if(this.parentDiv.innerHTML="",this.questionDiv=w(),this.p'
HTML += b'arentDiv.appendChild(this.questionDiv),this.questionDiv.clas'
HTML += b'sList.add("question"),this.feedbackPopupDiv=w(),this.feedbac'
HTML += b'kPopupDiv.classList.add("questionFeedback"),this.questionDiv'
HTML += b'.appendChild(this.feedbackPopupDiv),this.feedbackPopupDiv.in'
HTML += b'nerHTML="awesome",this.debug&&"src_line"in this.src){let i=w'
HTML += b'();i.classList.add("debugInfo"),i.innerHTML="Source code: li'
HTML += b'nes "+this.src.src_line+"..",this.questionDiv.appendChild(i)'
HTML += b'}if(this.titleDiv=w(),this.questionDiv.appendChild(this.titl'
HTML += b'eDiv),this.titleDiv.classList.add("questionTitle"),this.titl'
HTML += b'eDiv.innerHTML=this.src.title,this.src.error.length>0){let i'
HTML += b'=k(this.src.error);this.questionDiv.appendChild(i),i.style.c'
HTML += b'olor="red";return}let t=this.getCurrentInstance();if(t!=null'
HTML += b'&&"__svg_image"in t){let i=t.__svg_image.v,l=w();this.questi'
HTML += b'onDiv.appendChild(l);let o=document.createElement("img");l.a'
HTML += b'ppendChild(o),o.classList.add("img"),o.src="data:image/svg+x'
HTML += b'ml;base64,"+i}for(let i of this.src.text.c)this.questionDiv.'
HTML += b'appendChild(this.generateText(i));let s=w();if(s.innerHTML="'
HTML += b'",s.classList.add("button-group"),this.questionDiv.appendChi'
HTML += b'ld(s),this.hasCheckButton=Object.keys(this.expected).length>'
HTML += b'0,this.hasCheckButton&&(this.checkAndRepeatBtn=F(),s.appendC'
HTML += b'hild(this.checkAndRepeatBtn),this.checkAndRepeatBtn.innerHTM'
HTML += b'L=P,this.checkAndRepeatBtn.style.backgroundColor="black",e&&'
HTML += b'(this.checkAndRepeatBtn.style.height="0",this.checkAndRepeat'
HTML += b'Btn.style.visibility="hidden")),this.feedbackSpan=k(""),this'
HTML += b'.feedbackSpan.style.userSelect="none",s.appendChild(this.fee'
HTML += b'dbackSpan),this.debug){if(this.src.variables.length>0){let o'
HTML += b'=w();o.classList.add("debugInfo"),o.innerHTML="Variables gen'
HTML += b'erated by Python Code",this.questionDiv.appendChild(o);let c'
HTML += b'=w();c.classList.add("debugCode"),this.questionDiv.appendChi'
HTML += b'ld(c);let n=this.getCurrentInstance(),h="",p=[...this.src.va'
HTML += b'riables];p.sort();for(let m of p){let d=n[m].t,u=n[m].v;swit'
HTML += b'ch(d){case"vector":u="["+u+"]";break;case"set":u="{"+u+"}";b'
HTML += b'reak}h+=d+" "+m+" = "+u+"<br/>"}c.innerHTML=h}let i=["python'
HTML += b'_src_html","text_src_html"],l=["Python Source Code","Text So'
HTML += b'urce Code"];for(let o=0;o<i.length;o++){let c=i[o];if(c in t'
HTML += b'his.src&&this.src[c].length>0){let n=w();n.classList.add("de'
HTML += b'bugInfo"),n.innerHTML=l[o],this.questionDiv.appendChild(n);l'
HTML += b'et h=w();h.classList.add("debugCode"),this.questionDiv.appen'
HTML += b'd(h),h.innerHTML=this.src[c]}}}this.hasCheckButton&&this.che'
HTML += b'ckAndRepeatBtn.addEventListener("click",()=>{this.state==x.p'
HTML += b'assed?(this.state=x.init,this.editingEnabled=!0,this.reset()'
HTML += b',this.populateDom()):R(this)})}generateMathString(e){let t="'
HTML += b'";switch(e.t){case"math":case"display-math":for(let s of e.c'
HTML += b'){let i=this.generateMathString(s);s.t==="var"&&t.includes("'
HTML += b'!PM")&&(i.startsWith("{-")?(i="{"+i.substring(2),t=t.replace'
HTML += b'All("!PM","-")):t=t.replaceAll("!PM","+")),t+=i}break;case"t'
HTML += b'ext":return e.d;case"plus_minus":{t+=" !PM ";break}case"var"'
HTML += b':{let s=this.getCurrentInstance(),i=s[e.d].t,l=s[e.d].v;swit'
HTML += b'ch(i){case"vector":return"\\\\left["+l+"\\\\right]";case"set":re'
HTML += b'turn"\\\\left\\\\{"+l+"\\\\right\\\\}";case"complex":{let o=l.split('
HTML += b'","),c=parseFloat(o[0]),n=parseFloat(o[1]);return a.const(c,'
HTML += b'n).toTexString()}case"matrix":{let o=new E(0,0);return o.fro'
HTML += b'mString(l),t=o.toTeXString(e.d.includes("augmented"),this.la'
HTML += b'nguage!="de"),t}case"term":{try{t=b.parse(l).toTexString()}c'
HTML += b'atch{}break}default:t=l}}}return e.t==="plus_minus"?t:"{"+t+'
HTML += b'"}"}generateText(e,t=!1){switch(e.t){case"paragraph":case"sp'
HTML += b'an":{let s=document.createElement(e.t=="span"||t?"span":"p")'
HTML += b';for(let i of e.c)s.appendChild(this.generateText(i));return'
HTML += b' s.style.userSelect="none",s}case"text":return k(e.d);case"c'
HTML += b'ode":{let s=k(e.d);return s.classList.add("code"),s}case"ita'
HTML += b'lic":case"bold":{let s=k("");return s.append(...e.c.map(i=>t'
HTML += b'his.generateText(i))),e.t==="bold"?s.style.fontWeight="bold"'
HTML += b':s.style.fontStyle="italic",s}case"math":case"display-math":'
HTML += b'{let s=this.generateMathString(e);return L(s,e.t==="display-'
HTML += b'math")}case"string_var":{let s=k(""),i=this.getCurrentInstan'
HTML += b'ce(),l=i[e.d].t,o=i[e.d].v;return l==="string"?s.innerHTML=o'
HTML += b':(s.innerHTML="EXPECTED VARIABLE OF TYPE STRING",s.style.col'
HTML += b'or="red"),s}case"gap":{let s=k("");return new B(s,this,"",e.'
HTML += b'd),s}case"input":case"input2":{let s=e.t==="input2",i=k("");'
HTML += b'i.style.verticalAlign="text-bottom";let l=e.d,o=this.getCurr'
HTML += b'entInstance()[l];if(this.expected[l]=o.v,this.types[l]=o.t,!'
HTML += b's)switch(o.t){case"set":i.append(L("\\\\{"),k(" "));break;case'
HTML += b'"vector":i.append(L("["),k(" "));break}if(o.t==="string")new'
HTML += b' B(i,this,l,this.expected[l]);else if(o.t==="vector"||o.t==='
HTML += b'"set"){let c=o.v.split(","),n=c.length;for(let h=0;h<n;h++){'
HTML += b'h>0&&i.appendChild(k(" , "));let p=l+"-"+h;new I(i,this,p,c['
HTML += b'h].length,c[h],!1)}}else if(o.t==="matrix"){let c=w();i.appe'
HTML += b'ndChild(c),new H(c,this,l,o.v)}else if(o.t==="complex"){let '
HTML += b'c=o.v.split(",");new I(i,this,l+"-0",c[0].length,c[0],!1),i.'
HTML += b'append(k(" "),L("+"),k(" ")),new I(i,this,l+"-1",c[1].length'
HTML += b',c[1],!1),i.append(k(" "),L("i"))}else{let c=o.t==="int";new'
HTML += b' I(i,this,l,o.v.length,o.v,c)}if(!s)switch(o.t){case"set":i.'
HTML += b'append(k(" "),L("\\\\}"));break;case"vector":i.append(k(" "),L'
HTML += b'("]"));break}return i}case"itemize":return j(e.c.map(s=>O(th'
HTML += b'is.generateText(s))));case"single-choice":case"multi-choice"'
HTML += b':{let s=e.t=="multi-choice";s||(this.includesSingleChoice=!0'
HTML += b');let i=document.createElement("table"),l=e.c.length,o=this.'
HTML += b'debug==!1,c=z(l,o),n=s?X:G,h=s?Z:Y,p=[],m=[];for(let d=0;d<l'
HTML += b';d++){let u=c[d],g=e.c[u],v="mc-"+this.choiceIdx+"-"+u;m.pus'
HTML += b'h(v);let M=g.c[0].t=="bool"?g.c[0].d:this.getCurrentInstance'
HTML += b'()[g.c[0].d].v;this.expected[v]=M,this.types[v]="bool",this.'
HTML += b'student[v]=this.showSolution?M:"false";let S=this.generateTe'
HTML += b'xt(g.c[1],!0),C=document.createElement("tr");i.appendChild(C'
HTML += b'),C.style.cursor="pointer";let T=document.createElement("td"'
HTML += b');p.push(T),C.appendChild(T),T.innerHTML=this.student[v]=="t'
HTML += b'rue"?n:h;let y=document.createElement("td");C.appendChild(y)'
HTML += b',y.appendChild(S),s?C.addEventListener("click",()=>{this.edi'
HTML += b'tingEnabled!=!1&&(this.editedQuestion(),this.student[v]=this'
HTML += b'.student[v]==="true"?"false":"true",this.student[v]==="true"'
HTML += b'?T.innerHTML=n:T.innerHTML=h)}):C.addEventListener("click",('
HTML += b')=>{if(this.editingEnabled!=!1){this.editedQuestion();for(le'
HTML += b't D of m)this.student[D]="false";this.student[v]="true";for('
HTML += b'let D=0;D<m.length;D++){let U=c[D];p[U].innerHTML=this.stude'
HTML += b'nt[m[U]]=="true"?n:h}}})}return this.choiceIdx++,i}case"imag'
HTML += b'e":{let s=w(),l=e.d.split("."),o=l[l.length-1],c=e.c[0].d,n='
HTML += b'e.c[1].d,h=document.createElement("img");s.appendChild(h),h.'
HTML += b'classList.add("img"),h.style.width=c+"%";let p={svg:"svg+xml'
HTML += b'",png:"png",jpg:"jpeg"};return h.src="data:image/"+p[o]+";ba'
HTML += b'se64,"+n,s}default:{let s=k("UNIMPLEMENTED("+e.t+")");return'
HTML += b' s.style.color="red",s}}}};function R(r){r.feedbackSpan.inne'
HTML += b'rHTML="",r.numChecked=0,r.numCorrect=0;let e=!0;for(let i in'
HTML += b' r.expected){let l=r.types[i],o=r.student[i],c=r.expected[i]'
HTML += b';switch(o!=null&&o.length==0&&(e=!1),l){case"bool":r.numChec'
HTML += b'ked++,o.toLowerCase()===c.toLowerCase()&&r.numCorrect++;brea'
HTML += b'k;case"string":{r.numChecked++;let n=r.gapInputs[i],h=o.trim'
HTML += b'().toUpperCase(),p=c.trim().toUpperCase().split("|"),m=!1;fo'
HTML += b'r(let d of p)if(K(h,d)<=1){m=!0,r.numCorrect++,r.gapInputs[i'
HTML += b'].value=d,r.student[i]=d;break}n.style.color=m?"black":"whit'
HTML += b'e",n.style.backgroundColor=m?"transparent":"maroon";break}ca'
HTML += b'se"int":r.numChecked++,Math.abs(parseFloat(o)-parseFloat(c))'
HTML += b'<1e-9&&r.numCorrect++;break;case"float":case"term":{r.numChe'
HTML += b'cked++;try{let n=b.parse(c),h=b.parse(o),p=!1;r.src.is_ode?p'
HTML += b'=ce(n,h):p=b.compare(n,h),p&&r.numCorrect++}catch(n){r.debug'
HTML += b'&&(console.log("term invalid"),console.log(n))}break}case"ve'
HTML += b'ctor":case"complex":case"set":{let n=c.split(",");r.numCheck'
HTML += b'ed+=n.length;let h=[];for(let p=0;p<n.length;p++){let m=r.st'
HTML += b'udent[i+"-"+p];m.length==0&&(e=!1),h.push(m)}if(l==="set")fo'
HTML += b'r(let p=0;p<n.length;p++)try{let m=b.parse(n[p]);for(let d=0'
HTML += b';d<h.length;d++){let u=b.parse(h[d]);if(b.compare(m,u)){r.nu'
HTML += b'mCorrect++;break}}}catch(m){r.debug&&console.log(m)}else for'
HTML += b'(let p=0;p<n.length;p++)try{let m=b.parse(h[p]),d=b.parse(n['
HTML += b'p]);b.compare(m,d)&&r.numCorrect++}catch(m){r.debug&&console'
HTML += b'.log(m)}break}case"matrix":{let n=new E(0,0);n.fromString(c)'
HTML += b',r.numChecked+=n.m*n.n;for(let h=0;h<n.m;h++)for(let p=0;p<n'
HTML += b'.n;p++){let m=h*n.n+p;o=r.student[i+"-"+m],o!=null&&o.length'
HTML += b'==0&&(e=!1);let d=n.v[m];try{let u=b.parse(d),g=b.parse(o);b'
HTML += b'.compare(u,g)&&r.numCorrect++}catch(u){r.debug&&console.log('
HTML += b'u)}}break}default:r.feedbackSpan.innerHTML="UNIMPLEMENTED EV'
HTML += b'AL OF TYPE "+l}}e==!1?r.state=x.incomplete:r.state=r.numCorr'
HTML += b'ect==r.numChecked?x.passed:x.errors,r.updateVisualQuestionSt'
HTML += b'ate();let t=[];switch(r.state){case x.passed:t=ie[r.language'
HTML += b'];break;case x.incomplete:t=se[r.language];break;case x.erro'
HTML += b'rs:t=ne[r.language];break}let s=t[Math.floor(Math.random()*t'
HTML += b'.length)];r.feedbackPopupDiv.innerHTML=s,r.feedbackPopupDiv.'
HTML += b'style.color=r.state===x.passed?"var(--green)":"var(--red)",r'
HTML += b'.feedbackPopupDiv.style.display="flex",setTimeout(()=>{r.fee'
HTML += b'dbackPopupDiv.style.display="none"},1e3),r.editingEnabled=!0'
HTML += b',r.state===x.passed?(r.editingEnabled=!1,r.src.instances.len'
HTML += b'gth>1?r.checkAndRepeatBtn.innerHTML=J:r.checkAndRepeatBtn.st'
HTML += b'yle.visibility="hidden"):r.checkAndRepeatBtn!=null&&(r.check'
HTML += b'AndRepeatBtn.innerHTML=P)}f(R,"evalQuestion");function be(r,'
HTML += b'e){new q(r,e)}f(be,"init");var q=class{static{f(this,"Quiz")'
HTML += b'}constructor(e,t){this.quizSrc=e,["en","de","es","it","fr"].'
HTML += b'includes(this.quizSrc.lang)==!1&&(this.quizSrc.lang="en"),th'
HTML += b'is.debug=t,this.debug&&(document.getElementById("debug").sty'
HTML += b'le.display="block"),this.questions=[],this.timeLeft=e.timer,'
HTML += b'this.timeLimited=e.timer>0,this.fillPageMetadata(),this.time'
HTML += b'Limited?(document.getElementById("timer-info").style.display'
HTML += b'="block",document.getElementById("timer-info-text").innerHTM'
HTML += b'L=oe[this.quizSrc.lang],document.getElementById("start-btn")'
HTML += b'.addEventListener("click",()=>{document.getElementById("time'
HTML += b'r-info").style.display="none",this.generateQuestions(),this.'
HTML += b'runTimer()})):this.generateQuestions()}fillPageMetadata(){do'
HTML += b'cument.getElementById("date").innerHTML=this.quizSrc.date,do'
HTML += b'cument.getElementById("title").innerHTML=this.quizSrc.title,'
HTML += b'document.getElementById("author").innerHTML=this.quizSrc.aut'
HTML += b'hor,document.getElementById("courseInfo1").innerHTML=$[this.'
HTML += b'quizSrc.lang];let e=\'<span onclick="location.reload()" style'
HTML += b'="text-decoration: none; font-weight: bold; cursor: pointer"'
HTML += b'>\'+te[this.quizSrc.lang]+"</span>";document.getElementById("'
HTML += b'courseInfo2").innerHTML=ee[this.quizSrc.lang].replace("*",e)'
HTML += b',document.getElementById("data-policy").innerHTML=le[this.qu'
HTML += b'izSrc.lang]}generateQuestions(){let e=document.getElementByI'
HTML += b'd("questions"),t=1;for(let s of this.quizSrc.questions){s.ti'
HTML += b'tle=""+t+". "+s.title;let i=w();e.appendChild(i);let l=new V'
HTML += b'(i,s,this.quizSrc.lang,this.debug);l.showSolution=this.debug'
HTML += b',this.questions.push(l),l.populateDom(this.timeLimited),this'
HTML += b'.debug&&s.error.length==0&&l.hasCheckButton&&l.checkAndRepea'
HTML += b'tBtn.click(),t++}}runTimer(){document.getElementById("stop-n'
HTML += b'ow").style.display="block",document.getElementById("stop-now'
HTML += b'-btn").innerHTML=ae[this.quizSrc.lang],document.getElementBy'
HTML += b'Id("stop-now-btn").addEventListener("click",()=>{this.timeLe'
HTML += b'ft=1});let e=document.getElementById("timer");e.style.displa'
HTML += b'y="block",e.innerHTML=he(this.timeLeft);let t=setInterval(()'
HTML += b'=>{this.timeLeft--,e.innerHTML=he(this.timeLeft),this.timeLe'
HTML += b'ft<=0&&this.stopTimer(t)},1e3)}stopTimer(e){document.getElem'
HTML += b'entById("stop-now").style.display="none",clearInterval(e);le'
HTML += b't t=0,s=0;for(let l of this.questions){let o=l.src.points;s+'
HTML += b'=o,R(l),l.state===x.passed&&(t+=o),l.editingEnabled=!1}docum'
HTML += b'ent.getElementById("questions-eval").style.display="block";l'
HTML += b'et i=document.getElementById("questions-eval-percentage");i.'
HTML += b'innerHTML=s==0?"":""+t+" / "+s+" "+re[this.quizSrc.lang]+" <'
HTML += b'br/><br/>"+Math.round(t/s*100)+" %"}};function he(r){let e=M'
HTML += b'ath.floor(r/60),t=r%60;return e+":"+(""+t).padStart(2,"0")}f'
HTML += b'(he,"formatTime");return ge(ke);})();pysell.init(quizSrc,deb'
HTML += b'ug);</script></body> </html> '
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
