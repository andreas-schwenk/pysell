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


import json, sys, os, re, io, base64
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
                type = line[0]  # refer to "types" below
                if type not in "[(-!":
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
                "!": "command",
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
        if not math_mode and lex.token == "*":
            return self.parse_bold_italic(lex)
        elif lex.token == "$":
            return self.parse_math(lex)
        elif not math_mode and lex.token == "%":
            return self.parse_input(lex)
        elif not math_mode and lex.token == "&":
            return self.parse_string_var(lex)
        elif math_mode and lex.token == "+":
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

    def parse_string_var(self, lex: Lexer) -> Self:
        sv = TextNode("string_var")
        if lex.token == "&":
            lex.next()
        sv.data = lex.token.strip()
        lex.next()
        return sv

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
            res[id] = {"t": t, "v": v}
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


def compile(input_dirname: str, src: str) -> dict:
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
            question = Question(input_dirname, line_no + 1)
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
html += b'1 { text-align: center; font-size: 28pt; } img { width: 100%'
html += b'; display: block; margin-left: auto; margin-right: auto; } .'
html += b'author { text-align: center; font-size: 18pt; } .courseInfo '
html += b'{ font-size: 14pt; font-style: italic; /*margin-bottom: 24px'
html += b';*/ text-align: center; } .question { position: relative; /*'
html += b' required for feedback overlays */ color: black; background-'
html += b'color: white; border-style: solid; border-radius: 5px; borde'
html += b'r-width: 3px; border-color: black; padding: 8px; margin-top:'
html += b' 20px; margin-bottom: 20px; -webkit-box-shadow: 4px 6px 8px '
html += b'-1px rgba(0, 0, 0, 0.93); box-shadow: 4px 6px 8px -1px rgba('
html += b'0, 0, 0, 0.1); overflow-x: auto; } .questionFeedback { z-ind'
html += b'ex: 10; display: none; position: absolute; pointer-events: n'
html += b'one; left: 10%; top: 33%; width: 80%; /*height: 100%;*/ text'
html += b'-align: center; font-size: 24pt; text-shadow: 0px 0px 18px r'
html += b'gba(0, 0, 0, 0.33); background-color: rgba(255, 255, 255, 1)'
html += b'; padding-top: 20px; padding-bottom: 20px; /*border-style: s'
html += b'olid; border-width: 4px; border-color: rgb(200, 200, 200);*/'
html += b' border-radius: 16px; -webkit-box-shadow: 0px 0px 18px 5px r'
html += b'gba(0, 0, 0, 0.66); box-shadow: 0px 0px 18px 5px rgba(0, 0, '
html += b'0, 0.66); } .questionTitle { font-size: 24pt; } .code { font'
html += b'-family: "Courier New", Courier, monospace; color: black; ba'
html += b'ckground-color: rgb(235, 235, 235); padding: 2px 5px; border'
html += b'-radius: 5px; margin: 1px 2px; } .debugCode { font-family: "'
html += b'Courier New", Courier, monospace; padding: 4px; margin-botto'
html += b'm: 5px; background-color: black; color: white; border-radius'
html += b': 5px; opacity: 0.85; overflow-x: scroll; } .debugInfo { tex'
html += b't-align: end; font-size: 10pt; margin-top: 2px; color: rgb(6'
html += b'4, 64, 64); } ul { margin-top: 0; margin-left: 0px; padding-'
html += b'left: 20px; } .inputField { position: relative; width: 32px;'
html += b' height: 24px; font-size: 14pt; border-style: solid; border-'
html += b'color: black; border-radius: 5px; border-width: 0.2; padding'
html += b'-left: 5px; padding-right: 5px; outline-color: black; backgr'
html += b'ound-color: transparent; margin: 1px; } .inputField:focus { '
html += b'outline-color: maroon; } .equationPreview { position: absolu'
html += b'te; top: 120%; left: 0%; padding-left: 8px; padding-right: 8'
html += b'px; padding-top: 4px; padding-bottom: 4px; background-color:'
html += b' rgb(128, 0, 0); border-radius: 5px; font-size: 12pt; color:'
html += b' white; text-align: start; z-index: 20; opacity: 0.95; } .bu'
html += b'tton { padding-left: 8px; padding-right: 8px; padding-top: 5'
html += b'px; padding-bottom: 5px; font-size: 12pt; background-color: '
html += b'rgb(0, 150, 0); color: white; border-style: none; border-rad'
html += b'ius: 4px; height: 36px; cursor: pointer; } .buttonRow { disp'
html += b'lay: flex; align-items: baseline; margin-top: 12px; } .matri'
html += b'xResizeButton { width: 20px; background-color: black; color:'
html += b' #fff; text-align: center; border-radius: 3px; position: abs'
html += b'olute; z-index: 1; height: 20px; cursor: pointer; margin-bot'
html += b'tom: 3px; } a { color: black; text-decoration: underline; } '
html += b'</style> </head> <body> <h1 id="title"></h1> <div class="aut'
html += b'hor" id="author"></div> <p id="courseInfo1" class="courseInf'
html += b'o"></p> <p id="courseInfo2" class="courseInfo"></p> <h1 id="'
html += b'debug" class="debugCode" style="display: none">DEBUG VERSION'
html += b'</h1> <div id="questions"></div> <p style="font-size: 8pt; f'
html += b'ont-style: italic; text-align: center"> This quiz was create'
html += b'd using <a href="https://github.com/andreas-schwenk/pysell">'
html += b'pySELL</a>, the <i>Python-based Simple E-Learning Language</'
html += b'i>, written by Andreas Schwenk, GPLv3<br /> last update on <'
html += b'span id="date"></span> </p> <script>let debug = false; let q'
html += b'uizSrc = {};var sell=(()=>{var H=Object.defineProperty;var e'
html += b'e=Object.getOwnPropertyDescriptor;var te=Object.getOwnProper'
html += b'tyNames;var se=Object.prototype.hasOwnProperty;var ie=(n,e)='
html += b'>{for(var t in e)H(n,t,{get:e[t],enumerable:!0})},re=(n,e,t,'
html += b's)=>{if(e&&typeof e=="object"||typeof e=="function")for(let '
html += b'i of te(e))!se.call(n,i)&&i!==t&&H(n,i,{get:()=>e[i],enumera'
html += b'ble:!(s=ee(e,i))||s.enumerable});return n};var ne=n=>re(H({}'
html += b',"__esModule",{value:!0}),n);var le={};ie(le,{init:()=>ae});'
html += b'function v(n=[]){let e=document.createElement("div");return '
html += b'e.append(...n),e}function Q(n=[]){let e=document.createEleme'
html += b'nt("ul");return e.append(...n),e}function z(n){let e=documen'
html += b't.createElement("li");return e.appendChild(n),e}function B(n'
html += b'){let e=document.createElement("input");return e.spellcheck='
html += b'!1,e.type="text",e.classList.add("inputField"),e.style.width'
html += b'=n+"px",e}function U(){let n=document.createElement("button"'
html += b');return n.type="button",n.classList.add("button"),n}functio'
html += b'n m(n,e=[]){let t=document.createElement("span");return e.le'
html += b'ngth>0?t.append(...e):t.innerHTML=n,t}function V(n,e,t=!1){k'
html += b'atex.render(e,n,{throwOnError:!1,displayMode:t,macros:{"\\\\RR'
html += b'":"\\\\mathbb{R}","\\\\NN":"\\\\mathbb{N}","\\\\QQ":"\\\\mathbb{Q}","\\'
html += b'\\ZZ":"\\\\mathbb{Z}","\\\\CC":"\\\\mathbb{C}"}})}function C(n,e=!1'
html += b'){let t=document.createElement("span");return V(t,n,e),t}var'
html += b' O={en:"This page runs in your browser and does not store an'
html += b'y data on servers.",de:"Diese Seite wird in Ihrem Browser au'
html += b'sgef\\xFChrt und speichert keine Daten auf Servern.",es:"Esta'
html += b' p\\xE1gina se ejecuta en su navegador y no almacena ning\\xFA'
html += b'n dato en los servidores.",it:"Questa pagina viene eseguita '
html += b'nel browser e non memorizza alcun dato sui server.",fr:"Cett'
html += b'e page fonctionne dans votre navigateur et ne stocke aucune '
html += b'donn\\xE9e sur des serveurs."},_={en:"You can * this page in '
html += b'order to get new randomized tasks.",de:"Sie k\\xF6nnen diese '
html += b'Seite *, um neue randomisierte Aufgaben zu erhalten.",es:"Pu'
html += b'edes * esta p\\xE1gina para obtener nuevas tareas aleatorias.'
html += b'",it:"\\xC8 possibile * questa pagina per ottenere nuovi comp'
html += b'iti randomizzati",fr:"Vous pouvez * cette page pour obtenir '
html += b'de nouvelles t\\xE2ches al\\xE9atoires"},F={en:"reload",de:"ak'
html += b'tualisieren",es:"recargar",it:"ricaricare",fr:"recharger"},j'
html += b'={en:["awesome","great","well done","nice","you got it","goo'
html += b'd"],de:["super","gut gemacht","weiter so","richtig"],es:["im'
html += b'presionante","genial","correcto","bien hecho"],it:["fantasti'
html += b'co","grande","corretto","ben fatto"],fr:["g\\xE9nial","super"'
html += b',"correct","bien fait"]},Z={en:["try again","still some mist'
html += b'akes","wrong answer","no"],de:["leider falsch","nicht richti'
html += b'g","versuch\'s nochmal"],es:["int\\xE9ntalo de nuevo","todav\\x'
html += b'EDa algunos errores","respuesta incorrecta"],it:["riprova","'
html += b'ancora qualche errore","risposta sbagliata"],fr:["r\\xE9essay'
html += b'er","encore des erreurs","mauvaise r\\xE9ponse"]};function X('
html += b'n,e){let t=Array(e.length+1).fill(null).map(()=>Array(n.leng'
html += b'th+1).fill(null));for(let s=0;s<=n.length;s+=1)t[0][s]=s;for'
html += b'(let s=0;s<=e.length;s+=1)t[s][0]=s;for(let s=1;s<=e.length;'
html += b's+=1)for(let i=1;i<=n.length;i+=1){let a=n[i-1]===e[s-1]?0:1'
html += b';t[s][i]=Math.min(t[s][i-1]+1,t[s-1][i]+1,t[s-1][i-1]+a)}ret'
html += b'urn t[e.length][n.length]}var Y=\'<svg xmlns="http://www.w3.o'
html += b'rg/2000/svg" height="28" viewBox="0 0 448 512"><path d="M384'
html += b' 80c8.8 0 16 7.2 16 16V416c0 8.8-7.2 16-16 16H64c-8.8 0-16-7'
html += b'.2-16-16V96c0-8.8 7.2-16 16-16H384zM64 32C28.7 32 0 60.7 0 9'
html += b'6V416c0 35.3 28.7 64 64 64H384c35.3 0 64-28.7 64-64V96c0-35.'
html += b'3-28.7-64-64-64H64z"/></svg>\',q=\'<svg xmlns="http://www.w3.o'
html += b'rg/2000/svg" height="28" viewBox="0 0 448 512"><path d="M64 '
html += b'80c-8.8 0-16 7.2-16 16V416c0 8.8 7.2 16 16 16H384c8.8 0 16-7'
html += b'.2 16-16V96c0-8.8-7.2-16-16-16H64zM0 96C0 60.7 28.7 32 64 32'
html += b'H384c35.3 0 64 28.7 64 64V416c0 35.3-28.7 64-64 64H64c-35.3 '
html += b'0-64-28.7-64-64V96zM337 209L209 337c-9.4 9.4-24.6 9.4-33.9 0'
html += b'l-64-64c-9.4-9.4-9.4-24.6 0-33.9s24.6-9.4 33.9 0l47 47L303 1'
html += b'75c9.4-9.4 24.6-9.4 33.9 0s9.4 24.6 0 33.9z"/>\',K=\'<svg xmln'
html += b's="http://www.w3.org/2000/svg" height="28" viewBox="0 0 512 '
html += b'512"><path d="M464 256A208 208 0 1 0 48 256a208 208 0 1 0 41'
html += b'6 0zM0 256a256 256 0 1 1 512 0A256 256 0 1 1 0 256z"/></svg>'
html += b'\',G=\'<svg xmlns="http://www.w3.org/2000/svg" height="28" vie'
html += b'wBox="0 0 512 512"><path d="M256 48a208 208 0 1 1 0 416 208 '
html += b'208 0 1 1 0-416zm0 464A256 256 0 1 0 256 0a256 256 0 1 0 0 5'
html += b'12zM369 209c9.4-9.4 9.4-24.6 0-33.9s-24.6-9.4-33.9 0l-111 11'
html += b'1-47-47c-9.4-9.4-24.6-9.4-33.9 0s-9.4 24.6 0 33.9l64 64c9.4 '
html += b'9.4 24.6 9.4 33.9 0L369 209z"/></svg>\',T=\'<svg xmlns="http:/'
html += b'/www.w3.org/2000/svg" height="25" viewBox="0 0 384 512" fill'
html += b'="white"><path d="M73 39c-14.8-9.1-33.4-9.4-48.5-.9S0 62.6 0'
html += b' 80V432c0 17.4 9.4 33.4 24.5 41.9s33.7 8.1 48.5-.9L361 297c1'
html += b'4.3-8.7 23-24.2 23-41s-8.7-32.2-23-41L73 39z"/></svg>\',J=\'<s'
html += b'vg xmlns="http://www.w3.org/2000/svg" height="25" viewBox="0'
html += b' 0 512 512" fill="white"><path d="M0 224c0 17.7 14.3 32 32 3'
html += b'2s32-14.3 32-32c0-53 43-96 96-96H320v32c0 12.9 7.8 24.6 19.8'
html += b' 29.6s25.7 2.2 34.9-6.9l64-64c12.5-12.5 12.5-32.8 0-45.3l-64'
html += b'-64c-9.2-9.2-22.9-11.9-34.9-6.9S320 19.1 320 32V64H160C71.6 '
html += b'64 0 135.6 0 224zm512 64c0-17.7-14.3-32-32-32s-32 14.3-32 32'
html += b'c0 53-43 96-96 96H192V352c0-12.9-7.8-24.6-19.8-29.6s-25.7-2.'
html += b'2-34.9 6.9l-64 64c-12.5 12.5-12.5 32.8 0 45.3l64 64c9.2 9.2 '
html += b'22.9 11.9 34.9 6.9s19.8-16.6 19.8-29.6V448H352c88.4 0 160-71'
html += b'.6 160-160z"/></svg>\';function R(n,e=!1){let t=new Array(n);'
html += b'for(let s=0;s<n;s++)t[s]=s;if(e)for(let s=0;s<n;s++){let i=M'
html += b'ath.floor(Math.random()*n),a=Math.floor(Math.random()*n),o=t'
html += b'[i];t[i]=t[a],t[a]=o}return t}var w=class n{constructor(e,t)'
html += b'{this.m=e,this.n=t,this.v=new Array(e*t).fill("0")}getElemen'
html += b't(e,t){return e<0||e>=this.m||t<0||t>=this.n?"0":this.v[e*th'
html += b'is.n+t]}resize(e,t,s){if(e<1||e>50||t<1||t>50)return!1;let i'
html += b'=new n(e,t);i.v.fill(s);for(let a=0;a<i.m;a++)for(let o=0;o<'
html += b'i.n;o++)i.v[a*i.n+o]=this.getElement(a,o);return this.fromMa'
html += b'trix(i),!0}fromMatrix(e){this.m=e.m,this.n=e.n,this.v=[...e.'
html += b'v]}fromString(e){this.m=e.split("],").length,this.v=e.replac'
html += b'eAll("[","").replaceAll("]","").split(",").map(t=>t.trim()),'
html += b'this.n=this.v.length/this.m}getMaxCellStrlen(){let e=0;for(l'
html += b'et t of this.v)t.length>e&&(e=t.length);return e}toTeXString'
html += b'(e=!1){let t=e?"\\\\left[\\\\begin{array}":"\\\\begin{bmatrix}";e&'
html += b'&(t+="{"+"c".repeat(this.n-1)+"|c}");for(let s=0;s<this.m;s+'
html += b'+){for(let i=0;i<this.n;i++){i>0&&(t+="&");let a=this.getEle'
html += b'ment(s,i);try{a=g.parse(a).toTexString()}catch{}t+=a}t+="\\\\\\'
html += b'\\"}return t+=e?"\\\\end{array}\\\\right]":"\\\\end{bmatrix}",t}},g'
html += b'=class n{constructor(){this.root=null,this.src="",this.token'
html += b'="",this.skippedWhiteSpace=!1,this.pos=0}clone(){let e=new n'
html += b';return e.root=this.root.clone(),e}getVars(e,t="",s=null){if'
html += b'(s==null&&(s=this.root),s.op.startsWith("var:")){let i=s.op.'
html += b'substring(4);(t.length==0||t.length>0&&i.startsWith(t))&&e.a'
html += b'dd(i)}for(let i of s.c)this.getVars(e,t,i)}setVars(e,t=null)'
html += b'{t==null&&(t=this.root);for(let s of t.c)this.setVars(e,s);i'
html += b'f(t.op.startsWith("var:")){let s=t.op.substring(4);if(s in e'
html += b'){let i=e[s].clone();t.op=i.op,t.c=i.c,t.re=i.re,t.im=i.im}}'
html += b'}eval(e,t=null){let i=u.const(),a=0,o=0,l=null;switch(t==nul'
html += b'l&&(t=this.root),t.op){case"const":i=t;break;case"+":case"-"'
html += b':case"*":case"/":case"^":{let r=this.eval(e,t.c[0]),h=this.e'
html += b'val(e,t.c[1]);switch(t.op){case"+":i.re=r.re+h.re,i.im=r.im+'
html += b'h.im;break;case"-":i.re=r.re-h.re,i.im=r.im-h.im;break;case"'
html += b'*":i.re=r.re*h.re-r.im*h.im,i.im=r.re*h.im+r.im*h.re;break;c'
html += b'ase"/":a=h.re*h.re+h.im*h.im,i.re=(r.re*h.re+r.im*h.im)/a,i.'
html += b'im=(r.im*h.re-r.re*h.im)/a;break;case"^":l=new u("exp",[new '
html += b'u("*",[h,new u("ln",[r])])]),i=this.eval(e,l);break}break}ca'
html += b'se".-":case"abs":case"sin":case"sinc":case"cos":case"tan":ca'
html += b'se"cot":case"exp":case"ln":case"log":case"sqrt":{let r=this.'
html += b'eval(e,t.c[0]);switch(t.op){case".-":i.re=-r.re,i.im=-r.im;b'
html += b'reak;case"abs":i.re=Math.sqrt(r.re*r.re+r.im*r.im),i.im=0;br'
html += b'eak;case"sin":i.re=Math.sin(r.re)*Math.cosh(r.im),i.im=Math.'
html += b'cos(r.re)*Math.sinh(r.im);break;case"sinc":l=new u("/",[new '
html += b'u("sin",[r]),r]),i=this.eval(e,l);break;case"cos":i.re=Math.'
html += b'cos(r.re)*Math.cosh(r.im),i.im=-Math.sin(r.re)*Math.sinh(r.i'
html += b'm);break;case"tan":a=Math.cos(r.re)*Math.cos(r.re)+Math.sinh'
html += b'(r.im)*Math.sinh(r.im),i.re=Math.sin(r.re)*Math.cos(r.re)/a,'
html += b'i.im=Math.sinh(r.im)*Math.cosh(r.im)/a;break;case"cot":a=Mat'
html += b'h.sin(r.re)*Math.sin(r.re)+Math.sinh(r.im)*Math.sinh(r.im),i'
html += b'.re=Math.sin(r.re)*Math.cos(r.re)/a,i.im=-(Math.sinh(r.im)*M'
html += b'ath.cosh(r.im))/a;break;case"exp":i.re=Math.exp(r.re)*Math.c'
html += b'os(r.im),i.im=Math.exp(r.re)*Math.sin(r.im);break;case"ln":c'
html += b'ase"log":i.re=Math.log(Math.sqrt(r.re*r.re+r.im*r.im)),a=Mat'
html += b'h.abs(r.im)<1e-9?0:r.im,i.im=Math.atan2(a,r.re);break;case"s'
html += b'qrt":l=new u("^",[r,u.const(.5)]),i=this.eval(e,l);break}bre'
html += b'ak}default:if(t.op.startsWith("var:")){let r=t.op.substring('
html += b'4);if(r==="pi")return u.const(Math.PI);if(r==="e")return u.c'
html += b'onst(Math.E);if(r==="i")return u.const(0,1);if(r in e)return'
html += b' e[r];throw new Error("eval-error: unknown variable \'"+r+"\'"'
html += b')}else throw new Error("UNIMPLEMENTED eval \'"+t.op+"\'")}retu'
html += b'rn i}static parse(e){let t=new n;if(t.src=e,t.token="",t.ski'
html += b'ppedWhiteSpace=!1,t.pos=0,t.next(),t.root=t.parseExpr(!1),t.'
html += b'token!=="")throw new Error("remaining tokens: "+t.token+"...'
html += b'");return t}parseExpr(e){return this.parseAdd(e)}parseAdd(e)'
html += b'{let t=this.parseMul(e);for(;["+","-"].includes(this.token)&'
html += b'&!(e&&this.skippedWhiteSpace);){let s=this.token;this.next()'
html += b',t=new u(s,[t,this.parseMul(e)])}return t}parseMul(e){let t='
html += b'this.parsePow(e);for(;!(e&&this.skippedWhiteSpace);){let s="'
html += b'*";if(["*","/"].includes(this.token))s=this.token,this.next('
html += b');else if(!e&&this.token==="(")s="*";else if(this.token.leng'
html += b'th>0&&(this.isAlpha(this.token[0])||this.isNum(this.token[0]'
html += b')))s="*";else break;t=new u(s,[t,this.parsePow(e)])}return t'
html += b'}parsePow(e){let t=this.parseUnary(e);for(;["^"].includes(th'
html += b'is.token)&&!(e&&this.skippedWhiteSpace);){let s=this.token;t'
html += b'his.next(),t=new u(s,[t,this.parseUnary(e)])}return t}parseU'
html += b'nary(e){return this.token==="-"?(this.next(),new u(".-",[thi'
html += b's.parseMul(e)])):this.parseInfix(e)}parseInfix(e){if(this.to'
html += b'ken.length==0)throw new Error("expected unary");if(this.isNu'
html += b'm(this.token[0])){let t=this.token;return this.next(),this.t'
html += b'oken==="."&&(t+=".",this.next(),this.token.length>0&&(t+=thi'
html += b's.token,this.next())),new u("const",[],parseFloat(t))}else i'
html += b'f(this.fun1().length>0){let t=this.fun1();this.next(t.length'
html += b');let s=null;if(this.token==="(")if(this.next(),s=this.parse'
html += b'Expr(e),this.token+="",this.token===")")this.next();else thr'
html += b'ow Error("expected \')\'");else s=this.parseMul(!0);return new'
html += b' u(t,[s])}else if(this.token==="("){this.next();let t=this.p'
html += b'arseExpr(e);if(this.token+="",this.token===")")this.next();e'
html += b'lse throw Error("expected \')\'");return t.explicitParentheses'
html += b'=!0,t}else if(this.token==="|"){this.next();let t=this.parse'
html += b'Expr(e);if(this.token+="",this.token==="|")this.next();else '
html += b'throw Error("expected \'|\'");return new u("abs",[t])}else if('
html += b'this.isAlpha(this.token[0])){let t="";return this.token.star'
html += b'tsWith("pi")?t="pi":this.token.startsWith("C1")?t="C1":this.'
html += b'token.startsWith("C2")?t="C2":t=this.token[0],t==="I"&&(t="i'
html += b'"),this.next(t.length),new u("var:"+t,[])}else throw new Err'
html += b'or("expected unary")}static compare(e,t){let a=new Set;e.get'
html += b'Vars(a),t.getVars(a);for(let o=0;o<10;o++){let l={};for(let '
html += b'f of a)l[f]=u.const(Math.random(),Math.random());let r=e.eva'
html += b'l(l),h=t.eval(l),c=r.re-h.re,d=r.im-h.im;if(Math.sqrt(c*c+d*'
html += b'd)>1e-9)return!1}return!0}static compareODE(e,t){let s=e.clo'
html += b'ne(),i=t.clone(),a=new Set;s.getVars(a,"C"),i.getVars(a,"C")'
html += b';let o={};for(let l of a.keys())o[l]=u.const(0,0);return s.s'
html += b'etVars(o),i.setVars(o),n.compare(s,i)==!1?!1:(s=e.clone(),i='
html += b't.clone(),s.prepareODEconstantComparison(),i.prepareODEconst'
html += b'antComparison(),n.compare(s,i))}prepareODEconstantComparison'
html += b'(e=null){e==null&&(e=this.root);for(let t of e.c)this.prepar'
html += b'eODEconstantComparison(t);switch(e.op){case"+":case"-":case"'
html += b'*":case"/":case"^":{let t=[e.c[0].op,e.c[1].op],s=[t[0]==="c'
html += b'onst",t[1]==="const"],i=[t[0].startsWith("var:"),t[1].starts'
html += b'With("var:")];i[0]&&s[1]?(e.op=e.c[0].op,e.c=[]):i[1]&&s[0]?'
html += b'(e.op=e.c[1].op,e.c=[]):i[0]&&i[1]&&t[0]==t[1]?(e.op=e.c[0].'
html += b'op,e.c=[]):s[0]?(e.op=e.c[1].op,e.c=e.c[1].c):s[1]&&(e.op=e.'
html += b'c[0].op,e.c=e.c[0].c);break}case".-":case"abs":case"sin":cas'
html += b'e"sinc":case"cos":case"tan":case"cot":case"exp":case"ln":cas'
html += b'e"log":case"sqrt":e.c[0].op.startsWith("var:")?(e.op=e.c[0].'
html += b'op,e.c=[]):e.c[0].op==="const"&&(e.op="const",e.re=e.im=0,e.'
html += b'c=[]);break}}fun1(){let e=["abs","sinc","sin","cos","tan","c'
html += b'ot","exp","ln","sqrt"];for(let t of e)if(this.token.toLowerC'
html += b'ase().startsWith(t))return t;return""}next(e=-1){if(e>0&&thi'
html += b's.token.length>e){this.token=this.token.substring(e),this.sk'
html += b'ippedWhiteSpace=!1;return}this.token="";let t=!1,s=this.src.'
html += b'length;for(this.skippedWhiteSpace=!1;this.pos<s&&`\t\n `.inclu'
html += b'des(this.src[this.pos]);)this.skippedWhiteSpace=!0,this.pos+'
html += b'+;for(;!t&&this.pos<s;){let i=this.src[this.pos];if(this.tok'
html += b'en.length>0&&(this.isNum(this.token[0])&&this.isAlpha(i)||th'
html += b'is.isAlpha(this.token[0])&&this.isNum(i))&&this.token!="C")r'
html += b'eturn;if(`^%#*$()[]{},.:;+-*/_!<>=?|\t\n `.includes(i)){if(thi'
html += b's.token.length>0)return;t=!0}`\t\n `.includes(i)==!1&&(this.to'
html += b'ken+=i),this.pos++}}isNum(e){return e.charCodeAt(0)>=48&&e.c'
html += b'harCodeAt(0)<=57}isAlpha(e){return e.charCodeAt(0)>=65&&e.ch'
html += b'arCodeAt(0)<=90||e.charCodeAt(0)>=97&&e.charCodeAt(0)<=122||'
html += b'e==="_"}toString(){return this.root==null?"":this.root.toStr'
html += b'ing()}toTexString(){return this.root==null?"":this.root.toTe'
html += b'xString()}},u=class n{constructor(e,t,s=0,i=0){this.op=e,thi'
html += b's.c=t,this.re=s,this.im=i,this.explicitParentheses=!1}clone('
html += b'){let e=new n(this.op,this.c.map(t=>t.clone()),this.re,this.'
html += b'im);return e.explicitParentheses=this.explicitParentheses,e}'
html += b'static const(e=0,t=0){return new n("const",[],e,t)}compare(e'
html += b',t=0,s=1e-9){let i=this.re-e,a=this.im-t;return Math.sqrt(i*'
html += b'i+a*a)<s}toString(){let e="";if(this.op==="const"){let t=Mat'
html += b'h.abs(this.re)>1e-14,s=Math.abs(this.im)>1e-14;t&&s&&this.im'
html += b'>=0?e="("+this.re+"+"+this.im+"i)":t&&s&&this.im<0?e="("+thi'
html += b's.re+"-"+-this.im+"i)":t&&this.re>0?e=""+this.re:t&&this.re<'
html += b'0?e="("+this.re+")":s?e="("+this.im+"i)":e="0"}else this.op.'
html += b'startsWith("var")?e=this.op.split(":")[1]:this.c.length==1?e'
html += b'=(this.op===".-"?"-":this.op)+"("+this.c.toString()+")":e="('
html += b'"+this.c.map(t=>t.toString()).join(this.op)+")";return e}toT'
html += b'exString(e=!1){let s="";switch(this.op){case"const":{let i=M'
html += b'ath.abs(this.re)>1e-9,a=Math.abs(this.im)>1e-9,o=i?""+this.r'
html += b'e:"",l=a?""+this.im+"i":"";l==="1i"?l="i":l==="-1i"&&(l="-i"'
html += b'),!i&&!a?s="0":(a&&this.im>=0&&i&&(l="+"+l),s=o+l);break}cas'
html += b'e".-":s="-"+this.c[0].toTexString();break;case"+":case"-":ca'
html += b'se"*":case"^":{let i=this.c[0].toTexString(),a=this.c[1].toT'
html += b'exString(),o=this.op==="*"?"\\\\cdot ":this.op;s="{"+i+"}"+o+"'
html += b'{"+a+"}";break}case"/":{let i=this.c[0].toTexString(!0),a=th'
html += b'is.c[1].toTexString(!0);s="\\\\frac{"+i+"}{"+a+"}";break}case"'
html += b'sin":case"sinc":case"cos":case"tan":case"cot":case"exp":case'
html += b'"ln":{let i=this.c[0].toTexString(!0);s+="\\\\"+this.op+"\\\\lef'
html += b't("+i+"\\\\right)";break}case"sqrt":{let i=this.c[0].toTexStri'
html += b'ng(!0);s+="\\\\"+this.op+"{"+i+"}";break}case"abs":{let i=this'
html += b'.c[0].toTexString(!0);s+="\\\\left|"+i+"\\\\right|";break}defaul'
html += b't:if(this.op.startsWith("var:")){let i=this.op.substring(4);'
html += b'switch(i){case"pi":i="\\\\pi";break}s=" "+i+" "}else{let i="wa'
html += b'rning: Node.toString(..):";i+=" unimplemented operator \'"+th'
html += b'is.op+"\'",console.log(i),s=this.op,this.c.length>0&&(s+="\\\\l'
html += b'eft({"+this.c.map(a=>a.toTexString(!0)).join(",")+"}\\\\right)'
html += b'")}}return!e&&this.explicitParentheses&&(s="\\\\left({"+s+"}\\\\'
html += b'right)"),s}};function $(n){n.feedbackSpan.innerHTML="",n.num'
html += b'Checked=0,n.numCorrect=0;for(let s in n.expected){let i=n.ty'
html += b'pes[s],a=n.student[s],o=n.expected[s];switch(i){case"bool":n'
html += b'.numChecked++,a===o&&n.numCorrect++;break;case"string":{n.nu'
html += b'mChecked++;let l=n.gapInputs[s],r=a.trim().toUpperCase(),h=o'
html += b'.trim().toUpperCase().split("|"),c=!1;for(let d of h)if(X(r,'
html += b'd)<=1){c=!0,n.numCorrect++,n.gapInputs[s].value=d,n.student['
html += b's]=d;break}l.style.color=c?"black":"white",l.style.backgroun'
html += b'dColor=c?"transparent":"maroon";break}case"int":n.numChecked'
html += b'++,Math.abs(parseFloat(a)-parseFloat(o))<1e-9&&n.numCorrect+'
html += b'+;break;case"float":case"term":{n.numChecked++;try{let l=g.p'
html += b'arse(o),r=g.parse(a),h=!1;n.src.is_ode?h=g.compareODE(l,r):h'
html += b'=g.compare(l,r),h&&n.numCorrect++}catch(l){n.debug&&(console'
html += b'.log("term invalid"),console.log(l))}break}case"vector":case'
html += b'"complex":case"set":{let l=o.split(",");n.numChecked+=l.leng'
html += b'th;let r=[];for(let h=0;h<l.length;h++)r.push(n.student[s+"-'
html += b'"+h]);if(i==="set")for(let h=0;h<l.length;h++)try{let c=g.pa'
html += b'rse(l[h]);for(let d=0;d<r.length;d++){let p=g.parse(r[d]);if'
html += b'(g.compare(c,p)){n.numCorrect++;break}}}catch(c){n.debug&&co'
html += b'nsole.log(c)}else for(let h=0;h<l.length;h++)try{let c=g.par'
html += b'se(r[h]),d=g.parse(l[h]);g.compare(c,d)&&n.numCorrect++}catc'
html += b'h(c){n.debug&&console.log(c)}break}case"matrix":{let l=new w'
html += b'(0,0);l.fromString(o),n.numChecked+=l.m*l.n;for(let r=0;r<l.'
html += b'm;r++)for(let h=0;h<l.n;h++){let c=r*l.n+h;a=n.student[s+"-"'
html += b'+c];let d=l.v[c];try{let p=g.parse(d),f=g.parse(a);g.compare'
html += b'(p,f)&&n.numCorrect++}catch(p){n.debug&&console.log(p)}}brea'
html += b'k}default:n.feedbackSpan.innerHTML="UNIMPLEMENTED EVAL OF TY'
html += b'PE "+i}}n.state=n.numCorrect==n.numChecked?x.passed:x.errors'
html += b',n.updateVisualQuestionState();let e=n.state===x.passed?j[n.'
html += b'language]:Z[n.language],t=e[Math.floor(Math.random()*e.lengt'
html += b'h)];n.feedbackPopupDiv.innerHTML=t,n.feedbackPopupDiv.style.'
html += b'color=n.state===x.passed?"green":"maroon",n.feedbackPopupDiv'
html += b'.style.display="block",setTimeout(()=>{n.feedbackPopupDiv.st'
html += b'yle.display="none"},500),n.state===x.passed?n.src.instances.'
html += b'length>0?n.checkAndRepeatBtn.innerHTML=J:n.checkAndRepeatBtn'
html += b'.style.display="none":n.checkAndRepeatBtn.innerHTML=T}var L='
html += b'class{constructor(e,t,s,i){t.student[s]="",this.question=t,t'
html += b'his.inputId=s,s.length==0&&(this.inputId="gap-"+t.gapIdx,t.t'
html += b'ypes[this.inputId]="string",t.expected[this.inputId]=i,t.gap'
html += b'Idx++);let a=i.split("|"),o=0;for(let c=0;c<a.length;c++){le'
html += b't d=a[c];d.length>o&&(o=d.length)}let l=m("");e.appendChild('
html += b'l);let r=Math.max(o*15,24),h=B(r);if(t.gapInputs[this.inputI'
html += b'd]=h,h.addEventListener("keyup",()=>{this.question.editedQue'
html += b'stion(),h.value=h.value.toUpperCase(),this.question.student['
html += b'this.inputId]=h.value.trim()}),l.appendChild(h),this.questio'
html += b'n.showSolution&&(this.question.student[this.inputId]=h.value'
html += b'=a[0],a.length>1)){let c=m("["+a.join("|")+"]");c.style.font'
html += b'Size="small",c.style.textDecoration="underline",l.appendChil'
html += b'd(c)}}},M=class{constructor(e,t,s,i,a,o){t.student[s]="",thi'
html += b's.question=t,this.inputId=s,this.outerSpan=m(""),this.outerS'
html += b'pan.style.position="relative",e.appendChild(this.outerSpan),'
html += b'this.inputElement=B(Math.max(i*12,48)),this.outerSpan.append'
html += b'Child(this.inputElement),this.equationPreviewDiv=v(),this.eq'
html += b'uationPreviewDiv.classList.add("equationPreview"),this.equat'
html += b'ionPreviewDiv.style.display="none",this.outerSpan.appendChil'
html += b'd(this.equationPreviewDiv),this.inputElement.addEventListene'
html += b'r("click",()=>{this.question.editedQuestion(),this.edited()}'
html += b'),this.inputElement.addEventListener("keyup",()=>{this.quest'
html += b'ion.editedQuestion(),this.edited()}),this.inputElement.addEv'
html += b'entListener("focusout",()=>{this.equationPreviewDiv.innerHTM'
html += b'L="",this.equationPreviewDiv.style.display="none"}),this.inp'
html += b'utElement.addEventListener("keydown",l=>{let r="abcdefghijkl'
html += b'mnopqrstuvwxyz";r+="ABCDEFGHIJKLMNOPQRSTUVWXYZ",r+="01234567'
html += b'89",r+="+-*/^(). <>=|",o&&(r="-0123456789"),l.key.length<3&&'
html += b'r.includes(l.key)==!1&&l.preventDefault();let h=this.inputEl'
html += b'ement.value.length*12;this.inputElement.offsetWidth<h&&(this'
html += b'.inputElement.style.width=""+h+"px")}),this.question.showSol'
html += b'ution&&(t.student[s]=this.inputElement.value=a)}edited(){let'
html += b' e=this.inputElement.value.trim(),t="",s=!1;try{let i=g.pars'
html += b'e(e);s=i.root.op==="const",t=i.toTexString(),this.inputEleme'
html += b'nt.style.color="black",this.equationPreviewDiv.style.backgro'
html += b'undColor="green"}catch{t=e.replaceAll("^","\\\\hat{~}").replac'
html += b'eAll("_","\\\\_"),this.inputElement.style.color="maroon",this.'
html += b'equationPreviewDiv.style.backgroundColor="maroon"}V(this.equ'
html += b'ationPreviewDiv,t,!0),this.equationPreviewDiv.style.display='
html += b'e.length>0&&!s?"block":"none",this.question.student[this.inp'
html += b'utId]=e}},I=class{constructor(e,t,s,i){this.parent=e,this.qu'
html += b'estion=t,this.inputId=s,this.matExpected=new w(0,0),this.mat'
html += b'Expected.fromString(i),this.matStudent=new w(this.matExpecte'
html += b'd.m==1?1:3,this.matExpected.n==1?1:3),t.showSolution&&this.m'
html += b'atStudent.fromMatrix(this.matExpected),this.genMatrixDom()}g'
html += b'enMatrixDom(){let e=v();this.parent.innerHTML="",this.parent'
html += b'.appendChild(e),e.style.position="relative",e.style.display='
html += b'"inline-block";let t=document.createElement("table");e.appen'
html += b'dChild(t);let s=this.matExpected.getMaxCellStrlen();for(let '
html += b'p=0;p<this.matStudent.m;p++){let f=document.createElement("t'
html += b'r");t.appendChild(f),p==0&&f.appendChild(this.generateMatrix'
html += b'Parenthesis(!0,this.matStudent.m));for(let k=0;k<this.matStu'
html += b'dent.n;k++){let b=p*this.matStudent.n+k,E=document.createEle'
html += b'ment("td");f.appendChild(E);let A=this.inputId+"-"+b;new M(E'
html += b',this.question,A,s,this.matStudent.v[b],!1)}p==0&&f.appendCh'
html += b'ild(this.generateMatrixParenthesis(!1,this.matStudent.m))}le'
html += b't i=["+","-","+","-"],a=[0,0,1,-1],o=[1,-1,0,0],l=[0,22,888,'
html += b'888],r=[888,888,-22,-22],h=[-22,-22,0,22],c=[this.matExpecte'
html += b'd.n!=1,this.matExpected.n!=1,this.matExpected.m!=1,this.matE'
html += b'xpected.m!=1],d=[this.matStudent.n>=10,this.matStudent.n<=1,'
html += b'this.matStudent.m>=10,this.matStudent.m<=1];for(let p=0;p<4;'
html += b'p++){if(c[p]==!1)continue;let f=m(i[p]);l[p]!=888&&(f.style.'
html += b'top=""+l[p]+"px"),r[p]!=888&&(f.style.bottom=""+r[p]+"px"),h'
html += b'[p]!=888&&(f.style.right=""+h[p]+"px"),f.classList.add("matr'
html += b'ixResizeButton"),e.appendChild(f),d[p]?f.style.opacity="0.5"'
html += b':f.addEventListener("click",()=>{this.matStudent.resize(this'
html += b'.matStudent.m+a[p],this.matStudent.n+o[p],"0"),this.genMatri'
html += b'xDom()})}}generateMatrixParenthesis(e,t){let s=document.crea'
html += b'teElement("td");s.style.width="3px";for(let i of["Top",e?"Le'
html += b'ft":"Right","Bottom"])s.style["border"+i+"Width"]="2px",s.st'
html += b'yle["border"+i+"Style"]="solid";return s.rowSpan=t,s}};var x'
html += b'={init:0,errors:1,passed:2},P=class{constructor(e,t,s,i){thi'
html += b's.state=x.init,this.language=s,this.src=t,this.debug=i,this.'
html += b'instanceOrder=R(t.instances.length,!0),this.instanceIdx=0,th'
html += b'is.choiceIdx=0,this.gapIdx=0,this.expected={},this.types={},'
html += b'this.student={},this.gapInputs={},this.parentDiv=e,this.ques'
html += b'tionDiv=null,this.feedbackPopupDiv=null,this.titleDiv=null,t'
html += b'his.checkAndRepeatBtn=null,this.showSolution=!1,this.feedbac'
html += b'kSpan=null,this.numCorrect=0,this.numChecked=0}reset(){this.'
html += b'instanceIdx=(this.instanceIdx+1)%this.src.instances.length}g'
html += b'etCurrentInstance(){let e=this.instanceOrder[this.instanceId'
html += b'x];return this.src.instances[e]}editedQuestion(){this.state='
html += b'x.init,this.updateVisualQuestionState(),this.questionDiv.sty'
html += b'le.color="black",this.checkAndRepeatBtn.innerHTML=T,this.che'
html += b'ckAndRepeatBtn.style.display="block",this.checkAndRepeatBtn.'
html += b'style.color="black"}updateVisualQuestionState(){let e="black'
html += b'",t="transparent";switch(this.state){case x.init:e="rgb(0,0,'
html += b'0)",t="transparent";break;case x.passed:e="rgb(0,150,0)",t="'
html += b'rgba(0,150,0, 0.025)";break;case x.errors:e="rgb(150,0,0)",t'
html += b'="rgba(150,0,0, 0.025)",this.numChecked>=5&&(this.feedbackSp'
html += b'an.innerHTML=""+this.numCorrect+" / "+this.numChecked);break'
html += b'}this.questionDiv.style.color=this.feedbackSpan.style.color='
html += b'this.titleDiv.style.color=this.checkAndRepeatBtn.style.backg'
html += b'roundColor=this.questionDiv.style.borderColor=e,this.questio'
html += b'nDiv.style.backgroundColor=t}populateDom(){if(this.parentDiv'
html += b'.innerHTML="",this.questionDiv=v(),this.parentDiv.appendChil'
html += b'd(this.questionDiv),this.questionDiv.classList.add("question'
html += b'"),this.feedbackPopupDiv=v(),this.feedbackPopupDiv.classList'
html += b'.add("questionFeedback"),this.questionDiv.appendChild(this.f'
html += b'eedbackPopupDiv),this.feedbackPopupDiv.innerHTML="awesome",t'
html += b'his.debug&&"src_line"in this.src){let a=v();a.classList.add('
html += b'"debugInfo"),a.innerHTML="Source code: lines "+this.src.src_'
html += b'line+"..",this.questionDiv.appendChild(a)}if(this.titleDiv=v'
html += b'(),this.questionDiv.appendChild(this.titleDiv),this.titleDiv'
html += b'.classList.add("questionTitle"),this.titleDiv.innerHTML=this'
html += b'.src.title,this.src.error.length>0){let a=m(this.src.error);'
html += b'this.questionDiv.appendChild(a),a.style.color="red";return}l'
html += b'et e=this.getCurrentInstance();if(e!=null&&"__svg_image"in e'
html += b'){let a=e.__svg_image.v,o=v();this.questionDiv.appendChild(o'
html += b');let l=document.createElement("img");o.appendChild(l),l.cla'
html += b'ssList.add("img"),l.src="data:image/svg+xml;base64,"+a}for(l'
html += b'et a of this.src.text.c)this.questionDiv.appendChild(this.ge'
html += b'nerateText(a));let t=v();this.questionDiv.appendChild(t),t.c'
html += b'lassList.add("buttonRow");let s=Object.keys(this.expected).l'
html += b'ength>0;s&&(this.checkAndRepeatBtn=U(),t.appendChild(this.ch'
html += b'eckAndRepeatBtn),this.checkAndRepeatBtn.innerHTML=T,this.che'
html += b'ckAndRepeatBtn.style.backgroundColor="black");let i=m("&nbsp'
html += b';&nbsp;&nbsp;");if(t.appendChild(i),this.feedbackSpan=m(""),'
html += b't.appendChild(this.feedbackSpan),this.debug){if(this.src.var'
html += b'iables.length>0){let l=v();l.classList.add("debugInfo"),l.in'
html += b'nerHTML="Variables generated by Python Code",this.questionDi'
html += b'v.appendChild(l);let r=v();r.classList.add("debugCode"),this'
html += b'.questionDiv.appendChild(r);let h=this.getCurrentInstance(),'
html += b'c="",d=[...this.src.variables];d.sort();for(let p of d){let '
html += b'f=h[p].t,k=h[p].v;switch(f){case"vector":k="["+k+"]";break;c'
html += b'ase"set":k="{"+k+"}";break}c+=f+" "+p+" = "+k+"<br/>"}r.inne'
html += b'rHTML=c}let a=["python_src_html","text_src_html"],o=["Python'
html += b' Source Code","Text Source Code"];for(let l=0;l<a.length;l++'
html += b'){let r=a[l];if(r in this.src&&this.src[r].length>0){let h=v'
html += b'();h.classList.add("debugInfo"),h.innerHTML=o[l],this.questi'
html += b'onDiv.appendChild(h);let c=v();c.classList.add("debugCode"),'
html += b'this.questionDiv.append(c),c.innerHTML=this.src[r]}}}s&&this'
html += b'.checkAndRepeatBtn.addEventListener("click",()=>{this.state='
html += b'=x.passed?(this.state=x.init,this.reset(),this.populateDom()'
html += b'):$(this)})}generateMathString(e){let t="";switch(e.t){case"'
html += b'math":case"display-math":for(let s of e.c){let i=this.genera'
html += b'teMathString(s);s.t==="var"&&t.includes("!PM")&&(i.startsWit'
html += b'h("{-")?(i="{"+i.substring(2),t=t.replaceAll("!PM","-")):t=t'
html += b'.replaceAll("!PM","+")),t+=i}break;case"text":return e.d;cas'
html += b'e"plus_minus":{t+=" !PM ";break}case"var":{let s=this.getCur'
html += b'rentInstance(),i=s[e.d].t,a=s[e.d].v;switch(i){case"vector":'
html += b'return"\\\\left["+a+"\\\\right]";case"set":return"\\\\left\\\\{"+a+"'
html += b'\\\\right\\\\}";case"complex":{let o=a.split(","),l=parseFloat(o'
html += b'[0]),r=parseFloat(o[1]);return u.const(l,r).toTexString()}ca'
html += b'se"matrix":{let o=new w(0,0);return o.fromString(a),t=o.toTe'
html += b'XString(e.d.includes("augmented")),t}case"term":{try{t=g.par'
html += b'se(a).toTexString()}catch{}break}default:t=a}}}return e.t==='
html += b'"plus_minus"?t:"{"+t+"}"}generateText(e,t=!1){switch(e.t){ca'
html += b'se"paragraph":case"span":{let s=document.createElement(e.t=='
html += b'"span"||t?"span":"p");for(let i of e.c)s.appendChild(this.ge'
html += b'nerateText(i));return s}case"text":return m(e.d);case"code":'
html += b'{let s=m(e.d);return s.classList.add("code"),s}case"italic":'
html += b'case"bold":{let s=m("");return s.append(...e.c.map(i=>this.g'
html += b'enerateText(i))),e.t==="bold"?s.style.fontWeight="bold":s.st'
html += b'yle.fontStyle="italic",s}case"math":case"display-math":{let '
html += b's=this.generateMathString(e);return C(s,e.t==="display-math"'
html += b')}case"string_var":{let s=m(""),i=this.getCurrentInstance(),'
html += b'a=i[e.d].t,o=i[e.d].v;return a==="string"?s.innerHTML=o:(s.i'
html += b'nnerHTML="EXPECTED VARIABLE OF TYPE STRING",s.style.color="r'
html += b'ed"),s}case"gap":{let s=m("");return new L(s,this,"",e.d),s}'
html += b'case"input":case"input2":{let s=e.t==="input2",i=m("");i.sty'
html += b'le.verticalAlign="text-bottom";let a=e.d,o=this.getCurrentIn'
html += b'stance()[a];if(this.expected[a]=o.v,this.types[a]=o.t,!s)swi'
html += b'tch(o.t){case"set":i.append(C("\\\\{"),m(" "));break;case"vect'
html += b'or":i.append(C("["),m(" "));break}if(o.t==="string")new L(i,'
html += b'this,a,this.expected[a]);else if(o.t==="vector"||o.t==="set"'
html += b'){let l=o.v.split(","),r=l.length;for(let h=0;h<r;h++){h>0&&'
html += b'i.appendChild(m(" , "));let c=a+"-"+h;new M(i,this,c,l[h].le'
html += b'ngth,l[h],!1)}}else if(o.t==="matrix"){let l=v();i.appendChi'
html += b'ld(l),new I(l,this,a,o.v)}else if(o.t==="complex"){let l=o.v'
html += b'.split(",");new M(i,this,a+"-0",l[0].length,l[0],!1),i.appen'
html += b'd(m(" "),C("+"),m(" ")),new M(i,this,a+"-1",l[1].length,l[1]'
html += b',!1),i.append(m(" "),C("i"))}else{let l=o.t==="int";new M(i,'
html += b'this,a,o.v.length,o.v,l)}if(!s)switch(o.t){case"set":i.appen'
html += b'd(m(" "),C("\\\\}"));break;case"vector":i.append(m(" "),C("]")'
html += b');break}return i}case"itemize":return Q(e.c.map(s=>z(this.ge'
html += b'nerateText(s))));case"single-choice":case"multi-choice":{let'
html += b' s=e.t=="multi-choice",i=document.createElement("table"),a=e'
html += b'.c.length,o=this.debug==!1,l=R(a,o),r=s?q:G,h=s?Y:K,c=[],d=['
html += b'];for(let p=0;p<a;p++){let f=l[p],k=e.c[f],b="mc-"+this.choi'
html += b'ceIdx+"-"+f;d.push(b);let E=k.c[0].t=="bool"?k.c[0].d:this.g'
html += b'etCurrentInstance()[k.c[0].d].v;this.expected[b]=E,this.type'
html += b's[b]="bool",this.student[b]=this.showSolution?E:"false";let '
html += b'A=this.generateText(k.c[1],!0),y=document.createElement("tr"'
html += b');i.appendChild(y),y.style.cursor="pointer";let S=document.c'
html += b'reateElement("td");c.push(S),y.appendChild(S),S.innerHTML=th'
html += b'is.student[b]=="true"?r:h;let W=document.createElement("td")'
html += b';y.appendChild(W),W.appendChild(A),s?y.addEventListener("cli'
html += b'ck",()=>{this.editedQuestion(),this.student[b]=this.student['
html += b'b]==="true"?"false":"true",this.student[b]==="true"?S.innerH'
html += b'TML=r:S.innerHTML=h}):y.addEventListener("click",()=>{this.e'
html += b'ditedQuestion();for(let D of d)this.student[D]="false";this.'
html += b'student[b]="true";for(let D=0;D<d.length;D++){let N=l[D];c[N'
html += b'].innerHTML=this.student[d[N]]=="true"?r:h}})}return this.ch'
html += b'oiceIdx++,i}case"image":{let s=v(),a=e.d.split("."),o=a[a.le'
html += b'ngth-1],l=e.c[0].d,r=e.c[1].d,h=document.createElement("img"'
html += b');s.appendChild(h),h.classList.add("img"),h.style.width=l+"%'
html += b'";let c={svg:"svg+xml",png:"png",jpg:"jpeg"};return h.src="d'
html += b'ata:image/"+c[o]+";base64,"+r,s}default:{let s=m("UNIMPLEMEN'
html += b'TED("+e.t+")");return s.style.color="red",s}}}};function ae('
html += b'n,e){["en","de","es","it","fr"].includes(n.lang)==!1&&(n.lan'
html += b'g="en"),e&&(document.getElementById("debug").style.display="'
html += b'block"),document.getElementById("date").innerHTML=n.date,doc'
html += b'ument.getElementById("title").innerHTML=n.title,document.get'
html += b'ElementById("author").innerHTML=n.author,document.getElement'
html += b'ById("courseInfo1").innerHTML=O[n.lang];let t=\'<span onclick'
html += b'="location.reload()" style="text-decoration: underline; font'
html += b'-weight: bold; cursor: pointer">\'+F[n.lang]+"</span>";docume'
html += b'nt.getElementById("courseInfo2").innerHTML=_[n.lang].replace'
html += b'("*",t);let s=[],i=document.getElementById("questions"),a=1;'
html += b'for(let o of n.questions){o.title=""+a+". "+o.title;let l=v('
html += b');i.appendChild(l);let r=new P(l,o,n.lang,e);r.showSolution='
html += b'e,s.push(r),r.populateDom(),e&&o.error.length==0&&r.checkAnd'
html += b'RepeatBtn.click(),a++}}return ne(le);})();sell.init(quizSrc,'
html += b'debug);</script></body> </html> '
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
    input_dirname = os.path.dirname(input_path)
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
    out = compile(input_dirname, src)
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
