/*******************************************************************************
 * pySELL - Python based Simple E-Learning Language
 * AUTHOR:  Andreas Schwenk <mailto:contact@compiler-construction.com>
 * LICENSE: GPLv3
 ******************************************************************************/

/**
 * This file encapsulates the math features available to the quiz websites.
 * While PYTHON is used to draw random variables, as well as to calculate the
 * sample solution, the students answers need to be parsed robustly,
 * evaluated, and compared web-based. Trivial example: The sample solution
 * term is given by string "x^2", and the student entered string "xx".
 * Both terms must be treated equivalent.
 *
 * Implementation of new unary functions (e.g. "sin"):
 * 1. add evaluation in Term.eval(..)
 * 2. add to grammar in comment of Term.parse(..)
 * 3. add to Term.fun1(..)
 * 4. add to TermNode.toTexStr(..)
 */

// TODO: boolean operands and operators
// TODO: fun2: atan2

/**
 * Given n, the list [0,1,...,n-1] (or a permutation in case "shuffled" is true)
 * is returned.
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

/**
 * Generates all permutations of a list and writes the result
 * into a matrix, where each row is a distinct permutation of
 * the list.
 * @param {number} k
 * @param {number[]} list
 * @param {number[][]} result
 * @returns {void}
 */
export function heapsAlgorithm(list, result, k = -1) {
  if (k < 0) k = list.length;
  if (k == 1) {
    result.push([...list]);
    return;
  }
  for (let i = 0; i < k; i++) {
    heapsAlgorithm(list, result, k - 1);
    let j = k % 2 == 0 ? i : 0;
    let t = list[j];
    list[j] = list[k - 1];
    list[k - 1] = t;
  }
}

/**
 * Data structure to store stringified terms, i.e. the elements.
 */
export class Matrix {
  /**
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
   * Returns the term of element (i,j), or "" if the index is invalid.
   * @param {number} i
   * @param {number} j
   * @returns {string}
   */
  getElement(i, j) {
    if (i < 0 || i >= this.m || j < 0 || j >= this.n) return "";
    return this.v[i * this.n + j];
  }

  /**
   * Resizes the matrix to the new number of rows m, and the new number of
   * columns n. Old element values are kept, and new elements are initialized
   * with stringified term "initTerm".
   * @param {number} m
   * @param {number} n
   * @param {string} initTerm
   * @returns {boolean} -- success
   */
  resize(m, n, initTerm) {
    if (m < 1 || m > 50 || n < 1 || n > 50) return false;
    let mat = new Matrix(m, n);
    mat.v.fill(initTerm);
    for (let i = 0; i < mat.m; i++)
      for (let j = 0; j < mat.n; j++)
        mat.v[i * mat.n + j] = this.getElement(i, j);
    this.fromMatrix(mat);
    return true;
  }

  /**
   * Imports a matrix.
   * @param {Matrix} mat
   */
  fromMatrix(mat) {
    this.m = mat.m;
    this.n = mat.n;
    this.v = [...mat.v];
  }

  /**
   * Parses e.g. "[[1+sin(x),2,3/x],[4,5^2,6]]".
   * Attention: element terms are forbidden to include the comma, since it
   *            is used as separator
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
   * Gets the length of the longest element, measures as string length of the
   * stringified elements.
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
   * Converts the matrix to a TeX-string. Elements are converted recursively.
   * @param {boolean} [augmented=false]
   * @param {boolean} [brackets=true] -- true: "["..."]", false: "("...")"
   * @returns {string}
   */
  toTeXString(augmented = false, brackets = true) {
    let s = "";
    if (brackets) s += augmented ? "\\left[\\begin{array}" : "\\begin{bmatrix}";
    else s += augmented ? "\\left(\\begin{array}" : "\\begin{pmatrix}";
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
    if (brackets) s += augmented ? "\\end{array}\\right]" : "\\end{bmatrix}";
    else s += augmented ? "\\end{array}\\right)" : "\\end{pmatrix}";
    return s;
  }
}

/**
 * Representation of mathematical terms (internally represented as tree).
 */
