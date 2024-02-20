/*******************************************************************************
 * pySELL - Python based Simple E-Learning Language
 * AUTHOR:  Andreas Schwenk <mailto:contact@compiler-construction.com>
 * LICENSE: GPLv3
 ******************************************************************************/

/**
 * @param {number} n
 * @param {boolean} [shuffled=false]
 * @returns {number[]}
 */
export function range(n, shuffled = false) {
  let arr = new Array(n);
  for (let i = 0; i < n; i++) arr[i] = i;
  if (shuffled)
    for (let i = 0; i < n; i++) {
      let u = Math.floor(Math.random() * n);
      let v = Math.floor(Math.random() * n);
      let t = arr[u];
      arr[u] = arr[v];
      arr[v] = t;
    }
  return arr;
}

export class Matrix {
  /**
   * Matrix elements are strings that represent arbitrary terms
   * @param {number} m
   * @param {number} n
   */
  constructor(m, n) {
    /** @type {number} */
    this.m = m;
    /** @type {number} */
    this.n = n;
    /** @type {string[]} */
    this.v = new Array(m * n).fill("0");
  }

  /**
   * @param {number} i
   * @param {number} j
   * @returns {string} -- "0", if indices are invalid
   */
  getElement(i, j) {
    if (i < 0 || i >= this.m || j < 0 || j >= this.n) return "0";
    return this.v[i * this.n + j];
  }

  /**
   * @param {number} m
   * @param {number} n
   * @param {string} init
   * @returns {boolean} -- success
   */
  resize(m, n, init) {
    if (m < 1 || m > 50 || n < 1 || n > 50) return false;
    let mat = new Matrix(m, n);
    mat.v.fill(init);
    for (let i = 0; i < mat.m; i++)
      for (let j = 0; j < mat.n; j++)
        mat.v[i * mat.n + j] = this.getElement(i, j);
    this.fromMatrix(mat);
    return true;
  }

  /**
   * @param {Matrix} mat
   */
  fromMatrix(mat) {
    this.m = mat.m;
    this.n = mat.n;
    this.v = [...mat.v];
  }

  /**
   * parses e.g. "[[1,2,3],[4,5,6]]"
   * @param {string} s
   */
  fromString(s) {
    this.m = s.split("],").length;
    this.v = s
      .replaceAll("[", "")
      .replaceAll("]", "")
      .split(",")
      .map((e) => e.trim());
    this.n = this.v.length / this.m;
  }

  /**
   * @returns {number}
   */
  getMaxCellStrlen() {
    let m = 0;
    for (let vi of this.v) {
      if (vi.length > m) m = vi.length;
    }
    return m;
  }

  /**
   * @param {boolean} [augmented=false]
   * @returns {string}
   */
  toTeXString(augmented = false) {
    // TODO switch "[]" and "()" based on language
    let s = augmented ? "\\left[\\begin{array}" : "\\begin{bmatrix}";
    if (augmented) s += "{" + "c".repeat(this.n - 1) + "|c}";
    for (let i = 0; i < this.m; i++) {
      for (let j = 0; j < this.n; j++) {
        if (j > 0) s += "&";
        let e = this.getElement(i, j);
        try {
          e = Term.parse(e).toTexString();
        } catch (e) {
          // failed, so keep input...
        }
        s += e;
      }
      s += "\\\\";
    }
    s += augmented ? "\\end{array}\\right]" : "\\end{bmatrix}";
    return s;
  }
}

/**
 * @param {string} s
 * @returns {number}
 */
function pf(s) {
  return parseFloat(s);
}

export class Node {
  /**
   * @param {string} op
   * @param {Node[]} c
   * @param {number} [re=0]
   * @param {number} [im=0]
   */
  constructor(op, c, re = 0, im = 0) {
    /** @type {string} -- the operation (const, var, +, -, *, ...) */
    this.op = op;
    /** @type {Node[]} -- the children, i.e. operands */
    this.c = c;
    /** @type {number} -- the real part (only valid for this.op==="const") */
    this.re = re;
    /** @type {number} -- the imag part (only valid for this.op==="const") */
    this.im = im;
    /** @type {boolean} -- used e.g. for TeX conversion */
    this.explicitParentheses = false;
  }

  /**
   * @param {number} re
   * @param {number} im
   */
  static const(re = 0, im = 0) {
    return new Node("const", [], re, im);
  }

