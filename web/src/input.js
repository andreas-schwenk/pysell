/*******************************************************************************
 * pySELL - Python based Simple E-Learning Language
 * AUTHOR:  Andreas Schwenk <mailto:contact@compiler-construction.com>
 * LICENSE: GPLv3
 ******************************************************************************/

import { genDiv, genInputField, genSpan, updateMathElement } from "./dom.js";
import { Matrix, Term } from "./math.js";
import { Question } from "./question.js";

export class TermInput {
  /**
   * @param {HTMLElement} parent
   * @param {Question} question
   * @param {string} inputId
   * @param {number} numChars
   * @param {string} solutionString
   * @param {boolean} integersOnly
   */
  constructor(
    parent,
    question,
    inputId,
    numChars,
    solutionString,
    integersOnly
  ) {
    question.student[inputId] = "";
    /** @type {Question} */
    this.question = question;
    /** @type {string} */
    this.inputId = inputId;
    /** @type {HTMLElement} */
    this.outerSpan = genSpan("");
    this.outerSpan.style.position = "relative";
    parent.appendChild(this.outerSpan);
    /** @type {HTMLInputElement} */
    this.inputElement = genInputField(Math.max(numChars * 10, 48));
    this.outerSpan.appendChild(this.inputElement);
    /** @type {HTMLDivElement} */
    this.equationPreviewDiv = genDiv();
    this.equationPreviewDiv.classList.add("equationPreview");
    this.equationPreviewDiv.style.display = "none";
    this.outerSpan.appendChild(this.equationPreviewDiv);
    // events
    this.inputElement.addEventListener("click", () => {
      this.edited();
    });
    this.inputElement.addEventListener("focusout", () => {
      this.equationPreviewDiv.innerHTML = "";
      this.equationPreviewDiv.style.display = "none";
    });
    this.inputElement.addEventListener("keydown", (e) => {
      let allowed = "abcdefghijklmnopqrstuvwxyz";
      allowed += "ABCDEFGHIJKLMNOPQRSTUVWXYZ";
      allowed += "0123456789";
      allowed += "+-*/^(). <>=|";
      if (integersOnly) {
        allowed = "-0123456789";
      }
      if (e.key.length < 3 && allowed.includes(e.key) == false) {
        e.preventDefault();
      }
    });
    this.inputElement.addEventListener("keyup", () => {
      this.question.editedQuestion();
      this.edited();
    });
    if (this.question.showSolution)
      question.student[inputId] = this.inputElement.value = solutionString;
  }

  edited() {
    let input = this.inputElement.value.trim();
    let tex = "";
    let isConstant = false; // e.g. input is "123"
    try {
      let t = Term.parse(input);
      isConstant = t.root.op === "const";
      tex = t.toTexString();
      this.equationPreviewDiv.style.backgroundColor = "green";
    } catch (e) {
      // term is not valid, so use input, but with defused "^" and "_"
      tex = input.replaceAll("^", "\\hat{~}").replaceAll("_", "\\_");
      this.equationPreviewDiv.style.backgroundColor = "maroon";
    }
    updateMathElement(this.equationPreviewDiv, tex, true);
    this.equationPreviewDiv.style.display =
      input.length > 0 && !isConstant ? "block" : "none";
    this.question.student[this.inputId] = input;
    this.validateTermInput();
  }

  validateTermInput() {
    let ok = true;
    let value = this.inputElement.value.trim();
    if (value.length > 0) {
      try {
        Term.parse(value);
      } catch (e) {
        ok = false;
      }
    }
    this.inputElement.style.color = ok ? "black" : "maroon";
  }
}

export class MatrixInput {
  /**
   * @param {HTMLElement} parent
   * @param {Question} question
   * @param {string} inputId
   * @param {string} expectedMatrixString
   */
  constructor(parent, question, inputId, expectedMatrixString) {
    /** @type {HTMLElement} */
    this.parent = parent;
    /** @type {Question} */
    this.question = question;
    /** @type {string} */
    this.inputId = inputId;
    /** @type {Matrix} */
    this.matExpected = new Matrix(0, 0);
    this.matExpected.fromString(expectedMatrixString);
    /** @type {Matrix} */
    this.matStudent = new Matrix(
      this.matExpected.m == 1 ? 1 : 3,
      this.matExpected.n == 1 ? 1 : 3
    );
    if (question.showSolution) {
      this.matStudent.fromMatrix(this.matExpected);
    }
    this.genMatrixDom();
  }

  genMatrixDom() {
    // parent div
    let div = genDiv();
    this.parent.innerHTML = "";
    this.parent.appendChild(div);
    div.style.position = "relative";
    div.style.display = "inline-block";
    // core matrix
    let table = document.createElement("table");
    div.appendChild(table);
    let maxCellStrlen = this.matExpected.getMaxCellStrlen();
    for (let i = 0; i < this.matStudent.m; i++) {
      let row = document.createElement("tr");
      table.appendChild(row);
      if (i == 0)
        row.appendChild(
          this.generateMatrixParenthesis(true, this.matStudent.m)
        );
      for (let j = 0; j < this.matStudent.n; j++) {
        let idx = i * this.matStudent.n + j;
        let cell = document.createElement("td");
        row.appendChild(cell);
        let elementId = this.inputId + "-" + idx;
        new TermInput(
          cell,
          this.question,
          elementId,
          maxCellStrlen,
          this.matStudent.v[idx],
          false
        );
      }
      if (i == 0)
        row.appendChild(
          this.generateMatrixParenthesis(false, this.matStudent.m)
        );
    }
    // resize buttons [add col, remove col, add row, remove row]
    let text = ["+", "-", "+", "-"];
    let deltaM = [0, 0, 1, -1];
    let deltaN = [1, -1, 0, 0];
    let top = [0, 22, 888, 888];
    let bottom = [888, 888, -22, -22];
    let right = [-22, -22, 0, 22];
    let available = [
      this.matExpected.n != 1,
      this.matExpected.n != 1,
      this.matExpected.m != 1,
      this.matExpected.m != 1,
    ];
    let hidden = [
      this.matStudent.n >= 10,
      this.matStudent.n <= 1,
      this.matStudent.m >= 10,
      this.matStudent.m <= 1,
    ];
    for (let i = 0; i < 4; i++) {
      if (available[i] == false) continue;
      let btn = genSpan(text[i]);
      if (top[i] != 888) btn.style.top = "" + top[i] + "px";
      if (bottom[i] != 888) btn.style.bottom = "" + bottom[i] + "px";
      if (right[i] != 888) btn.style.right = "" + right[i] + "px";
      btn.classList.add("matrixResizeButton");
      div.appendChild(btn);
      if (hidden[i]) {
        btn.style.opacity = "0.5";
      } else {
        btn.addEventListener("click", () => {
          this.matStudent.resize(
            this.matStudent.m + deltaM[i],
            this.matStudent.n + deltaN[i],
            "0"
          );
          this.genMatrixDom();
        });
      }
    }
  }

  /**
   * @param {boolean} left
   * @param {number} rowSpan
   * @returns {HTMLTableCellElement}
   */
  generateMatrixParenthesis(left, rowSpan) {
    let cell = document.createElement("td");
    cell.style.width = "3px";
    for (let side of ["Top", left ? "Left" : "Right", "Bottom"]) {
      cell.style["border" + side + "Width"] = "2px";
      cell.style["border" + side + "Style"] = "solid";
    }
    cell.rowSpan = rowSpan;
    return cell;
  }
}
