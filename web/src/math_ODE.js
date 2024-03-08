/*******************************************************************************
 * pySELL - Python based Simple E-Learning Language
 * AUTHOR:  Andreas Schwenk <mailto:contact@compiler-construction.com>
 * LICENSE: GPLv3
 ******************************************************************************/

import { Term, TermNode, heapsAlgorithm, range } from "./math.js";

/**
 * This file implements the comparison of ODE-terms that include a finite set
 * of constants C0, C1, ... .
 *
 * The following challenges arise:
 *
 * For example, valid solutions for the ODE
 *     y'(x) = -2*x^2 / y(x)    are
 *     sqrt(2/3)*sqrt(C-2*x^3)  [output from wolframalpha.com]   and
 *     sqrt(C-12*x^3)/3         [output from sympy]
 *
 * In the example, the constant C of one of the terms must be multiplied by
 * a factor to get two equivalent terms. If the C of the first term is replaced
 * by K*C, and we determine K=1/6, then term comparison can be applied!
 *
 * Furthermore, the names of constant variables may be swapped by the student.
 * Both  C1 * exp(2x) + C2 * exp(-4x)  and  C2 * exp(2x) + C1 * exp(-4x)
 * are equivalent. Our comparison algorithm has check for all permutations.
 * If all permutations fail, then the terms are not equal.
 *
 * ALGORITHM to compare two ODE-terms  u  and  v:
 *
 *   1. Try to compare both terms numerically, as implemented in method
 *      Term.compare(..). If the test succeeds, then things are easy.
 *
 *   2. Reduce subterms that only contain C_i and constants, by C_i.
 *      For example we rewrite  sin(exp(cos(C+3))) + 3*C1 + sin(C1+C2)
 *      to  C + C1 + sin(C1+C2).  This is done, by recursively (depth first)
 *      checking, if an k-ary operation has one occurrence of C_j and all other
 *      (k-1) operands are constants. If this is applicable, replace the
 *      operation by C_i.
 *
 *   3. Rename constants to C0, C1, ... . For example,  C * exp(-3*x)  is
 *      rewritten to  C0 * exp(-3*x).
 *
 *   4. Generate all permutations of the list [0,1,...,n], with n, the order
 *      of the ODE.
 *
 *   5. For all permutations from the last step:
 *
 *   5.a)  In ONE of the terms to compare, rename constant variables,
 *         i.e. Ci becomes C{permutation(i)}
 *
 *         ATTENTION: The next sub steps work must work on COPIES of u and v!
 *
 *   5.b)  For each 0 <= i < n, set Cj with i != j in both terms u and v to
 *         zero, so we are focussing on just one Ci.
 *
 *   5.b.1)  In ONE of the terms, replace Ci by (K*Ci). We will find a suitable
 *           K \in \R in the following.
 *
 *   5.b.2)  To get K, set all occurring variables, except K, to random values
 *           \in \C (bounded to range [-1, 1] on both axes, to circumvent
 *           numerical instability).
 *
 *   5.b.3)  Minimize f(K) = abs(u - v), where K is the only decision variable.
 *           The problem should be convex in the context of ODE-class-exercises.
 *           Sophisticated algorithms are available for this non-linear
 *           optimization tasks, but our math engine in file math.js is weak...
 *           So, we naively initialize K=0, as well as a step width S that is
 *           initialized to e.g. 1. In a (finite) sequence of iterations, we
 *           check, chose min { f(K-S), f(K), f(+S) }. In case that the
 *           "direction" changes, S is replaced by S/2.
 *
 *   5.b.4)  Now check (with 10+ numerical tests), if our K from the last step
 *           let to equivalency. If not, continue with the next permutation in
 *           step 5.
 *
 *   5.c)  If we get here, all K's for the present permutation are known.
 *         We now numerically check, if terms u and v are equal under the
 *         factors K. If we succeed, then QUIT WITH SUCCESS.
 *
 *   6. In case no of the permutations showed to be correct, then QUIT WITH
 *      FAILURE.
 */

/**
 * Algorithm to compare two terms with constants C0, C1, ...
 * @param {Term} tu
 * @param {Term} tv
 * @return {boolean}
 */
