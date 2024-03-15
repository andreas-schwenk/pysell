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

    # pylint: disable-next=too-many-branches
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
HTML += b'ct.defineProperty;var re=Object.getOwnPropertyDescriptor;var'
HTML += b' ne=Object.getOwnPropertyNames;var ae=Object.prototype.hasOw'
HTML += b'nProperty;var le=(r,e)=>{for(var t in e)B(r,t,{get:e[t],enum'
HTML += b'erable:!0})},oe=(r,e,t,i)=>{if(e&&typeof e=="object"||typeof'
HTML += b' e=="function")for(let s of ne(e))!ae.call(r,s)&&s!==t&&B(r,'
HTML += b's,{get:()=>e[s],enumerable:!(i=re(e,s))||i.enumerable});retu'
HTML += b'rn r};var he=r=>oe(B({},"__esModule",{value:!0}),r);var de={'
HTML += b'};le(de,{init:()=>pe});function b(r=[]){let e=document.creat'
HTML += b'eElement("div");return e.append(...r),e}function z(r=[]){let'
HTML += b' e=document.createElement("ul");return e.append(...r),e}func'
HTML += b'tion U(r){let e=document.createElement("li");return e.append'
HTML += b'Child(r),e}function R(r){let e=document.createElement("input'
HTML += b'");return e.spellcheck=!1,e.type="text",e.classList.add("inp'
HTML += b'utField"),e.style.width=r+"px",e}function j(){let r=document'
HTML += b'.createElement("button");return r.type="button",r.classList.'
HTML += b'add("button"),r}function v(r,e=[]){let t=document.createElem'
HTML += b'ent("span");return e.length>0?t.append(...e):t.innerHTML=r,t'
HTML += b'}function W(r,e,t=!1){katex.render(e,r,{throwOnError:!1,disp'
HTML += b'layMode:t,macros:{"\\\\RR":"\\\\mathbb{R}","\\\\NN":"\\\\mathbb{N}",'
HTML += b'"\\\\QQ":"\\\\mathbb{Q}","\\\\ZZ":"\\\\mathbb{Z}","\\\\CC":"\\\\mathbb{C'
HTML += b'}"}})}function T(r,e=!1){let t=document.createElement("span"'
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
HTML += b'care",fr:"recharger"},X={en:["awesome","great","well done","'
HTML += b'nice","you got it","good"],de:["super","gut gemacht","weiter'
HTML += b' so","richtig"],es:["impresionante","genial","correcto","bie'
HTML += b'n hecho"],it:["fantastico","grande","corretto","ben fatto"],'
HTML += b'fr:["g\\xE9nial","super","correct","bien fait"]},Z={en:["fill'
HTML += b' all fields"],de:["bitte alles ausf\\xFCllen"],es:["por favor'
HTML += b', rellene todo"],it:["compilare tutto"],fr:["remplis tout s\''
HTML += b'il te plait"]},q={en:["try again","still some mistakes","wro'
HTML += b'ng answer","no"],de:["leider falsch","nicht richtig","versuc'
HTML += b'h\'s nochmal"],es:["int\\xE9ntalo de nuevo","todav\\xEDa alguno'
HTML += b's errores","respuesta incorrecta"],it:["riprova","ancora qua'
HTML += b'lche errore","risposta sbagliata"],fr:["r\\xE9essayer","encor'
HTML += b'e des erreurs","mauvaise r\\xE9ponse"]};function Y(r,e){let t'
HTML += b'=Array(e.length+1).fill(null).map(()=>Array(r.length+1).fill'
HTML += b'(null));for(let i=0;i<=r.length;i+=1)t[0][i]=i;for(let i=0;i'
HTML += b'<=e.length;i+=1)t[i][0]=i;for(let i=1;i<=e.length;i+=1)for(l'
HTML += b'et s=1;s<=r.length;s+=1){let a=r[s-1]===e[i-1]?0:1;t[i][s]=M'
HTML += b'ath.min(t[i][s-1]+1,t[i-1][s]+1,t[i-1][s-1]+a)}return t[e.le'
HTML += b'ngth][r.length]}var G=\'<svg xmlns="http://www.w3.org/2000/sv'
HTML += b'g" height="28" viewBox="0 0 448 512"><path d="M384 80c8.8 0 '
HTML += b'16 7.2 16 16V416c0 8.8-7.2 16-16 16H64c-8.8 0-16-7.2-16-16V9'
HTML += b'6c0-8.8 7.2-16 16-16H384zM64 32C28.7 32 0 60.7 0 96V416c0 35'
HTML += b'.3 28.7 64 64 64H384c35.3 0 64-28.7 64-64V96c0-35.3-28.7-64-'
HTML += b'64-64H64z"/></svg>\',J=\'<svg xmlns="http://www.w3.org/2000/sv'
HTML += b'g" height="28" viewBox="0 0 448 512"><path d="M64 80c-8.8 0-'
HTML += b'16 7.2-16 16V416c0 8.8 7.2 16 16 16H384c8.8 0 16-7.2 16-16V9'
HTML += b'6c0-8.8-7.2-16-16-16H64zM0 96C0 60.7 28.7 32 64 32H384c35.3 '
HTML += b'0 64 28.7 64 64V416c0 35.3-28.7 64-64 64H64c-35.3 0-64-28.7-'
HTML += b'64-64V96zM337 209L209 337c-9.4 9.4-24.6 9.4-33.9 0l-64-64c-9'
HTML += b'.4-9.4-9.4-24.6 0-33.9s24.6-9.4 33.9 0l47 47L303 175c9.4-9.4'
HTML += b' 24.6-9.4 33.9 0s9.4 24.6 0 33.9z"/>\',$=\'<svg xmlns="http://'
HTML += b'www.w3.org/2000/svg" height="28" viewBox="0 0 512 512"><path'
HTML += b' d="M464 256A208 208 0 1 0 48 256a208 208 0 1 0 416 0zM0 256'
HTML += b'a256 256 0 1 1 512 0A256 256 0 1 1 0 256z"/></svg>\',ee=\'<svg'
HTML += b' xmlns="http://www.w3.org/2000/svg" height="28" viewBox="0 0'
HTML += b' 512 512"><path d="M256 48a208 208 0 1 1 0 416 208 208 0 1 1'
HTML += b' 0-416zm0 464A256 256 0 1 0 256 0a256 256 0 1 0 0 512zM369 2'
HTML += b'09c9.4-9.4 9.4-24.6 0-33.9s-24.6-9.4-33.9 0l-111 111-47-47c-'
HTML += b'9.4-9.4-24.6-9.4-33.9 0s-9.4 24.6 0 33.9l64 64c9.4 9.4 24.6 '
HTML += b'9.4 33.9 0L369 209z"/></svg>\',I=\'<svg xmlns="http://www.w3.o'
HTML += b'rg/2000/svg" height="25" viewBox="0 0 384 512" fill="white">'
HTML += b'<path d="M73 39c-14.8-9.1-33.4-9.4-48.5-.9S0 62.6 0 80V432c0'
HTML += b' 17.4 9.4 33.4 24.5 41.9s33.7 8.1 48.5-.9L361 297c14.3-8.7 2'
HTML += b'3-24.2 23-41s-8.7-32.2-23-41L73 39z"/></svg>\',te=\'<svg xmlns'
HTML += b'="http://www.w3.org/2000/svg" height="25" viewBox="0 0 512 5'
HTML += b'12" fill="white"><path d="M0 224c0 17.7 14.3 32 32 32s32-14.'
HTML += b'3 32-32c0-53 43-96 96-96H320v32c0 12.9 7.8 24.6 19.8 29.6s25'
HTML += b'.7 2.2 34.9-6.9l64-64c12.5-12.5 12.5-32.8 0-45.3l-64-64c-9.2'
HTML += b'-9.2-22.9-11.9-34.9-6.9S320 19.1 320 32V64H160C71.6 64 0 135'
HTML += b'.6 0 224zm512 64c0-17.7-14.3-32-32-32s-32 14.3-32 32c0 53-43'
HTML += b' 96-96 96H192V352c0-12.9-7.8-24.6-19.8-29.6s-25.7-2.2-34.9 6'
HTML += b'.9l-64 64c-12.5 12.5-12.5 32.8 0 45.3l64 64c9.2 9.2 22.9 11.'
HTML += b'9 34.9 6.9s19.8-16.6 19.8-29.6V448H352c88.4 0 160-71.6 160-1'
HTML += b'60z"/></svg>\';function P(r,e=!1){let t=new Array(r);for(let '
HTML += b'i=0;i<r;i++)t[i]=i;if(e)for(let i=0;i<r;i++){let s=Math.floo'
HTML += b'r(Math.random()*r),a=Math.floor(Math.random()*r),l=t[s];t[s]'
HTML += b'=t[a],t[a]=l}return t}function _(r,e,t=-1){if(t<0&&(t=r.leng'
HTML += b'th),t==1){e.push([...r]);return}for(let i=0;i<t;i++){_(r,e,t'
HTML += b'-1);let s=t%2==0?i:0,a=r[s];r[s]=r[t-1],r[t-1]=a}}var E=clas'
HTML += b's r{constructor(e,t){this.m=e,this.n=t,this.v=new Array(e*t)'
HTML += b'.fill("0")}getElement(e,t){return e<0||e>=this.m||t<0||t>=th'
HTML += b'is.n?"":this.v[e*this.n+t]}resize(e,t,i){if(e<1||e>50||t<1||'
HTML += b't>50)return!1;let s=new r(e,t);s.v.fill(i);for(let a=0;a<s.m'
HTML += b';a++)for(let l=0;l<s.n;l++)s.v[a*s.n+l]=this.getElement(a,l)'
HTML += b';return this.fromMatrix(s),!0}fromMatrix(e){this.m=e.m,this.'
HTML += b'n=e.n,this.v=[...e.v]}fromString(e){this.m=e.split("],").len'
HTML += b'gth,this.v=e.replaceAll("[","").replaceAll("]","").split(","'
HTML += b').map(t=>t.trim()),this.n=this.v.length/this.m}getMaxCellStr'
HTML += b'len(){let e=0;for(let t of this.v)t.length>e&&(e=t.length);r'
HTML += b'eturn e}toTeXString(e=!1,t=!0){let i="";t?i+=e?"\\\\left[\\\\beg'
HTML += b'in{array}":"\\\\begin{bmatrix}":i+=e?"\\\\left(\\\\begin{array}":"'
HTML += b'\\\\begin{pmatrix}",e&&(i+="{"+"c".repeat(this.n-1)+"|c}");for'
HTML += b'(let s=0;s<this.m;s++){for(let a=0;a<this.n;a++){a>0&&(i+="&'
HTML += b'");let l=this.getElement(s,a);try{l=k.parse(l).toTexString()'
HTML += b'}catch{}i+=l}i+="\\\\\\\\"}return t?i+=e?"\\\\end{array}\\\\right]":'
HTML += b'"\\\\end{bmatrix}":i+=e?"\\\\end{array}\\\\right)":"\\\\end{pmatrix}'
HTML += b'",i}},k=class r{constructor(){this.root=null,this.src="",thi'
HTML += b's.token="",this.skippedWhiteSpace=!1,this.pos=0}clone(){let '
HTML += b'e=new r;return e.root=this.root.clone(),e}getVars(e,t="",i=n'
HTML += b'ull){if(i==null&&(i=this.root),i.op.startsWith("var:")){let '
HTML += b's=i.op.substring(4);(t.length==0||t.length>0&&s.startsWith(t'
HTML += b'))&&e.add(s)}for(let s of i.c)this.getVars(e,t,s)}setVars(e,'
HTML += b't=null){t==null&&(t=this.root);for(let i of t.c)this.setVars'
HTML += b'(e,i);if(t.op.startsWith("var:")){let i=t.op.substring(4);if'
HTML += b'(i in e){let s=e[i].clone();t.op=s.op,t.c=s.c,t.re=s.re,t.im'
HTML += b'=s.im}}}renameVar(e,t,i=null){i==null&&(i=this.root);for(let'
HTML += b' s of i.c)this.renameVar(e,t,s);i.op.startsWith("var:")&&i.o'
HTML += b'p.substring(4)===e&&(i.op="var:"+t)}eval(e,t=null){let s=m.c'
HTML += b'onst(),a=0,l=0,h=null;switch(t==null&&(t=this.root),t.op){ca'
HTML += b'se"const":s=t;break;case"+":case"-":case"*":case"/":case"^":'
HTML += b'{let n=this.eval(e,t.c[0]),o=this.eval(e,t.c[1]);switch(t.op'
HTML += b'){case"+":s.re=n.re+o.re,s.im=n.im+o.im;break;case"-":s.re=n'
HTML += b'.re-o.re,s.im=n.im-o.im;break;case"*":s.re=n.re*o.re-n.im*o.'
HTML += b'im,s.im=n.re*o.im+n.im*o.re;break;case"/":a=o.re*o.re+o.im*o'
HTML += b'.im,s.re=(n.re*o.re+n.im*o.im)/a,s.im=(n.im*o.re-n.re*o.im)/'
HTML += b'a;break;case"^":h=new m("exp",[new m("*",[o,new m("ln",[n])]'
HTML += b')]),s=this.eval(e,h);break}break}case".-":case"abs":case"sin'
HTML += b'":case"sinc":case"cos":case"tan":case"cot":case"exp":case"ln'
HTML += b'":case"log":case"sqrt":{let n=this.eval(e,t.c[0]);switch(t.o'
HTML += b'p){case".-":s.re=-n.re,s.im=-n.im;break;case"abs":s.re=Math.'
HTML += b'sqrt(n.re*n.re+n.im*n.im),s.im=0;break;case"sin":s.re=Math.s'
HTML += b'in(n.re)*Math.cosh(n.im),s.im=Math.cos(n.re)*Math.sinh(n.im)'
HTML += b';break;case"sinc":h=new m("/",[new m("sin",[n]),n]),s=this.e'
HTML += b'val(e,h);break;case"cos":s.re=Math.cos(n.re)*Math.cosh(n.im)'
HTML += b',s.im=-Math.sin(n.re)*Math.sinh(n.im);break;case"tan":a=Math'
HTML += b'.cos(n.re)*Math.cos(n.re)+Math.sinh(n.im)*Math.sinh(n.im),s.'
HTML += b're=Math.sin(n.re)*Math.cos(n.re)/a,s.im=Math.sinh(n.im)*Math'
HTML += b'.cosh(n.im)/a;break;case"cot":a=Math.sin(n.re)*Math.sin(n.re'
HTML += b')+Math.sinh(n.im)*Math.sinh(n.im),s.re=Math.sin(n.re)*Math.c'
HTML += b'os(n.re)/a,s.im=-(Math.sinh(n.im)*Math.cosh(n.im))/a;break;c'
HTML += b'ase"exp":s.re=Math.exp(n.re)*Math.cos(n.im),s.im=Math.exp(n.'
HTML += b're)*Math.sin(n.im);break;case"ln":case"log":s.re=Math.log(Ma'
HTML += b'th.sqrt(n.re*n.re+n.im*n.im)),a=Math.abs(n.im)<1e-9?0:n.im,s'
HTML += b'.im=Math.atan2(a,n.re);break;case"sqrt":h=new m("^",[n,m.con'
HTML += b'st(.5)]),s=this.eval(e,h);break}break}default:if(t.op.starts'
HTML += b'With("var:")){let n=t.op.substring(4);if(n==="pi")return m.c'
HTML += b'onst(Math.PI);if(n==="e")return m.const(Math.E);if(n==="i")r'
HTML += b'eturn m.const(0,1);if(n in e)return e[n];throw new Error("ev'
HTML += b'al-error: unknown variable \'"+n+"\'")}else throw new Error("U'
HTML += b'NIMPLEMENTED eval \'"+t.op+"\'")}return s}static parse(e){let '
HTML += b't=new r;if(t.src=e,t.token="",t.skippedWhiteSpace=!1,t.pos=0'
HTML += b',t.next(),t.root=t.parseExpr(!1),t.token!=="")throw new Erro'
HTML += b'r("remaining tokens: "+t.token+"...");return t}parseExpr(e){'
HTML += b'return this.parseAdd(e)}parseAdd(e){let t=this.parseMul(e);f'
HTML += b'or(;["+","-"].includes(this.token)&&!(e&&this.skippedWhiteSp'
HTML += b'ace);){let i=this.token;this.next(),t=new m(i,[t,this.parseM'
HTML += b'ul(e)])}return t}parseMul(e){let t=this.parsePow(e);for(;!(e'
HTML += b'&&this.skippedWhiteSpace);){let i="*";if(["*","/"].includes('
HTML += b'this.token))i=this.token,this.next();else if(!e&&this.token='
HTML += b'=="(")i="*";else if(this.token.length>0&&(this.isAlpha(this.'
HTML += b'token[0])||this.isNum(this.token[0])))i="*";else break;t=new'
HTML += b' m(i,[t,this.parsePow(e)])}return t}parsePow(e){let t=this.p'
HTML += b'arseUnary(e);for(;["^"].includes(this.token)&&!(e&&this.skip'
HTML += b'pedWhiteSpace);){let i=this.token;this.next(),t=new m(i,[t,t'
HTML += b'his.parseUnary(e)])}return t}parseUnary(e){return this.token'
HTML += b'==="-"?(this.next(),new m(".-",[this.parseMul(e)])):this.par'
HTML += b'seInfix(e)}parseInfix(e){if(this.token.length==0)throw new E'
HTML += b'rror("expected unary");if(this.isNum(this.token[0])){let t=t'
HTML += b'his.token;return this.next(),this.token==="."&&(t+=".",this.'
HTML += b'next(),this.token.length>0&&(t+=this.token,this.next())),new'
HTML += b' m("const",[],parseFloat(t))}else if(this.fun1().length>0){l'
HTML += b'et t=this.fun1();this.next(t.length);let i=null;if(this.toke'
HTML += b'n==="(")if(this.next(),i=this.parseExpr(e),this.token+="",th'
HTML += b'is.token===")")this.next();else throw Error("expected \')\'");'
HTML += b'else i=this.parseMul(!0);return new m(t,[i])}else if(this.to'
HTML += b'ken==="("){this.next();let t=this.parseExpr(e);if(this.token'
HTML += b'+="",this.token===")")this.next();else throw Error("expected'
HTML += b' \')\'");return t.explicitParentheses=!0,t}else if(this.token='
HTML += b'=="|"){this.next();let t=this.parseExpr(e);if(this.token+=""'
HTML += b',this.token==="|")this.next();else throw Error("expected \'|\''
HTML += b'");return new m("abs",[t])}else if(this.isAlpha(this.token[0'
HTML += b'])){let t="";return this.token.startsWith("pi")?t="pi":this.'
HTML += b'token.startsWith("C1")?t="C1":this.token.startsWith("C2")?t='
HTML += b'"C2":t=this.token[0],t==="I"&&(t="i"),this.next(t.length),ne'
HTML += b'w m("var:"+t,[])}else throw new Error("expected unary")}stat'
HTML += b'ic compare(e,t,i={}){let l=new Set;e.getVars(l),t.getVars(l)'
HTML += b';for(let h=0;h<10;h++){let n={};for(let f of l)f in i?n[f]=i'
HTML += b'[f]:n[f]=m.const(Math.random(),Math.random());let o=e.eval(n'
HTML += b'),c=t.eval(n),u=o.re-c.re,p=o.im-c.im;if(Math.sqrt(u*u+p*p)>'
HTML += b'1e-9)return!1}return!0}fun1(){let e=["abs","sinc","sin","cos'
HTML += b'","tan","cot","exp","ln","sqrt"];for(let t of e)if(this.toke'
HTML += b'n.toLowerCase().startsWith(t))return t;return""}next(e=-1){i'
HTML += b'f(e>0&&this.token.length>e){this.token=this.token.substring('
HTML += b'e),this.skippedWhiteSpace=!1;return}this.token="";let t=!1,i'
HTML += b'=this.src.length;for(this.skippedWhiteSpace=!1;this.pos<i&&`'
HTML += b'\t\n `.includes(this.src[this.pos]);)this.skippedWhiteSpace=!0'
HTML += b',this.pos++;for(;!t&&this.pos<i;){let s=this.src[this.pos];i'
HTML += b'f(this.token.length>0&&(this.isNum(this.token[0])&&this.isAl'
HTML += b'pha(s)||this.isAlpha(this.token[0])&&this.isNum(s))&&this.to'
HTML += b'ken!="C")return;if(`^%#*$()[]{},.:;+-*/_!<>=?|\t\n `.includes('
HTML += b's)){if(this.token.length>0)return;t=!0}`\t\n `.includes(s)==!1'
HTML += b'&&(this.token+=s),this.pos++}}isNum(e){return e.charCodeAt(0'
HTML += b')>=48&&e.charCodeAt(0)<=57}isAlpha(e){return e.charCodeAt(0)'
HTML += b'>=65&&e.charCodeAt(0)<=90||e.charCodeAt(0)>=97&&e.charCodeAt'
HTML += b'(0)<=122||e==="_"}toString(){return this.root==null?"":this.'
HTML += b'root.toString()}toTexString(){return this.root==null?"":this'
HTML += b'.root.toTexString()}},m=class r{constructor(e,t,i=0,s=0){thi'
HTML += b's.op=e,this.c=t,this.re=i,this.im=s,this.explicitParentheses'
HTML += b'=!1}clone(){let e=new r(this.op,this.c.map(t=>t.clone()),thi'
HTML += b's.re,this.im);return e.explicitParentheses=this.explicitPare'
HTML += b'ntheses,e}static const(e=0,t=0){return new r("const",[],e,t)'
HTML += b'}compare(e,t=0,i=1e-9){let s=this.re-e,a=this.im-t;return Ma'
HTML += b'th.sqrt(s*s+a*a)<i}toString(){let e="";if(this.op==="const")'
HTML += b'{let t=Math.abs(this.re)>1e-14,i=Math.abs(this.im)>1e-14;t&&'
HTML += b'i&&this.im>=0?e="("+this.re+"+"+this.im+"i)":t&&i&&this.im<0'
HTML += b'?e="("+this.re+"-"+-this.im+"i)":t&&this.re>0?e=""+this.re:t'
HTML += b'&&this.re<0?e="("+this.re+")":i?e="("+this.im+"i)":e="0"}els'
HTML += b'e this.op.startsWith("var")?e=this.op.split(":")[1]:this.c.l'
HTML += b'ength==1?e=(this.op===".-"?"-":this.op)+"("+this.c.toString('
HTML += b')+")":e="("+this.c.map(t=>t.toString()).join(this.op)+")";re'
HTML += b'turn e}toTexString(e=!1){let i="";switch(this.op){case"const'
HTML += b'":{let s=Math.abs(this.re)>1e-9,a=Math.abs(this.im)>1e-9,l=s'
HTML += b'?""+this.re:"",h=a?""+this.im+"i":"";h==="1i"?h="i":h==="-1i'
HTML += b'"&&(h="-i"),!s&&!a?i="0":(a&&this.im>=0&&s&&(h="+"+h),i=l+h)'
HTML += b';break}case".-":i="-"+this.c[0].toTexString();break;case"+":'
HTML += b'case"-":case"*":case"^":{let s=this.c[0].toTexString(),a=thi'
HTML += b's.c[1].toTexString(),l=this.op==="*"?"\\\\cdot ":this.op;i="{"'
HTML += b'+s+"}"+l+"{"+a+"}";break}case"/":{let s=this.c[0].toTexStrin'
HTML += b'g(!0),a=this.c[1].toTexString(!0);i="\\\\frac{"+s+"}{"+a+"}";b'
HTML += b'reak}case"sin":case"sinc":case"cos":case"tan":case"cot":case'
HTML += b'"exp":case"ln":{let s=this.c[0].toTexString(!0);i+="\\\\"+this'
HTML += b'.op+"\\\\left("+s+"\\\\right)";break}case"sqrt":{let s=this.c[0]'
HTML += b'.toTexString(!0);i+="\\\\"+this.op+"{"+s+"}";break}case"abs":{'
HTML += b'let s=this.c[0].toTexString(!0);i+="\\\\left|"+s+"\\\\right|";br'
HTML += b'eak}default:if(this.op.startsWith("var:")){let s=this.op.sub'
HTML += b'string(4);switch(s){case"pi":s="\\\\pi";break}i=" "+s+" "}else'
HTML += b'{let s="warning: Node.toString(..):";s+=" unimplemented oper'
HTML += b'ator \'"+this.op+"\'",console.log(s),i=this.op,this.c.length>0'
HTML += b'&&(i+="\\\\left({"+this.c.map(a=>a.toTexString(!0)).join(",")+'
HTML += b'"}\\\\right)")}}return!e&&this.explicitParentheses&&(i="\\\\left'
HTML += b'({"+i+"}\\\\right)"),i}};function ie(r,e){let t=1e-9;if(k.comp'
HTML += b'are(r,e))return!0;r=r.clone(),e=e.clone(),N(r.root),N(e.root'
HTML += b');let i=new Set;r.getVars(i),e.getVars(i);let s=[],a=[];for('
HTML += b'let n of i.keys())n.startsWith("C")?s.push(n):a.push(n);let '
HTML += b'l=s.length;for(let n=0;n<l;n++){let o=s[n];r.renameVar(o,"_C'
HTML += b'"+n),e.renameVar(o,"_C"+n)}for(let n=0;n<l;n++)r.renameVar("'
HTML += b'_C"+n,"C"+n),e.renameVar("_C"+n,"C"+n);s=[];for(let n=0;n<l;'
HTML += b'n++)s.push("C"+n);let h=[];_(P(l),h);for(let n of h){let o=r'
HTML += b'.clone(),c=e.clone();for(let p=0;p<l;p++)c.renameVar("C"+p,"'
HTML += b'__C"+n[p]);for(let p=0;p<l;p++)c.renameVar("__C"+p,"C"+p);le'
HTML += b't u=!0;for(let p=0;p<l;p++){let d="C"+p,f={};f[d]=new m("*",'
HTML += b'[new m("var:C"+p,[]),new m("var:K",[])]),c.setVars(f);let g='
HTML += b'{};g[d]=m.const(Math.random(),Math.random());for(let w=0;w<l'
HTML += b';w++)p!=w&&(g["C"+w]=m.const(0,0));let M=new m("abs",[new m('
HTML += b'"-",[o.root,c.root])]),y=new k;y.root=M;for(let w of a)g[w]='
HTML += b'm.const(Math.random(),Math.random());let C=ce(y,"K",g)[0];c.'
HTML += b'setVars({K:m.const(C,0)}),g={};for(let w=0;w<l;w++)p!=w&&(g['
HTML += b'"C"+w]=m.const(0,0));if(k.compare(o,c,g)==!1){u=!1;break}}if'
HTML += b'(u&&k.compare(o,c))return!0}return!1}function ce(r,e,t){let '
HTML += b'i=1e-11,s=1e3,a=0,l=0,h=1,n=888;for(;a<s;){t[e]=m.const(l);l'
HTML += b'et c=r.eval(t).re;t[e]=m.const(l+h);let u=r.eval(t).re;t[e]='
HTML += b'm.const(l-h);let p=r.eval(t).re,d=0;if(u<c&&(c=u,d=1),p<c&&('
HTML += b'c=p,d=-1),d==1&&(l+=h),d==-1&&(l-=h),c<i)break;(d==0||d!=n)&'
HTML += b'&(h/=2),n=d,a++}t[e]=m.const(l);let o=r.eval(t).re;return[l,'
HTML += b'o]}function N(r){for(let e of r.c)N(e);switch(r.op){case"+":'
HTML += b'case"-":case"*":case"/":case"^":{let e=[r.c[0].op,r.c[1].op]'
HTML += b',t=[e[0]==="const",e[1]==="const"],i=[e[0].startsWith("var:C'
HTML += b'"),e[1].startsWith("var:C")];i[0]&&t[1]?(r.op=r.c[0].op,r.c='
HTML += b'[]):i[1]&&t[0]?(r.op=r.c[1].op,r.c=[]):i[0]&&i[1]&&e[0]==e[1'
HTML += b']&&(r.op=r.c[0].op,r.c=[]);break}case".-":case"abs":case"sin'
HTML += b'":case"sinc":case"cos":case"tan":case"cot":case"exp":case"ln'
HTML += b'":case"log":case"sqrt":r.c[0].op.startsWith("var:C")&&(r.op='
HTML += b'r.c[0].op,r.c=[]);break}}function se(r){r.feedbackSpan.inner'
HTML += b'HTML="",r.numChecked=0,r.numCorrect=0;let e=!0;for(let s in '
HTML += b'r.expected){let a=r.types[s],l=r.student[s],h=r.expected[s];'
HTML += b'switch(l!=null&&l.length==0&&(e=!1),a){case"bool":r.numCheck'
HTML += b'ed++,l===h&&r.numCorrect++;break;case"string":{r.numChecked+'
HTML += b'+;let n=r.gapInputs[s],o=l.trim().toUpperCase(),c=h.trim().t'
HTML += b'oUpperCase().split("|"),u=!1;for(let p of c)if(Y(o,p)<=1){u='
HTML += b'!0,r.numCorrect++,r.gapInputs[s].value=p,r.student[s]=p;brea'
HTML += b'k}n.style.color=u?"black":"white",n.style.backgroundColor=u?'
HTML += b'"transparent":"maroon";break}case"int":r.numChecked++,Math.a'
HTML += b'bs(parseFloat(l)-parseFloat(h))<1e-9&&r.numCorrect++;break;c'
HTML += b'ase"float":case"term":{r.numChecked++;try{let n=k.parse(h),o'
HTML += b'=k.parse(l),c=!1;r.src.is_ode?c=ie(n,o):c=k.compare(n,o),c&&'
HTML += b'r.numCorrect++}catch(n){r.debug&&(console.log("term invalid"'
HTML += b'),console.log(n))}break}case"vector":case"complex":case"set"'
HTML += b':{let n=h.split(",");r.numChecked+=n.length;let o=[];for(let'
HTML += b' c=0;c<n.length;c++){let u=r.student[s+"-"+c];u.length==0&&('
HTML += b'e=!1),o.push(u)}if(a==="set")for(let c=0;c<n.length;c++)try{'
HTML += b'let u=k.parse(n[c]);for(let p=0;p<o.length;p++){let d=k.pars'
HTML += b'e(o[p]);if(k.compare(u,d)){r.numCorrect++;break}}}catch(u){r'
HTML += b'.debug&&console.log(u)}else for(let c=0;c<n.length;c++)try{l'
HTML += b'et u=k.parse(o[c]),p=k.parse(n[c]);k.compare(u,p)&&r.numCorr'
HTML += b'ect++}catch(u){r.debug&&console.log(u)}break}case"matrix":{l'
HTML += b'et n=new E(0,0);n.fromString(h),r.numChecked+=n.m*n.n;for(le'
HTML += b't o=0;o<n.m;o++)for(let c=0;c<n.n;c++){let u=o*n.n+c;l=r.stu'
HTML += b'dent[s+"-"+u],l!=null&&l.length==0&&(e=!1);let p=n.v[u];try{'
HTML += b'let d=k.parse(p),f=k.parse(l);k.compare(d,f)&&r.numCorrect++'
HTML += b'}catch(d){r.debug&&console.log(d)}}break}default:r.feedbackS'
HTML += b'pan.innerHTML="UNIMPLEMENTED EVAL OF TYPE "+a}}e==!1?r.state'
HTML += b'=x.incomplete:r.state=r.numCorrect==r.numChecked?x.passed:x.'
HTML += b'errors,r.updateVisualQuestionState();let t=[];switch(r.state'
HTML += b'){case x.passed:t=X[r.language];break;case x.incomplete:t=Z['
HTML += b'r.language];break;case x.errors:t=q[r.language];break}let i='
HTML += b't[Math.floor(Math.random()*t.length)];r.feedbackPopupDiv.inn'
HTML += b'erHTML=i,r.feedbackPopupDiv.style.color=r.state===x.passed?"'
HTML += b'green":"maroon",r.feedbackPopupDiv.style.display="block",set'
HTML += b'Timeout(()=>{r.feedbackPopupDiv.style.display="none"},500),r'
HTML += b'.state===x.passed?r.src.instances.length>0?r.checkAndRepeatB'
HTML += b'tn.innerHTML=te:r.checkAndRepeatBtn.style.display="none":r.c'
HTML += b'heckAndRepeatBtn.innerHTML=I}var A=class{constructor(e,t,i,s'
HTML += b'){this.question=t,this.inputId=i,i.length==0&&(this.inputId='
HTML += b'i="gap-"+t.gapIdx,t.types[this.inputId]="string",t.expected['
HTML += b'this.inputId]=s,t.gapIdx++),i in t.student||(t.student[i]=""'
HTML += b');let a=s.split("|"),l=0;for(let c=0;c<a.length;c++){let u=a'
HTML += b'[c];u.length>l&&(l=u.length)}let h=v("");e.appendChild(h);le'
HTML += b't n=Math.max(l*15,24),o=R(n);if(t.gapInputs[this.inputId]=o,'
HTML += b'o.addEventListener("keyup",()=>{this.question.editedQuestion'
HTML += b'(),o.value=o.value.toUpperCase(),this.question.student[this.'
HTML += b'inputId]=o.value.trim()}),h.appendChild(o),this.question.sho'
HTML += b'wSolution&&(this.question.student[this.inputId]=o.value=a[0]'
HTML += b',a.length>1)){let c=v("["+a.join("|")+"]");c.style.fontSize='
HTML += b'"small",c.style.textDecoration="underline",h.appendChild(c)}'
HTML += b'}},D=class{constructor(e,t,i,s,a,l,h=!1){i in t.student||(t.'
HTML += b'student[i]=""),this.question=t,this.inputId=i,this.outerSpan'
HTML += b'=v(""),this.outerSpan.style.position="relative",e.appendChil'
HTML += b'd(this.outerSpan),this.inputElement=R(Math.max(s*12,48)),thi'
HTML += b's.outerSpan.appendChild(this.inputElement),this.equationPrev'
HTML += b'iewDiv=b(),this.equationPreviewDiv.classList.add("equationPr'
HTML += b'eview"),this.equationPreviewDiv.style.display="none",this.ou'
HTML += b'terSpan.appendChild(this.equationPreviewDiv),this.inputEleme'
HTML += b'nt.addEventListener("click",()=>{this.question.editedQuestio'
HTML += b'n(),this.edited()}),this.inputElement.addEventListener("keyu'
HTML += b'p",()=>{this.question.editedQuestion(),this.edited()}),this.'
HTML += b'inputElement.addEventListener("focusout",()=>{this.equationP'
HTML += b'reviewDiv.innerHTML="",this.equationPreviewDiv.style.display'
HTML += b'="none"}),this.inputElement.addEventListener("keydown",n=>{l'
HTML += b'et o="abcdefghijklmnopqrstuvwxyz";o+="ABCDEFGHIJKLMNOPQRSTUV'
HTML += b'WXYZ",o+="0123456789",o+="+-*/^(). <>=|",l&&(o="-0123456789"'
HTML += b'),n.key.length<3&&o.includes(n.key)==!1&&n.preventDefault();'
HTML += b'let c=this.inputElement.value.length*12;this.inputElement.of'
HTML += b'fsetWidth<c&&(this.inputElement.style.width=""+c+"px")}),(h|'
HTML += b'|this.question.showSolution)&&(t.student[i]=this.inputElemen'
HTML += b't.value=a)}edited(){let e=this.inputElement.value.trim(),t="'
HTML += b'",i=!1;try{let s=k.parse(e);i=s.root.op==="const",t=s.toTexS'
HTML += b'tring(),this.inputElement.style.color="black",this.equationP'
HTML += b'reviewDiv.style.backgroundColor="green"}catch{t=e.replaceAll'
HTML += b'("^","\\\\hat{~}").replaceAll("_","\\\\_"),this.inputElement.sty'
HTML += b'le.color="maroon",this.equationPreviewDiv.style.backgroundCo'
HTML += b'lor="maroon"}W(this.equationPreviewDiv,t,!0),this.equationPr'
HTML += b'eviewDiv.style.display=e.length>0&&!i?"block":"none",this.qu'
HTML += b'estion.student[this.inputId]=e}},V=class{constructor(e,t,i,s'
HTML += b'){this.parent=e,this.question=t,this.inputId=i,this.matExpec'
HTML += b'ted=new E(0,0),this.matExpected.fromString(s),this.matStuden'
HTML += b't=new E(this.matExpected.m==1?1:3,this.matExpected.n==1?1:3)'
HTML += b',t.showSolution&&this.matStudent.fromMatrix(this.matExpected'
HTML += b'),this.genMatrixDom(!0)}genMatrixDom(e){let t=b();this.paren'
HTML += b't.innerHTML="",this.parent.appendChild(t),t.style.position="'
HTML += b'relative",t.style.display="inline-block";let i=document.crea'
HTML += b'teElement("table");t.appendChild(i);let s=this.matExpected.g'
HTML += b'etMaxCellStrlen();for(let d=0;d<this.matStudent.m;d++){let f'
HTML += b'=document.createElement("tr");i.appendChild(f),d==0&&f.appen'
HTML += b'dChild(this.generateMatrixParenthesis(!0,this.matStudent.m))'
HTML += b';for(let g=0;g<this.matStudent.n;g++){let M=d*this.matStuden'
HTML += b't.n+g,y=document.createElement("td");f.appendChild(y);let C='
HTML += b'this.inputId+"-"+M;new D(y,this.question,C,s,this.matStudent'
HTML += b'.v[M],!1,!e)}d==0&&f.appendChild(this.generateMatrixParenthe'
HTML += b'sis(!1,this.matStudent.m))}let a=["+","-","+","-"],l=[0,0,1,'
HTML += b'-1],h=[1,-1,0,0],n=[0,22,888,888],o=[888,888,-22,-22],c=[-22'
HTML += b',-22,0,22],u=[this.matExpected.n!=1,this.matExpected.n!=1,th'
HTML += b'is.matExpected.m!=1,this.matExpected.m!=1],p=[this.matStuden'
HTML += b't.n>=10,this.matStudent.n<=1,this.matStudent.m>=10,this.matS'
HTML += b'tudent.m<=1];for(let d=0;d<4;d++){if(u[d]==!1)continue;let f'
HTML += b'=v(a[d]);n[d]!=888&&(f.style.top=""+n[d]+"px"),o[d]!=888&&(f'
HTML += b'.style.bottom=""+o[d]+"px"),c[d]!=888&&(f.style.right=""+c[d'
HTML += b']+"px"),f.classList.add("matrixResizeButton"),t.appendChild('
HTML += b'f),p[d]?f.style.opacity="0.5":f.addEventListener("click",()='
HTML += b'>{for(let g=0;g<this.matStudent.m;g++)for(let M=0;M<this.mat'
HTML += b'Student.n;M++){let y=g*this.matStudent.n+M,C=this.inputId+"-'
HTML += b'"+y,S=this.question.student[C];this.matStudent.v[y]=S,delete'
HTML += b' this.question.student[C]}this.matStudent.resize(this.matStu'
HTML += b'dent.m+l[d],this.matStudent.n+h[d],""),this.genMatrixDom(!1)'
HTML += b'})}}generateMatrixParenthesis(e,t){let i=document.createElem'
HTML += b'ent("td");i.style.width="3px";for(let s of["Top",e?"Left":"R'
HTML += b'ight","Bottom"])i.style["border"+s+"Width"]="2px",i.style["b'
HTML += b'order"+s+"Style"]="solid";return this.question.language=="de'
HTML += b'"&&(e?i.style.borderTopLeftRadius="5px":i.style.borderTopRig'
HTML += b'htRadius="5px",e?i.style.borderBottomLeftRadius="5px":i.styl'
HTML += b'e.borderBottomRightRadius="5px"),i.rowSpan=t,i}};var x={init'
HTML += b':0,errors:1,passed:2,incomplete:3},H=class{constructor(e,t,i'
HTML += b',s){this.state=x.init,this.language=i,this.src=t,this.debug='
HTML += b's,this.instanceOrder=P(t.instances.length,!0),this.instanceI'
HTML += b'dx=0,this.choiceIdx=0,this.gapIdx=0,this.expected={},this.ty'
HTML += b'pes={},this.student={},this.gapInputs={},this.parentDiv=e,th'
HTML += b'is.questionDiv=null,this.feedbackPopupDiv=null,this.titleDiv'
HTML += b'=null,this.checkAndRepeatBtn=null,this.showSolution=!1,this.'
HTML += b'feedbackSpan=null,this.numCorrect=0,this.numChecked=0}reset('
HTML += b'){this.instanceIdx=(this.instanceIdx+1)%this.src.instances.l'
HTML += b'ength}getCurrentInstance(){let e=this.instanceOrder[this.ins'
HTML += b'tanceIdx];return this.src.instances[e]}editedQuestion(){this'
HTML += b'.state=x.init,this.updateVisualQuestionState(),this.question'
HTML += b'Div.style.color="black",this.checkAndRepeatBtn.innerHTML=I,t'
HTML += b'his.checkAndRepeatBtn.style.display="block",this.checkAndRep'
HTML += b'eatBtn.style.color="black"}updateVisualQuestionState(){let e'
HTML += b'="black",t="transparent";switch(this.state){case x.init:case'
HTML += b' x.incomplete:e="rgb(0,0,0)",t="transparent";break;case x.pa'
HTML += b'ssed:e="rgb(0,150,0)",t="rgba(0,150,0, 0.025)";break;case x.'
HTML += b'errors:e="rgb(150,0,0)",t="rgba(150,0,0, 0.025)",this.numChe'
HTML += b'cked>=5&&(this.feedbackSpan.innerHTML=""+this.numCorrect+" /'
HTML += b' "+this.numChecked);break}this.questionDiv.style.color=this.'
HTML += b'feedbackSpan.style.color=this.titleDiv.style.color=this.chec'
HTML += b'kAndRepeatBtn.style.backgroundColor=this.questionDiv.style.b'
HTML += b'orderColor=e,this.questionDiv.style.backgroundColor=t}popula'
HTML += b'teDom(){if(this.parentDiv.innerHTML="",this.questionDiv=b(),'
HTML += b'this.parentDiv.appendChild(this.questionDiv),this.questionDi'
HTML += b'v.classList.add("question"),this.feedbackPopupDiv=b(),this.f'
HTML += b'eedbackPopupDiv.classList.add("questionFeedback"),this.quest'
HTML += b'ionDiv.appendChild(this.feedbackPopupDiv),this.feedbackPopup'
HTML += b'Div.innerHTML="awesome",this.debug&&"src_line"in this.src){l'
HTML += b'et a=b();a.classList.add("debugInfo"),a.innerHTML="Source co'
HTML += b'de: lines "+this.src.src_line+"..",this.questionDiv.appendCh'
HTML += b'ild(a)}if(this.titleDiv=b(),this.questionDiv.appendChild(thi'
HTML += b's.titleDiv),this.titleDiv.classList.add("questionTitle"),thi'
HTML += b's.titleDiv.innerHTML=this.src.title,this.src.error.length>0)'
HTML += b'{let a=v(this.src.error);this.questionDiv.appendChild(a),a.s'
HTML += b'tyle.color="red";return}let e=this.getCurrentInstance();if(e'
HTML += b'!=null&&"__svg_image"in e){let a=e.__svg_image.v,l=b();this.'
HTML += b'questionDiv.appendChild(l);let h=document.createElement("img'
HTML += b'");l.appendChild(h),h.classList.add("img"),h.src="data:image'
HTML += b'/svg+xml;base64,"+a}for(let a of this.src.text.c)this.questi'
HTML += b'onDiv.appendChild(this.generateText(a));let t=b();this.quest'
HTML += b'ionDiv.appendChild(t),t.classList.add("buttonRow");let i=Obj'
HTML += b'ect.keys(this.expected).length>0;i&&(this.checkAndRepeatBtn='
HTML += b'j(),t.appendChild(this.checkAndRepeatBtn),this.checkAndRepea'
HTML += b'tBtn.innerHTML=I,this.checkAndRepeatBtn.style.backgroundColo'
HTML += b'r="black");let s=v("&nbsp;&nbsp;&nbsp;");if(t.appendChild(s)'
HTML += b',this.feedbackSpan=v(""),t.appendChild(this.feedbackSpan),th'
HTML += b'is.debug){if(this.src.variables.length>0){let h=b();h.classL'
HTML += b'ist.add("debugInfo"),h.innerHTML="Variables generated by Pyt'
HTML += b'hon Code",this.questionDiv.appendChild(h);let n=b();n.classL'
HTML += b'ist.add("debugCode"),this.questionDiv.appendChild(n);let o=t'
HTML += b'his.getCurrentInstance(),c="",u=[...this.src.variables];u.so'
HTML += b'rt();for(let p of u){let d=o[p].t,f=o[p].v;switch(d){case"ve'
HTML += b'ctor":f="["+f+"]";break;case"set":f="{"+f+"}";break}c+=d+" "'
HTML += b'+p+" = "+f+"<br/>"}n.innerHTML=c}let a=["python_src_html","t'
HTML += b'ext_src_html"],l=["Python Source Code","Text Source Code"];f'
HTML += b'or(let h=0;h<a.length;h++){let n=a[h];if(n in this.src&&this'
HTML += b'.src[n].length>0){let o=b();o.classList.add("debugInfo"),o.i'
HTML += b'nnerHTML=l[h],this.questionDiv.appendChild(o);let c=b();c.cl'
HTML += b'assList.add("debugCode"),this.questionDiv.append(c),c.innerH'
HTML += b'TML=this.src[n]}}}i&&this.checkAndRepeatBtn.addEventListener'
HTML += b'("click",()=>{this.state==x.passed?(this.state=x.init,this.r'
HTML += b'eset(),this.populateDom()):se(this)})}generateMathString(e){'
HTML += b'let t="";switch(e.t){case"math":case"display-math":for(let i'
HTML += b' of e.c){let s=this.generateMathString(i);i.t==="var"&&t.inc'
HTML += b'ludes("!PM")&&(s.startsWith("{-")?(s="{"+s.substring(2),t=t.'
HTML += b'replaceAll("!PM","-")):t=t.replaceAll("!PM","+")),t+=s}break'
HTML += b';case"text":return e.d;case"plus_minus":{t+=" !PM ";break}ca'
HTML += b'se"var":{let i=this.getCurrentInstance(),s=i[e.d].t,a=i[e.d]'
HTML += b'.v;switch(s){case"vector":return"\\\\left["+a+"\\\\right]";case"'
HTML += b'set":return"\\\\left\\\\{"+a+"\\\\right\\\\}";case"complex":{let l=a'
HTML += b'.split(","),h=parseFloat(l[0]),n=parseFloat(l[1]);return m.c'
HTML += b'onst(h,n).toTexString()}case"matrix":{let l=new E(0,0);retur'
HTML += b'n l.fromString(a),t=l.toTeXString(e.d.includes("augmented"),'
HTML += b'this.language!="de"),t}case"term":{try{t=k.parse(a).toTexStr'
HTML += b'ing()}catch{}break}default:t=a}}}return e.t==="plus_minus"?t'
HTML += b':"{"+t+"}"}generateText(e,t=!1){switch(e.t){case"paragraph":'
HTML += b'case"span":{let i=document.createElement(e.t=="span"||t?"spa'
HTML += b'n":"p");for(let s of e.c)i.appendChild(this.generateText(s))'
HTML += b';return i}case"text":return v(e.d);case"code":{let i=v(e.d);'
HTML += b'return i.classList.add("code"),i}case"italic":case"bold":{le'
HTML += b't i=v("");return i.append(...e.c.map(s=>this.generateText(s)'
HTML += b')),e.t==="bold"?i.style.fontWeight="bold":i.style.fontStyle='
HTML += b'"italic",i}case"math":case"display-math":{let i=this.generat'
HTML += b'eMathString(e);return T(i,e.t==="display-math")}case"string_'
HTML += b'var":{let i=v(""),s=this.getCurrentInstance(),a=s[e.d].t,l=s'
HTML += b'[e.d].v;return a==="string"?i.innerHTML=l:(i.innerHTML="EXPE'
HTML += b'CTED VARIABLE OF TYPE STRING",i.style.color="red"),i}case"ga'
HTML += b'p":{let i=v("");return new A(i,this,"",e.d),i}case"input":ca'
HTML += b'se"input2":{let i=e.t==="input2",s=v("");s.style.verticalAli'
HTML += b'gn="text-bottom";let a=e.d,l=this.getCurrentInstance()[a];if'
HTML += b'(this.expected[a]=l.v,this.types[a]=l.t,!i)switch(l.t){case"'
HTML += b'set":s.append(T("\\\\{"),v(" "));break;case"vector":s.append(T'
HTML += b'("["),v(" "));break}if(l.t==="string")new A(s,this,a,this.ex'
HTML += b'pected[a]);else if(l.t==="vector"||l.t==="set"){let h=l.v.sp'
HTML += b'lit(","),n=h.length;for(let o=0;o<n;o++){o>0&&s.appendChild('
HTML += b'v(" , "));let c=a+"-"+o;new D(s,this,c,h[o].length,h[o],!1)}'
HTML += b'}else if(l.t==="matrix"){let h=b();s.appendChild(h),new V(h,'
HTML += b'this,a,l.v)}else if(l.t==="complex"){let h=l.v.split(",");ne'
HTML += b'w D(s,this,a+"-0",h[0].length,h[0],!1),s.append(v(" "),T("+"'
HTML += b'),v(" ")),new D(s,this,a+"-1",h[1].length,h[1],!1),s.append('
HTML += b'v(" "),T("i"))}else{let h=l.t==="int";new D(s,this,a,l.v.len'
HTML += b'gth,l.v,h)}if(!i)switch(l.t){case"set":s.append(v(" "),T("\\\\'
HTML += b'}"));break;case"vector":s.append(v(" "),T("]"));break}return'
HTML += b' s}case"itemize":return z(e.c.map(i=>U(this.generateText(i))'
HTML += b'));case"single-choice":case"multi-choice":{let i=e.t=="multi'
HTML += b'-choice",s=document.createElement("table"),a=e.c.length,l=th'
HTML += b'is.debug==!1,h=P(a,l),n=i?J:ee,o=i?G:$,c=[],u=[];for(let p=0'
HTML += b';p<a;p++){let d=h[p],f=e.c[d],g="mc-"+this.choiceIdx+"-"+d;u'
HTML += b'.push(g);let M=f.c[0].t=="bool"?f.c[0].d:this.getCurrentInst'
HTML += b'ance()[f.c[0].d].v;this.expected[g]=M,this.types[g]="bool",t'
HTML += b'his.student[g]=this.showSolution?M:"false";let y=this.genera'
HTML += b'teText(f.c[1],!0),C=document.createElement("tr");s.appendChi'
HTML += b'ld(C),C.style.cursor="pointer";let S=document.createElement('
HTML += b'"td");c.push(S),C.appendChild(S),S.innerHTML=this.student[g]'
HTML += b'=="true"?n:o;let w=document.createElement("td");C.appendChil'
HTML += b'd(w),w.appendChild(y),i?C.addEventListener("click",()=>{this'
HTML += b'.editedQuestion(),this.student[g]=this.student[g]==="true"?"'
HTML += b'false":"true",this.student[g]==="true"?S.innerHTML=n:S.inner'
HTML += b'HTML=o}):C.addEventListener("click",()=>{this.editedQuestion'
HTML += b'();for(let L of u)this.student[L]="false";this.student[g]="t'
HTML += b'rue";for(let L=0;L<u.length;L++){let Q=h[L];c[Q].innerHTML=t'
HTML += b'his.student[u[Q]]=="true"?n:o}})}return this.choiceIdx++,s}c'
HTML += b'ase"image":{let i=b(),a=e.d.split("."),l=a[a.length-1],h=e.c'
HTML += b'[0].d,n=e.c[1].d,o=document.createElement("img");i.appendChi'
HTML += b'ld(o),o.classList.add("img"),o.style.width=h+"%";let c={svg:'
HTML += b'"svg+xml",png:"png",jpg:"jpeg"};return o.src="data:image/"+c'
HTML += b'[l]+";base64,"+n,i}default:{let i=v("UNIMPLEMENTED("+e.t+")"'
HTML += b');return i.style.color="red",i}}}};function pe(r,e){["en","d'
HTML += b'e","es","it","fr"].includes(r.lang)==!1&&(r.lang="en"),e&&(d'
HTML += b'ocument.getElementById("debug").style.display="block"),docum'
HTML += b'ent.getElementById("date").innerHTML=r.date,document.getElem'
HTML += b'entById("title").innerHTML=r.title,document.getElementById("'
HTML += b'author").innerHTML=r.author,document.getElementById("courseI'
HTML += b'nfo1").innerHTML=O[r.lang];let t=\'<span onclick="location.re'
HTML += b'load()" style="text-decoration: underline; font-weight: bold'
HTML += b'; cursor: pointer">\'+K[r.lang]+"</span>";document.getElement'
HTML += b'ById("courseInfo2").innerHTML=F[r.lang].replace("*",t);let i'
HTML += b'=[],s=document.getElementById("questions"),a=1;for(let l of '
HTML += b'r.questions){l.title=""+a+". "+l.title;let h=b();s.appendChi'
HTML += b'ld(h);let n=new H(h,l,r.lang,e);n.showSolution=e,i.push(n),n'
HTML += b'.populateDom(),e&&l.error.length==0&&n.checkAndRepeatBtn.cli'
HTML += b'ck(),a++}}return he(de);})();sell.init(quizSrc,debug);</scri'
HTML += b'pt></body> </html> '
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
