/**
 * @param {number} n
 * @returns {number[]}
 */
export function unShuffledIndices(n) {
  let arr = new Array(n);
  for (let i = 0; i < n; i++) arr[i] = i;
  return arr;
}

/**
 * @param {number} n
 * @returns {number[]}
 */
export function shuffledIndices(n) {
  let arr = new Array(n);
  for (let i = 0; i < n; i++) arr[i] = i;
  for (let i = 0; i < n; i++) {
    let u = Math.floor(Math.random() * n);
    let v = Math.floor(Math.random() * n);
    let t = arr[u];
    arr[u] = arr[v];
    arr[v] = t;
  }
  return arr;
}

export class Vector {
  constructor() {
    /** @type {number} */
    this.n = 0;
    /** @type {number[]} */
    this.v = [];
  }

  /**
   * parses e.g. "[1,2,3]"
   * @param {string} s
   */
  fromString(s) {
    this.v = s.split(",").map((e) => parseFloat(e));
    this.n = this.v.length;
  }
}

export class Matrix {
  constructor() {
    /** @type {number} */
    this.m = 0;
    /** @type {number} */
    this.n = 0;
    /** @type {number[]} */
    this.v = [];
  }

  /**
   * parses e.g. "[[1,2,3],[4,5,6]]"
   * @param {string} s
   */
  fromString(s) {
    this.m = s.split("],[").length;
    this.v = s
      .replaceAll("[", "")
      .replaceAll("]", "")
      .split(",")
      .map((e) => parseFloat(e));
    this.n = this.v.length / this.m;
  }

  /**
   * @returns {number}
   */
  getMaxCellStrlen() {
    let m = 0;
    for (let vi of this.v) {
      let s = vi.toString();
      if (s.length > m) m = s.length;
    }
    return m;
  }
}

export class Node {
  /**
   * @param {string} op
   * @param {Node[]} c
   */
  constructor(op, c) {
    /** @type {string} -- the operation */
    this.op = op;
    /** @type {Node[]} -- the children/operands */
    this.c = c;
  }
}

/**
 * @param {string} s
 * @returns {number}
 */
function pf(s) {
  return parseFloat(s);
}