export function compareODE(tu, tv) {
  let EPS = 1e-9;

  // first try comparing conventionally... maybe we are in luck:
  if (Term.compare(tu, tv)) return true;

  // Some of the following steps are destructive, so work on copies!
  tu = tu.clone();
  tv = tv.clone();

  // Reduce subterms that only contain C_i by C_i (e.g. "e^C" -> "C").
  prepareODEconstantComparison(tu.root);
  prepareODEconstantComparison(tv.root);

  // get all variables that start with "C"
  let allVariables = new Set();
  tu.getVars(allVariables);
  tv.getVars(allVariables);
  let constantVariables = []; // variables starting with "C"
  let nonConstantVariables = []; // variables NOT starting with "C"
  for (let v of allVariables.keys()) {
    if (v.startsWith("C")) constantVariables.push(v);
    else nonConstantVariables.push(v);
  }

  // N := number of constant variables
  let N = constantVariables.length;

  // rename constants to C0, C1, ... for easier handling
  // (this has to be done in two steps to prevent overwriting)
  for (let i = 0; i < N; i++) {
    let v = constantVariables[i];
    tu.renameVar(v, "_C" + i);
    tv.renameVar(v, "_C" + i);
  }
  for (let i = 0; i < N; i++) {
    tu.renameVar("_C" + i, "C" + i);
    tv.renameVar("_C" + i, "C" + i);
  }
  constantVariables = [];
  for (let i = 0; i < N; i++) constantVariables.push("C" + i);

  // Since the constants can be given in shuffled order, we generate all
  // permutations. It is sufficient, if one of the permutations matches.
  let constantPermutations = [];
  heapsAlgorithm(range(N), constantPermutations);
  for (let permutation of constantPermutations) {
    // Some of the following steps are destructive, so work on copies!
    let tuClone = tu.clone();
    let tvClone = tv.clone();
    // Perform permutation on tvClone
    for (let i = 0; i < N; i++) {
      tvClone.renameVar("C" + i, "__C" + permutation[i]);
    }
    for (let i = 0; i < N; i++) {
      tvClone.renameVar("__C" + i, "C" + i);
    }
    // For each constant C_k, set the other constants (C_j with j != k)
    // to zero.
    let success = true;
    for (let k = 0; k < N; k++) {
      // For the fixed C_k, replace "C_k" by "(K * C_k)" in tv and check,
      // if there is a K in RR which results in comparing terms
      // successfully.
      let ckId = "C" + k;
      /** @type {Object.<string,TermNode>} */
      let dict = {};
      dict[ckId] = new TermNode("*", [
        new TermNode("var:C" + k, []),
        new TermNode("var:K", []),
      ]);
      tvClone.setVars(dict);
      /** @type {Object.<string,TermNode>} */
      let context = {};
      context[ckId] = TermNode.const(Math.random(), Math.random());
      for (let j = 0; j < N; j++)
        if (k != j) context["C" + j] = TermNode.const(0, 0);
      let absRoot = new TermNode("abs", [
        new TermNode("-", [tuClone.root, tvClone.root]),
      ]);
      let abs = new Term();
      abs.root = absRoot;
      for (let varId of nonConstantVariables)
        context[varId] = TermNode.const(Math.random(), Math.random());
      let K = minimize(abs, "K", context)[0];
      tvClone.setVars({ K: TermNode.const(K, 0) });

      // finally compare the terms w.r.t to C_k. All other C_k are set to 0
      context = {};
      for (let j = 0; j < N; j++)
        if (k != j) context["C" + j] = TermNode.const(0, 0);
      let equal = Term.compare(tuClone, tvClone, context);

      if (equal == false) {
        success = false;
        break;
      }
    }
    // Compare once again, with all C_k replaced with K_k*C_k in tvClone
    if (success && Term.compare(tuClone, tvClone)) return true;
  }

  return false;
}

/**
 * Naive implementation for convex optimization with one decision variable.
 * WARNING: Due to the primitivity of the math engine implemented in this
 *          file, we do not have the opportunity for automatic differentiation
 *          etc. This method should only be used for special cases.
 *          Currently, it is used to compare ODE solutions numerically.
 *          Refer to
 * @param {Term} term -- the term
 * @param {string} dvId -- name of the decision variable; all other
 *                         variables MUST be set by constants in the dict
 * @param {Object.<string,TermNode>} vars -- values for all other variables
 * @returns {number[]} -- [value for varId, minimized function output value]
 */
export function minimize(term, dvId, vars) {
  let EPS = 1e-11;
  let MAX_ITERATIONS = 1000;
  let cnt = 0;
  let dvValue = 0;
  let step = 1;
  let lastDirection = 888; // -1 := left, 0 := stand, 1 := right
  while (cnt < MAX_ITERATIONS) {
    vars[dvId] = TermNode.const(dvValue);
    let y = term.eval(vars).re;
    vars[dvId] = TermNode.const(dvValue + step);
    let yRight = term.eval(vars).re;
    vars[dvId] = TermNode.const(dvValue - step);
    let yLeft = term.eval(vars).re;
    let direction = 0;
    if (yRight < y) {
      y = yRight;
      direction = 1;
    }
    if (yLeft < y) {
      y = yLeft;
      direction = -1;
    }
    if (direction == 1) dvValue += step;
    if (direction == -1) dvValue -= step;
    if (y < EPS) break;
    if (direction == 0 || direction != lastDirection) step /= 2.0;
    lastDirection = direction;
    cnt++;
  }
  vars[dvId] = TermNode.const(dvValue);
  let y = term.eval(vars).re;
  return [dvValue, y];
}

/**
 * This method optimizes the occurrences of constants, i.e. removes any
 * operations that involves constants and ONE of the constant variables
 * C0, C1, ...
 *
 * The Term Rewriting System (TRS) is specified as follows:
 *   unary_op(C)           -> C      (e.g. unary minus)
 *   binary_op(C,constant) -> C      (e.g. addition)
 *   binary_op(constant,C) -> C      (e.g. addition)
 *   function(C)           -> C      (e.g. the sine-function)
 * @param {TermNode} node
 * @return {void}
 */
export function prepareODEconstantComparison(node) {
  for (let c of node.c) {
    prepareODEconstantComparison(c);
  }
  switch (node.op) {
    case "+":
    case "-":
    case "*":
    case "/":
    case "^": {
      let op = [node.c[0].op, node.c[1].op];
      let isConst = [op[0] === "const", op[1] === "const"];
      let isConstVar = [op[0].startsWith("var:C"), op[1].startsWith("var:C")];
      if (isConstVar[0] && isConst[1]) {
        node.op = node.c[0].op;
        node.c = [];
      } else if (isConstVar[1] && isConst[0]) {
        node.op = node.c[1].op;
        node.c = [];
      } else if (isConstVar[0] && isConstVar[1] && op[0] == op[1]) {
        node.op = node.c[0].op;
        node.c = [];
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
    case "sqrt":
      if (node.c[0].op.startsWith("var:C")) {
        node.op = node.c[0].op;
        node.c = [];
      }
      break;
  }
}
