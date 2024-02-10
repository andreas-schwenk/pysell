#!/usr/bin/env python3

"""SELL - Simple E-Learning Language
AUTHOR:  Andreas Schwenk <mailto:contact@compiler-construction.com>
LICENSE: GPLv3
"""

# TODO: test python program with indents

import json, sys, numpy, types


class Lexer:
    def __init__(self, src: str):
        self.src = src
        self.token = ""
        self.pos = 0
        self.next()

    def next(self):
        self.token = ""
        stop = False
        while not stop and self.pos < len(self.src):
            ch = self.src[self.pos]
            if ch in "#*$()[]{},.:;+-*/_!<> ":
                if len(self.token) > 0:
                    return
                stop = True
            self.token += ch
            self.pos += 1


# lex = Lexer("abc 123 *blub* $123$")
# while len(lex.token) > 0:
#    print(lex.token)
#    lex.next()
# exit(0)


class TextNode:

    def __init__(self, type: str, data: str = ""):
        self.type = type
        self.data = data
        self.children = []

    def parse(self):
        if self.type == "root":
            self.children = [TextNode(" ", "")]
            lines = self.data.split("\n")
            self.data = ""
            for line in lines:
                line = line.strip()
                if len(line) == 0:
                    continue
                type = line[0]  # '[' := multi-choice, '-' := itemize, ...
                if type not in "[(-":
                    type = " "
                if type != self.children[-1].type:
                    self.children.append(TextNode(type, ""))
                self.children[-1].data += line + "\n"
            types = {
                " ": "paragraph",
                "(": "single-choice",
                "[": "multi-choice",
                "-": "itemize",
            }
            for child in self.children:
                child.type = types[child.type]
                child.parse()
        elif self.type == "multi-choice" or self.type == "single-choice":
            options = self.data.strip().split("\n")
            self.data = ""
            for option in options:
                correct = option.startswith("[x]") or option.startswith("(x)")
                node = TextNode("answer")
                self.children.append(node)
                node.children.append(TextNode("bool", "true" if correct else "false"))
                node.children.append(TextNode("paragraph", option[3:].strip()))
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
        else:
            raise Exception("unimplemented")

    def parse_span(self, lex: Lexer):
        # grammar: span = { item };
        #          item = bold | math | text | input;
        #          bold = "*" { item } "*";
        #          math = "$" { item } "$";
        #          input = "#" var;
        #          text = otherwise;
        span = TextNode("span")
        while lex.token != "":
            span.children.append(self.parse_item(lex))
        return span

    def parse_item(self, lex: Lexer):
        if lex.token == "*":
            return self.parse_bold(lex)
        elif lex.token == "$":
            return self.parse_math(lex)
        elif lex.token == "#":
            return self.parse_input(lex)
        else:
            n = TextNode("text", lex.token)
            lex.next()
            return n

    def parse_bold(self, lex: Lexer):
        bold = TextNode("bold")
        if lex.token == "*":
            lex.next()
        while lex.token != "" and lex.token != "*":
            bold.children.append(self.parse_item(lex))
        if lex.token == "*":
            lex.next()
        return bold

    def parse_math(self, lex: Lexer):
        math = TextNode("math")
        if lex.token == "$":
            lex.next()
        while lex.token != "" and lex.token != "$":
            math.children.append(self.parse_item(lex))
        if lex.token == "$":
            lex.next()
        return math

    def parse_input(self, lex: Lexer):
        input = TextNode("input")
        if lex.token == "#":
            lex.next()
        input.data = lex.token.strip()
        lex.next()
        return input

    def optimize(self):
        children_opt = []
        for c in self.children:
            opt = c.optimize()
            if (
                opt.type == "text"
                and len(children_opt) > 0
                and children_opt[-1].type == "text"
            ):
                children_opt[-1].data += opt.data
            else:
                children_opt.append(opt)
        self.children = children_opt
        return self

    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "data": self.data,
            "children": list(map(lambda o: o.to_dict(), self.children)),
        }


class Question:
    """quiz question instance"""

    def __init__(self):
        self.title = ""
        self.python_src = ""
        self.variables = set()
        self.instances = []
        self.text_src = ""
        self.text = None
        self.error = ""

    def build(self):
        if len(self.python_src) > 0:
            for i in range(0, 5):
                # TODO: some or all instances may be equal!!
                res = self.run_python_code()
                self.instances.append(res)
        self.text = TextNode("root", self.text_src)
        self.text.parse()
        self.post_process_text(self.text)
        self.text.optimize()

    def post_process_text(self, node, math=False):
        for c in node.children:
            self.post_process_text(c, math or node.type == "math")
        if node.type == "input":
            var_id = node.data
            if var_id not in self.variables:
                self.error += "Unknown input variable '" + var_id + "'. "
        elif math and node.type == "text":
            var_id = node.data
            if var_id in self.variables:
                node.type = "var"

    def run_python_code(self) -> dict:
        locals = {}
        res = {}
        try:
            exec(self.python_src, globals(), locals)
        except Exception as e:
            # print(e)
            self.error += e + ". "
            return res
        for id in locals:
            value = locals[id]
            if isinstance(value, types.ModuleType):
                continue
            self.variables.add(id)
            if isinstance(value, numpy.matrix):
                rows, cols = value.shape
                v = numpy.array2string(value, separator=",").replace("\\n", "")
                # TODO: res
            elif isinstance(value, int):
                res[id] = {"type": "int", "value": str(value)}
            elif isinstance(value, float):
                res[id] = {"type": "float", "value": str(value)}
            elif isinstance(value, complex):
                v = str(value).replace("j", "i")
                if v.startswith("("):
                    v = v[1:-1]
                res[id] = {"type": "complex", "value": v}
            elif isinstance(value, set):
                res[id] = {"type": "set", "value": str(value)}
            else:
                res[id] = {"type": "unknown", "value": str(value)}
        return res

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "error": self.error,
            "variables": list(self.variables),
            "instances": self.instances,
            "text": self.text.to_dict(),
        }


def compile(src: str) -> str:
    """compiles an"""

    lines = src.split("\n")

    lang = "en"
    title = ""
    author = ""
    info = ""
    questions = []

    question = None
    parsing_python = False
    for line in lines:
        line = line.strip()
        if line.startswith("LANG"):
            lang = line[4:].strip()
        elif line.startswith("TITLE"):
            title = line[5:].strip()
        elif line.startswith("AUTHOR"):
            author = line[6:].strip()
        elif line.startswith("INFO"):
            info = line[4:].strip()
        elif line.startswith("QUESTION"):
            question = Question()
            questions.append(question)
            question.title = line[8:].strip()
            parsing_python = False
        elif question != None:
            if line.startswith('"""'):
                parsing_python = not parsing_python
            else:
                if parsing_python:
                    question.python_src += line + "\n"
                else:
                    question.text_src += line + "\n"
    for question in questions:
        question.build()
    output = {
        "lang": lang,
        "title": title,
        "author": author,
        "info": info,
        "questions": list(map(lambda o: o.to_dict(), questions)),
    }
    output_json = json.dumps(output)
    return output_json


if __name__ == "__main__":

    # TODO: get path from args

    # read input
    f = open("examples/ex1.txt")
    src = f.read()
    f.close()
    # compile
    out = compile(src)
    # write output
    f = open("examples/ex1.json", "w")
    f.write(out)
    f.close()
    # exit normally
    sys.exit(0)