  /**
   * @param {number} re
   * @param {number} [im=0]
   * @param {number} [EPS=1e-9]
   * @returns {boolean}
   */
  compare(re, im = 0, EPS = 1e-9) {
    let dr = this.re - re;
    let di = this.im - im;
    return Math.sqrt(dr * dr + di * di) < EPS;
  }

  /**
   * @returns {string}
   */
  toString() {
    let s = "";
    if (this.op === "const") {
      let hasReal = Math.abs(this.re) > 1e-14;
      let hasImag = Math.abs(this.im) > 1e-14;
      if (hasReal && hasImag && this.im >= 0)
        s = "(" + this.re + "+" + this.im + "i)";
      else if (hasReal && hasImag && this.im < 0)
        s = "(" + this.re + "-" + -this.im + "i)";
      else if (hasReal) s = "" + this.re;
      else if (hasImag) s = "(" + this.im + "i)";
    } else if (this.op.startsWith("var")) {
      s = this.op.split(":")[1];
    } else if (this.c.length == 1) {
      s = (this.op === ".-" ? "-" : this.op) + "(" + this.c.toString() + ")";
    } else {
      s = "(" + this.c.map((ci) => ci.toString()).join(this.op) + ")";
    }
    return s;
  }

  /**
   * Does NOT take care for operator precedence.
   * Parentheses are ONLY generated, if attribute "explicitParentheses"
   * of Node is set (automatically filled while parsing)
   * @param {boolean} [suppressParentheses=false]
   * @returns {string}
   */
  toTexString(suppressParentheses = false) {
    const EPS = 1e-9;
    let s = "";
    switch (this.op) {
      case "const": {
        let hasRe = Math.abs(this.re) > EPS;
        let hasIm = Math.abs(this.im) > EPS;
        let re = hasRe ? "" + this.re : "";
        let im = hasIm ? "" + this.im + "i" : "";
        if (im === "1i") im = "i";
        else if (im === "-1i") im = "-i";
        if (hasIm && this.im >= 0 && hasRe) im = "+" + im;
        if (!hasRe && !hasIm) s = "0";
        else s = re + im;
        break;
      }
      case ".-": // unary minus
        s = "-" + this.c[0].toTexString();
        break;
      case "+":
      case "-":
      case "*":
      case "^": {
        let op = this.op === "*" ? "\\cdot " : this.op;
        s =
          "{" +
          this.c[0].toTexString() +
          "}" +
          op +
          "{" +
          this.c[1].toTexString() +
          "}";
        break;
      }
      case "/":
        s =
          "\\frac{" +
          this.c[0].toTexString(true) +
          "}{" +
          this.c[1].toTexString(true) +
          "}";
        break;
      case "sin":
      case "sinc":
      case "cos":
      case "tan":
      case "cot":
      case "exp":
      case "ln":
        s +=
          "\\" + this.op + "\\left(" + this.c[0].toTexString(true) + "\\right)";
        break;
      case "sqrt":
        s += "\\" + this.op + "{" + this.c[0].toTexString(true) + "}";
        break;
      case "abs":
        s += "\\left|" + this.c[0].toTexString(true) + "\\right|";
        break;
      default:
        if (this.op.startsWith("var:")) {
          let id = this.op.substring(4);
          switch (id) {
            case "pi":
              id = "\\pi";
              break;
          }
          s = " " + id + " ";
        } else {
          // fallback for unimplemented cases
          let msg = "warning: Node.toString(..):";
          msg += " unimplemented operator '" + this.op + "'";
          console.log(msg);
          s = this.op;
          if (this.c.length > 0) {
            s +=
              "\\left({" +
              this.c.map((x) => x.toTexString(true)).join(",") +
              "}\\right)";
          }
        }
    }
    if (!suppressParentheses && this.explicitParentheses) {
      s = "\\left({" + s + "}\\right)";
    }
    return s;
  }
}

export class Term {
  constructor() {
    /** @type {Node} */
    this.root = null;
    /** @type {string} -- parser input string */
    this.src = "";
    /** @type {string} -- current lexer token */
    this.token = "";
    /** @type {boolean} -- true, if there was a whitespace, before this.token */
    this.skippedWhiteSpace = false;
    /** @type {number} -- current lexer position of this.src */
    this.pos = 0;
  }

  /**
   * @param {Set<string>} s
   * @param {Node} node
   */
  getVars(s, node = null) {
    if (node == null) node = this.root;
    if (node.op.startsWith("var:")) s.add(node.op.substring(4));
    for (let c of node.c) this.getVars(s, c);
  }

