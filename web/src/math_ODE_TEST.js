/*******************************************************************************
 * pySELL - Python based Simple E-Learning Language
 * AUTHOR:  Andreas Schwenk <mailto:contact@compiler-construction.com>
 * LICENSE: GPLv3
 ******************************************************************************/

import { Term } from "./math.js";

import assert from "assert";
import { compareODE, prepareODEconstantComparison } from "./math_ODE.js";

let t = Term.parse("sin(exp(cos(C+3))) + 3*C1 + sin(C1+C2)");
prepareODEconstantComparison(t.root);
assert.equal(compareODE(t, Term.parse("C+C1+sin(C1+C2)")), true);

// simple example; both terms are equivalent
assert.equal(
  compareODE(
    Term.parse("(C*exp(2*x)-2)*exp(3*x)"),
    Term.parse("C*exp(5*x)-2*exp(3*x)")
  ),
  true
);

// example where the constant C of one of the terms must be multiplied by
// a factor to get two equivalent terms. If the C of the first term is replaced
// by K*C, and we determine K=1/6, then term comparison can be applied!
assert.equal(
  compareODE(
    Term.parse("sqrt(C-12*x^3)/3"),
    Term.parse("sqrt(2/3)*sqrt(C-2*x^3)")
  ),
  true
);

// example with two constants
assert.equal(
  compareODE(
    Term.parse("C1 * exp(2x) + C2 * exp(-4x)"),
    Term.parse("2*C1 * exp(2x) + exp(C2) * exp(-4x)")
  ),
  true
);

// example with swapped constants
assert.equal(
  compareODE(
    Term.parse("C1 * exp(2x) + C2 * exp(-4x)"),
    Term.parse("C2 * exp(2x) + C1 * exp(-4x)")
  ),
  true
);