export class Term {
  constructor() {
    /** @type {TermNode} -- the root node */
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
   * Clone the current term, but excludes scanner/parser attributes.
   * @returns {Term}
   */
  clone() {
    let c = new Term();
    c.root = this.root.clone();
    return c;
  }

  /**
   * Gets the set of variables (e.g. {x,y} for x^2+y^2).
   * @param {Set<string>} s
   * @param {string} [prefix=""] -- if set, then only variables starting with prefix are filled
   * @param {TermNode} node
   */
  getVars(s, prefix = "", node = null) {
    if (node == null) node = this.root;
    if (node.op.startsWith("var:")) {
      let id = node.op.substring(4);
      if (prefix.length == 0 || (prefix.length > 0 && id.startsWith(prefix)))
        s.add(id);
    }
    for (let c of node.c) {
      this.getVars(s, prefix, c);
    }
  }

  /**
   * Replaces variables driven by a given dict
   * @param {Object.<string,TermNode>} dict
   * @param {TermNode} [node=null]
   */
  setVars(dict, node = null) {
    if (node == null) node = this.root;
    for (let c of node.c) {
      this.setVars(dict, c);
    }
    if (node.op.startsWith("var:")) {
      let id = node.op.substring(4);
      if (id in dict) {
        let x = dict[id].clone();
        node.op = x.op;
        node.c = x.c;
        node.re = x.re;
        node.im = x.im;
      }
    }
  }

  /**
   * Renames variables
   * @param {string} oldName
   * @param {string} newName
   * @param {TermNode} node
   */
  renameVar(oldName, newName, node = null) {
    if (node == null) node = this.root;
    for (let c of node.c) {
      this.renameVar(oldName, newName, c);
    }
    if (node.op.startsWith("var:")) {
      let id = node.op.substring(4);
      if (id === oldName) {
        node.op = "var:" + newName;
      }
    }
  }

  /**
   * Evaluates the term numerically (under the field of complex numbers).
   * Each occurring variable must be defined in the dict parameter.
   * If there are unset variables, evaluation throws an exception.
   * @param {Object.<string,TermNode>} dict
   * @param {TermNode} [node=null]
   * @returns {TermNode}
   */
  eval(dict, node = null) {
    const EPS = 1e-9; // epsilon, used for numerical thresholds
    let res = TermNode.const(); // thr result
    let t1 = 0; // temporary value
    let t2 = 0; // temporary value
    let tn = null; // temporary term node
    // if no node is given, then we assume that the root node is meant.
    if (node == null) node = this.root;
    // evaluate the current term node
    switch (node.op) {
      case "const":
        res = node;
        break;
      case "+":
      case "-":
      case "*":
      case "/":
      case "^": {
        // binary operation
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
            tn = new TermNode("exp", [
              new TermNode("*", [v, new TermNode("ln", [u])]),
            ]);
            res = this.eval(dict, tn);
            break;
        }
        break;
      }
      case ".-":
      case "abs":
      case "acos":
      case "acosh":
      case "asin":
      case "asinh":
      case "atan":
      case "atanh":
      case "ceil":
      case "cos":
      case "cosh":
      case "cot":
      case "exp":
      case "floor":
      case "ln":
      case "log":
      case "log10":
      case "log2":
      case "round":
      case "sin":
      case "sinc":
      case "sinh":
      case "sqrt":
      case "tan":
      case "tanh": {
        // TODO: throw error, if e.g. div/0, catch when comparing terms numerically

        // unary operation (".-" is the UNARY minus, e.g. "-5")
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
          case "acos": // TODO: test!!!!!
            // acos(u) = -i * ln( u + i * sqrt(1 - u^2) )
            tn = new TermNode("*", [
              TermNode.const(0, -1),
              new TermNode("ln", [
                new TermNode("+", [
                  TermNode.const(0, 1),
                  new TermNode("sqrt", [
                    new TermNode("-", [
                      TermNode.const(1, 0),
                      new TermNode("*", [u, u]),
                    ]),
                  ]),
                ]),
              ]),
            ]);
            res = this.eval(dict, tn);
            break;
          case "acosh":
            // TODO: test!!!!!
            // acosh(u) = ln( u + sqrt( u^2 - 1 ) )
            tn = new TermNode("*", [
              u,
              new TermNode("sqrt", [
                new TermNode("-", [
                  new TermNode("*", [u, u]),
                  TermNode.const(1, 0),
                ]),
              ]),
            ]);
            res = this.eval(dict, tn);
            break;
          case "asin":
            // TODO: test!!!!!
            // asin(u) = -i * ln( i * u + sqrt(1 - u^2) )
            tn = new TermNode("*", [
              TermNode.const(0, -1),
              new TermNode("ln", [
                new TermNode("+", [
                  new TermNode("*", [TermNode.const(0, 1), u]),
                  new TermNode("sqrt", [
                    new TermNode("-", [
                      TermNode.const(1, 0),
                      new TermNode("*", [u, u]),
                    ]),
                  ]),
                ]),
              ]),
            ]);
            res = this.eval(dict, tn);
            break;
          case "asinh":
            // TODO: test!!!!!
            // asinh(u) = ln( u + sqrt( u^2 + 1 ) )
            tn = new TermNode("*", [
              u,
              new TermNode("sqrt", [
                new TermNode("+", [
                  new TermNode("*", [u, u]),
                  TermNode.const(1, 0),
                ]),
              ]),
            ]);
            res = this.eval(dict, tn);
            break;
          case "atan":
            // TODO: test!!!!!
            // atan(u) = 0.5*i * ln( (1 - i*u) / (1 + i*u) )
            tn = new TermNode("*", [
              TermNode.const(0, 0.5),
              new TermNode("ln", [
                new TermNode("/", [
                  new TermNode("-", [
                    TermNode.const(0, 1),
                    new TermNode("*", [TermNode.const(0, 1), u]),
                  ]),
                  new TermNode("+", [
                    TermNode.const(0, 1),
                    new TermNode("*", [TermNode.const(0, 1), u]),
                  ]),
                ]),
              ]),
            ]);
            res = this.eval(dict, tn);
            break;
          case "atanh":
            // TODO: test!!!!!
            // atanh(u) = 0.5 * ln( (1+z) / (1-z) )
            tn = new TermNode("*", [
              TermNode.const(0.5, 0),
              new TermNode("ln", [
                new TermNode("/", [
                  new TermNode("+", [TermNode.const(1, 0), u]),
                  new TermNode("-", [TermNode.const(1, 0), u]),
                ]),
              ]),
            ]);
            res = this.eval(dict, tn);
            break;
          case "ceil": // TODO: test!!!!!
            res.re = Math.ceil(u.re);
            res.im = Math.ceil(u.im);
            break;
          case "cos":
            res.re = Math.cos(u.re) * Math.cosh(u.im);
            res.im = -Math.sin(u.re) * Math.sinh(u.im);
            break;
          case "cosh":
            // TODO: test!!!!!
            // cosh(u) = 0.5 * (exp(u) + exp(-u))
            tn = new TermNode("*", [
              TermNode.const(0.5, 0),
              new TermNode("+", [
                new TermNode("exp", [u]),
                new TermNode("exp", [new TermNode(".-", [u])]),
              ]),
            ]);
            res = this.eval(dict, tn);
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
          case "floor": // TODO: test!!!!!
            res.re = Math.floor(u.re);
            res.im = Math.floor(u.im);
            break;
          case "ln":
          case "log":
            // ln(u) = ln|u| + i * arg(u)
            res.re = Math.log(Math.sqrt(u.re * u.re + u.im * u.im));
            t1 = Math.abs(u.im) < EPS ? 0 : u.im; // prevent "-0" and similar
            res.im = Math.atan2(t1, u.re);
            break;
          case "log10": // TODO: test!!!!!
            // log10(u) = ln(u) / ln(10)
            tn = new TermNode("/", [
              new TermNode("ln", [u]),
              new TermNode("ln", [TermNode.const(10)]),
            ]);
            res = this.eval(dict, tn);
            break;
          case "log2": // TODO: test!!!!!
            // log2(u) = ln(u) / ln(2)
            tn = new TermNode("/", [
              new TermNode("ln", [u]),
              new TermNode("ln", [TermNode.const(2)]),
            ]);
            res = this.eval(dict, tn);
            break;
          case "round": // TODO: test!!!!!
            res.re = Math.round(u.re);
            res.im = Math.round(u.im);
            break;
          case "sin":
            res.re = Math.sin(u.re) * Math.cosh(u.im);
            res.im = Math.cos(u.re) * Math.sinh(u.im);
            break;
          case "sinc":
            // "unroll" term first, and then evaluate recursively
            tn = new TermNode("/", [new TermNode("sin", [u]), u]);
            res = this.eval(dict, tn);
            break;
          case "sinh":
            // TODO: test!!!!!
            // sinh(u) = 0.5 * (exp(u) - exp(-u))
            tn = new TermNode("*", [
              TermNode.const(0.5, 0),
              new TermNode("-", [
                new TermNode("exp", [u]),
                new TermNode("exp", [new TermNode(".-", [u])]),
              ]),
            ]);
            res = this.eval(dict, tn);
            break;
          case "sqrt": // u^(0.5)
            // "unroll" term first, and then evaluate recursively
            tn = new TermNode("^", [u, TermNode.const(0.5)]);
            res = this.eval(dict, tn);
            break;
          case "tan":
            // TODO: throw error, if abs(t1)<EPS + catch when comparing terms numerically
            t1 =
              Math.cos(u.re) * Math.cos(u.re) +
              Math.sinh(u.im) * Math.sinh(u.im);
            res.re = (Math.sin(u.re) * Math.cos(u.re)) / t1;
            res.im = (Math.sinh(u.im) * Math.cosh(u.im)) / t1;
            break;
          case "tanh":
            // TODO: test!!!!!
            // tanh(u) = (exp(u) - exp(-u)) / (exp(u) + exp(-u))
            tn = new TermNode("/", [
              new TermNode("-", [
                new TermNode("exp", [u]),
                new TermNode("exp", [new TermNode(".-", [u])]),
              ]),
              new TermNode("+", [
                new TermNode("exp", [u]),
                new TermNode("exp", [new TermNode(".-", [u])]),
              ]),
            ]);
            res = this.eval(dict, tn);
            break;
        }
        break;
      }
      default:
        if (node.op.startsWith("var:")) {
          let id = node.op.substring(4);
          if (id === "pi") return TermNode.const(Math.PI);
          else if (id === "e") return TermNode.const(Math.E);
          else if (id === "i") return TermNode.const(0, 1);
          else if (id === "true") return TermNode.const(1);
          else if (id === "false") return TermNode.const(0);
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
   * Robust parsing of a term. The grammar is given by the following grammar
   * roughly, but the detailed processing also depends on spacing in some
   * cases. Refer to the examples given in "math_TEST.js".
   *   expr = add;
   *   add = mul { ("+"|"-") mul };
   *   mul = pow { ("*"|"/"|epsilon) pow };  // epsilon := implicit mul
   *   pow = unary { "^" unary };
   *   unary = "-" mul | infix;
   *   infix = NUM | fct1 mul | fct1 "(" expr ")" | "(" expr ")" |
   *           "|" expr "|" STR;
   *   fct1 = "abs" | "acos" | "acosh" | "asin" | "asinh" | "atan" | "atanh" |
   *          "ceil" | "cos" | "cosh" | "cot" | "exp" | "floor" | "ln" | "log" |
   *          "log10" | "log2" | "round" | "sin" | "sinc" | "sinh" | "sqrt" |
   *          "tan" | "tanh";
   * @param {string} src -- the input term to be parsed, e.g. "sin xy ^2"
   */
  static parse(src) {
    let term = new Term();
    term.src = src;
    // the current token of the lexer/scanner
    term.token = "";
    // true, iff there were white-space(s) before the current token
    term.skippedWhiteSpace = false;
    // the current string position of the lexer/scanner
    term.pos = 0;
    // advance the input to the next token
    term.next();
    // // lexer test
    // while (term.token.length > 0) {
    //   console.log("'" + term.token + "'");
    //   term.next();
    // }
    // parse the expression
    term.root = term.parseExpr(false);
    if (term.token !== "")
      // something bad happened...
      throw new Error("remaining tokens: " + term.token + "...");
    // return the parsed term
    return term;
  }

  /**
   * @param {boolean} stopAtSpace -- if true, then stop at the next white space
   * @returns {TermNode}
   */
  parseExpr(stopAtSpace) {
    return this.parseAdd(stopAtSpace);
  }

  /**
   * @param {boolean} stopAtSpace
   * @returns {TermNode}
   */
  parseAdd(stopAtSpace) {
    let node = this.parseMul(stopAtSpace);
    while (["+", "-"].includes(this.token)) {
      if (stopAtSpace && this.skippedWhiteSpace) break;
      let op = this.token;
      this.next();
      node = new TermNode(op, [node, this.parseMul(stopAtSpace)]);
    }
    return node;
  }

  /**
   * @param {boolean} stopAtSpace
   * @returns {TermNode}
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
        // e.g. x(x+1) -> x*(x+1)
        op = "*";
      } else if (
        this.token.length > 0 &&
        (this.isAlpha(this.token[0]) || this.isNum(this.token[0]))
      ) {
        // e.g. x2 -> x*2,  or xy -> x*y
        op = "*";
      } else {
        break;
      }
      node = new TermNode(op, [node, this.parsePow(stopAtSpace)]);
    }
    return node;
  }

  /**
   * @param {boolean} stopAtSpace
   * @returns {TermNode}
   */
  parsePow(stopAtSpace) {
    let node = this.parseUnary(stopAtSpace);
    while (["^"].includes(this.token)) {
      if (stopAtSpace && this.skippedWhiteSpace) break;
      let op = this.token;
      this.next();
      node = new TermNode(op, [node, this.parseUnary(stopAtSpace)]);
    }
    return node;
  }

  /**
   * @param {boolean} stopAtSpace
   * @returns {TermNode}
   */
  parseUnary(stopAtSpace) {
    if (this.token === "-") {
      this.next();
      return new TermNode(".-", [this.parseMul(stopAtSpace)]);
    }
    return this.parseInfix(stopAtSpace);
  }

  /**
   * @param {boolean} stopAtSpace
   * @returns {TermNode}
   */
  parseInfix(stopAtSpace) {
    if (this.token.length == 0) {
      throw new Error("expected unary");
    } else if (this.isNum(this.token[0])) {
      // integer number
      let v = this.token;
      this.next();
      if (this.token === ".") {
        // floating point number
        v += ".";
        this.next();
        if (this.token.length > 0) {
          v += this.token;
          this.next();
        }
      }
      return new TermNode("const", [], parseFloat(v));
    } else if (this.fun1().length > 0) {
      // unary function (e.g. "sin")
      let op = this.fun1();
      this.next(op.length); // only consume the function id
      let arg = null;
      if (this.token === "(") {
        // parentheses are explicitly given
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
      return new TermNode(op, [arg]);
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
      return new TermNode("abs", [arg]);
    } else if (this.isAlpha(this.token[0])) {
      let id = "";
      if (this.token.startsWith("pi")) id = "pi";
      else if (this.token.startsWith("true")) id = "true";
      else if (this.token.startsWith("false")) id = "false";
      else if (this.token.startsWith("C1")) id = "C1";
      else if (this.token.startsWith("C2")) id = "C2";
      else id = this.token[0];
      if (id === "I") id = "i";
      this.next(id.length); // only consume next char(s)
      return new TermNode("var:" + id, []);
    } else throw new Error("expected unary");
  }

  /**
   * Compares two terms numerically. E.g. "x+x" and "2x" are equal.
   * This method randomly sets all occurring variables to a (complex) number
   * and then evaluates both terms.
   * Optionally, a predefined context, with variable values can be given.
   * Then only those variables that are not predefined are set randomly.
   * @param {Term} tu
   * @param {Term} tv
   * @param {Object.<string,TermNode>} [predefinedContext={}]
   * @return {boolean}
   */
  static compare(tu, tv, predefinedContext = {}) {
    const EPS = 1e-9;
    const NUM_TESTS = 10; // TODO
    let vars = new Set();
    tu.getVars(vars);
    tv.getVars(vars);
    for (let i = 0; i < NUM_TESTS; i++) {
      /** @type {Object.<string,TermNode>} */
      let context = {};
      for (let v of vars) {
        if (v in predefinedContext) context[v] = predefinedContext[v];
        else context[v] = TermNode.const(Math.random(), Math.random());
      }
      let r1 = tu.eval(context); // TODO: catch DIV/0, ... -> test again
      let r2 = tv.eval(context); // TODO: catch DIV/0, ... -> test again
      let dre = r1.re - r2.re;
      let dim = r1.im - r2.im;
      let abs = Math.sqrt(dre * dre + dim * dim);
      if (abs > EPS) return false;
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
      "acos",
      "acosh",
      "asin",
      "asinh",
      "atan",
      "atanh",
      "ceil",
      "cos",
      "cosh",
      "cot",
      "exp",
      "floor",
      "ln",
      "log",
      "log10",
      "log2",
      "round",
      "sin",
      "sinc",
      "sinh",
      "sqrt",
      "tan",
      "tanh",
    ];
    for (let f of fun1) {
      if (this.token.toLowerCase().startsWith(f)) return f;
    }
    return "";
  }

  /**
   * Advances the input to the next token. If numChars is set > 0,
   * then only the first characters of the current token are consumed,
   * and the rest is kept in this.token
   * @param {number} numChars
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
        // ... but keep ODE-constants (e.g. "C1", "C2", ...)
        if (this.token != "C") return;
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
   * Is the given character a numeral 0|1|...|9 ?
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
   * Is the given character alpha A|B|...|Z|a|b|...|z ?
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
   * Stringifies the term by setting parentheses "everywhere".
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

/**
 * Implementation of a node within the term tree structure
 */
export class TermNode {
  /**
   * @param {string} op -- the operation ("const", "var", "+", "-", "*", ...)
   * @param {TermNode[]} c -- the children, i.e. operands
   * @param {number} [re=0] -- the real part (only valid for this.op==="const")
   * @param {number} [im=0] -- the imag part (only valid for this.op==="const")
   */
  constructor(op, c, re = 0, im = 0) {
    /** @type {string} -- the operation ("const", "var", "+", "-", "*", ...) */
    this.op = op;
    /** @type {TermNode[]} -- the children, i.e. operands */
    this.c = c;
    /** @type {number} -- the real part (only valid for this.op==="const") */
    this.re = re;
    /** @type {number} -- the imag part (only valid for this.op==="const") */
    this.im = im;
    /** @type {boolean} -- used e.g. for TeX conversion */
    this.explicitParentheses = false;
  }

  /**
   * @returns {TermNode}
   */
  clone() {
    let c = new TermNode(
      this.op,
      this.c.map((ci) => ci.clone()),
      this.re,
      this.im
    );
    c.explicitParentheses = this.explicitParentheses;
    return c;
  }

  /**
   * Creates a constant (i.e. a leaf)
   * @param {number} re
   * @param {number} im
   */
  static const(re = 0, im = 0) {
    return new TermNode("const", [], re, im);
  }

  /**
   * Compares the node to the given real number. This is only applicable for
   * term nodes which are constants, i.e. leafs.
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
   * Stringifies the term by setting parentheses "everywhere".
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
      else if (hasReal && this.re > 0) s = "" + this.re;
      else if (hasReal && this.re < 0) s = "(" + this.re + ")";
      else if (hasImag) s = "(" + this.im + "i)";
      else s = "0";
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
        // returns (parts of) a complex number
        let hasRe = Math.abs(this.re) > EPS;
        let hasIm = Math.abs(this.im) > EPS;
        let re = hasRe ? "" + this.re : "";
        let im = hasIm ? "" + this.im + "i" : "";
        if (im === "1i") im = "i";
        else if (im === "-1i") im = "-i";
        if (!hasRe && !hasIm) s = "0";
        else {
          if (hasIm && this.im >= 0 && hasRe) im = "+" + im;
          s = re + im;
        }
        break;
      }
      case ".-":
        // unary minus
        s = "-" + this.c[0].toTexString();
        break;
      case "+":
      case "-":
      case "*":
      case "^": {
        let u = this.c[0].toTexString();
        let v = this.c[1].toTexString();
        let op = this.op === "*" ? "\\cdot " : this.op;
        s = "{" + u + "}" + op + "{" + v + "}";
        break;
      }
      case "/": {
        let u = this.c[0].toTexString(true); // operand w/o parentheses!
        let v = this.c[1].toTexString(true); // operand w/o parentheses!
        s = "\\frac{" + u + "}{" + v + "}";
        break;
      }
      case "floor": {
        let u = this.c[0].toTexString(true); // operand w/o parentheses!
        s += "\\" + this.op + "\\left\\lfloor" + u + "\\right\\rfloor";
        break;
      }
      case "ceil": {
        let u = this.c[0].toTexString(true); // operand w/o parentheses!
        s += "\\" + this.op + "\\left\\lceil" + u + "\\right\\rceil";
        break;
      }
      case "round": {
        let u = this.c[0].toTexString(true); // operand w/o parentheses!
        s += "\\" + this.op + "\\left[" + u + "\\right]";
        break;
      }
      case "acos":
      case "acosh":
      case "asin":
      case "asinh":
      case "atan":
      case "atanh":
      case "cos":
      case "cosh":
      case "cot":
      case "exp":
      case "ln":
      case "log":
      case "log10":
      case "log2":
      case "sin":
      case "sinc":
      case "sinh":
      case "tan":
      case "tanh": {
        let u = this.c[0].toTexString(true); // operand w/o parentheses!
        s += "\\" + this.op + "\\left(" + u + "\\right)";
        break;
      }
      case "sqrt": {
        let u = this.c[0].toTexString(true); // operand w/o parentheses!
        s += "\\" + this.op + "{" + u + "}";
        break;
      }
      case "abs": {
        let u = this.c[0].toTexString(true); // operand w/o parentheses!
        s += "\\left|" + u + "\\right|";
        break;
      }
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