  /**
   *
   * @param {Object.<string,Node>} dict
   * @param {Node} [node=null]
   * @returns {Node}
   */
  eval(dict, node = null) {
    const EPS = 1e-9;
    let res = Node.const();
    let t1 = 0; // temp value
    let t2 = 0; // temp value
    let tn = null; // temp node
    if (node == null) node = this.root;
    switch (node.op) {
      case "const":
        res = node;
        break;
      case "+":
      case "-":
      case "*":
      case "/":
      case "^":
      case "==": {
        let u = this.eval(dict, node.c[0]);
        let v = this.eval(dict, node.c[1]);
        switch (node.op) {
          case "+":
            res.re = u.re + v.re;
            res.im = u.im + v.im;
            break;
          case "-":
            res.re = u.re - v.re;
            res.im = u.im - v.im;
            break;
          case "*":
            res.re = u.re * v.re - u.im * v.im;
            res.im = u.re * v.im + u.im * v.re;
            break;
          case "/":
            t1 = v.re * v.re + v.im * v.im;
            // TODO: throw error, if abs(t1)<EPS + catch when comparing terms numerically
            res.re = (u.re * v.re + u.im * v.im) / t1;
            res.im = (u.im * v.re - u.re * v.im) / t1;
            break;
          case "^":
            // u^v = exp(v*ln(u))
            tn = new Node("exp", [new Node("*", [v, new Node("ln", [u])])]);
            res = this.eval(dict, tn);
            break;
          case "==":
            t1 = u.re - v.re;
            t2 = u.im - v.im;
            res.re = Math.sqrt(t1 * t1 + t2 * t2) < EPS ? 1 : 0;
            res.im = 0;
            break;
        }
        break;
      }
      case ".-":
      case "abs":
      case "sin":
      case "sinc":
      case "cos":
      case "tan":
      case "cot":
      case "exp":
      case "ln":
      case "log":
      case "sqrt": {
        let u = this.eval(dict, node.c[0]);
        switch (node.op) {
          case ".-":
            res.re = -u.re;
            res.im = -u.im;
            break;
          case "abs":
            res.re = Math.sqrt(u.re * u.re + u.im * u.im);
            res.im = 0;
            break;
          case "sin":
            res.re = Math.sin(u.re) * Math.cosh(u.im);
            res.im = Math.cos(u.re) * Math.sinh(u.im);
            break;
          case "sinc":
            tn = new Node("/", [new Node("sin", [u]), u]);
            res = this.eval(dict, tn);
            break;
          case "cos":
            res.re = Math.cos(u.re) * Math.cosh(u.im);
            res.im = -Math.sin(u.re) * Math.sinh(u.im);
            break;
          case "tan":
            // https://planetmath.org/complextangentandcotangent
            // TODO: throw error, if abs(t1)<EPS + catch when comparing terms numerically
            t1 =
              Math.cos(u.re) * Math.cos(u.re) +
              Math.sinh(u.im) * Math.sinh(u.im);
            res.re = (Math.sin(u.re) * Math.cos(u.re)) / t1;
            res.im = (Math.sinh(u.im) * Math.cosh(u.im)) / t1;
            break;
          case "cot":
            // TODO: throw error, if abs(t1)<EPS + catch when comparing terms numerically
            t1 =
              Math.sin(u.re) * Math.sin(u.re) +
              Math.sinh(u.im) * Math.sinh(u.im);
            res.re = (Math.sin(u.re) * Math.cos(u.re)) / t1;
            res.im = -(Math.sinh(u.im) * Math.cosh(u.im)) / t1;
            break;
          case "exp":
            res.re = Math.exp(u.re) * Math.cos(u.im);
            res.im = Math.exp(u.re) * Math.sin(u.im);
            break;
          case "ln":
          case "log":
            res.re = Math.log(Math.sqrt(u.re * u.re + u.im * u.im));
            t1 = Math.abs(u.im) < EPS ? 0 : u.im; // prevent "-0" and similar
            res.im = Math.atan2(t1, u.re);
            break;
          case "sqrt": // u^(0.5)
            tn = new Node("^", [u, Node.const(0.5)]);
            res = this.eval(dict, tn);
            break;
        }
        break;
      }
      default:
        if (node.op.startsWith("var:")) {
          let id = node.op.substring(4);
          if (id === "pi") return Node.const(Math.PI);
          else if (id === "e") return Node.const(Math.E);
          else if (id === "i") return Node.const(0, 1);
          else if (id in dict) return dict[id];
          throw new Error("eval-error: unknown variable '" + id + "'");
        } else {
          throw new Error("UNIMPLEMENTED eval '" + node.op + "'");
        }
    }
    // TODO: throw error, if "too large" when comparing terms numerically
    return res;
  }

