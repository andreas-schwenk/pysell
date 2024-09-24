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
HTML += b'color: black; background-color: white; border-style: solid; '
HTML += b'border-width: 3px; border-color: black; padding: 4px; margin'
HTML += b'-top: 32px; margin-bottom: 32px; -webkit-box-shadow: 0px 0px'
HTML += b' 6px 3px #e8e8e8; box-shadow: 0px 0px 6px 3px #e8e8e8; overf'
HTML += b'low-x: auto; overflow-y: hidden; } .button-group { display: '
HTML += b'flex; align-items: center; justify-content: center; text-ali'
HTML += b'gn: center; margin-left: auto; margin-right: auto; }  @media'
HTML += b' (min-width: 800px) { .question { border-radius: 6px; paddin'
HTML += b'g: 16px; margin: 16px; } }  .questionFeedback { opacity: 1.8'
HTML += b'; z-index: 10; display: none; position: absolute; pointer-ev'
HTML += b'ents: none; left: 0%; top: 0%; width: 100%; height: 100%; te'
HTML += b'xt-align: center; font-size: 4vw; text-shadow: 0px 0px 18px '
HTML += b'rgba(0, 0, 0, 0.15); background-color: rgba(255, 255, 255, 0'
HTML += b'.95); padding: 10px; justify-content: center; align-items: c'
HTML += b'enter; /*padding-top: 20px; padding-bottom: 20px;*/ /*border'
HTML += b'-style: solid; border-width: 4px; border-color: rgb(200, 200'
HTML += b', 200); border-radius: 16px; -webkit-box-shadow: 0px 0px 18p'
HTML += b'x 5px rgba(0, 0, 0, 0.66); box-shadow: 0px 0px 18px 5px rgba'
HTML += b'(0, 0, 0, 0.66);*/ } .questionTitle { user-select: none; fon'
HTML += b't-size: 24pt; } .code { font-family: "Courier New", Courier,'
HTML += b' monospace; color: black; background-color: rgb(235, 235, 23'
HTML += b'5); padding: 2px 5px; border-radius: 5px; margin: 1px 2px; }'
HTML += b' .debugCode { font-family: "Courier New", Courier, monospace'
HTML += b'; padding: 4px; margin-bottom: 5px; background-color: black;'
HTML += b' color: white; border-radius: 5px; opacity: 0.85; overflow-x'
HTML += b': scroll; } .debugInfo { text-align: end; font-size: 10pt; m'
HTML += b'argin-top: 2px; color: rgb(64, 64, 64); } ul { user-select: '
HTML += b'none; margin-top: 0; margin-left: 0px; padding-left: 20px; }'
HTML += b' .inputField { position: relative; width: 32px; height: 24px'
HTML += b'; font-size: 14pt; border-style: solid; border-color: black;'
HTML += b' border-radius: 5px; border-width: 0.2; padding-left: 5px; p'
HTML += b'adding-right: 5px; outline-color: black; background-color: t'
HTML += b'ransparent; margin: 1px; } .inputField:focus { outline-color'
HTML += b': maroon; } .equationPreview { position: absolute; top: 120%'
HTML += b'; left: 0%; padding-left: 8px; padding-right: 8px; padding-t'
HTML += b'op: 4px; padding-bottom: 4px; background-color: rgb(128, 0, '
HTML += b'0); border-radius: 5px; font-size: 12pt; color: white; text-'
HTML += b'align: start; z-index: 100; opacity: 0.95; } .button { paddi'
HTML += b'ng-left: 8px; padding-right: 8px; padding-top: 5px; padding-'
HTML += b'bottom: 5px; font-size: 12pt; background-color: rgb(0, 150, '
HTML += b'0); color: white; border-style: none; border-radius: 4px; he'
HTML += b'ight: 36px; cursor: pointer; } .matrixResizeButton { width: '
HTML += b'20px; background-color: black; color: #fff; text-align: cent'
HTML += b'er; border-radius: 3px; position: absolute; z-index: 1; heig'
HTML += b'ht: 20px; cursor: pointer; margin-bottom: 3px; } a { color: '
HTML += b'black; text-decoration: underline; } .timer { display: none;'
HTML += b' position: fixed; left: 0; top: 0; padding: 5px 15px; backgr'
HTML += b'ound-color: rgb(32, 32, 32); color: white; opacity: 0.4; fon'
HTML += b't-size: 32pt; z-index: 1000; /*margin: 2px; border-radius: 1'
HTML += b'0px;*/ border-bottom-right-radius: 10px; text-align: center;'
HTML += b' font-family: "Courier New", Courier, monospace; } .evalBtn '
HTML += b'{ text-align: center; } .eval { text-align: center; backgrou'
HTML += b'nd-color: black; color: white; padding: 10px; } @media (min-'
HTML += b'width: 800px) { .eval { border-radius: 10px; } } .timerInfo '
HTML += b'{ font-size: x-large; text-align: center; background-color: '
HTML += b'black; color: white; padding: 20px 10px; user-select: none; '
HTML += b'} @media (min-width: 800px) { .timerInfo { border-radius: 6p'
HTML += b'x; } } </style> </head> <body> <div id="timer" class="timer"'
HTML += b'>02:34</div> <h1 id="title"></h1> <div style="margin-top: 15'
HTML += b'px"></div> <div class="author" id="author"></div> <p id="cou'
HTML += b'rseInfo1" class="courseInfo"></p> <p id="courseInfo2" class='
HTML += b'"courseInfo"></p> <h1 id="debug" class="debugCode" style="di'
HTML += b'splay: none">DEBUG VERSION</h1>  <br />  <div class="content'
HTML += b's"> <div id="timer-info" class="timerInfo" style="display: n'
HTML += b'one"> <span id="timer-info-text"></span> <br /><br /> <butto'
HTML += b'n id="start-btn" class="button" style="background-color: var'
HTML += b'(--green); font-size: x-large" > Start </button> </div>  <di'
HTML += b'v id="questions"></div>  <div id="stop-now" class="evalBtn" '
HTML += b'style="display: none"> <button id="stop-now-btn" class="butt'
HTML += b'on" style="background-color: var(--green)" > jetzt auswerten'
HTML += b' (TODO: translate) </button> </div> <br /> <div id="question'
HTML += b's-eval" class="eval" style="display: none"> <h1 id="question'
HTML += b's-eval-percentage">0 %</h1> </div> </div>  <br /><br /><br /'
HTML += b'><br />  <div class="footer"> <div class="contents"> <span i'
HTML += b'd="date"></span> &mdash; This quiz was developed using pySEL'
HTML += b'L, a Python-based Simple E-Learning Language &mdash; <a href'
HTML += b'="https://pysell.org" style="color: var(--grey)" >https://py'
HTML += b'sell.org</a > <br /> <span style="width: 64px"> <img style="'
HTML += b'max-width: 48px; padding: 16px 0px" src="data:image/svg+xml;'
HTML += b'base64,PD94bWwgdmVyc2lvbj0iMS4wIiBlbmNvZGluZz0iVVRGLTgiPz4KP'
HTML += b'CEtLSBDcmVhdGVkIHdpdGggSW5rc2NhcGUgKGh0dHA6Ly93d3cuaW5rc2Nhc'
HTML += b'GUub3JnLykgLS0+Cjxzdmcgd2lkdGg9IjEwMG1tIiBoZWlnaHQ9IjEwMG1tI'
HTML += b'iB2ZXJzaW9uPSIxLjEiIHZpZXdCb3g9IjAgMCAxMDAgMTAwIiB4bWxucz0ia'
HTML += b'HR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHhtbG5zOnhsaW5rPSJodHRwO'
HTML += b'i8vd3d3LnczLm9yZy8xOTk5L3hsaW5rIj4KIDxkZWZzPgogIDxsaW5lYXJHc'
HTML += b'mFkaWVudCBpZD0ibGluZWFyR3JhZGllbnQzNjU4IiB4MT0iMjguNTI3IiB4M'
HTML += b'j0iMTI4LjUzIiB5MT0iNzkuNjQ4IiB5Mj0iNzkuNjQ4IiBncmFkaWVudFRyY'
HTML += b'W5zZm9ybT0ibWF0cml4KDEuMDE2MSAwIDAgMS4wMTYxIC0yOS43OSAtMzAuO'
HTML += b'TI4KSIgZ3JhZGllbnRVbml0cz0idXNlclNwYWNlT25Vc2UiPgogICA8c3Rvc'
HTML += b'CBzdG9wLWNvbG9yPSIjNTkwMDVlIiBvZmZzZXQ9IjAiLz4KICAgPHN0b3Agc'
HTML += b'3RvcC1jb2xvcj0iI2FkMDA3ZiIgb2Zmc2V0PSIxIi8+CiAgPC9saW5lYXJHc'
HTML += b'mFkaWVudD4KIDwvZGVmcz4KIDxyZWN0IHdpZHRoPSIxMDAiIGhlaWdodD0iM'
HTML += b'TAwIiByeT0iMCIgZmlsbD0idXJsKCNsaW5lYXJHcmFkaWVudDM2NTgpIi8+C'
HTML += b'iA8ZyBmaWxsPSIjZmZmIj4KICA8ZyB0cmFuc2Zvcm09Im1hdHJpeCguNDA3N'
HTML += b'DMgMCAwIC40MDc0MyAtNDIuODQyIC0zNi4xMzYpIiBzdHJva2Utd2lkdGg9I'
HTML += b'jMuNzc5NSIgc3R5bGU9InNoYXBlLWluc2lkZTp1cmwoI3JlY3Q5NTItNyk7c'
HTML += b'2hhcGUtcGFkZGluZzo2LjUzMTQ0O3doaXRlLXNwYWNlOnByZSIgYXJpYS1sY'
HTML += b'WJlbD0iU0VMTCI+CiAgIDxwYXRoIGQ9Im0xNzEuMDEgMjM4LjM5cS0yLjExM'
HTML += b'i0yLjY4OC01LjU2OC00LjIyNC0zLjM2LTEuNjMyLTYuNTI4LTEuNjMyLTEuN'
HTML += b'jMyIDAtMy4zNiAwLjI4OC0xLjYzMiAwLjI4OC0yLjk3NiAxLjE1Mi0xLjM0N'
HTML += b'CAwLjc2OC0yLjMwNCAyLjExMi0wLjg2NCAxLjI0OC0wLjg2NCAzLjI2NCAwI'
HTML += b'DEuNzI4IDAuNjcyIDIuODggMC43NjggMS4xNTIgMi4xMTIgMi4wMTYgMS40N'
HTML += b'CAwLjg2NCAzLjM2IDEuNjMyIDEuOTIgMC42NzIgNC4zMiAxLjQ0IDMuNDU2I'
HTML += b'DEuMTUyIDcuMiAyLjU5MiAzLjc0NCAxLjM0NCA2LjgxNiAzLjY0OHQ1LjA4O'
HTML += b'CA1Ljc2cTIuMDE2IDMuMzYgMi4wMTYgOC40NDggMCA1Ljg1Ni0yLjIwOCAxM'
HTML += b'C4xNzYtMi4xMTIgNC4yMjQtNS43NiA3LjAwOHQtOC4zNTIgNC4xMjgtOS42O'
HTML += b'TYgMS4zNDRxLTcuMjk2IDAtMTQuMTEyLTIuNDk2LTYuODE2LTIuNTkyLTExL'
HTML += b'jMyOC03LjI5NmwxMC43NTItMTAuOTQ0cTIuNDk2IDMuMDcyIDYuNTI4IDUuM'
HTML += b'Tg0IDQuMTI4IDIuMDE2IDguMTYgMi4wMTYgMS44MjQgMCAzLjU1Mi0wLjM4N'
HTML += b'HQyLjk3Ni0xLjI0OHExLjM0NC0wLjg2NCAyLjExMi0yLjMwNHQwLjc2OC0zL'
HTML += b'jQ1NnEwLTEuOTItMC45Ni0zLjI2NHQtMi43ODQtMi40cS0xLjcyOC0xLjE1M'
HTML += b'i00LjQxNi0yLjAxNi0yLjU5Mi0wLjk2LTUuOTUyLTIuMDE2LTMuMjY0LTEuM'
HTML += b'DU2LTYuNDMyLTIuNDk2LTMuMDcyLTEuNDQtNS41NjgtMy42NDgtMi40LTIuM'
HTML += b'zA0LTMuOTM2LTUuNDcyLTEuNDQtMy4yNjQtMS40NC03Ljg3MiAwLTUuNjY0I'
HTML += b'DIuMzA0LTkuNjk2dDYuMDQ4LTYuNjI0IDguNDQ4LTMuNzQ0cTQuNzA0LTEuM'
HTML += b'jQ4IDkuNTA0LTEuMjQ4IDUuNzYgMCAxMS43MTIgMi4xMTIgNi4wNDggMi4xM'
HTML += b'TIgMTAuNTYgNi4yNHoiLz4KICAgPHBhdGggZD0ibTE5MS44NCAyODguN3YtN'
HTML += b'jcuOTY4aDUyLjE5bC0xLjI5ODggMTMuOTJoLTM1LjA1MXYxMi43NjhoMzMuN'
HTML += b'DE5bC0xLjI5ODggMTMuMTUyaC0zMi4xMnYxNC4xMTJoMzEuNTg0bC0xLjI5O'
HTML += b'DggMTQuMDE2eiIvPgogIDwvZz4KICA8ZyB0cmFuc2Zvcm09Im1hdHJpeCguN'
HTML += b'DA3NDMgMCAwIC40MDc0MyAtNDAuMTY4IC03OC4wODIpIiBzdHJva2Utd2lkd'
HTML += b'Gg9IjMuNzc5NSIgc3R5bGU9InNoYXBlLWluc2lkZTp1cmwoI3JlY3Q5NTItO'
HTML += b'S05KTtzaGFwZS1wYWRkaW5nOjYuNTMxNDQ7d2hpdGUtc3BhY2U6cHJlIiBhc'
HTML += b'mlhLWxhYmVsPSJweSI+CiAgIDxwYXRoIGQ9Im0xODcuNDMgMjY0LjZxMCA0L'
HTML += b'jk5Mi0xLjUzNiA5LjZ0LTQuNTEyIDguMTZxLTIuODggMy40NTYtNy4xMDQgN'
HTML += b'S41Njh0LTkuNiAyLjExMnEtNC40MTYgMC04LjM1Mi0xLjcyOC0zLjkzNi0xL'
HTML += b'jgyNC02LjE0NC00Ljg5NmgtMC4xOTJ2MjguMzJoLTE1Ljc0NHYtNzAuODQ4a'
HTML += b'DE0Ljk3NnY1Ljg1NmgwLjI4OHEyLjIwOC0yLjg4IDYuMDQ4LTQuOTkyIDMuO'
HTML += b'TM2LTIuMjA4IDkuMjE2LTIuMjA4IDUuMTg0IDAgOS40MDggMi4wMTZ0Ny4xM'
HTML += b'DQgNS40NzJxMi45NzYgMy40NTYgNC41MTIgOC4wNjQgMS42MzIgNC41MTIgM'
HTML += b'S42MzIgOS41MDR6bS0xNS4yNjQgMHEwLTIuMzA0LTAuNzY4LTQuNTEyLTAuN'
HTML += b'jcyLTIuMjA4LTIuMTEyLTMuODQtMS4zNDQtMS43MjgtMy40NTYtMi43ODR0L'
HTML += b'TQuODk2LTEuMDU2cS0yLjY4OCAwLTQuOCAxLjA1NnQtMy42NDggMi43ODRxL'
HTML += b'TEuNDQgMS43MjgtMi4zMDQgMy45MzYtMC43NjggMi4yMDgtMC43NjggNC41M'
HTML += b'TJ0MC43NjggNC41MTJxMC44NjQgMi4yMDggMi4zMDQgMy45MzYgMS41MzYgM'
HTML += b'S43MjggMy42NDggMi43ODR0NC44IDEuMDU2cTIuNzg0IDAgNC44OTYtMS4wN'
HTML += b'TZ0My40NTYtMi43ODRxMS40NC0xLjcyOCAyLjExMi0zLjkzNiAwLjc2OC0yL'
HTML += b'jMwNCAwLjc2OC00LjYwOHoiLz4KICAgPHBhdGggZD0ibTIyNC4yOSAyOTUuO'
HTML += b'XEtMS40NCAzLjc0NC0zLjI2NCA2LjYyNC0xLjcyOCAyLjk3Ni00LjIyNCA0L'
HTML += b'jk5Mi0yLjQgMi4xMTItNS43NiAzLjE2OC0zLjI2NCAxLjA1Ni03Ljc3NiAxL'
HTML += b'jA1Ni0yLjIwOCAwLTQuNjA4LTAuMjg4LTIuMzA0LTAuMjg4LTQuMDMyLTAuN'
HTML += b'zY4bDEuNzI4LTEzLjI0OHExLjE1MiAwLjM4NCAyLjQ5NiAwLjU3NiAxLjQ0I'
HTML += b'DAuMjg4IDIuNTkyIDAuMjg4IDMuNjQ4IDAgNS4yOC0xLjcyOCAxLjYzMi0xL'
HTML += b'jYzMiAyLjc4NC00LjcwNGwxLjUzNi0zLjkzNi0xOS45NjgtNDcuMDRoMTcuN'
HTML += b'DcybDEwLjY1NiAzMC43MmgwLjI4OGw5LjUwNC0zMC43MmgxNi43MDR6Ii8+C'
HTML += b'iAgPC9nPgogIDxwYXRoIGQ9Im02OC4wOTYgMTUuNzc1aDcuODAyOWwtOC45O'
HTML += b'DU0IDY5Ljc5MWgtNy44MDN6IiBzdHJva2Utd2lkdGg9IjEuMTE3NiIvPgogI'
HTML += b'DxwYXRoIGQ9Im04My44NTMgMTUuNzQ4aDcuODAzbC04Ljk4NTQgNjkuNzkxa'
HTML += b'C03LjgwM3oiIHN0cm9rZS13aWR0aD0iMS4xMTc2Ii8+CiA8L2c+Cjwvc3ZnP'
HTML += b'go=" /> </span> <span id="data-policy"></span> </div> </div>'
HTML += b'  <script>let debug = false; let quizSrc = {};var pysell=(()'
HTML += b'=>{var A=Object.defineProperty;var pe=Object.getOwnPropertyD'
HTML += b'escriptor;var ue=Object.getOwnPropertyNames;var de=Object.pr'
HTML += b'ototype.hasOwnProperty;var f=(r,e)=>A(r,"name",{value:e,conf'
HTML += b'igurable:!0});var me=(r,e)=>{for(var t in e)A(r,t,{get:e[t],'
HTML += b'enumerable:!0})},fe=(r,e,t,s)=>{if(e&&typeof e=="object"||ty'
HTML += b'peof e=="function")for(let i of ue(e))!de.call(r,i)&&i!==t&&'
HTML += b'A(r,i,{get:()=>e[i],enumerable:!(s=pe(e,i))||s.enumerable});'
HTML += b'return r};var ge=r=>fe(A({},"__esModule",{value:!0}),r);var '
HTML += b'ke={};me(ke,{Quiz:()=>q,init:()=>be});function w(r=[]){let e'
HTML += b'=document.createElement("div");return e.append(...r),e}f(w,"'
HTML += b'genDiv");function j(r=[]){let e=document.createElement("ul")'
HTML += b';return e.append(...r),e}f(j,"genUl");function O(r){let e=do'
HTML += b'cument.createElement("li");return e.appendChild(r),e}f(O,"ge'
HTML += b'nLi");function W(r){let e=document.createElement("input");re'
HTML += b'turn e.spellcheck=!1,e.type="text",e.classList.add("inputFie'
HTML += b'ld"),e.style.width=r+"px",e}f(W,"genInputField");function F('
HTML += b'){let r=document.createElement("button");return r.type="butt'
HTML += b'on",r.classList.add("button"),r}f(F,"genButton");function k('
HTML += b'r,e=[]){let t=document.createElement("span");return e.length'
HTML += b'>0?t.append(...e):t.innerHTML=r,t}f(k,"genSpan");function Q('
HTML += b'r,e,t=!1){katex.render(e,r,{throwOnError:!1,displayMode:t,ma'
HTML += b'cros:{"\\\\RR":"\\\\mathbb{R}","\\\\NN":"\\\\mathbb{N}","\\\\QQ":"\\\\ma'
HTML += b'thbb{Q}","\\\\ZZ":"\\\\mathbb{Z}","\\\\CC":"\\\\mathbb{C}"}})}f(Q,"u'
HTML += b'pdateMathElement");function L(r,e=!1){let t=document.createE'
HTML += b'lement("span");return Q(t,r,e),t}f(L,"genMathSpan");function'
HTML += b' K(r,e){let t=Array(e.length+1).fill(null).map(()=>Array(r.l'
HTML += b'ength+1).fill(null));for(let s=0;s<=r.length;s+=1)t[0][s]=s;'
HTML += b'for(let s=0;s<=e.length;s+=1)t[s][0]=s;for(let s=1;s<=e.leng'
HTML += b'th;s+=1)for(let i=1;i<=r.length;i+=1){let l=r[i-1]===e[s-1]?'
HTML += b'0:1;t[s][i]=Math.min(t[s][i-1]+1,t[s-1][i]+1,t[s-1][i-1]+l)}'
HTML += b'return t[e.length][r.length]}f(K,"levenshteinDistance");var '
HTML += b'Z=\'<svg xmlns="http://www.w3.org/2000/svg" height="28" viewB'
HTML += b'ox="0 0 448 512"><path d="M384 80c8.8 0 16 7.2 16 16V416c0 8'
HTML += b'.8-7.2 16-16 16H64c-8.8 0-16-7.2-16-16V96c0-8.8 7.2-16 16-16'
HTML += b'H384zM64 32C28.7 32 0 60.7 0 96V416c0 35.3 28.7 64 64 64H384'
HTML += b'c35.3 0 64-28.7 64-64V96c0-35.3-28.7-64-64-64H64z"/></svg>\','
HTML += b'X=\'<svg xmlns="http://www.w3.org/2000/svg" height="28" viewB'
HTML += b'ox="0 0 448 512"><path d="M64 80c-8.8 0-16 7.2-16 16V416c0 8'
HTML += b'.8 7.2 16 16 16H384c8.8 0 16-7.2 16-16V96c0-8.8-7.2-16-16-16'
HTML += b'H64zM0 96C0 60.7 28.7 32 64 32H384c35.3 0 64 28.7 64 64V416c'
HTML += b'0 35.3-28.7 64-64 64H64c-35.3 0-64-28.7-64-64V96zM337 209L20'
HTML += b'9 337c-9.4 9.4-24.6 9.4-33.9 0l-64-64c-9.4-9.4-9.4-24.6 0-33'
HTML += b'.9s24.6-9.4 33.9 0l47 47L303 175c9.4-9.4 24.6-9.4 33.9 0s9.4'
HTML += b' 24.6 0 33.9z"/>\',Y=\'<svg xmlns="http://www.w3.org/2000/svg"'
HTML += b' height="28" viewBox="0 0 512 512"><path d="M464 256A208 208'
HTML += b' 0 1 0 48 256a208 208 0 1 0 416 0zM0 256a256 256 0 1 1 512 0'
HTML += b'A256 256 0 1 1 0 256z"/></svg>\',G=\'<svg xmlns="http://www.w3'
HTML += b'.org/2000/svg" height="28" viewBox="0 0 512 512"><path d="M2'
HTML += b'56 48a208 208 0 1 1 0 416 208 208 0 1 1 0-416zm0 464A256 256'
HTML += b' 0 1 0 256 0a256 256 0 1 0 0 512zM369 209c9.4-9.4 9.4-24.6 0'
HTML += b'-33.9s-24.6-9.4-33.9 0l-111 111-47-47c-9.4-9.4-24.6-9.4-33.9'
HTML += b' 0s-9.4 24.6 0 33.9l64 64c9.4 9.4 24.6 9.4 33.9 0L369 209z"/'
HTML += b'></svg>\',P=\'<svg xmlns="http://www.w3.org/2000/svg" width="5'
HTML += b'0" height="25" viewBox="0 0 384 512" fill="white"><path d="M'
HTML += b'73 39c-14.8-9.1-33.4-9.4-48.5-.9S0 62.6 0 80V432c0 17.4 9.4 '
HTML += b'33.4 24.5 41.9s33.7 8.1 48.5-.9L361 297c14.3-8.7 23-24.2 23-'
HTML += b'41s-8.7-32.2-23-41L73 39z"/></svg>\',J=\'<svg xmlns="http://ww'
HTML += b'w.w3.org/2000/svg" width="50" height="25" viewBox="0 0 512 5'
HTML += b'12" fill="white"><path d="M0 224c0 17.7 14.3 32 32 32s32-14.'
HTML += b'3 32-32c0-53 43-96 96-96H320v32c0 12.9 7.8 24.6 19.8 29.6s25'
HTML += b'.7 2.2 34.9-6.9l64-64c12.5-12.5 12.5-32.8 0-45.3l-64-64c-9.2'
HTML += b'-9.2-22.9-11.9-34.9-6.9S320 19.1 320 32V64H160C71.6 64 0 135'
HTML += b'.6 0 224zm512 64c0-17.7-14.3-32-32-32s-32 14.3-32 32c0 53-43'
HTML += b' 96-96 96H192V352c0-12.9-7.8-24.6-19.8-29.6s-25.7-2.2-34.9 6'
HTML += b'.9l-64 64c-12.5 12.5-12.5 32.8 0 45.3l64 64c9.2 9.2 22.9 11.'
HTML += b'9 34.9 6.9s19.8-16.6 19.8-29.6V448H352c88.4 0 160-71.6 160-1'
HTML += b'60z"/></svg>\';var $={en:"This page operates entirely in your'
HTML += b' browser and does not store any data on external servers.",d'
HTML += b'e:"Diese Seite wird in Ihrem Browser ausgef\\xFChrt und speic'
HTML += b'hert keine Daten auf Servern.",es:"Esta p\\xE1gina se ejecuta'
HTML += b' en su navegador y no almacena ning\\xFAn dato en los servido'
HTML += b'res.",it:"Questa pagina viene eseguita nel browser e non mem'
HTML += b'orizza alcun dato sui server.",fr:"Cette page fonctionne dan'
HTML += b's votre navigateur et ne stocke aucune donn\\xE9e sur des ser'
HTML += b'veurs."},ee={en:"* this page to receive a new set of randomi'
HTML += b'zed tasks.",de:"Sie k\\xF6nnen diese Seite *, um neue randomi'
HTML += b'sierte Aufgaben zu erhalten.",es:"Puedes * esta p\\xE1gina pa'
HTML += b'ra obtener nuevas tareas aleatorias.",it:"\\xC8 possibile * q'
HTML += b'uesta pagina per ottenere nuovi compiti randomizzati",fr:"Vo'
HTML += b'us pouvez * cette page pour obtenir de nouvelles t\\xE2ches a'
HTML += b'l\\xE9atoires"},te={en:"Refresh",de:"aktualisieren",es:"recar'
HTML += b'gar",it:"ricaricare",fr:"recharger"},ie={en:["awesome","grea'
HTML += b't","well done","nice","you got it","good"],de:["super","gut '
HTML += b'gemacht","weiter so","richtig"],es:["impresionante","genial"'
HTML += b',"correcto","bien hecho"],it:["fantastico","grande","corrett'
HTML += b'o","ben fatto"],fr:["g\\xE9nial","super","correct","bien fait'
HTML += b'"]},se={en:["please complete all fields"],de:["bitte alles a'
HTML += b'usf\\xFCllen"],es:["por favor, rellene todo"],it:["compilare '
HTML += b'tutto"],fr:["remplis tout s\'il te plait"]},ne={en:["try agai'
HTML += b'n","still some mistakes","wrong answer","no"],de:["leider fa'
HTML += b'lsch","nicht richtig","versuch\'s nochmal"],es:["int\\xE9ntalo'
HTML += b' de nuevo","todav\\xEDa algunos errores","respuesta incorrect'
HTML += b'a"],it:["riprova","ancora qualche errore","risposta sbagliat'
HTML += b'a"],fr:["r\\xE9essayer","encore des erreurs","mauvaise r\\xE9p'
HTML += b'onse"]},re={en:"point(s)",de:"Punkt(e)",es:"punto(s)",it:"pu'
HTML += b'nto/i",fr:"point(s)"},ae={en:"Evaluate now",de:"Jetzt auswer'
HTML += b'ten",es:"Evaluar ahora",it:"Valuta ora",fr:"\\xC9valuer maint'
HTML += b'enant"},le={en:"Data Policy: This website does not collect, '
HTML += b'store, or process any personal data on external servers. All'
HTML += b' functionality is executed locally in your browser, ensuring'
HTML += b' complete privacy. No cookies are used, and no data is trans'
HTML += b'mitted to or from the server. Your activity on this site rem'
HTML += b'ains entirely private and local to your device.",de:"Datensc'
HTML += b'hutzrichtlinie: Diese Website sammelt, speichert oder verarb'
HTML += b'eitet keine personenbezogenen Daten auf externen Servern. Al'
HTML += b'le Funktionen werden lokal in Ihrem Browser ausgef\\xFChrt, u'
HTML += b'm vollst\\xE4ndige Privatsph\\xE4re zu gew\\xE4hrleisten. Es we'
HTML += b'rden keine Cookies verwendet, und es werden keine Daten an d'
HTML += b'en Server gesendet oder von diesem empfangen. Ihre Aktivit\\x'
HTML += b'E4t auf dieser Seite bleibt vollst\\xE4ndig privat und lokal '
HTML += b'auf Ihrem Ger\\xE4t.",es:"Pol\\xEDtica de datos: Este sitio we'
HTML += b'b no recopila, almacena ni procesa ning\\xFAn dato personal e'
HTML += b'n servidores externos. Toda la funcionalidad se ejecuta loca'
HTML += b'lmente en su navegador, garantizando una privacidad completa'
HTML += b'. No se utilizan cookies y no se transmiten datos hacia o de'
HTML += b'sde el servidor. Su actividad en este sitio permanece comple'
HTML += b'tamente privada y local en su dispositivo.",it:"Politica sui'
HTML += b' dati: Questo sito web non raccoglie, memorizza o elabora al'
HTML += b'cun dato personale su server esterni. Tutte le funzionalit\\x'
HTML += b'E0 vengono eseguite localmente nel tuo browser, garantendo u'
HTML += b'na privacy completa. Non vengono utilizzati cookie e nessun '
HTML += b'dato viene trasmesso da o verso il server. La tua attivit\\xE'
HTML += b'0 su questo sito rimane completamente privata e locale sul t'
HTML += b'uo dispositivo.",fr:"Politique de confidentialit\\xE9: Ce sit'
HTML += b'e web ne collecte, ne stocke ni ne traite aucune donn\\xE9e p'
HTML += b'ersonnelle sur des serveurs externes. Toutes les fonctionnal'
HTML += b'it\\xE9s sont ex\\xE9cut\\xE9es localement dans votre navigateu'
HTML += b'r, garantissant une confidentialit\\xE9 totale. Aucun cookie '
HTML += b'n\\u2019est utilis\\xE9 et aucune donn\\xE9e n\\u2019est transmi'
HTML += b'se vers ou depuis le serveur. Votre activit\\xE9 sur ce site '
HTML += b'reste enti\\xE8rement priv\\xE9e et locale sur votre appareil.'
HTML += b'"},oe={en:"You have a limited time to complete this quiz. Th'
HTML += b'e countdown, displayed in minutes, is visible at the top-lef'
HTML += b"t of the screen. When you're ready to begin, simply press th"
HTML += b'e Start button.",de:"Die Zeit f\\xFCr dieses Quiz ist begrenz'
HTML += b't. Der Countdown, in Minuten angezeigt, l\\xE4uft oben links '
HTML += b'auf dem Bildschirm. Mit dem Start-Button beginnt das Quiz.",'
HTML += b'es:"Tienes un tiempo limitado para completar este cuestionar'
HTML += b'io. La cuenta regresiva, mostrada en minutos, se encuentra e'
HTML += b'n la parte superior izquierda de la pantalla. Cuando est\\xE9'
HTML += b's listo, simplemente presiona el bot\\xF3n de inicio.",it:"Ha'
HTML += b'i un tempo limitato per completare questo quiz. Il conto all'
HTML += b'a rovescia, visualizzato in minuti, \\xE8 visibile in alto a '
HTML += b'sinistra dello schermo. Quando sei pronto, premi semplicemen'
HTML += b'te il pulsante Start.",fr:"Vous disposez d\\u2019un temps lim'
HTML += b'it\\xE9 pour compl\\xE9ter ce quiz. Le compte \\xE0 rebours, af'
HTML += b'fich\\xE9 en minutes, est visible en haut \\xE0 gauche de l\\u2'
HTML += b'019\\xE9cran. Lorsque vous \\xEAtes pr\\xEAt, appuyez simplemen'
HTML += b't sur le bouton D\\xE9marrer."};function z(r,e=!1){let t=new '
HTML += b'Array(r);for(let s=0;s<r;s++)t[s]=s;if(e)for(let s=0;s<r;s++'
HTML += b'){let i=Math.floor(Math.random()*r),l=Math.floor(Math.random'
HTML += b'()*r),o=t[i];t[i]=t[l],t[l]=o}return t}f(z,"range");function'
HTML += b' N(r,e,t=-1){if(t<0&&(t=r.length),t==1){e.push([...r]);retur'
HTML += b'n}for(let s=0;s<t;s++){N(r,e,t-1);let i=t%2==0?s:0,l=r[i];r['
HTML += b'i]=r[t-1],r[t-1]=l}}f(N,"heapsAlgorithm");var E=class r{stat'
HTML += b'ic{f(this,"Matrix")}constructor(e,t){this.m=e,this.n=t,this.'
HTML += b'v=new Array(e*t).fill("0")}getElement(e,t){return e<0||e>=th'
HTML += b'is.m||t<0||t>=this.n?"":this.v[e*this.n+t]}resize(e,t,s){if('
HTML += b'e<1||e>50||t<1||t>50)return!1;let i=new r(e,t);i.v.fill(s);f'
HTML += b'or(let l=0;l<i.m;l++)for(let o=0;o<i.n;o++)i.v[l*i.n+o]=this'
HTML += b'.getElement(l,o);return this.fromMatrix(i),!0}fromMatrix(e){'
HTML += b'this.m=e.m,this.n=e.n,this.v=[...e.v]}fromString(e){this.m=e'
HTML += b'.split("],").length,this.v=e.replaceAll("[","").replaceAll("'
HTML += b']","").split(",").map(t=>t.trim()),this.n=this.v.length/this'
HTML += b'.m}getMaxCellStrlen(){let e=0;for(let t of this.v)t.length>e'
HTML += b'&&(e=t.length);return e}toTeXString(e=!1,t=!0){let s="";t?s+'
HTML += b'=e?"\\\\left[\\\\begin{array}":"\\\\begin{bmatrix}":s+=e?"\\\\left(\\'
HTML += b'\\begin{array}":"\\\\begin{pmatrix}",e&&(s+="{"+"c".repeat(this'
HTML += b'.n-1)+"|c}");for(let i=0;i<this.m;i++){for(let l=0;l<this.n;'
HTML += b'l++){l>0&&(s+="&");let o=this.getElement(i,l);try{o=b.parse('
HTML += b'o).toTexString()}catch{}s+=o}s+="\\\\\\\\"}return t?s+=e?"\\\\end{'
HTML += b'array}\\\\right]":"\\\\end{bmatrix}":s+=e?"\\\\end{array}\\\\right)"'
HTML += b':"\\\\end{pmatrix}",s}},b=class r{static{f(this,"Term")}constr'
HTML += b'uctor(){this.root=null,this.src="",this.token="",this.skippe'
HTML += b'dWhiteSpace=!1,this.pos=0}clone(){let e=new r;return e.root='
HTML += b'this.root.clone(),e}getVars(e,t="",s=null){if(s==null&&(s=th'
HTML += b'is.root),s.op.startsWith("var:")){let i=s.op.substring(4);(t'
HTML += b'.length==0||t.length>0&&i.startsWith(t))&&e.add(i)}for(let i'
HTML += b' of s.c)this.getVars(e,t,i)}setVars(e,t=null){t==null&&(t=th'
HTML += b'is.root);for(let s of t.c)this.setVars(e,s);if(t.op.startsWi'
HTML += b'th("var:")){let s=t.op.substring(4);if(s in e){let i=e[s].cl'
HTML += b'one();t.op=i.op,t.c=i.c,t.re=i.re,t.im=i.im}}}renameVar(e,t,'
HTML += b's=null){s==null&&(s=this.root);for(let i of s.c)this.renameV'
HTML += b'ar(e,t,i);s.op.startsWith("var:")&&s.op.substring(4)===e&&(s'
HTML += b'.op="var:"+t)}eval(e,t=null){let i=a.const(),l=0,o=0,c=null;'
HTML += b'switch(t==null&&(t=this.root),t.op){case"const":i=t;break;ca'
HTML += b'se"+":case"-":case"*":case"/":case"^":{let n=this.eval(e,t.c'
HTML += b'[0]),h=this.eval(e,t.c[1]);switch(t.op){case"+":i.re=n.re+h.'
HTML += b're,i.im=n.im+h.im;break;case"-":i.re=n.re-h.re,i.im=n.im-h.i'
HTML += b'm;break;case"*":i.re=n.re*h.re-n.im*h.im,i.im=n.re*h.im+n.im'
HTML += b'*h.re;break;case"/":l=h.re*h.re+h.im*h.im,i.re=(n.re*h.re+n.'
HTML += b'im*h.im)/l,i.im=(n.im*h.re-n.re*h.im)/l;break;case"^":c=new '
HTML += b'a("exp",[new a("*",[h,new a("ln",[n])])]),i=this.eval(e,c);b'
HTML += b'reak}break}case".-":case"abs":case"acos":case"acosh":case"as'
HTML += b'in":case"asinh":case"atan":case"atanh":case"ceil":case"cos":'
HTML += b'case"cosh":case"cot":case"exp":case"floor":case"ln":case"log'
HTML += b'":case"log10":case"log2":case"round":case"sin":case"sinc":ca'
HTML += b'se"sinh":case"sqrt":case"tan":case"tanh":{let n=this.eval(e,'
HTML += b't.c[0]);switch(t.op){case".-":i.re=-n.re,i.im=-n.im;break;ca'
HTML += b'se"abs":i.re=Math.sqrt(n.re*n.re+n.im*n.im),i.im=0;break;cas'
HTML += b'e"acos":c=new a("*",[a.const(0,-1),new a("ln",[new a("+",[a.'
HTML += b'const(0,1),new a("sqrt",[new a("-",[a.const(1,0),new a("*",['
HTML += b'n,n])])])])])]),i=this.eval(e,c);break;case"acosh":c=new a("'
HTML += b'*",[n,new a("sqrt",[new a("-",[new a("*",[n,n]),a.const(1,0)'
HTML += b'])])]),i=this.eval(e,c);break;case"asin":c=new a("*",[a.cons'
HTML += b't(0,-1),new a("ln",[new a("+",[new a("*",[a.const(0,1),n]),n'
HTML += b'ew a("sqrt",[new a("-",[a.const(1,0),new a("*",[n,n])])])])]'
HTML += b')]),i=this.eval(e,c);break;case"asinh":c=new a("*",[n,new a('
HTML += b'"sqrt",[new a("+",[new a("*",[n,n]),a.const(1,0)])])]),i=thi'
HTML += b's.eval(e,c);break;case"atan":c=new a("*",[a.const(0,.5),new '
HTML += b'a("ln",[new a("/",[new a("-",[a.const(0,1),new a("*",[a.cons'
HTML += b't(0,1),n])]),new a("+",[a.const(0,1),new a("*",[a.const(0,1)'
HTML += b',n])])])])]),i=this.eval(e,c);break;case"atanh":c=new a("*",'
HTML += b'[a.const(.5,0),new a("ln",[new a("/",[new a("+",[a.const(1,0'
HTML += b'),n]),new a("-",[a.const(1,0),n])])])]),i=this.eval(e,c);bre'
HTML += b'ak;case"ceil":i.re=Math.ceil(n.re),i.im=Math.ceil(n.im);brea'
HTML += b'k;case"cos":i.re=Math.cos(n.re)*Math.cosh(n.im),i.im=-Math.s'
HTML += b'in(n.re)*Math.sinh(n.im);break;case"cosh":c=new a("*",[a.con'
HTML += b'st(.5,0),new a("+",[new a("exp",[n]),new a("exp",[new a(".-"'
HTML += b',[n])])])]),i=this.eval(e,c);break;case"cot":l=Math.sin(n.re'
HTML += b')*Math.sin(n.re)+Math.sinh(n.im)*Math.sinh(n.im),i.re=Math.s'
HTML += b'in(n.re)*Math.cos(n.re)/l,i.im=-(Math.sinh(n.im)*Math.cosh(n'
HTML += b'.im))/l;break;case"exp":i.re=Math.exp(n.re)*Math.cos(n.im),i'
HTML += b'.im=Math.exp(n.re)*Math.sin(n.im);break;case"floor":i.re=Mat'
HTML += b'h.floor(n.re),i.im=Math.floor(n.im);break;case"ln":case"log"'
HTML += b':i.re=Math.log(Math.sqrt(n.re*n.re+n.im*n.im)),l=Math.abs(n.'
HTML += b'im)<1e-9?0:n.im,i.im=Math.atan2(l,n.re);break;case"log10":c='
HTML += b'new a("/",[new a("ln",[n]),new a("ln",[a.const(10)])]),i=thi'
HTML += b's.eval(e,c);break;case"log2":c=new a("/",[new a("ln",[n]),ne'
HTML += b'w a("ln",[a.const(2)])]),i=this.eval(e,c);break;case"round":'
HTML += b'i.re=Math.round(n.re),i.im=Math.round(n.im);break;case"sin":'
HTML += b'i.re=Math.sin(n.re)*Math.cosh(n.im),i.im=Math.cos(n.re)*Math'
HTML += b'.sinh(n.im);break;case"sinc":c=new a("/",[new a("sin",[n]),n'
HTML += b']),i=this.eval(e,c);break;case"sinh":c=new a("*",[a.const(.5'
HTML += b',0),new a("-",[new a("exp",[n]),new a("exp",[new a(".-",[n])'
HTML += b'])])]),i=this.eval(e,c);break;case"sqrt":c=new a("^",[n,a.co'
HTML += b'nst(.5)]),i=this.eval(e,c);break;case"tan":l=Math.cos(n.re)*'
HTML += b'Math.cos(n.re)+Math.sinh(n.im)*Math.sinh(n.im),i.re=Math.sin'
HTML += b'(n.re)*Math.cos(n.re)/l,i.im=Math.sinh(n.im)*Math.cosh(n.im)'
HTML += b'/l;break;case"tanh":c=new a("/",[new a("-",[new a("exp",[n])'
HTML += b',new a("exp",[new a(".-",[n])])]),new a("+",[new a("exp",[n]'
HTML += b'),new a("exp",[new a(".-",[n])])])]),i=this.eval(e,c);break}'
HTML += b'break}default:if(t.op.startsWith("var:")){let n=t.op.substri'
HTML += b'ng(4);if(n==="pi")return a.const(Math.PI);if(n==="e")return '
HTML += b'a.const(Math.E);if(n==="i")return a.const(0,1);if(n==="true"'
HTML += b')return a.const(1);if(n==="false")return a.const(0);if(n in '
HTML += b'e)return e[n];throw new Error("eval-error: unknown variable '
HTML += b'\'"+n+"\'")}else throw new Error("UNIMPLEMENTED eval \'"+t.op+"'
HTML += b'\'")}return i}static parse(e){let t=new r;if(t.src=e,t.token='
HTML += b'"",t.skippedWhiteSpace=!1,t.pos=0,t.next(),t.root=t.parseExp'
HTML += b'r(!1),t.token!=="")throw new Error("remaining tokens: "+t.to'
HTML += b'ken+"...");return t}parseExpr(e){return this.parseAdd(e)}par'
HTML += b'seAdd(e){let t=this.parseMul(e);for(;["+","-"].includes(this'
HTML += b'.token)&&!(e&&this.skippedWhiteSpace);){let s=this.token;thi'
HTML += b's.next(),t=new a(s,[t,this.parseMul(e)])}return t}parseMul(e'
HTML += b'){let t=this.parsePow(e);for(;!(e&&this.skippedWhiteSpace);)'
HTML += b'{let s="*";if(["*","/"].includes(this.token))s=this.token,th'
HTML += b'is.next();else if(!e&&this.token==="(")s="*";else if(this.to'
HTML += b'ken.length>0&&(this.isAlpha(this.token[0])||this.isNum(this.'
HTML += b'token[0])))s="*";else break;t=new a(s,[t,this.parsePow(e)])}'
HTML += b'return t}parsePow(e){let t=this.parseUnary(e);for(;["^"].inc'
HTML += b'ludes(this.token)&&!(e&&this.skippedWhiteSpace);){let s=this'
HTML += b'.token;this.next(),t=new a(s,[t,this.parseUnary(e)])}return '
HTML += b't}parseUnary(e){return this.token==="-"?(this.next(),new a("'
HTML += b'.-",[this.parseMul(e)])):this.parseInfix(e)}parseInfix(e){if'
HTML += b'(this.token.length==0)throw new Error("expected unary");if(t'
HTML += b'his.isNum(this.token[0])){let t=this.token;return this.next('
HTML += b'),this.token==="."&&(t+=".",this.next(),this.token.length>0&'
HTML += b'&(t+=this.token,this.next())),new a("const",[],parseFloat(t)'
HTML += b')}else if(this.fun1().length>0){let t=this.fun1();this.next('
HTML += b't.length);let s=null;if(this.token==="(")if(this.next(),s=th'
HTML += b'is.parseExpr(e),this.token+="",this.token===")")this.next();'
HTML += b'else throw Error("expected \')\'");else s=this.parseMul(!0);re'
HTML += b'turn new a(t,[s])}else if(this.token==="("){this.next();let '
HTML += b't=this.parseExpr(e);if(this.token+="",this.token===")")this.'
HTML += b'next();else throw Error("expected \')\'");return t.explicitPar'
HTML += b'entheses=!0,t}else if(this.token==="|"){this.next();let t=th'
HTML += b'is.parseExpr(e);if(this.token+="",this.token==="|")this.next'
HTML += b'();else throw Error("expected \'|\'");return new a("abs",[t])}'
HTML += b'else if(this.isAlpha(this.token[0])){let t="";return this.to'
HTML += b'ken.startsWith("pi")?t="pi":this.token.startsWith("true")?t='
HTML += b'"true":this.token.startsWith("false")?t="false":this.token.s'
HTML += b'tartsWith("C1")?t="C1":this.token.startsWith("C2")?t="C2":t='
HTML += b'this.token[0],t==="I"&&(t="i"),this.next(t.length),new a("va'
HTML += b'r:"+t,[])}else throw new Error("expected unary")}static comp'
HTML += b'are(e,t,s={}){let o=new Set;e.getVars(o),t.getVars(o);for(le'
HTML += b't c=0;c<10;c++){let n={};for(let g of o)g in s?n[g]=s[g]:n[g'
HTML += b']=a.const(Math.random(),Math.random());let h=e.eval(n),p=t.e'
HTML += b'val(n),m=h.re-p.re,d=h.im-p.im;if(Math.sqrt(m*m+d*d)>1e-9)re'
HTML += b'turn!1}return!0}fun1(){let e=["abs","acos","acosh","asin","a'
HTML += b'sinh","atan","atanh","ceil","cos","cosh","cot","exp","floor"'
HTML += b',"ln","log","log10","log2","round","sin","sinc","sinh","sqrt'
HTML += b'","tan","tanh"];for(let t of e)if(this.token.toLowerCase().s'
HTML += b'tartsWith(t))return t;return""}next(e=-1){if(e>0&&this.token'
HTML += b'.length>e){this.token=this.token.substring(e),this.skippedWh'
HTML += b'iteSpace=!1;return}this.token="";let t=!1,s=this.src.length;'
HTML += b'for(this.skippedWhiteSpace=!1;this.pos<s&&`\t\n `.includes(thi'
HTML += b's.src[this.pos]);)this.skippedWhiteSpace=!0,this.pos++;for(;'
HTML += b'!t&&this.pos<s;){let i=this.src[this.pos];if(this.token.leng'
HTML += b'th>0&&(this.isNum(this.token[0])&&this.isAlpha(i)||this.isAl'
HTML += b'pha(this.token[0])&&this.isNum(i))&&this.token!="C")return;i'
HTML += b'f(`^%#*$()[]{},.:;+-*/_!<>=?|\t\n `.includes(i)){if(this.token'
HTML += b'.length>0)return;t=!0}`\t\n `.includes(i)==!1&&(this.token+=i)'
HTML += b',this.pos++}}isNum(e){return e.charCodeAt(0)>=48&&e.charCode'
HTML += b'At(0)<=57}isAlpha(e){return e.charCodeAt(0)>=65&&e.charCodeA'
HTML += b't(0)<=90||e.charCodeAt(0)>=97&&e.charCodeAt(0)<=122||e==="_"'
HTML += b'}toString(){return this.root==null?"":this.root.toString()}t'
HTML += b'oTexString(){return this.root==null?"":this.root.toTexString'
HTML += b'()}},a=class r{static{f(this,"TermNode")}constructor(e,t,s=0'
HTML += b',i=0){this.op=e,this.c=t,this.re=s,this.im=i,this.explicitPa'
HTML += b'rentheses=!1}clone(){let e=new r(this.op,this.c.map(t=>t.clo'
HTML += b'ne()),this.re,this.im);return e.explicitParentheses=this.exp'
HTML += b'licitParentheses,e}static const(e=0,t=0){return new r("const'
HTML += b'",[],e,t)}compare(e,t=0,s=1e-9){let i=this.re-e,l=this.im-t;'
HTML += b'return Math.sqrt(i*i+l*l)<s}toString(){let e="";if(this.op=='
HTML += b'="const"){let t=Math.abs(this.re)>1e-14,s=Math.abs(this.im)>'
HTML += b'1e-14;t&&s&&this.im>=0?e="("+this.re+"+"+this.im+"i)":t&&s&&'
HTML += b'this.im<0?e="("+this.re+"-"+-this.im+"i)":t&&this.re>0?e=""+'
HTML += b'this.re:t&&this.re<0?e="("+this.re+")":s?e="("+this.im+"i)":'
HTML += b'e="0"}else this.op.startsWith("var")?e=this.op.split(":")[1]'
HTML += b':this.c.length==1?e=(this.op===".-"?"-":this.op)+"("+this.c.'
HTML += b'toString()+")":e="("+this.c.map(t=>t.toString()).join(this.o'
HTML += b'p)+")";return e}toTexString(e=!1){let s="";switch(this.op){c'
HTML += b'ase"const":{let i=Math.abs(this.re)>1e-9,l=Math.abs(this.im)'
HTML += b'>1e-9,o=i?""+this.re:"",c=l?""+this.im+"i":"";c==="1i"?c="i"'
HTML += b':c==="-1i"&&(c="-i"),!i&&!l?s="0":(l&&this.im>=0&&i&&(c="+"+'
HTML += b'c),s=o+c);break}case".-":s="-"+this.c[0].toTexString();break'
HTML += b';case"+":case"-":case"*":case"^":{let i=this.c[0].toTexStrin'
HTML += b'g(),l=this.c[1].toTexString(),o=this.op==="*"?"\\\\cdot ":this'
HTML += b'.op;s="{"+i+"}"+o+"{"+l+"}";break}case"/":{let i=this.c[0].t'
HTML += b'oTexString(!0),l=this.c[1].toTexString(!0);s="\\\\frac{"+i+"}{'
HTML += b'"+l+"}";break}case"floor":{let i=this.c[0].toTexString(!0);s'
HTML += b'+="\\\\"+this.op+"\\\\left\\\\lfloor"+i+"\\\\right\\\\rfloor";break}ca'
HTML += b'se"ceil":{let i=this.c[0].toTexString(!0);s+="\\\\"+this.op+"\\'
HTML += b'\\left\\\\lceil"+i+"\\\\right\\\\rceil";break}case"round":{let i=th'
HTML += b'is.c[0].toTexString(!0);s+="\\\\"+this.op+"\\\\left["+i+"\\\\right'
HTML += b']";break}case"acos":case"acosh":case"asin":case"asinh":case"'
HTML += b'atan":case"atanh":case"cos":case"cosh":case"cot":case"exp":c'
HTML += b'ase"ln":case"log":case"log10":case"log2":case"sin":case"sinc'
HTML += b'":case"sinh":case"tan":case"tanh":{let i=this.c[0].toTexStri'
HTML += b'ng(!0);s+="\\\\"+this.op+"\\\\left("+i+"\\\\right)";break}case"sqr'
HTML += b't":{let i=this.c[0].toTexString(!0);s+="\\\\"+this.op+"{"+i+"}'
HTML += b'";break}case"abs":{let i=this.c[0].toTexString(!0);s+="\\\\lef'
HTML += b't|"+i+"\\\\right|";break}default:if(this.op.startsWith("var:")'
HTML += b'){let i=this.op.substring(4);switch(i){case"pi":i="\\\\pi";bre'
HTML += b'ak}s=" "+i+" "}else{let i="warning: Node.toString(..):";i+="'
HTML += b' unimplemented operator \'"+this.op+"\'",console.log(i),s=this'
HTML += b'.op,this.c.length>0&&(s+="\\\\left({"+this.c.map(l=>l.toTexStr'
HTML += b'ing(!0)).join(",")+"}\\\\right)")}}return!e&&this.explicitPare'
HTML += b'ntheses&&(s="\\\\left({"+s+"}\\\\right)"),s}};function ce(r,e){l'
HTML += b'et t=1e-9;if(b.compare(r,e))return!0;r=r.clone(),e=e.clone()'
HTML += b',_(r.root),_(e.root);let s=new Set;r.getVars(s),e.getVars(s)'
HTML += b';let i=[],l=[];for(let n of s.keys())n.startsWith("C")?i.pus'
HTML += b'h(n):l.push(n);let o=i.length;for(let n=0;n<o;n++){let h=i[n'
HTML += b'];r.renameVar(h,"_C"+n),e.renameVar(h,"_C"+n)}for(let n=0;n<'
HTML += b'o;n++)r.renameVar("_C"+n,"C"+n),e.renameVar("_C"+n,"C"+n);i='
HTML += b'[];for(let n=0;n<o;n++)i.push("C"+n);let c=[];N(z(o),c);for('
HTML += b'let n of c){let h=r.clone(),p=e.clone();for(let d=0;d<o;d++)'
HTML += b'p.renameVar("C"+d,"__C"+n[d]);for(let d=0;d<o;d++)p.renameVa'
HTML += b'r("__C"+d,"C"+d);let m=!0;for(let d=0;d<o;d++){let u="C"+d,g'
HTML += b'={};g[u]=new a("*",[new a("var:C"+d,[]),new a("var:K",[])]),'
HTML += b'p.setVars(g);let v={};v[u]=a.const(Math.random(),Math.random'
HTML += b'());for(let y=0;y<o;y++)d!=y&&(v["C"+y]=a.const(0,0));let M='
HTML += b'new a("abs",[new a("-",[h.root,p.root])]),S=new b;S.root=M;f'
HTML += b'or(let y of l)v[y]=a.const(Math.random(),Math.random());let '
HTML += b'C=ve(S,"K",v)[0];p.setVars({K:a.const(C,0)}),v={};for(let y='
HTML += b'0;y<o;y++)d!=y&&(v["C"+y]=a.const(0,0));if(b.compare(h,p,v)='
HTML += b'=!1){m=!1;break}}if(m&&b.compare(h,p))return!0}return!1}f(ce'
HTML += b',"compareODE");function ve(r,e,t){let s=1e-11,i=1e3,l=0,o=0,'
HTML += b'c=1,n=888;for(;l<i;){t[e]=a.const(o);let p=r.eval(t).re;t[e]'
HTML += b'=a.const(o+c);let m=r.eval(t).re;t[e]=a.const(o-c);let d=r.e'
HTML += b'val(t).re,u=0;if(m<p&&(p=m,u=1),d<p&&(p=d,u=-1),u==1&&(o+=c)'
HTML += b',u==-1&&(o-=c),p<s)break;(u==0||u!=n)&&(c/=2),n=u,l++}t[e]=a'
HTML += b'.const(o);let h=r.eval(t).re;return[o,h]}f(ve,"minimize");fu'
HTML += b'nction _(r){for(let e of r.c)_(e);switch(r.op){case"+":case"'
HTML += b'-":case"*":case"/":case"^":{let e=[r.c[0].op,r.c[1].op],t=[e'
HTML += b'[0]==="const",e[1]==="const"],s=[e[0].startsWith("var:C"),e['
HTML += b'1].startsWith("var:C")];s[0]&&t[1]?(r.op=r.c[0].op,r.c=[]):s'
HTML += b'[1]&&t[0]?(r.op=r.c[1].op,r.c=[]):s[0]&&s[1]&&e[0]==e[1]&&(r'
HTML += b'.op=r.c[0].op,r.c=[]);break}case".-":case"abs":case"sin":cas'
HTML += b'e"sinc":case"cos":case"tan":case"cot":case"exp":case"ln":cas'
HTML += b'e"log":case"sqrt":r.c[0].op.startsWith("var:C")&&(r.op=r.c[0'
HTML += b'].op,r.c=[]);break}}f(_,"prepareODEconstantComparison");var '
HTML += b'B=class{static{f(this,"GapInput")}constructor(e,t,s,i){this.'
HTML += b'question=t,this.inputId=s,s.length==0&&(this.inputId=s="gap-'
HTML += b'"+t.gapIdx,t.types[this.inputId]="string",t.expected[this.in'
HTML += b'putId]=i,t.gapIdx++),s in t.student||(t.student[s]="");let l'
HTML += b'=i.split("|"),o=0;for(let p=0;p<l.length;p++){let m=l[p];m.l'
HTML += b'ength>o&&(o=m.length)}let c=k("");e.appendChild(c);let n=Mat'
HTML += b'h.max(o*15,24),h=W(n);if(t.gapInputs[this.inputId]=h,h.addEv'
HTML += b'entListener("keyup",()=>{t.editingEnabled!=!1&&(this.questio'
HTML += b'n.editedQuestion(),h.value=h.value.toUpperCase(),this.questi'
HTML += b'on.student[this.inputId]=h.value.trim())}),c.appendChild(h),'
HTML += b'this.question.showSolution&&(this.question.student[this.inpu'
HTML += b'tId]=h.value=l[0],l.length>1)){let p=k("["+l.join("|")+"]");'
HTML += b'p.style.fontSize="small",p.style.textDecoration="underline",'
HTML += b'c.appendChild(p)}}},I=class{static{f(this,"TermInput")}const'
HTML += b'ructor(e,t,s,i,l,o,c=!1){s in t.student||(t.student[s]=""),t'
HTML += b'his.question=t,this.inputId=s,this.outerSpan=k(""),this.oute'
HTML += b'rSpan.style.position="relative",e.appendChild(this.outerSpan'
HTML += b'),this.inputElement=W(Math.max(i*12,48)),this.outerSpan.appe'
HTML += b'ndChild(this.inputElement),this.equationPreviewDiv=w(),this.'
HTML += b'equationPreviewDiv.classList.add("equationPreview"),this.equ'
HTML += b'ationPreviewDiv.style.display="none",this.outerSpan.appendCh'
HTML += b'ild(this.equationPreviewDiv),this.inputElement.addEventListe'
HTML += b'ner("click",()=>{t.editingEnabled!=!1&&(this.question.edited'
HTML += b'Question(),this.edited())}),this.inputElement.addEventListen'
HTML += b'er("keyup",()=>{t.editingEnabled!=!1&&(this.question.editedQ'
HTML += b'uestion(),this.edited())}),this.inputElement.addEventListene'
HTML += b'r("focus",()=>{t.editingEnabled!=!1}),this.inputElement.addE'
HTML += b'ventListener("focusout",()=>{this.equationPreviewDiv.innerHT'
HTML += b'ML="",this.equationPreviewDiv.style.display="none"}),this.in'
HTML += b'putElement.addEventListener("keydown",n=>{if(t.editingEnable'
HTML += b'd==!1){n.preventDefault();return}let h="abcdefghijklmnopqrst'
HTML += b'uvwxyz";h+="ABCDEFGHIJKLMNOPQRSTUVWXYZ",h+="0123456789",h+="'
HTML += b'+-*/^(). <>=|",o&&(h="-0123456789"),n.key.length<3&&h.includ'
HTML += b'es(n.key)==!1&&n.preventDefault();let p=this.inputElement.va'
HTML += b'lue.length*12;this.inputElement.offsetWidth<p&&(this.inputEl'
HTML += b'ement.style.width=""+p+"px")}),(c||this.question.showSolutio'
HTML += b'n)&&(t.student[s]=this.inputElement.value=l)}edited(){let e='
HTML += b'this.inputElement.value.trim(),t="",s=!1;try{let i=b.parse(e'
HTML += b');s=i.root.op==="const",t=i.toTexString(),this.inputElement.'
HTML += b'style.color="black",this.equationPreviewDiv.style.background'
HTML += b'Color="green"}catch{t=e.replaceAll("^","\\\\hat{~}").replaceAl'
HTML += b'l("_","\\\\_"),this.inputElement.style.color="maroon",this.equ'
HTML += b'ationPreviewDiv.style.backgroundColor="maroon"}Q(this.equati'
HTML += b'onPreviewDiv,t,!0),this.equationPreviewDiv.style.display=e.l'
HTML += b'ength>0&&!s?"block":"none",this.question.student[this.inputI'
HTML += b'd]=e}},H=class{static{f(this,"MatrixInput")}constructor(e,t,'
HTML += b's,i){this.parent=e,this.question=t,this.inputId=s,this.matEx'
HTML += b'pected=new E(0,0),this.matExpected.fromString(i),this.matStu'
HTML += b'dent=new E(this.matExpected.m==1?1:3,this.matExpected.n==1?1'
HTML += b':3),t.showSolution&&this.matStudent.fromMatrix(this.matExpec'
HTML += b'ted),this.genMatrixDom(!0)}genMatrixDom(e){let t=w();this.pa'
HTML += b'rent.innerHTML="",this.parent.appendChild(t),t.style.positio'
HTML += b'n="relative",t.style.display="inline-block";let s=document.c'
HTML += b'reateElement("table");t.appendChild(s);let i=this.matExpecte'
HTML += b'd.getMaxCellStrlen();for(let u=0;u<this.matStudent.m;u++){le'
HTML += b't g=document.createElement("tr");s.appendChild(g),u==0&&g.ap'
HTML += b'pendChild(this.generateMatrixParenthesis(!0,this.matStudent.'
HTML += b'm));for(let v=0;v<this.matStudent.n;v++){let M=u*this.matStu'
HTML += b'dent.n+v,S=document.createElement("td");g.appendChild(S);let'
HTML += b' C=this.inputId+"-"+M;new I(S,this.question,C,i,this.matStud'
HTML += b'ent.v[M],!1,!e)}u==0&&g.appendChild(this.generateMatrixParen'
HTML += b'thesis(!1,this.matStudent.m))}let l=["+","-","+","-"],o=[0,0'
HTML += b',1,-1],c=[1,-1,0,0],n=[0,22,888,888],h=[888,888,-22,-22],p=['
HTML += b'-22,-22,0,22],m=[this.matExpected.n!=1,this.matExpected.n!=1'
HTML += b',this.matExpected.m!=1,this.matExpected.m!=1],d=[this.matStu'
HTML += b'dent.n>=10,this.matStudent.n<=1,this.matStudent.m>=10,this.m'
HTML += b'atStudent.m<=1];for(let u=0;u<4;u++){if(m[u]==!1)continue;le'
HTML += b't g=k(l[u]);n[u]!=888&&(g.style.top=""+n[u]+"px"),h[u]!=888&'
HTML += b'&(g.style.bottom=""+h[u]+"px"),p[u]!=888&&(g.style.right=""+'
HTML += b'p[u]+"px"),g.classList.add("matrixResizeButton"),t.appendChi'
HTML += b'ld(g),d[u]?g.style.opacity="0.5":g.addEventListener("click",'
HTML += b'()=>{for(let v=0;v<this.matStudent.m;v++)for(let M=0;M<this.'
HTML += b'matStudent.n;M++){let S=v*this.matStudent.n+M,C=this.inputId'
HTML += b'+"-"+S,T=this.question.student[C];this.matStudent.v[S]=T,del'
HTML += b'ete this.question.student[C]}this.matStudent.resize(this.mat'
HTML += b'Student.m+o[u],this.matStudent.n+c[u],""),this.genMatrixDom('
HTML += b'!1)})}}generateMatrixParenthesis(e,t){let s=document.createE'
HTML += b'lement("td");s.style.width="3px";for(let i of["Top",e?"Left"'
HTML += b':"Right","Bottom"])s.style["border"+i+"Width"]="2px",s.style'
HTML += b'["border"+i+"Style"]="solid";return this.question.language=='
HTML += b'"de"&&(e?s.style.borderTopLeftRadius="5px":s.style.borderTop'
HTML += b'RightRadius="5px",e?s.style.borderBottomLeftRadius="5px":s.s'
HTML += b'tyle.borderBottomRightRadius="5px"),s.rowSpan=t,s}};var x={i'
HTML += b'nit:0,errors:1,passed:2,incomplete:3},V=class{static{f(this,'
HTML += b'"Question")}constructor(e,t,s,i){this.state=x.init,this.lang'
HTML += b'uage=s,this.src=t,this.debug=i,this.instanceOrder=z(t.instan'
HTML += b'ces.length,!0),this.instanceIdx=0,this.choiceIdx=0,this.incl'
HTML += b'udesSingleChoice=!1,this.gapIdx=0,this.expected={},this.type'
HTML += b's={},this.student={},this.gapInputs={},this.parentDiv=e,this'
HTML += b'.questionDiv=null,this.feedbackPopupDiv=null,this.titleDiv=n'
HTML += b'ull,this.checkAndRepeatBtn=null,this.showSolution=!1,this.fe'
HTML += b'edbackSpan=null,this.numCorrect=0,this.numChecked=0,this.has'
HTML += b'CheckButton=!0,this.editingEnabled=!0}reset(){this.gapIdx=0,'
HTML += b'this.choiceIdx=0,this.instanceIdx=(this.instanceIdx+1)%this.'
HTML += b'src.instances.length}getCurrentInstance(){let e=this.instanc'
HTML += b'eOrder[this.instanceIdx];return this.src.instances[e]}edited'
HTML += b'Question(){this.state=x.init,this.updateVisualQuestionState('
HTML += b'),this.questionDiv.style.color="black",this.checkAndRepeatBt'
HTML += b'n.innerHTML=P,this.checkAndRepeatBtn.style.display="block",t'
HTML += b'his.checkAndRepeatBtn.style.color="black"}updateVisualQuesti'
HTML += b'onState(){let e="black",t="transparent";switch(this.state){c'
HTML += b'ase x.init:e="black";break;case x.passed:e="var(--green)",t='
HTML += b'"rgba(0,150,0, 0.035)";break;case x.incomplete:case x.errors'
HTML += b':e="var(--red)",t="rgba(150,0,0, 0.035)",this.includesSingle'
HTML += b'Choice==!1&&this.numChecked>=5&&(this.feedbackSpan.innerHTML'
HTML += b'="&nbsp;&nbsp;"+this.numCorrect+" / "+this.numChecked);break'
HTML += b'}this.questionDiv.style.backgroundColor=t,this.questionDiv.s'
HTML += b'tyle.borderColor=e}populateDom(e=!1){if(this.parentDiv.inner'
HTML += b'HTML="",this.questionDiv=w(),this.parentDiv.appendChild(this'
HTML += b'.questionDiv),this.questionDiv.classList.add("question"),thi'
HTML += b's.feedbackPopupDiv=w(),this.feedbackPopupDiv.classList.add("'
HTML += b'questionFeedback"),this.questionDiv.appendChild(this.feedbac'
HTML += b'kPopupDiv),this.feedbackPopupDiv.innerHTML="awesome",this.de'
HTML += b'bug&&"src_line"in this.src){let i=w();i.classList.add("debug'
HTML += b'Info"),i.innerHTML="Source code: lines "+this.src.src_line+"'
HTML += b'..",this.questionDiv.appendChild(i)}if(this.titleDiv=w(),thi'
HTML += b's.questionDiv.appendChild(this.titleDiv),this.titleDiv.class'
HTML += b'List.add("questionTitle"),this.titleDiv.innerHTML=this.src.t'
HTML += b'itle,this.src.error.length>0){let i=k(this.src.error);this.q'
HTML += b'uestionDiv.appendChild(i),i.style.color="red";return}let t=t'
HTML += b'his.getCurrentInstance();if(t!=null&&"__svg_image"in t){let '
HTML += b'i=t.__svg_image.v,l=w();this.questionDiv.appendChild(l);let '
HTML += b'o=document.createElement("img");l.appendChild(o),o.classList'
HTML += b'.add("img"),o.src="data:image/svg+xml;base64,"+i}for(let i o'
HTML += b'f this.src.text.c)this.questionDiv.appendChild(this.generate'
HTML += b'Text(i));let s=w();if(s.innerHTML="",s.classList.add("button'
HTML += b'-group"),this.questionDiv.appendChild(s),this.hasCheckButton'
HTML += b'=Object.keys(this.expected).length>0,this.hasCheckButton&&(t'
HTML += b'his.checkAndRepeatBtn=F(),s.appendChild(this.checkAndRepeatB'
HTML += b'tn),this.checkAndRepeatBtn.innerHTML=P,this.checkAndRepeatBt'
HTML += b'n.style.backgroundColor="black",e&&(this.checkAndRepeatBtn.s'
HTML += b'tyle.height="0",this.checkAndRepeatBtn.style.visibility="hid'
HTML += b'den")),this.feedbackSpan=k(""),this.feedbackSpan.style.userS'
HTML += b'elect="none",s.appendChild(this.feedbackSpan),this.debug){if'
HTML += b'(this.src.variables.length>0){let o=w();o.classList.add("deb'
HTML += b'ugInfo"),o.innerHTML="Variables generated by Python Code",th'
HTML += b'is.questionDiv.appendChild(o);let c=w();c.classList.add("deb'
HTML += b'ugCode"),this.questionDiv.appendChild(c);let n=this.getCurre'
HTML += b'ntInstance(),h="",p=[...this.src.variables];p.sort();for(let'
HTML += b' m of p){let d=n[m].t,u=n[m].v;switch(d){case"vector":u="["+'
HTML += b'u+"]";break;case"set":u="{"+u+"}";break}h+=d+" "+m+" = "+u+"'
HTML += b'<br/>"}c.innerHTML=h}let i=["python_src_html","text_src_html'
HTML += b'"],l=["Python Source Code","Text Source Code"];for(let o=0;o'
HTML += b'<i.length;o++){let c=i[o];if(c in this.src&&this.src[c].leng'
HTML += b'th>0){let n=w();n.classList.add("debugInfo"),n.innerHTML=l[o'
HTML += b'],this.questionDiv.appendChild(n);let h=w();h.classList.add('
HTML += b'"debugCode"),this.questionDiv.append(h),h.innerHTML=this.src'
HTML += b'[c]}}}this.hasCheckButton&&this.checkAndRepeatBtn.addEventLi'
HTML += b'stener("click",()=>{this.state==x.passed?(this.state=x.init,'
HTML += b'this.editingEnabled=!0,this.reset(),this.populateDom()):R(th'
HTML += b'is)})}generateMathString(e){let t="";switch(e.t){case"math":'
HTML += b'case"display-math":for(let s of e.c){let i=this.generateMath'
HTML += b'String(s);s.t==="var"&&t.includes("!PM")&&(i.startsWith("{-"'
HTML += b')?(i="{"+i.substring(2),t=t.replaceAll("!PM","-")):t=t.repla'
HTML += b'ceAll("!PM","+")),t+=i}break;case"text":return e.d;case"plus'
HTML += b'_minus":{t+=" !PM ";break}case"var":{let s=this.getCurrentIn'
HTML += b'stance(),i=s[e.d].t,l=s[e.d].v;switch(i){case"vector":return'
HTML += b'"\\\\left["+l+"\\\\right]";case"set":return"\\\\left\\\\{"+l+"\\\\righ'
HTML += b't\\\\}";case"complex":{let o=l.split(","),c=parseFloat(o[0]),n'
HTML += b'=parseFloat(o[1]);return a.const(c,n).toTexString()}case"mat'
HTML += b'rix":{let o=new E(0,0);return o.fromString(l),t=o.toTeXStrin'
HTML += b'g(e.d.includes("augmented"),this.language!="de"),t}case"term'
HTML += b'":{try{t=b.parse(l).toTexString()}catch{}break}default:t=l}}'
HTML += b'}return e.t==="plus_minus"?t:"{"+t+"}"}generateText(e,t=!1){'
HTML += b'switch(e.t){case"paragraph":case"span":{let s=document.creat'
HTML += b'eElement(e.t=="span"||t?"span":"p");for(let i of e.c)s.appen'
HTML += b'dChild(this.generateText(i));return s.style.userSelect="none'
HTML += b'",s}case"text":return k(e.d);case"code":{let s=k(e.d);return'
HTML += b' s.classList.add("code"),s}case"italic":case"bold":{let s=k('
HTML += b'"");return s.append(...e.c.map(i=>this.generateText(i))),e.t'
HTML += b'==="bold"?s.style.fontWeight="bold":s.style.fontStyle="itali'
HTML += b'c",s}case"math":case"display-math":{let s=this.generateMathS'
HTML += b'tring(e);return L(s,e.t==="display-math")}case"string_var":{'
HTML += b'let s=k(""),i=this.getCurrentInstance(),l=i[e.d].t,o=i[e.d].'
HTML += b'v;return l==="string"?s.innerHTML=o:(s.innerHTML="EXPECTED V'
HTML += b'ARIABLE OF TYPE STRING",s.style.color="red"),s}case"gap":{le'
HTML += b't s=k("");return new B(s,this,"",e.d),s}case"input":case"inp'
HTML += b'ut2":{let s=e.t==="input2",i=k("");i.style.verticalAlign="te'
HTML += b'xt-bottom";let l=e.d,o=this.getCurrentInstance()[l];if(this.'
HTML += b'expected[l]=o.v,this.types[l]=o.t,!s)switch(o.t){case"set":i'
HTML += b'.append(L("\\\\{"),k(" "));break;case"vector":i.append(L("["),'
HTML += b'k(" "));break}if(o.t==="string")new B(i,this,l,this.expected'
HTML += b'[l]);else if(o.t==="vector"||o.t==="set"){let c=o.v.split(",'
HTML += b'"),n=c.length;for(let h=0;h<n;h++){h>0&&i.appendChild(k(" , '
HTML += b'"));let p=l+"-"+h;new I(i,this,p,c[h].length,c[h],!1)}}else '
HTML += b'if(o.t==="matrix"){let c=w();i.appendChild(c),new H(c,this,l'
HTML += b',o.v)}else if(o.t==="complex"){let c=o.v.split(",");new I(i,'
HTML += b'this,l+"-0",c[0].length,c[0],!1),i.append(k(" "),L("+"),k(" '
HTML += b'")),new I(i,this,l+"-1",c[1].length,c[1],!1),i.append(k(" ")'
HTML += b',L("i"))}else{let c=o.t==="int";new I(i,this,l,o.v.length,o.'
HTML += b'v,c)}if(!s)switch(o.t){case"set":i.append(k(" "),L("\\\\}"));b'
HTML += b'reak;case"vector":i.append(k(" "),L("]"));break}return i}cas'
HTML += b'e"itemize":return j(e.c.map(s=>O(this.generateText(s))));cas'
HTML += b'e"single-choice":case"multi-choice":{let s=e.t=="multi-choic'
HTML += b'e";s||(this.includesSingleChoice=!0);let i=document.createEl'
HTML += b'ement("table"),l=e.c.length,o=this.debug==!1,c=z(l,o),n=s?X:'
HTML += b'G,h=s?Z:Y,p=[],m=[];for(let d=0;d<l;d++){let u=c[d],g=e.c[u]'
HTML += b',v="mc-"+this.choiceIdx+"-"+u;m.push(v);let M=g.c[0].t=="boo'
HTML += b'l"?g.c[0].d:this.getCurrentInstance()[g.c[0].d].v;this.expec'
HTML += b'ted[v]=M,this.types[v]="bool",this.student[v]=this.showSolut'
HTML += b'ion?M:"false";let S=this.generateText(g.c[1],!0),C=document.'
HTML += b'createElement("tr");i.appendChild(C),C.style.cursor="pointer'
HTML += b'";let T=document.createElement("td");p.push(T),C.appendChild'
HTML += b'(T),T.innerHTML=this.student[v]=="true"?n:h;let y=document.c'
HTML += b'reateElement("td");C.appendChild(y),y.appendChild(S),s?C.add'
HTML += b'EventListener("click",()=>{this.editingEnabled!=!1&&(this.ed'
HTML += b'itedQuestion(),this.student[v]=this.student[v]==="true"?"fal'
HTML += b'se":"true",this.student[v]==="true"?T.innerHTML=n:T.innerHTM'
HTML += b'L=h)}):C.addEventListener("click",()=>{if(this.editingEnable'
HTML += b'd!=!1){this.editedQuestion();for(let D of m)this.student[D]='
HTML += b'"false";this.student[v]="true";for(let D=0;D<m.length;D++){l'
HTML += b'et U=c[D];p[U].innerHTML=this.student[m[U]]=="true"?n:h}}})}'
HTML += b'return this.choiceIdx++,i}case"image":{let s=w(),l=e.d.split'
HTML += b'("."),o=l[l.length-1],c=e.c[0].d,n=e.c[1].d,h=document.creat'
HTML += b'eElement("img");s.appendChild(h),h.classList.add("img"),h.st'
HTML += b'yle.width=c+"%";let p={svg:"svg+xml",png:"png",jpg:"jpeg"};r'
HTML += b'eturn h.src="data:image/"+p[o]+";base64,"+n,s}default:{let s'
HTML += b'=k("UNIMPLEMENTED("+e.t+")");return s.style.color="red",s}}}'
HTML += b'};function R(r){r.feedbackSpan.innerHTML="",r.numChecked=0,r'
HTML += b'.numCorrect=0;let e=!0;for(let i in r.expected){let l=r.type'
HTML += b's[i],o=r.student[i],c=r.expected[i];switch(o!=null&&o.length'
HTML += b'==0&&(e=!1),l){case"bool":r.numChecked++,o.toLowerCase()===c'
HTML += b'.toLowerCase()&&r.numCorrect++;break;case"string":{r.numChec'
HTML += b'ked++;let n=r.gapInputs[i],h=o.trim().toUpperCase(),p=c.trim'
HTML += b'().toUpperCase().split("|"),m=!1;for(let d of p)if(K(h,d)<=1'
HTML += b'){m=!0,r.numCorrect++,r.gapInputs[i].value=d,r.student[i]=d;'
HTML += b'break}n.style.color=m?"black":"white",n.style.backgroundColo'
HTML += b'r=m?"transparent":"maroon";break}case"int":r.numChecked++,Ma'
HTML += b'th.abs(parseFloat(o)-parseFloat(c))<1e-9&&r.numCorrect++;bre'
HTML += b'ak;case"float":case"term":{r.numChecked++;try{let n=b.parse('
HTML += b'c),h=b.parse(o),p=!1;r.src.is_ode?p=ce(n,h):p=b.compare(n,h)'
HTML += b',p&&r.numCorrect++}catch(n){r.debug&&(console.log("term inva'
HTML += b'lid"),console.log(n))}break}case"vector":case"complex":case"'
HTML += b'set":{let n=c.split(",");r.numChecked+=n.length;let h=[];for'
HTML += b'(let p=0;p<n.length;p++){let m=r.student[i+"-"+p];m.length=='
HTML += b'0&&(e=!1),h.push(m)}if(l==="set")for(let p=0;p<n.length;p++)'
HTML += b'try{let m=b.parse(n[p]);for(let d=0;d<h.length;d++){let u=b.'
HTML += b'parse(h[d]);if(b.compare(m,u)){r.numCorrect++;break}}}catch('
HTML += b'm){r.debug&&console.log(m)}else for(let p=0;p<n.length;p++)t'
HTML += b'ry{let m=b.parse(h[p]),d=b.parse(n[p]);b.compare(m,d)&&r.num'
HTML += b'Correct++}catch(m){r.debug&&console.log(m)}break}case"matrix'
HTML += b'":{let n=new E(0,0);n.fromString(c),r.numChecked+=n.m*n.n;fo'
HTML += b'r(let h=0;h<n.m;h++)for(let p=0;p<n.n;p++){let m=h*n.n+p;o=r'
HTML += b'.student[i+"-"+m],o!=null&&o.length==0&&(e=!1);let d=n.v[m];'
HTML += b'try{let u=b.parse(d),g=b.parse(o);b.compare(u,g)&&r.numCorre'
HTML += b'ct++}catch(u){r.debug&&console.log(u)}}break}default:r.feedb'
HTML += b'ackSpan.innerHTML="UNIMPLEMENTED EVAL OF TYPE "+l}}e==!1?r.s'
HTML += b'tate=x.incomplete:r.state=r.numCorrect==r.numChecked?x.passe'
HTML += b'd:x.errors,r.updateVisualQuestionState();let t=[];switch(r.s'
HTML += b'tate){case x.passed:t=ie[r.language];break;case x.incomplete'
HTML += b':t=se[r.language];break;case x.errors:t=ne[r.language];break'
HTML += b'}let s=t[Math.floor(Math.random()*t.length)];r.feedbackPopup'
HTML += b'Div.innerHTML=s,r.feedbackPopupDiv.style.color=r.state===x.p'
HTML += b'assed?"var(--green)":"var(--red)",r.feedbackPopupDiv.style.d'
HTML += b'isplay="flex",setTimeout(()=>{r.feedbackPopupDiv.style.displ'
HTML += b'ay="none"},1e3),r.editingEnabled=!0,r.state===x.passed?(r.ed'
HTML += b'itingEnabled=!1,r.src.instances.length>1?r.checkAndRepeatBtn'
HTML += b'.innerHTML=J:r.checkAndRepeatBtn.style.visibility="hidden"):'
HTML += b'r.checkAndRepeatBtn!=null&&(r.checkAndRepeatBtn.innerHTML=P)'
HTML += b'}f(R,"evalQuestion");function be(r,e){new q(r,e)}f(be,"init"'
HTML += b');var q=class{static{f(this,"Quiz")}constructor(e,t){this.qu'
HTML += b'izSrc=e,["en","de","es","it","fr"].includes(this.quizSrc.lan'
HTML += b'g)==!1&&(this.quizSrc.lang="en"),this.debug=t,this.debug&&(d'
HTML += b'ocument.getElementById("debug").style.display="block"),this.'
HTML += b'questions=[],this.timeLeft=e.timer,this.timeLimited=e.timer>'
HTML += b'0,this.fillPageMetadata(),this.timeLimited?(document.getElem'
HTML += b'entById("timer-info").style.display="block",document.getElem'
HTML += b'entById("timer-info-text").innerHTML=oe[this.quizSrc.lang],d'
HTML += b'ocument.getElementById("start-btn").addEventListener("click"'
HTML += b',()=>{document.getElementById("timer-info").style.display="n'
HTML += b'one",this.generateQuestions(),this.runTimer()})):this.genera'
HTML += b'teQuestions()}fillPageMetadata(){document.getElementById("da'
HTML += b'te").innerHTML=this.quizSrc.date,document.getElementById("ti'
HTML += b'tle").innerHTML=this.quizSrc.title,document.getElementById("'
HTML += b'author").innerHTML=this.quizSrc.author,document.getElementBy'
HTML += b'Id("courseInfo1").innerHTML=$[this.quizSrc.lang];let e=\'<spa'
HTML += b'n onclick="location.reload()" style="text-decoration: none; '
HTML += b'font-weight: bold; cursor: pointer">\'+te[this.quizSrc.lang]+'
HTML += b'"</span>";document.getElementById("courseInfo2").innerHTML=e'
HTML += b'e[this.quizSrc.lang].replace("*",e),document.getElementById('
HTML += b'"data-policy").innerHTML=le[this.quizSrc.lang]}generateQuest'
HTML += b'ions(){let e=document.getElementById("questions"),t=1;for(le'
HTML += b't s of this.quizSrc.questions){s.title=""+t+". "+s.title;let'
HTML += b' i=w();e.appendChild(i);let l=new V(i,s,this.quizSrc.lang,th'
HTML += b'is.debug);l.showSolution=this.debug,this.questions.push(l),l'
HTML += b'.populateDom(this.timeLimited),this.debug&&s.error.length==0'
HTML += b'&&l.hasCheckButton&&l.checkAndRepeatBtn.click(),t++}}runTime'
HTML += b'r(){document.getElementById("stop-now").style.display="block'
HTML += b'",document.getElementById("stop-now-btn").innerHTML=ae[this.'
HTML += b'quizSrc.lang],document.getElementById("stop-now-btn").addEve'
HTML += b'ntListener("click",()=>{this.timeLeft=1});let e=document.get'
HTML += b'ElementById("timer");e.style.display="block",e.innerHTML=he('
HTML += b'this.timeLeft);let t=setInterval(()=>{this.timeLeft--,e.inne'
HTML += b'rHTML=he(this.timeLeft),this.timeLeft<=0&&this.stopTimer(t)}'
HTML += b',1e3)}stopTimer(e){document.getElementById("stop-now").style'
HTML += b'.display="none",clearInterval(e);let t=0,s=0;for(let l of th'
HTML += b'is.questions){let o=l.src.points;s+=o,R(l),l.state===x.passe'
HTML += b'd&&(t+=o),l.editingEnabled=!1}document.getElementById("quest'
HTML += b'ions-eval").style.display="block";let i=document.getElementB'
HTML += b'yId("questions-eval-percentage");i.innerHTML=s==0?"":""+t+" '
HTML += b'/ "+s+" "+re[this.quizSrc.lang]+" <br/><br/>"+Math.round(t/s'
HTML += b'*100)+" %"}};function he(r){let e=Math.floor(r/60),t=r%60;re'
HTML += b'turn e+":"+(""+t).padStart(2,"0")}f(he,"formatTime");return '
HTML += b'ge(ke);})();pysell.init(quizSrc,debug);</script></body> </ht'
HTML += b'ml> '
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