export class Term {
  constructor() {
    /** @type {Node} */
    this.root = null;
    /** @type {string} -- parser input string */
    this.src = "";
    /** @type {string} -- current lexer token */
    this.token = "";
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
   * @param {Object.<string,string>} dict
   * @param {Node} [node=null]
   * @returns {string}
   */
  eval(dict, node = null) {
    const EPS = 1e-9;
    if (node == null) node = this.root;
    switch (node.op) {
      case "+":
      case "-":
      case "*":
      case "/":
      case "^":
      case "==": {
        let u = this.eval(dict, node.c[0]).split(":");
        let v = this.eval(dict, node.c[1]).split(":");
        switch (node.op) {
          case "+":
            if (u[0] === "num" && v[0] == "num")
              return "num:" + (pf(u[1]) + pf(v[1]));
            break;
          case "-":
            if (u[0] === "num" && v[0] == "num")
              return "num:" + (pf(u[1]) - pf(v[1]));
            break;
          case "*":
            if (u[0] === "num" && v[0] == "num")
              return "num:" + pf(u[1]) * pf(v[1]);
            break;
          case "/":
            if (u[0] === "num" && v[0] == "num")
              return "num:" + pf(u[1]) / pf(v[1]);
            break;
          case "^":
            if (u[0] === "num" && v[0] == "num")
              return "num:" + Math.pow(pf(u[1]), pf(v[1]));
            break;
          case "==":
            if (u[0] === "num" && v[0] == "num")
              return "num:" + (Math.abs(pf(u[1]) - pf(v[1])) < EPS ? 1 : 0);
            break;
        }
        let msg = "eval-error: " + u[0] + " " + node.op + " " + v[0];
        throw new Error(msg);
      }
      case ".-":
      case "sin":
      case "cos":
      case "tan":
      case "exp":
      case "ln":
      case "sqrt": {
        let u = this.eval(dict, node.c[0]).split(":");
        switch (node.op) {
          case ".-":
            if (u[0] === "num") return "num:" + -pf(u[1]);
            break;
          case "sin":
            if (u[0] === "num") return "num:" + Math.sin(pf(u[1]));
            break;
          case "cos":
            if (u[0] === "num") return "num:" + Math.cos(pf(u[1]));
            break;
          case "tan":
            if (u[0] === "num") return "num:" + Math.tan(pf(u[1]));
            break;
          case "exp":
            if (u[0] === "num") return "num:" + Math.exp(pf(u[1]));
            break;
          case "ln":
            if (u[0] === "num") return "num:" + Math.log(pf(u[1]));
            break;
          case "sqrt":
            if (u[0] === "num") return "num:" + Math.sqrt(pf(u[1]));
            break;
        }
        let msg = "eval-error: " + node.op + "(" + u[0] + ")";
        throw new Error(msg);
      }
      default:
        if (node.op.startsWith("num:")) {
          return node.op;
        } else if (node.op.startsWith("var:")) {
          let id = node.op.substring(4);
          if (id in dict) return dict[id];
          throw new Error("eval-error: unknown variable '" + id + "'");
        }
        throw new Error("UNIMPLEMENTED eval '" + node.op + "'");
    }
  }

  /**
   * @param {string} src
   * expr = mul { ("+"|"-") mul };
   * mul = pow { ("*"|"/"|epsilon) pow };
   * pow = unary [ "^" unary ];
   * unary = "-" mul | infix;
   * infix = NUM | fct1 mul | fct1 "(" expr ")"
   *       | "(" expr ")" | "pi" | "e" | STR;
   * fct1 = "sin" | "cos" | "tan" | "exp" | "ln" | "sqrt";
   */
  parse(src) {
    this.src = src;
    this.token = "";
    this.pos = 0;
    this.next();
    // // lexer test
    // while (this.token.length > 0) {
    //   console.log("'" + this.token + "'");
    //   this.next();
    // }
    this.root = this.parseExpr();
    if (this.token !== "")
      throw new Error("remaining tokens: " + this.token + "...");
  }

  /**
   * @returns {Node}
   */
  parseExpr() {
    let node = this.parseMul();
    while (["+", "-"].includes(this.token)) {
      let op = this.token;
      this.next();
      node = new Node(op, [node, this.parseMul()]);
    }
    return node;
  }

  /**
   * @returns {Node}
   */
  parseMul() {
    // TODO: implicit mul
    let node = this.parsePow();
    while (
      ["*", "/", "("].includes(this.token) ||
      (this.token.length > 0 && this.isAlpha(this.token[0]))
    ) {
      let op = "*";
      if (["*", "/"].includes(this.token)) {
        op = this.token;
        this.next();
      }
      node = new Node(op, [node, this.parsePow()]);
    }
    return node;
  }

  /**
   * @returns {Node}
   */
  parsePow() {
    // TODO: implicit mul
    let node = this.parseUnary();
    if (["^"].includes(this.token)) {
      let op = this.token;
      this.next();
      node = new Node(op, [node, this.parseUnary()]);
    }
    return node;
  }

  /**
   * @returns {Node}
   */
  parseUnary() {
    if (this.token === "-") {
      this.next();
      return new Node(".-", [this.parseMul()]);
    }
    return this.parseInfix();
  }

  /**
   * @returns {Node}
   */
  parseInfix() {
    if (this.token.length == 0) throw new Error("expected unary");
    if (this.isNum(this.token[0])) {
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
      return new Node("num:" + v, []);
    } else if (
      ["sin", "cos", "tan", "exp", "ln", "sqrt"].includes(this.token)
    ) {
      let op = this.token;
      this.next();
      let paren = false;
      if (this.token === "(") {
        paren = true;
        this.next();
      }
      let fun = new Node(op, [this.parseMul()]);
      if (paren) {
        if (this.token === ")") this.next();
        else throw Error("expected ')'");
      }
      return fun;
    } else if (this.token === "(") {
      this.next();
      let n = this.parseExpr();
      this.token += ""; // LINTER_FIX
      if (this.token === ")") this.next();
      else throw Error("expected ')'");
      return n;
    } else if (this.token.toLowerCase() === "pi") {
      this.next();
      return new Node("num:" + Math.PI, []);
    } else if (this.token.toLowerCase() === "e") {
      this.next();
      return new Node("num:" + Math.E, []);
    } else if (this.isAlpha(this.token[0])) {
      let v = this.token;
      this.next();
      return new Node("var:" + v, []);
    } else throw new Error("expected unary");
  }

  /**
   * @param {Term} term
   * @return {boolean}
   */
  compare(term) {
    const NUM_TESTS = 10;
    let vars = new Set();
    this.getVars(vars);
    term.getVars(vars);
    for (let i = 0; i < NUM_TESTS; i++) {
      /** @type {Object.<string,string>} */
      let context = {};
      for (let v of vars) context[v] = "num:" + Math.random();
      let t = new Node("==", [this.root, term.root]);
      let res = this.eval(context, t);
      if (res === "num:0") return false;
    }
    return true;
  }

  next() {
    this.token = "";
    let stop = false;
    const n = this.src.length;
    // skip white spaces
    while (this.pos < n && "\t\n ".includes(this.src[this.pos])) this.pos++;
    // get next token
    while (!stop && this.pos < n) {
      // get current character from input
      let ch = this.src[this.pos];
      // stop, if alpha occurs while scanning a number
      // (e.g. "2pi", then current token is "2" and next
      //  token is "pi")
      if (
        this.token.length > 0 &&
        this.isNum(this.token[0]) &&
        this.isAlpha(ch)
      ) {
        return;
      }
      // delimiter?
      if ("^%#*$()[]{},.:;+-*/_!<>=?\t\n ".includes(ch)) {
        // return current token before delimiter (if present)
        if (this.token.length > 0) return;
        // delimiter stop scanning
        stop = true;
      }
      // only add non-white spaces to current token
      if ("\t\n ".includes(ch) == false) this.token += ch;
      // split variables (e.g. "xy" is considered as two tokens
      // "x" and "y").
      if (["x", "y", "z", "t"].includes(this.token)) stop = true;
      // advance to next character in input
      this.pos++;
    }
  }

  /**
   * @param {string} ch
   * @returns {boolean}
   */
  isNum(ch) {
    return (
      ch.charCodeAt(0) >= "0".charCodeAt(0) &&
      ch.charCodeAt(0) <= "9".charCodeAt(0)
    );
  }

  /**
   * @param {string} ch
   * @returns {boolean}
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
}