  /**
   * @param {string} src
   * expr = add { add };
   * add = mul { ("+"|"-") mul };
   * mul = pow { ("*"|"/"|epsilon) pow };  // epsilon := implicit multiplication
   * pow = unary { "^" unary };
   * unary = "-" mul | infix;
   * infix = NUM | fct1 mul | fct1 "(" expr ")" | "(" expr ")" | "|" expr "|" STR;
   * fct1 = "abs" | "sin" | "sinc" | "cos" | "tan" | "cot" | "exp" | "ln" | "sqrt";
   */
  static parse(src) {
    let term = new Term();
    term.src = src;
    term.token = "";
    term.skippedWhiteSpace = false;
    term.pos = 0;
    term.next();
    // // lexer test
    // while (term.token.length > 0) {
    //   console.log("'" + term.token + "'");
    //   term.next();
    // }
    term.root = term.parseExpr(false);
    if (term.token !== "")
      throw new Error("remaining tokens: " + term.token + "...");
    return term;
  }

  /**
   * @param {boolean} stopAtSpace
   * @returns {Node}
   */
  parseExpr(stopAtSpace) {
    let node = this.parseAdd(stopAtSpace);
    return node;
  }

  /**
   * @param {boolean} stopAtSpace
   * @returns {Node}
   */
  parseAdd(stopAtSpace) {
    let node = this.parseMul(stopAtSpace);
    while (["+", "-"].includes(this.token)) {
      if (stopAtSpace && this.skippedWhiteSpace) break;
      let op = this.token;
      this.next();
      node = new Node(op, [node, this.parseMul(stopAtSpace)]);
    }
    return node;
  }

  /**
   * @param {boolean} stopAtSpace
   * @returns {Node}
   */
  parseMul(stopAtSpace) {
    let node = this.parsePow(stopAtSpace);
    while (true) {
      if (stopAtSpace && this.skippedWhiteSpace) break;
      let op = "*";
      if (["*", "/"].includes(this.token)) {
        op = this.token;
        this.next();
      } else if (!stopAtSpace && this.token === "(") {
        op = "*";
      } else if (
        this.token.length > 0 &&
        (this.isAlpha(this.token[0]) || this.isNum(this.token[0]))
      ) {
        op = "*";
      } else {
        break;
      }
      node = new Node(op, [node, this.parsePow(stopAtSpace)]);
    }
    return node;
  }

  /**
   * @param {boolean} stopAtSpace
   * @returns {Node}
   */
  parsePow(stopAtSpace) {
    let node = this.parseUnary(stopAtSpace);
    while (["^"].includes(this.token)) {
      if (stopAtSpace && this.skippedWhiteSpace) break;
      let op = this.token;
      this.next();
      node = new Node(op, [node, this.parseUnary(stopAtSpace)]);
    }
    return node;
  }

  /**
   * @param {boolean} stopAtSpace
   * @returns {Node}
   */
  parseUnary(stopAtSpace) {
    if (this.token === "-") {
      this.next();
      return new Node(".-", [this.parseMul(stopAtSpace)]);
    }
    return this.parseInfix(stopAtSpace);
  }

  /**
   * @param {boolean} stopAtSpace
   * @returns {Node}
   */
  parseInfix(stopAtSpace) {
    if (this.token.length == 0) {
      throw new Error("expected unary");
    } else if (this.isNum(this.token[0])) {
      let v = this.token;
      this.next();
      if (this.token === ".") {
        v += ".";
        this.next();
        if (this.token.length > 0) {
          v += this.token;
          this.next();
        }
      }
      return new Node("const", [], pf(v));
    } else if (this.fun1().length > 0) {
      let op = this.fun1();
      this.next(op.length); // only consume the function id
      let arg = null;
      if (this.token === "(") {
        this.next();
        arg = this.parseExpr(stopAtSpace);
        this.token += ""; // linter hack...
        if (this.token === ")") this.next();
        else throw Error("expected ')'");
      } else {
        // if the argument is NOT embedded into parentheses, then things
        // get a bit complicated:
        //    e.g. sin 2pi == sin(2*pi), and sin 2 pi == sin(2)*pi
        // We parse only up to the next space, as indicated by "true"
        arg = this.parseMul(true);
      }
      return new Node(op, [arg]);
    } else if (this.token === "(") {
      this.next();
      let n = this.parseExpr(stopAtSpace);
      this.token += ""; // linter hack...
      if (this.token === ")") this.next();
      else throw Error("expected ')'");
      n.explicitParentheses = true;
      return n;
    } else if (this.token === "|") {
      this.next();
      let arg = this.parseExpr(stopAtSpace);
      this.token += ""; // linter hack...
      if (this.token === "|") this.next();
      else throw Error("expected '|'");
      return new Node("abs", [arg]);
    } else if (this.isAlpha(this.token[0])) {
      let id = "";
      if (this.token.startsWith("pi")) id = "pi";
      else id = this.token[0];
      this.next(id.length); // only consume next char(s)
      return new Node("var:" + id, []);
    } else throw new Error("expected unary");
  }

