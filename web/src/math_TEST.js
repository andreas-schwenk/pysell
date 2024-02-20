/*******************************************************************************
 * pySELL - Python based Simple E-Learning Language
 * AUTHOR:  Andreas Schwenk <mailto:contact@compiler-construction.com>
 * LICENSE: GPLv3
 ******************************************************************************/

import assert from "assert";

import { Node, Term } from "./math.js";

// TODO: compare e.g. "1/x" -> need to adjust compare implementation!!

// TODO: test "all combinations" of complex:
let texTests = [
  "ln(x) * (2+4)",
  "|1/(x+x)|",
  "sqrt(x^2)",
  "sqrt x^2",
  "sqrt x ^2",
  "-sin 3x + cos(x^5+1) / 7",
];
for (let tt of texTests) {
  let t = Term.parse(tt);
  console.log(t.toString());
  console.log(t.toTexString());
}

let tests = `
xyz t          == x*y*z*t
2+4*5          == 2+(4*5)
(2+4)*5        == 30
2^3            == (2^3)
2^3^4          == ((2^3)^4)
(2i)^3         == ((2*(1i))^3)
-sin 3x + cos(x^5+1) == (-(sin((3*x)))+cos(((x^5)+1)))
2^3            == 8
2^3            != 8.000001
(1+2i)^(3+4i)  == 0.129009594074467+0.03392409290517014i
sin(1-3i)      == 8.471645454300148-5.412680923178193i
cos(5.1+8.2i)  == 688.0991411542753+1685.422498937827i
tan(2-3i)      == -0.003764025641504249-1.00323862735361i
cot(-1+3i)     == -0.004498537605093545-0.9979289472313777i
exp(-1-3i)     == -0.3641978864132929-0.05191514970317339i
2x             == x + x
2x             != x + x + 0.00001
cos 0          == 1
cos(0)         == 1
sinpi2         == sin(pi)*2
sin2pi         == sin(2*pi)
sin pi+pi      == sin(pi)+pi
sin pipi       == sin(pi*pi)
sin 2pi        == sin(2*pi)
sin 2*pi       == sin(2*pi)
sin 2*pi*5     == sin(2*pi*5)
sin 2*pi *5    == sin(2*pi)*5
sin (2*pi)     == sin(2*pi)
sin 2* pi      == sin(2*pi)
sin 2(pi)      == sin(2)*pi
sin 2 * pi     == sin(2)*pi
sin 2 *pi      == sin(2)*pi
sin 2 pi       == sin(2)*pi
sin pi^2       == sin(pi^2)
sin pi^2^2     == sin((pi^2)^2)
sin pi^2 ^2    == sin(pi^2)^2
sin pi ^2      == (sin(pi))^2
lnx            == ln(x)
lnx 2          == ln(x)*2
sin 2pi + 1    == 1
sin 2 * pi + 1 == sin(2) * pi + 1
sin 2 pi + 1   == sin(2) * pi + 1
sin 2*pi*4 + 3 == 3
sin 2 pi 4 + 3 == sin(2)*pi*4+3
sin(2pi)       == 0
sin(pi/2)      == 1
sqrt(-1)       == i
1/x            == x^(-1)
sinc2x+1       == sin(2x)/(2x)+1
`;

for (let test of tests.split("\n")) {
  test = test.split("#")[0].trim();
  if (test.length == 0) continue;
  let equal = test.includes("==");
  let tk = equal ? test.split("==") : test.split("!=");
  console.log("comparing " + tk[0] + " == " + tk[1]);
  console.log(
    " ----> " +
      Term.parse(tk[0]).toString() +
      " == " +
      Term.parse(tk[1]).toString()
  );
  let res = Term.parse(tk[0]).compare(Term.parse(tk[1]));
  assert.equal(res, equal);
}

assert.equal(Term.parse("2^3").compare(Term.parse("8")), true);

assert.ok(
  Term.parse("- x^2 + y^2 + xy + x(y+1) + sin(2) + sin 3*x + e^0 + e^3 + 2pi")
    .eval({ x: Node.const(3), y: Node.const(5) })
    .compare(77.69013814243468, 0)
);
assert.ok(
  Term.parse("(8*x + 5)*cos(4*x^2 + 5*x + 6)")
    .eval({ x: Node.const(2) })
    .compare(17.51869057063671, 0)
);
