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
 * a factor to get two equivalent terms. If C of the first term is replaced
 * by K*C, with K=1/6, then term comparison can be applied!
 *
 * Furthermore, the names of constant variables may be swapped by the student.
 * Both  C1 * exp(2x) + C2 * exp(-4x)  and  C2 * exp(2x) + C1 * exp(-4x)
 * are valid solutions. Our comparison algorithm has to check all permutations.
 * If all permutations fail, then terms are considered not to be equal.
 *
 * ALGORITHM to compare two ODE solution-terms  u  and  v:
 *
 *   1. Try to compare both terms numerically, as implemented in method
 *      Term.compare(..) in file main.js. If the test succeeds, then QUIT WITH
 *      SUCCESS.
 *
 *   2. Reduce those subterms that only contain C_i and constants as operands
 *      to just by C_i.
 *      For example we rewrite
 *           sin(exp(cos(C+3))) + 3*C1 + sin(C1+C2)
 *      to
 *           C + C1 + sin(C1+C2).
 *      This is done, by checking recursively and depth-first, if an operation
 *      only deals with C_j (with fixed j) and constant operations.
 *      If this is applicable, then replace the operation by C_i.
 *
 *   3. Rename constants to C0, C1, ... .
 *      For example,  C * exp(-3*x)  is rewritten to  C0 * exp(-3*x).
 *
 *   4. Generate all permutations of the list [0,1,...,n-1],
 *      with n, the order of the ODE.
 *
 *   5. For all permutations from the last step:
 *
 *   5.a)  Rename constant variables either in  u  (or in v, alternatively),
 *         sucht that  Ci  becomes  C{permutation(i)}.
 *
 *         ATTENTION: The next subordinate steps must be applied on COPIES of
 *         terms u and v!
 *
 *   5.b)  For each 0 <= i < n, set Cj with i != j to zero (in both terms),
 *         so we are focussing on just one Ci over each iteration in 5.b)
 *
 *   5.b.1)  Replace Ci by (K*Ci) in either  u  or  v  (NOT in both).
 *           We will try to determine K \in \R in the following steps.
 *
 *   5.b.2)  To get K, set all occurring variables, except K, to random values
 *           \in \C (bounded to range [-1, 1] on both axes, to circumvent
 *           numerical instability).
 *
 *   5.b.3)  Minimize f(K) = abs(u - v), where K is the only decision variable.
 *           The problem should be convex in the context of ODE-school-exercises.
 *           Sophisticated algorithms are available for this non-linear
 *           optimization tasks, but our math engine in file math.js is weak...
 *           So, we naively initialize K=0, as well as a step width S that is
 *           initialized to e.g. 1.
 *           In a (finite) sequence of iterations, we chose
 *               min { f(K-S), f(K), f(K+S) }.
 *           In case that the "direction" changes, S is replaced by S/2.
 *
 *   5.b.4)  Now check (with 10+ numerical tests), if our concrete  K from the
 *           last step yields in equivalency. If not, continue with the next
 *           permutation in step 5.
 *
 *   5.c)  If we get here, all K's for the present permutation are known.
 *         We now numerically check, if terms  u  and  v  are equivalent
 *         under the factors K. If we succeed, then QUIT WITH SUCCESS.
 *
 *   6. In case that none of the permutations tests succeeded, then QUIT WITH
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

  // first try comparing terms as implemented in file math.js
  // ... maybe we are in luck!
  if (Term.compare(tu, tv)) return true;

  // Some of the following steps are destructive, so work on copies!
  tu = tu.clone();
  tv = tv.clone();

  // Reduce subterms that only contain C_i as variable (e.g. "e^C" -> "C").
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
      // if there is a K \in \R which results in comparing terms
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
 * WARNING: Due to the primitivity of the math engine implemented in file
 *          math.js, we do not have the opportunity for automatic
 *          differentiation etc. This method should only be used for special
 *          cases.
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