  /**
   * @param {Term} term
   * @return {boolean}
   */
  compare(term) {
    const EPS = 1e-9;
    const NUM_TESTS = 10; // TODO
    let vars = new Set();
    this.getVars(vars);
    term.getVars(vars);
    for (let i = 0; i < NUM_TESTS; i++) {
      /** @type {Object.<string,Node>} */
      let context = {};
      for (let v of vars) context[v] = Node.const(Math.random(), Math.random());
      let t = new Node("==", [this.root, term.root]);
      let res = this.eval(context, t); // TODO: catch DIV/0, ... -> test again
      if (Math.abs(res.re) < EPS) return false;
    }
    return true;
  }

  /**
   * Returns function id, if the current token starts with a function id,
   * otherwise returns the empty string.
   * @returns {string}
   */
  fun1() {
    const fun1 = [
      "abs",
      "sinc",
      "sin",
      "cos",
      "tan",
      "cot",
      "exp",
      "ln",
      "sqrt",
    ];
    for (let f of fun1) if (this.token.startsWith(f)) return f;
    return "";
  }

  /**
   * @param {number} numChars -- if > 0, then only consume the first chars of the current token
   * @returns {void}
   */
  next(numChars = -1) {
    // only consuming parts of the current token?
    if (numChars > 0 && this.token.length > numChars) {
      this.token = this.token.substring(numChars);
      this.skippedWhiteSpace = false;
      return;
    }
    // get next token from input
    this.token = "";
    let stop = false;
    const n = this.src.length;
    // (a) skip white spaces
    this.skippedWhiteSpace = false;
    while (this.pos < n && "\t\n ".includes(this.src[this.pos])) {
      this.skippedWhiteSpace = true;
      this.pos++;
    }
    // (b) get non white-spaces, i.e. the token
    while (!stop && this.pos < n) {
      // get current character from input
      let ch = this.src[this.pos];
      // stop, if alpha occurs while scanning a number, or vice versa
      // (e.g. "2pi", then current token is "2" and next token is "pi")
      if (
        this.token.length > 0 &&
        ((this.isNum(this.token[0]) && this.isAlpha(ch)) ||
          (this.isAlpha(this.token[0]) && this.isNum(ch)))
      ) {
        return;
      }
      // delimiter?
      if ("^%#*$()[]{},.:;+-*/_!<>=?|\t\n ".includes(ch)) {
        // return current token before delimiter (if present)
        if (this.token.length > 0) return;
        // delimiter stop scanning
        stop = true;
      }
      // only add non-white spaces to current token
      if ("\t\n ".includes(ch) == false) this.token += ch;
      // advance to next character in input
      this.pos++;
    }
  }

  /**
   * @param {string} ch
   * @returns {boolean} -- true, iff ch is a numeral (0-9)
   */
  isNum(ch) {
    return (
      ch.charCodeAt(0) >= "0".charCodeAt(0) &&
      ch.charCodeAt(0) <= "9".charCodeAt(0)
    );
  }

  /**
   * @param {string} ch
   * @returns {boolean} -- true, iff ch is alpha (a-z,A-Z)
   */
  isAlpha(ch) {
    return (
      (ch.charCodeAt(0) >= "A".charCodeAt(0) &&
        ch.charCodeAt(0) <= "Z".charCodeAt(0)) ||
      (ch.charCodeAt(0) >= "a".charCodeAt(0) &&
        ch.charCodeAt(0) <= "z".charCodeAt(0)) ||
      ch === "_"
    );
  }

  /**
   * @returns {string}
   */
  toString() {
    return this.root == null ? "" : this.root.toString();
  }

  /**
   * Does NOT take care for operator precedence.
   * Parentheses are ONLY generated, if attribute "explicitParentheses"
   * of Node is set (automatically filled while parsing)
   * @returns {string}
   */
  toTexString() {
    return this.root == null ? "" : this.root.toTexString();
  }
}
