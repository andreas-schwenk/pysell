/*******************************************************************************
 * SELL - Simple E-Learning Language
 * AUTHOR:  Andreas Schwenk <mailto:contact@compiler-construction.com>
 * LICENSE: GPLv3
 ******************************************************************************/

import { Term } from "./math.js";

let t = new Term();
t.parse("- x^2 + y^2 + xy + x(y+1) + sin(2) + sin 3*x + e^0 + e^3 + 2pi");
let vars = new Set();
t.getVars(vars);
let res = t.eval({ x: "num:3", y: "num:5" });

let u = new Term();
u.parse("2x");
let v = new Term();
v.parse("x + x + 0.0000000001");
let equal = u.compare(v);

let z = new Term();
z.parse("(8*x + 5)*cos(4*x^2 + 5*x + 6)");
res = z.eval({ x: "num:2" });

let bp = 1337;
