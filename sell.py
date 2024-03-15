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
HTML += b'nProperty;var le=(n,e)=>{for(var t in e)B(n,t,{get:e[t],enum'
HTML += b'erable:!0})},oe=(n,e,t,i)=>{if(e&&typeof e=="object"||typeof'
HTML += b' e=="function")for(let s of ne(e))!ae.call(n,s)&&s!==t&&B(n,'
HTML += b's,{get:()=>e[s],enumerable:!(i=re(e,s))||i.enumerable});retu'
HTML += b'rn n};var he=n=>oe(B({},"__esModule",{value:!0}),n);var de={'
HTML += b'};le(de,{init:()=>pe});function v(n=[]){let e=document.creat'
HTML += b'eElement("div");return e.append(...n),e}function z(n=[]){let'
HTML += b' e=document.createElement("ul");return e.append(...n),e}func'
HTML += b'tion U(n){let e=document.createElement("li");return e.append'
HTML += b'Child(n),e}function R(n){let e=document.createElement("input'
HTML += b'");return e.spellcheck=!1,e.type="text",e.classList.add("inp'
HTML += b'utField"),e.style.width=n+"px",e}function j(){let n=document'
HTML += b'.createElement("button");return n.type="button",n.classList.'
HTML += b'add("button"),n}function k(n,e=[]){let t=document.createElem'
HTML += b'ent("span");return e.length>0?t.append(...e):t.innerHTML=n,t'
HTML += b'}function W(n,e,t=!1){katex.render(e,n,{throwOnError:!1,disp'
HTML += b'layMode:t,macros:{"\\\\RR":"\\\\mathbb{R}","\\\\NN":"\\\\mathbb{N}",'
HTML += b'"\\\\QQ":"\\\\mathbb{Q}","\\\\ZZ":"\\\\mathbb{Z}","\\\\CC":"\\\\mathbb{C'
HTML += b'}"}})}function y(n,e=!1){let t=document.createElement("span"'
HTML += b');return W(t,n,e),t}var O={en:"This page runs in your browse'
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
HTML += b'e des erreurs","mauvaise r\\xE9ponse"]};function Y(n,e){let t'
HTML += b'=Array(e.length+1).fill(null).map(()=>Array(n.length+1).fill'
HTML += b'(null));for(let i=0;i<=n.length;i+=1)t[0][i]=i;for(let i=0;i'
HTML += b'<=e.length;i+=1)t[i][0]=i;for(let i=1;i<=e.length;i+=1)for(l'
HTML += b'et s=1;s<=n.length;s+=1){let a=n[s-1]===e[i-1]?0:1;t[i][s]=M'
HTML += b'ath.min(t[i][s-1]+1,t[i-1][s]+1,t[i-1][s-1]+a)}return t[e.le'
HTML += b'ngth][n.length]}var G=\'<svg xmlns="http://www.w3.org/2000/sv'
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
HTML += b'60z"/></svg>\';function P(n,e=!1){let t=new Array(n);for(let '
HTML += b'i=0;i<n;i++)t[i]=i;if(e)for(let i=0;i<n;i++){let s=Math.floo'
HTML += b'r(Math.random()*n),a=Math.floor(Math.random()*n),l=t[s];t[s]'
HTML += b'=t[a],t[a]=l}return t}function _(n,e,t=-1){if(t<0&&(t=n.leng'
HTML += b'th),t==1){e.push([...n]);return}for(let i=0;i<t;i++){_(n,e,t'
HTML += b'-1);let s=t%2==0?i:0,a=n[s];n[s]=n[t-1],n[t-1]=a}}var C=clas'
HTML += b's n{constructor(e,t){this.m=e,this.n=t,this.v=new Array(e*t)'
HTML += b'.fill("0")}getElement(e,t){return e<0||e>=this.m||t<0||t>=th'
HTML += b'is.n?"0":this.v[e*this.n+t]}resize(e,t,i){if(e<1||e>50||t<1|'
HTML += b'|t>50)return!1;let s=new n(e,t);s.v.fill(i);for(let a=0;a<s.'
HTML += b'm;a++)for(let l=0;l<s.n;l++)s.v[a*s.n+l]=this.getElement(a,l'
HTML += b');return this.fromMatrix(s),!0}fromMatrix(e){this.m=e.m,this'
HTML += b'.n=e.n,this.v=[...e.v]}fromString(e){this.m=e.split("],").le'
HTML += b'ngth,this.v=e.replaceAll("[","").replaceAll("]","").split(",'
HTML += b'").map(t=>t.trim()),this.n=this.v.length/this.m}getMaxCellSt'
HTML += b'rlen(){let e=0;for(let t of this.v)t.length>e&&(e=t.length);'
HTML += b'return e}toTeXString(e=!1,t=!0){let i="";t?i+=e?"\\\\left[\\\\be'
HTML += b'gin{array}":"\\\\begin{bmatrix}":i+=e?"\\\\left(\\\\begin{array}":'
HTML += b'"\\\\begin{pmatrix}",e&&(i+="{"+"c".repeat(this.n-1)+"|c}");fo'
HTML += b'r(let s=0;s<this.m;s++){for(let a=0;a<this.n;a++){a>0&&(i+="'
HTML += b'&");let l=this.getElement(s,a);try{l=f.parse(l).toTexString('
HTML += b')}catch{}i+=l}i+="\\\\\\\\"}return t?i+=e?"\\\\end{array}\\\\right]"'
HTML += b':"\\\\end{bmatrix}":i+=e?"\\\\end{array}\\\\right)":"\\\\end{pmatrix'
HTML += b'}",i}},f=class n{constructor(){this.root=null,this.src="",th'
HTML += b'is.token="",this.skippedWhiteSpace=!1,this.pos=0}clone(){let'
HTML += b' e=new n;return e.root=this.root.clone(),e}getVars(e,t="",i='
HTML += b'null){if(i==null&&(i=this.root),i.op.startsWith("var:")){let'
HTML += b' s=i.op.substring(4);(t.length==0||t.length>0&&s.startsWith('
HTML += b't))&&e.add(s)}for(let s of i.c)this.getVars(e,t,s)}setVars(e'
HTML += b',t=null){t==null&&(t=this.root);for(let i of t.c)this.setVar'
HTML += b's(e,i);if(t.op.startsWith("var:")){let i=t.op.substring(4);i'
HTML += b'f(i in e){let s=e[i].clone();t.op=s.op,t.c=s.c,t.re=s.re,t.i'
HTML += b'm=s.im}}}renameVar(e,t,i=null){i==null&&(i=this.root);for(le'
HTML += b't s of i.c)this.renameVar(e,t,s);i.op.startsWith("var:")&&i.'
HTML += b'op.substring(4)===e&&(i.op="var:"+t)}eval(e,t=null){let s=u.'
HTML += b'const(),a=0,l=0,o=null;switch(t==null&&(t=this.root),t.op){c'
HTML += b'ase"const":s=t;break;case"+":case"-":case"*":case"/":case"^"'
HTML += b':{let r=this.eval(e,t.c[0]),h=this.eval(e,t.c[1]);switch(t.o'
HTML += b'p){case"+":s.re=r.re+h.re,s.im=r.im+h.im;break;case"-":s.re='
HTML += b'r.re-h.re,s.im=r.im-h.im;break;case"*":s.re=r.re*h.re-r.im*h'
HTML += b'.im,s.im=r.re*h.im+r.im*h.re;break;case"/":a=h.re*h.re+h.im*'
HTML += b'h.im,s.re=(r.re*h.re+r.im*h.im)/a,s.im=(r.im*h.re-r.re*h.im)'
HTML += b'/a;break;case"^":o=new u("exp",[new u("*",[h,new u("ln",[r])'
HTML += b'])]),s=this.eval(e,o);break}break}case".-":case"abs":case"si'
HTML += b'n":case"sinc":case"cos":case"tan":case"cot":case"exp":case"l'
HTML += b'n":case"log":case"sqrt":{let r=this.eval(e,t.c[0]);switch(t.'
HTML += b'op){case".-":s.re=-r.re,s.im=-r.im;break;case"abs":s.re=Math'
HTML += b'.sqrt(r.re*r.re+r.im*r.im),s.im=0;break;case"sin":s.re=Math.'
HTML += b'sin(r.re)*Math.cosh(r.im),s.im=Math.cos(r.re)*Math.sinh(r.im'
HTML += b');break;case"sinc":o=new u("/",[new u("sin",[r]),r]),s=this.'
HTML += b'eval(e,o);break;case"cos":s.re=Math.cos(r.re)*Math.cosh(r.im'
HTML += b'),s.im=-Math.sin(r.re)*Math.sinh(r.im);break;case"tan":a=Mat'
HTML += b'h.cos(r.re)*Math.cos(r.re)+Math.sinh(r.im)*Math.sinh(r.im),s'
HTML += b'.re=Math.sin(r.re)*Math.cos(r.re)/a,s.im=Math.sinh(r.im)*Mat'
HTML += b'h.cosh(r.im)/a;break;case"cot":a=Math.sin(r.re)*Math.sin(r.r'
HTML += b'e)+Math.sinh(r.im)*Math.sinh(r.im),s.re=Math.sin(r.re)*Math.'
HTML += b'cos(r.re)/a,s.im=-(Math.sinh(r.im)*Math.cosh(r.im))/a;break;'
HTML += b'case"exp":s.re=Math.exp(r.re)*Math.cos(r.im),s.im=Math.exp(r'
HTML += b'.re)*Math.sin(r.im);break;case"ln":case"log":s.re=Math.log(M'
HTML += b'ath.sqrt(r.re*r.re+r.im*r.im)),a=Math.abs(r.im)<1e-9?0:r.im,'
HTML += b's.im=Math.atan2(a,r.re);break;case"sqrt":o=new u("^",[r,u.co'
HTML += b'nst(.5)]),s=this.eval(e,o);break}break}default:if(t.op.start'
HTML += b'sWith("var:")){let r=t.op.substring(4);if(r==="pi")return u.'
HTML += b'const(Math.PI);if(r==="e")return u.const(Math.E);if(r==="i")'
HTML += b'return u.const(0,1);if(r in e)return e[r];throw new Error("e'
HTML += b'val-error: unknown variable \'"+r+"\'")}else throw new Error("'
HTML += b'UNIMPLEMENTED eval \'"+t.op+"\'")}return s}static parse(e){let'
HTML += b' t=new n;if(t.src=e,t.token="",t.skippedWhiteSpace=!1,t.pos='
HTML += b'0,t.next(),t.root=t.parseExpr(!1),t.token!=="")throw new Err'
HTML += b'or("remaining tokens: "+t.token+"...");return t}parseExpr(e)'
HTML += b'{return this.parseAdd(e)}parseAdd(e){let t=this.parseMul(e);'
HTML += b'for(;["+","-"].includes(this.token)&&!(e&&this.skippedWhiteS'
HTML += b'pace);){let i=this.token;this.next(),t=new u(i,[t,this.parse'
HTML += b'Mul(e)])}return t}parseMul(e){let t=this.parsePow(e);for(;!('
HTML += b'e&&this.skippedWhiteSpace);){let i="*";if(["*","/"].includes'
HTML += b'(this.token))i=this.token,this.next();else if(!e&&this.token'
HTML += b'==="(")i="*";else if(this.token.length>0&&(this.isAlpha(this'
HTML += b'.token[0])||this.isNum(this.token[0])))i="*";else break;t=ne'
HTML += b'w u(i,[t,this.parsePow(e)])}return t}parsePow(e){let t=this.'
HTML += b'parseUnary(e);for(;["^"].includes(this.token)&&!(e&&this.ski'
HTML += b'ppedWhiteSpace);){let i=this.token;this.next(),t=new u(i,[t,'
HTML += b'this.parseUnary(e)])}return t}parseUnary(e){return this.toke'
HTML += b'n==="-"?(this.next(),new u(".-",[this.parseMul(e)])):this.pa'
HTML += b'rseInfix(e)}parseInfix(e){if(this.token.length==0)throw new '
HTML += b'Error("expected unary");if(this.isNum(this.token[0])){let t='
HTML += b'this.token;return this.next(),this.token==="."&&(t+=".",this'
HTML += b'.next(),this.token.length>0&&(t+=this.token,this.next())),ne'
HTML += b'w u("const",[],parseFloat(t))}else if(this.fun1().length>0){'
HTML += b'let t=this.fun1();this.next(t.length);let i=null;if(this.tok'
HTML += b'en==="(")if(this.next(),i=this.parseExpr(e),this.token+="",t'
HTML += b'his.token===")")this.next();else throw Error("expected \')\'")'
HTML += b';else i=this.parseMul(!0);return new u(t,[i])}else if(this.t'
HTML += b'oken==="("){this.next();let t=this.parseExpr(e);if(this.toke'
HTML += b'n+="",this.token===")")this.next();else throw Error("expecte'
HTML += b'd \')\'");return t.explicitParentheses=!0,t}else if(this.token'
HTML += b'==="|"){this.next();let t=this.parseExpr(e);if(this.token+="'
HTML += b'",this.token==="|")this.next();else throw Error("expected \'|'
HTML += b'\'");return new u("abs",[t])}else if(this.isAlpha(this.token['
HTML += b'0])){let t="";return this.token.startsWith("pi")?t="pi":this'
HTML += b'.token.startsWith("C1")?t="C1":this.token.startsWith("C2")?t'
HTML += b'="C2":t=this.token[0],t==="I"&&(t="i"),this.next(t.length),n'
HTML += b'ew u("var:"+t,[])}else throw new Error("expected unary")}sta'
HTML += b'tic compare(e,t,i={}){let l=new Set;e.getVars(l),t.getVars(l'
HTML += b');for(let o=0;o<10;o++){let r={};for(let g of l)g in i?r[g]='
HTML += b'i[g]:r[g]=u.const(Math.random(),Math.random());let h=e.eval('
HTML += b'r),c=t.eval(r),d=h.re-c.re,p=h.im-c.im;if(Math.sqrt(d*d+p*p)'
HTML += b'>1e-9)return!1}return!0}fun1(){let e=["abs","sinc","sin","co'
HTML += b's","tan","cot","exp","ln","sqrt"];for(let t of e)if(this.tok'
HTML += b'en.toLowerCase().startsWith(t))return t;return""}next(e=-1){'
HTML += b'if(e>0&&this.token.length>e){this.token=this.token.substring'
HTML += b'(e),this.skippedWhiteSpace=!1;return}this.token="";let t=!1,'
HTML += b'i=this.src.length;for(this.skippedWhiteSpace=!1;this.pos<i&&'
HTML += b'`\t\n `.includes(this.src[this.pos]);)this.skippedWhiteSpace=!'
HTML += b'0,this.pos++;for(;!t&&this.pos<i;){let s=this.src[this.pos];'
HTML += b'if(this.token.length>0&&(this.isNum(this.token[0])&&this.isA'
HTML += b'lpha(s)||this.isAlpha(this.token[0])&&this.isNum(s))&&this.t'
HTML += b'oken!="C")return;if(`^%#*$()[]{},.:;+-*/_!<>=?|\t\n `.includes'
HTML += b'(s)){if(this.token.length>0)return;t=!0}`\t\n `.includes(s)==!'
HTML += b'1&&(this.token+=s),this.pos++}}isNum(e){return e.charCodeAt('
HTML += b'0)>=48&&e.charCodeAt(0)<=57}isAlpha(e){return e.charCodeAt(0'
HTML += b')>=65&&e.charCodeAt(0)<=90||e.charCodeAt(0)>=97&&e.charCodeA'
HTML += b't(0)<=122||e==="_"}toString(){return this.root==null?"":this'
HTML += b'.root.toString()}toTexString(){return this.root==null?"":thi'
HTML += b's.root.toTexString()}},u=class n{constructor(e,t,i=0,s=0){th'
HTML += b'is.op=e,this.c=t,this.re=i,this.im=s,this.explicitParenthese'
HTML += b's=!1}clone(){let e=new n(this.op,this.c.map(t=>t.clone()),th'
HTML += b'is.re,this.im);return e.explicitParentheses=this.explicitPar'
HTML += b'entheses,e}static const(e=0,t=0){return new n("const",[],e,t'
HTML += b')}compare(e,t=0,i=1e-9){let s=this.re-e,a=this.im-t;return M'
HTML += b'ath.sqrt(s*s+a*a)<i}toString(){let e="";if(this.op==="const"'
HTML += b'){let t=Math.abs(this.re)>1e-14,i=Math.abs(this.im)>1e-14;t&'
HTML += b'&i&&this.im>=0?e="("+this.re+"+"+this.im+"i)":t&&i&&this.im<'
HTML += b'0?e="("+this.re+"-"+-this.im+"i)":t&&this.re>0?e=""+this.re:'
HTML += b't&&this.re<0?e="("+this.re+")":i?e="("+this.im+"i)":e="0"}el'
HTML += b'se this.op.startsWith("var")?e=this.op.split(":")[1]:this.c.'
HTML += b'length==1?e=(this.op===".-"?"-":this.op)+"("+this.c.toString'
HTML += b'()+")":e="("+this.c.map(t=>t.toString()).join(this.op)+")";r'
HTML += b'eturn e}toTexString(e=!1){let i="";switch(this.op){case"cons'
HTML += b't":{let s=Math.abs(this.re)>1e-9,a=Math.abs(this.im)>1e-9,l='
HTML += b's?""+this.re:"",o=a?""+this.im+"i":"";o==="1i"?o="i":o==="-1'
HTML += b'i"&&(o="-i"),!s&&!a?i="0":(a&&this.im>=0&&s&&(o="+"+o),i=l+o'
HTML += b');break}case".-":i="-"+this.c[0].toTexString();break;case"+"'
HTML += b':case"-":case"*":case"^":{let s=this.c[0].toTexString(),a=th'
HTML += b'is.c[1].toTexString(),l=this.op==="*"?"\\\\cdot ":this.op;i="{'
HTML += b'"+s+"}"+l+"{"+a+"}";break}case"/":{let s=this.c[0].toTexStri'
HTML += b'ng(!0),a=this.c[1].toTexString(!0);i="\\\\frac{"+s+"}{"+a+"}";'
HTML += b'break}case"sin":case"sinc":case"cos":case"tan":case"cot":cas'
HTML += b'e"exp":case"ln":{let s=this.c[0].toTexString(!0);i+="\\\\"+thi'
HTML += b's.op+"\\\\left("+s+"\\\\right)";break}case"sqrt":{let s=this.c[0'
HTML += b'].toTexString(!0);i+="\\\\"+this.op+"{"+s+"}";break}case"abs":'
HTML += b'{let s=this.c[0].toTexString(!0);i+="\\\\left|"+s+"\\\\right|";b'
HTML += b'reak}default:if(this.op.startsWith("var:")){let s=this.op.su'
HTML += b'bstring(4);switch(s){case"pi":s="\\\\pi";break}i=" "+s+" "}els'
HTML += b'e{let s="warning: Node.toString(..):";s+=" unimplemented ope'
HTML += b'rator \'"+this.op+"\'",console.log(s),i=this.op,this.c.length>'
HTML += b'0&&(i+="\\\\left({"+this.c.map(a=>a.toTexString(!0)).join(",")'
HTML += b'+"}\\\\right)")}}return!e&&this.explicitParentheses&&(i="\\\\lef'
HTML += b't({"+i+"}\\\\right)"),i}};function ie(n,e){let t=1e-9;if(f.com'
HTML += b'pare(n,e))return!0;n=n.clone(),e=e.clone(),N(n.root),N(e.roo'
HTML += b't);let i=new Set;n.getVars(i),e.getVars(i);let s=[],a=[];for'
HTML += b'(let r of i.keys())r.startsWith("C")?s.push(r):a.push(r);let'
HTML += b' l=s.length;for(let r=0;r<l;r++){let h=s[r];n.renameVar(h,"_'
HTML += b'C"+r),e.renameVar(h,"_C"+r)}for(let r=0;r<l;r++)n.renameVar('
HTML += b'"_C"+r,"C"+r),e.renameVar("_C"+r,"C"+r);s=[];for(let r=0;r<l'
HTML += b';r++)s.push("C"+r);let o=[];_(P(l),o);for(let r of o){let h='
HTML += b'n.clone(),c=e.clone();for(let p=0;p<l;p++)c.renameVar("C"+p,'
HTML += b'"__C"+r[p]);for(let p=0;p<l;p++)c.renameVar("__C"+p,"C"+p);l'
HTML += b'et d=!0;for(let p=0;p<l;p++){let m="C"+p,g={};g[m]=new u("*"'
HTML += b',[new u("var:C"+p,[]),new u("var:K",[])]),c.setVars(g);let b'
HTML += b'={};b[m]=u.const(Math.random(),Math.random());for(let w=0;w<'
HTML += b'l;w++)p!=w&&(b["C"+w]=u.const(0,0));let S=new u("abs",[new u'
HTML += b'("-",[h.root,c.root])]),T=new f;T.root=S;for(let w of a)b[w]'
HTML += b'=u.const(Math.random(),Math.random());let M=ce(T,"K",b)[0];c'
HTML += b'.setVars({K:u.const(M,0)}),b={};for(let w=0;w<l;w++)p!=w&&(b'
HTML += b'["C"+w]=u.const(0,0));if(f.compare(h,c,b)==!1){d=!1;break}}i'
HTML += b'f(d&&f.compare(h,c))return!0}return!1}function ce(n,e,t){let'
HTML += b' i=1e-11,s=1e3,a=0,l=0,o=1,r=888;for(;a<s;){t[e]=u.const(l);'
HTML += b'let c=n.eval(t).re;t[e]=u.const(l+o);let d=n.eval(t).re;t[e]'
HTML += b'=u.const(l-o);let p=n.eval(t).re,m=0;if(d<c&&(c=d,m=1),p<c&&'
HTML += b'(c=p,m=-1),m==1&&(l+=o),m==-1&&(l-=o),c<i)break;(m==0||m!=r)'
HTML += b'&&(o/=2),r=m,a++}t[e]=u.const(l);let h=n.eval(t).re;return[l'
HTML += b',h]}function N(n){for(let e of n.c)N(e);switch(n.op){case"+"'
HTML += b':case"-":case"*":case"/":case"^":{let e=[n.c[0].op,n.c[1].op'
HTML += b'],t=[e[0]==="const",e[1]==="const"],i=[e[0].startsWith("var:'
HTML += b'C"),e[1].startsWith("var:C")];i[0]&&t[1]?(n.op=n.c[0].op,n.c'
HTML += b'=[]):i[1]&&t[0]?(n.op=n.c[1].op,n.c=[]):i[0]&&i[1]&&e[0]==e['
HTML += b'1]&&(n.op=n.c[0].op,n.c=[]);break}case".-":case"abs":case"si'
HTML += b'n":case"sinc":case"cos":case"tan":case"cot":case"exp":case"l'
HTML += b'n":case"log":case"sqrt":n.c[0].op.startsWith("var:C")&&(n.op'
HTML += b'=n.c[0].op,n.c=[]);break}}function se(n){n.feedbackSpan.inne'
HTML += b'rHTML="",n.numChecked=0,n.numCorrect=0;let e=!0;for(let s in'
HTML += b' n.expected){let a=n.types[s],l=n.student[s],o=n.expected[s]'
HTML += b';switch(l!=null&&l.length==0&&(e=!1),a){case"bool":n.numChec'
HTML += b'ked++,l===o&&n.numCorrect++;break;case"string":{n.numChecked'
HTML += b'++;let r=n.gapInputs[s],h=l.trim().toUpperCase(),c=o.trim().'
HTML += b'toUpperCase().split("|"),d=!1;for(let p of c)if(Y(h,p)<=1){d'
HTML += b'=!0,n.numCorrect++,n.gapInputs[s].value=p,n.student[s]=p;bre'
HTML += b'ak}r.style.color=d?"black":"white",r.style.backgroundColor=d'
HTML += b'?"transparent":"maroon";break}case"int":n.numChecked++,Math.'
HTML += b'abs(parseFloat(l)-parseFloat(o))<1e-9&&n.numCorrect++;break;'
HTML += b'case"float":case"term":{n.numChecked++;try{let r=f.parse(o),'
HTML += b'h=f.parse(l),c=!1;n.src.is_ode?c=ie(r,h):c=f.compare(r,h),c&'
HTML += b'&n.numCorrect++}catch(r){n.debug&&(console.log("term invalid'
HTML += b'"),console.log(r))}break}case"vector":case"complex":case"set'
HTML += b'":{let r=o.split(",");n.numChecked+=r.length;let h=[];for(le'
HTML += b't c=0;c<r.length;c++){let d=n.student[s+"-"+c];d.length==0&&'
HTML += b'(e=!1),h.push(d)}if(a==="set")for(let c=0;c<r.length;c++)try'
HTML += b'{let d=f.parse(r[c]);for(let p=0;p<h.length;p++){let m=f.par'
HTML += b'se(h[p]);if(f.compare(d,m)){n.numCorrect++;break}}}catch(d){'
HTML += b'n.debug&&console.log(d)}else for(let c=0;c<r.length;c++)try{'
HTML += b'let d=f.parse(h[c]),p=f.parse(r[c]);f.compare(d,p)&&n.numCor'
HTML += b'rect++}catch(d){n.debug&&console.log(d)}break}case"matrix":{'
HTML += b'let r=new C(0,0);r.fromString(o),n.numChecked+=r.m*r.n;for(l'
HTML += b'et h=0;h<r.m;h++)for(let c=0;c<r.n;c++){let d=h*r.n+c;l=n.st'
HTML += b'udent[s+"-"+d],l.length==0&&(e=!1);let p=r.v[d];try{let m=f.'
HTML += b'parse(p),g=f.parse(l);f.compare(m,g)&&n.numCorrect++}catch(m'
HTML += b'){n.debug&&console.log(m)}}break}default:n.feedbackSpan.inne'
HTML += b'rHTML="UNIMPLEMENTED EVAL OF TYPE "+a}}e==!1?n.state=x.incom'
HTML += b'plete:n.state=n.numCorrect==n.numChecked?x.passed:x.errors,n'
HTML += b'.updateVisualQuestionState();let t=[];switch(n.state){case x'
HTML += b'.passed:t=X[n.language];break;case x.incomplete:t=Z[n.langua'
HTML += b'ge];break;case x.errors:t=q[n.language];break}let i=t[Math.f'
HTML += b'loor(Math.random()*t.length)];n.feedbackPopupDiv.innerHTML=i'
HTML += b',n.feedbackPopupDiv.style.color=n.state===x.passed?"green":"'
HTML += b'maroon",n.feedbackPopupDiv.style.display="block",setTimeout('
HTML += b'()=>{n.feedbackPopupDiv.style.display="none"},500),n.state=='
HTML += b'=x.passed?n.src.instances.length>0?n.checkAndRepeatBtn.inner'
HTML += b'HTML=te:n.checkAndRepeatBtn.style.display="none":n.checkAndR'
HTML += b'epeatBtn.innerHTML=I}var A=class{constructor(e,t,i,s){t.stud'
HTML += b'ent[i]="",this.question=t,this.inputId=i,i.length==0&&(this.'
HTML += b'inputId="gap-"+t.gapIdx,t.types[this.inputId]="string",t.exp'
HTML += b'ected[this.inputId]=s,t.gapIdx++);let a=s.split("|"),l=0;for'
HTML += b'(let c=0;c<a.length;c++){let d=a[c];d.length>l&&(l=d.length)'
HTML += b'}let o=k("");e.appendChild(o);let r=Math.max(l*15,24),h=R(r)'
HTML += b';if(t.gapInputs[this.inputId]=h,h.addEventListener("keyup",('
HTML += b')=>{this.question.editedQuestion(),h.value=h.value.toUpperCa'
HTML += b'se(),this.question.student[this.inputId]=h.value.trim()}),o.'
HTML += b'appendChild(h),this.question.showSolution&&(this.question.st'
HTML += b'udent[this.inputId]=h.value=a[0],a.length>1)){let c=k("["+a.'
HTML += b'join("|")+"]");c.style.fontSize="small",c.style.textDecorati'
HTML += b'on="underline",o.appendChild(c)}}},E=class{constructor(e,t,i'
HTML += b',s,a,l){t.student[i]="",this.question=t,this.inputId=i,this.'
HTML += b'outerSpan=k(""),this.outerSpan.style.position="relative",e.a'
HTML += b'ppendChild(this.outerSpan),this.inputElement=R(Math.max(s*12'
HTML += b',48)),this.outerSpan.appendChild(this.inputElement),this.equ'
HTML += b'ationPreviewDiv=v(),this.equationPreviewDiv.classList.add("e'
HTML += b'quationPreview"),this.equationPreviewDiv.style.display="none'
HTML += b'",this.outerSpan.appendChild(this.equationPreviewDiv),this.i'
HTML += b'nputElement.addEventListener("click",()=>{this.question.edit'
HTML += b'edQuestion(),this.edited()}),this.inputElement.addEventListe'
HTML += b'ner("keyup",()=>{this.question.editedQuestion(),this.edited('
HTML += b')}),this.inputElement.addEventListener("focusout",()=>{this.'
HTML += b'equationPreviewDiv.innerHTML="",this.equationPreviewDiv.styl'
HTML += b'e.display="none"}),this.inputElement.addEventListener("keydo'
HTML += b'wn",o=>{let r="abcdefghijklmnopqrstuvwxyz";r+="ABCDEFGHIJKLM'
HTML += b'NOPQRSTUVWXYZ",r+="0123456789",r+="+-*/^(). <>=|",l&&(r="-01'
HTML += b'23456789"),o.key.length<3&&r.includes(o.key)==!1&&o.preventD'
HTML += b'efault();let h=this.inputElement.value.length*12;this.inputE'
HTML += b'lement.offsetWidth<h&&(this.inputElement.style.width=""+h+"p'
HTML += b'x")}),this.question.showSolution&&(t.student[i]=this.inputEl'
HTML += b'ement.value=a)}edited(){let e=this.inputElement.value.trim()'
HTML += b',t="",i=!1;try{let s=f.parse(e);i=s.root.op==="const",t=s.to'
HTML += b'TexString(),this.inputElement.style.color="black",this.equat'
HTML += b'ionPreviewDiv.style.backgroundColor="green"}catch{t=e.replac'
HTML += b'eAll("^","\\\\hat{~}").replaceAll("_","\\\\_"),this.inputElement'
HTML += b'.style.color="maroon",this.equationPreviewDiv.style.backgrou'
HTML += b'ndColor="maroon"}W(this.equationPreviewDiv,t,!0),this.equati'
HTML += b'onPreviewDiv.style.display=e.length>0&&!i?"block":"none",thi'
HTML += b's.question.student[this.inputId]=e}},V=class{constructor(e,t'
HTML += b',i,s){this.parent=e,this.question=t,this.inputId=i,this.matE'
HTML += b'xpected=new C(0,0),this.matExpected.fromString(s),this.matSt'
HTML += b'udent=new C(this.matExpected.m==1?1:3,this.matExpected.n==1?'
HTML += b'1:3),t.showSolution&&this.matStudent.fromMatrix(this.matExpe'
HTML += b'cted),this.genMatrixDom()}genMatrixDom(){let e=v();this.pare'
HTML += b'nt.innerHTML="",this.parent.appendChild(e),e.style.position='
HTML += b'"relative",e.style.display="inline-block";let t=document.cre'
HTML += b'ateElement("table");e.appendChild(t);let i=this.matExpected.'
HTML += b'getMaxCellStrlen();for(let p=0;p<this.matStudent.m;p++){let '
HTML += b'm=document.createElement("tr");t.appendChild(m),p==0&&m.appe'
HTML += b'ndChild(this.generateMatrixParenthesis(!0,this.matStudent.m)'
HTML += b');for(let g=0;g<this.matStudent.n;g++){let b=p*this.matStude'
HTML += b'nt.n+g,S=document.createElement("td");m.appendChild(S);let T'
HTML += b'=this.inputId+"-"+b;new E(S,this.question,T,i,this.matStuden'
HTML += b't.v[b],!1)}p==0&&m.appendChild(this.generateMatrixParenthesi'
HTML += b's(!1,this.matStudent.m))}let s=["+","-","+","-"],a=[0,0,1,-1'
HTML += b'],l=[1,-1,0,0],o=[0,22,888,888],r=[888,888,-22,-22],h=[-22,-'
HTML += b'22,0,22],c=[this.matExpected.n!=1,this.matExpected.n!=1,this'
HTML += b'.matExpected.m!=1,this.matExpected.m!=1],d=[this.matStudent.'
HTML += b'n>=10,this.matStudent.n<=1,this.matStudent.m>=10,this.matStu'
HTML += b'dent.m<=1];for(let p=0;p<4;p++){if(c[p]==!1)continue;let m=k'
HTML += b'(s[p]);o[p]!=888&&(m.style.top=""+o[p]+"px"),r[p]!=888&&(m.s'
HTML += b'tyle.bottom=""+r[p]+"px"),h[p]!=888&&(m.style.right=""+h[p]+'
HTML += b'"px"),m.classList.add("matrixResizeButton"),e.appendChild(m)'
HTML += b',d[p]?m.style.opacity="0.5":m.addEventListener("click",()=>{'
HTML += b'this.matStudent.resize(this.matStudent.m+a[p],this.matStuden'
HTML += b't.n+l[p],"0"),this.genMatrixDom()})}}generateMatrixParenthes'
HTML += b'is(e,t){let i=document.createElement("td");i.style.width="3p'
HTML += b'x";for(let s of["Top",e?"Left":"Right","Bottom"])i.style["bo'
HTML += b'rder"+s+"Width"]="2px",i.style["border"+s+"Style"]="solid";r'
HTML += b'eturn this.question.language=="de"&&(e?i.style.borderTopLeft'
HTML += b'Radius="5px":i.style.borderTopRightRadius="5px",e?i.style.bo'
HTML += b'rderBottomLeftRadius="5px":i.style.borderBottomRightRadius="'
HTML += b'5px"),i.rowSpan=t,i}};var x={init:0,errors:1,passed:2,incomp'
HTML += b'lete:3},H=class{constructor(e,t,i,s){this.state=x.init,this.'
HTML += b'language=i,this.src=t,this.debug=s,this.instanceOrder=P(t.in'
HTML += b'stances.length,!0),this.instanceIdx=0,this.choiceIdx=0,this.'
HTML += b'gapIdx=0,this.expected={},this.types={},this.student={},this'
HTML += b'.gapInputs={},this.parentDiv=e,this.questionDiv=null,this.fe'
HTML += b'edbackPopupDiv=null,this.titleDiv=null,this.checkAndRepeatBt'
HTML += b'n=null,this.showSolution=!1,this.feedbackSpan=null,this.numC'
HTML += b'orrect=0,this.numChecked=0}reset(){this.instanceIdx=(this.in'
HTML += b'stanceIdx+1)%this.src.instances.length}getCurrentInstance(){'
HTML += b'let e=this.instanceOrder[this.instanceIdx];return this.src.i'
HTML += b'nstances[e]}editedQuestion(){this.state=x.init,this.updateVi'
HTML += b'sualQuestionState(),this.questionDiv.style.color="black",thi'
HTML += b's.checkAndRepeatBtn.innerHTML=I,this.checkAndRepeatBtn.style'
HTML += b'.display="block",this.checkAndRepeatBtn.style.color="black"}'
HTML += b'updateVisualQuestionState(){let e="black",t="transparent";sw'
HTML += b'itch(this.state){case x.init:case x.incomplete:e="rgb(0,0,0)'
HTML += b'",t="transparent";break;case x.passed:e="rgb(0,150,0)",t="rg'
HTML += b'ba(0,150,0, 0.025)";break;case x.errors:e="rgb(150,0,0)",t="'
HTML += b'rgba(150,0,0, 0.025)",this.numChecked>=5&&(this.feedbackSpan'
HTML += b'.innerHTML=""+this.numCorrect+" / "+this.numChecked);break}t'
HTML += b'his.questionDiv.style.color=this.feedbackSpan.style.color=th'
HTML += b'is.titleDiv.style.color=this.checkAndRepeatBtn.style.backgro'
HTML += b'undColor=this.questionDiv.style.borderColor=e,this.questionD'
HTML += b'iv.style.backgroundColor=t}populateDom(){if(this.parentDiv.i'
HTML += b'nnerHTML="",this.questionDiv=v(),this.parentDiv.appendChild('
HTML += b'this.questionDiv),this.questionDiv.classList.add("question")'
HTML += b',this.feedbackPopupDiv=v(),this.feedbackPopupDiv.classList.a'
HTML += b'dd("questionFeedback"),this.questionDiv.appendChild(this.fee'
HTML += b'dbackPopupDiv),this.feedbackPopupDiv.innerHTML="awesome",thi'
HTML += b's.debug&&"src_line"in this.src){let a=v();a.classList.add("d'
HTML += b'ebugInfo"),a.innerHTML="Source code: lines "+this.src.src_li'
HTML += b'ne+"..",this.questionDiv.appendChild(a)}if(this.titleDiv=v()'
HTML += b',this.questionDiv.appendChild(this.titleDiv),this.titleDiv.c'
HTML += b'lassList.add("questionTitle"),this.titleDiv.innerHTML=this.s'
HTML += b'rc.title,this.src.error.length>0){let a=k(this.src.error);th'
HTML += b'is.questionDiv.appendChild(a),a.style.color="red";return}let'
HTML += b' e=this.getCurrentInstance();if(e!=null&&"__svg_image"in e){'
HTML += b'let a=e.__svg_image.v,l=v();this.questionDiv.appendChild(l);'
HTML += b'let o=document.createElement("img");l.appendChild(o),o.class'
HTML += b'List.add("img"),o.src="data:image/svg+xml;base64,"+a}for(let'
HTML += b' a of this.src.text.c)this.questionDiv.appendChild(this.gene'
HTML += b'rateText(a));let t=v();this.questionDiv.appendChild(t),t.cla'
HTML += b'ssList.add("buttonRow");let i=Object.keys(this.expected).len'
HTML += b'gth>0;i&&(this.checkAndRepeatBtn=j(),t.appendChild(this.chec'
HTML += b'kAndRepeatBtn),this.checkAndRepeatBtn.innerHTML=I,this.check'
HTML += b'AndRepeatBtn.style.backgroundColor="black");let s=k("&nbsp;&'
HTML += b'nbsp;&nbsp;");if(t.appendChild(s),this.feedbackSpan=k(""),t.'
HTML += b'appendChild(this.feedbackSpan),this.debug){if(this.src.varia'
HTML += b'bles.length>0){let o=v();o.classList.add("debugInfo"),o.inne'
HTML += b'rHTML="Variables generated by Python Code",this.questionDiv.'
HTML += b'appendChild(o);let r=v();r.classList.add("debugCode"),this.q'
HTML += b'uestionDiv.appendChild(r);let h=this.getCurrentInstance(),c='
HTML += b'"",d=[...this.src.variables];d.sort();for(let p of d){let m='
HTML += b'h[p].t,g=h[p].v;switch(m){case"vector":g="["+g+"]";break;cas'
HTML += b'e"set":g="{"+g+"}";break}c+=m+" "+p+" = "+g+"<br/>"}r.innerH'
HTML += b'TML=c}let a=["python_src_html","text_src_html"],l=["Python S'
HTML += b'ource Code","Text Source Code"];for(let o=0;o<a.length;o++){'
HTML += b'let r=a[o];if(r in this.src&&this.src[r].length>0){let h=v()'
HTML += b';h.classList.add("debugInfo"),h.innerHTML=l[o],this.question'
HTML += b'Div.appendChild(h);let c=v();c.classList.add("debugCode"),th'
HTML += b'is.questionDiv.append(c),c.innerHTML=this.src[r]}}}i&&this.c'
HTML += b'heckAndRepeatBtn.addEventListener("click",()=>{this.state==x'
HTML += b'.passed?(this.state=x.init,this.reset(),this.populateDom()):'
HTML += b'se(this)})}generateMathString(e){let t="";switch(e.t){case"m'
HTML += b'ath":case"display-math":for(let i of e.c){let s=this.generat'
HTML += b'eMathString(i);i.t==="var"&&t.includes("!PM")&&(s.startsWith'
HTML += b'("{-")?(s="{"+s.substring(2),t=t.replaceAll("!PM","-")):t=t.'
HTML += b'replaceAll("!PM","+")),t+=s}break;case"text":return e.d;case'
HTML += b'"plus_minus":{t+=" !PM ";break}case"var":{let i=this.getCurr'
HTML += b'entInstance(),s=i[e.d].t,a=i[e.d].v;switch(s){case"vector":r'
HTML += b'eturn"\\\\left["+a+"\\\\right]";case"set":return"\\\\left\\\\{"+a+"\\'
HTML += b'\\right\\\\}";case"complex":{let l=a.split(","),o=parseFloat(l['
HTML += b'0]),r=parseFloat(l[1]);return u.const(o,r).toTexString()}cas'
HTML += b'e"matrix":{let l=new C(0,0);return l.fromString(a),t=l.toTeX'
HTML += b'String(e.d.includes("augmented"),this.language!="de"),t}case'
HTML += b'"term":{try{t=f.parse(a).toTexString()}catch{}break}default:'
HTML += b't=a}}}return e.t==="plus_minus"?t:"{"+t+"}"}generateText(e,t'
HTML += b'=!1){switch(e.t){case"paragraph":case"span":{let i=document.'
HTML += b'createElement(e.t=="span"||t?"span":"p");for(let s of e.c)i.'
HTML += b'appendChild(this.generateText(s));return i}case"text":return'
HTML += b' k(e.d);case"code":{let i=k(e.d);return i.classList.add("cod'
HTML += b'e"),i}case"italic":case"bold":{let i=k("");return i.append(.'
HTML += b'..e.c.map(s=>this.generateText(s))),e.t==="bold"?i.style.fon'
HTML += b'tWeight="bold":i.style.fontStyle="italic",i}case"math":case"'
HTML += b'display-math":{let i=this.generateMathString(e);return y(i,e'
HTML += b'.t==="display-math")}case"string_var":{let i=k(""),s=this.ge'
HTML += b'tCurrentInstance(),a=s[e.d].t,l=s[e.d].v;return a==="string"'
HTML += b'?i.innerHTML=l:(i.innerHTML="EXPECTED VARIABLE OF TYPE STRIN'
HTML += b'G",i.style.color="red"),i}case"gap":{let i=k("");return new '
HTML += b'A(i,this,"",e.d),i}case"input":case"input2":{let i=e.t==="in'
HTML += b'put2",s=k("");s.style.verticalAlign="text-bottom";let a=e.d,'
HTML += b'l=this.getCurrentInstance()[a];if(this.expected[a]=l.v,this.'
HTML += b'types[a]=l.t,!i)switch(l.t){case"set":s.append(y("\\\\{"),k(" '
HTML += b'"));break;case"vector":s.append(y("["),k(" "));break}if(l.t='
HTML += b'=="string")new A(s,this,a,this.expected[a]);else if(l.t==="v'
HTML += b'ector"||l.t==="set"){let o=l.v.split(","),r=o.length;for(let'
HTML += b' h=0;h<r;h++){h>0&&s.appendChild(k(" , "));let c=a+"-"+h;new'
HTML += b' E(s,this,c,o[h].length,o[h],!1)}}else if(l.t==="matrix"){le'
HTML += b't o=v();s.appendChild(o),new V(o,this,a,l.v)}else if(l.t==="'
HTML += b'complex"){let o=l.v.split(",");new E(s,this,a+"-0",o[0].leng'
HTML += b'th,o[0],!1),s.append(k(" "),y("+"),k(" ")),new E(s,this,a+"-'
HTML += b'1",o[1].length,o[1],!1),s.append(k(" "),y("i"))}else{let o=l'
HTML += b'.t==="int";new E(s,this,a,l.v.length,l.v,o)}if(!i)switch(l.t'
HTML += b'){case"set":s.append(k(" "),y("\\\\}"));break;case"vector":s.a'
HTML += b'ppend(k(" "),y("]"));break}return s}case"itemize":return z(e'
HTML += b'.c.map(i=>U(this.generateText(i))));case"single-choice":case'
HTML += b'"multi-choice":{let i=e.t=="multi-choice",s=document.createE'
HTML += b'lement("table"),a=e.c.length,l=this.debug==!1,o=P(a,l),r=i?J'
HTML += b':ee,h=i?G:$,c=[],d=[];for(let p=0;p<a;p++){let m=o[p],g=e.c['
HTML += b'm],b="mc-"+this.choiceIdx+"-"+m;d.push(b);let S=g.c[0].t=="b'
HTML += b'ool"?g.c[0].d:this.getCurrentInstance()[g.c[0].d].v;this.exp'
HTML += b'ected[b]=S,this.types[b]="bool",this.student[b]=this.showSol'
HTML += b'ution?S:"false";let T=this.generateText(g.c[1],!0),M=documen'
HTML += b't.createElement("tr");s.appendChild(M),M.style.cursor="point'
HTML += b'er";let D=document.createElement("td");c.push(D),M.appendChi'
HTML += b'ld(D),D.innerHTML=this.student[b]=="true"?r:h;let w=document'
HTML += b'.createElement("td");M.appendChild(w),w.appendChild(T),i?M.a'
HTML += b'ddEventListener("click",()=>{this.editedQuestion(),this.stud'
HTML += b'ent[b]=this.student[b]==="true"?"false":"true",this.student['
HTML += b'b]==="true"?D.innerHTML=r:D.innerHTML=h}):M.addEventListener'
HTML += b'("click",()=>{this.editedQuestion();for(let L of d)this.stud'
HTML += b'ent[L]="false";this.student[b]="true";for(let L=0;L<d.length'
HTML += b';L++){let Q=o[L];c[Q].innerHTML=this.student[d[Q]]=="true"?r'
HTML += b':h}})}return this.choiceIdx++,s}case"image":{let i=v(),a=e.d'
HTML += b'.split("."),l=a[a.length-1],o=e.c[0].d,r=e.c[1].d,h=document'
HTML += b'.createElement("img");i.appendChild(h),h.classList.add("img"'
HTML += b'),h.style.width=o+"%";let c={svg:"svg+xml",png:"png",jpg:"jp'
HTML += b'eg"};return h.src="data:image/"+c[l]+";base64,"+r,i}default:'
HTML += b'{let i=k("UNIMPLEMENTED("+e.t+")");return i.style.color="red'
HTML += b'",i}}}};function pe(n,e){["en","de","es","it","fr"].includes'
HTML += b'(n.lang)==!1&&(n.lang="en"),e&&(document.getElementById("deb'
HTML += b'ug").style.display="block"),document.getElementById("date").'
HTML += b'innerHTML=n.date,document.getElementById("title").innerHTML='
HTML += b'n.title,document.getElementById("author").innerHTML=n.author'
HTML += b',document.getElementById("courseInfo1").innerHTML=O[n.lang];'
HTML += b'let t=\'<span onclick="location.reload()" style="text-decorat'
HTML += b'ion: underline; font-weight: bold; cursor: pointer">\'+K[n.la'
HTML += b'ng]+"</span>";document.getElementById("courseInfo2").innerHT'
HTML += b'ML=F[n.lang].replace("*",t);let i=[],s=document.getElementBy'
HTML += b'Id("questions"),a=1;for(let l of n.questions){l.title=""+a+"'
HTML += b'. "+l.title;let o=v();s.appendChild(o);let r=new H(o,l,n.lan'
HTML += b'g,e);r.showSolution=e,i.push(r),r.populateDom(),e&&l.error.l'
HTML += b'ength==0&&r.checkAndRepeatBtn.click(),a++}}return he(de);})('
HTML += b');sell.init(quizSrc,debug);</script></body> </html> '
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
