/*******************************************************************************
 * pySELL - Python based Simple E-Learning Language
 * AUTHOR:  Andreas Schwenk <mailto:contact@compiler-construction.com>
 * LICENSE: GPLv3
 ******************************************************************************/

import { genDiv, genInputField, genSpan, updateMathElement } from "./dom.js";
import { Matrix, Term } from "./math.js";
import { Question } from "./question.js";

/**
 * This file implements the textual input fields for terms and matrices.
 * Each input field observes the students inputs and forbids not allowed keys
 *   (e.g. special characters).
 * In case of non-integer inputs, the entered term is rendered via TeX,
 *   to let the student verify its input.
 * Matrices are resizable, i.e. its row and/or column count can be adjusted
 *   by students (this is NOT the case, if the sample solution is a row or
 *   column vector. Then only one dimension is resizable).
 */

/**
 * Input field for a textual gap.
 */
export class GapInput {
  /**
   * @param {HTMLElement} parent -- parent element where the input is appended to
   * @param {Question} question -- the question
   * @param {string} inputId -- the id for persisting the students input
   * @param {string} solutionString -- the sample solution
   */
  constructor(parent, question, inputId, solutionString) {
    /** @type {Question} */
    this.question = question;
    /** @type {string} */
    this.inputId = inputId;
    if (inputId.length == 0) {
      // generate a new id, if the input does not correspond to a variable,
      // but the solution was given directly as string in the text.
      this.inputId = inputId = "gap-" + question.gapIdx;
      question.types[this.inputId] = "string";
      question.expected[this.inputId] = solutionString;
      question.gapIdx++;
    }
    // initialize the students answer to "unset" in case it does not yet exist
    if (inputId in question.student == false) question.student[inputId] = "";
    // split the solution string into single answers
    let expectedList = solutionString.split("|");
    // get the maximum number of characters (to estimate the width of the input)
    let maxAnswerLen = 0;
    for (let i = 0; i < expectedList.length; i++) {
      let e = expectedList[i];
      if (e.length > maxAnswerLen) maxAnswerLen = e.length;
    }
    let span = genSpan("");
    parent.appendChild(span);
    let width = Math.max(maxAnswerLen * 15, 24);
    let input = genInputField(width);
    question.gapInputs[this.inputId] = input;
    input.addEventListener("keyup", () => {
      if (question.editingEnabled == false) return;
      this.question.editedQuestion();
      input.value = input.value.toUpperCase();
      this.question.student[this.inputId] = input.value.trim();
    });
    span.appendChild(input);
    if (this.question.showSolution) {
      this.question.student[this.inputId] = input.value = expectedList[0];
      if (expectedList.length > 1) {
        let allOptions = genSpan("[" + expectedList.join("|") + "]");
        allOptions.style.fontSize = "small";
        allOptions.style.textDecoration = "underline";
        span.appendChild(allOptions);
      }
    }
  }
}

/**
 * Input field for typing a term.
 */
export class TermInput {
  /**
   * @param {HTMLElement} parent -- parent element where the input is appended to
   * @param {Question} question -- the question
   * @param {string} inputId -- the id for persisting the students input
   * @param {number} numChars -- number of characters for the width-estimation
   * @param {string} solutionString -- the sample solution
   * @param {boolean} integersOnly -- if true, then only numbers can be entered
   * @param {boolean} forceSolution -- if true, the solution string will be set, regardless of question.showSolution
   */
  constructor(
    parent,
    question,
    inputId,
    numChars,
    solutionString,
    integersOnly,
    forceSolution = false
  ) {
    // initialize the students answer to "unset" in case it does not yet exist
    if (inputId in question.student == false) question.student[inputId] = "";
    /** @type {Question} */
    this.question = question;
    /** @type {string} */
    this.inputId = inputId;
    /**
     * @type {HTMLElement} -- additional span, where the HTMLInputElement,
     * as well as the TeX preview are embedded into
     */
    this.outerSpan = genSpan("");
    this.outerSpan.style.position = "relative";
    parent.appendChild(this.outerSpan);
    /** @type {HTMLInputElement} -- the input field for entering the input */
    this.inputElement = genInputField(Math.max(numChars * 12, 48));
    this.outerSpan.appendChild(this.inputElement);
    /** @type {HTMLDivElement} -- the TeX preview */
    this.equationPreviewDiv = genDiv();
    this.equationPreviewDiv.classList.add("equationPreview");
    this.equationPreviewDiv.style.display = "none"; // hidden per default
    this.outerSpan.appendChild(this.equationPreviewDiv);
    // events
    this.inputElement.addEventListener("click", () => {
      if (question.editingEnabled == false) return;
      // mark the question as altered
      this.question.editedQuestion();
      this.edited();
    });
    this.inputElement.addEventListener("keyup", () => {
      if (question.editingEnabled == false) return;
      // mark the question as altered
      this.question.editedQuestion();
      this.edited();
    });

    this.inputElement.addEventListener("focus", () => {
      if (question.editingEnabled == false) return;
    });

    this.inputElement.addEventListener("focusout", () => {
      // hide the TeX preview in case that the focus to the input was lost
      this.equationPreviewDiv.innerHTML = "";
      this.equationPreviewDiv.style.display = "none";
    });
    this.inputElement.addEventListener("keydown", (e) => {
      if (question.editingEnabled == false) {
        e.preventDefault();
        return;
      }
      // forbid special characters
      let allowed = "abcdefghijklmnopqrstuvwxyz";
      allowed += "ABCDEFGHIJKLMNOPQRSTUVWXYZ";
      allowed += "0123456789";
      allowed += "+-*/^(). <>=|";
      // only allow numbers in case of integral solutions
      if (integersOnly) allowed = "-0123456789";
      if (e.key.length < 3 && allowed.includes(e.key) == false)
        e.preventDefault();
      // extend the width of the input field, in case the student enters a
      // term that is longer than expected...
      let requiredWidth = this.inputElement.value.length * 12;
      if (this.inputElement.offsetWidth < requiredWidth)
        this.inputElement.style.width = "" + requiredWidth + "px";
    });
    // for debugging purposes
    if (forceSolution || this.question.showSolution)
      question.student[inputId] = this.inputElement.value = solutionString;
  }

  edited() {
    // the student updated the answer, so we must validate the syntax,
    // as well as update the TeX preview
    let input = this.inputElement.value.trim();
    let tex = "";
    let isConstant = false; // e.g. input is "123"
    try {
      let t = Term.parse(input);
      isConstant = t.root.op === "const";
      tex = t.toTexString();
      this.inputElement.style.color = "black";
      this.equationPreviewDiv.style.backgroundColor = "green";
    } catch (e) {
      // term is not valid, so use input, but with defused "^" and "_"
      tex = input.replaceAll("^", "\\hat{~}").replaceAll("_", "\\_");
      this.inputElement.style.color = "maroon";
      this.equationPreviewDiv.style.backgroundColor = "maroon";
    }
    // render the equation
    updateMathElement(this.equationPreviewDiv, tex, true);
    this.equationPreviewDiv.style.display =
      input.length > 0 && !isConstant ? "block" : "none";
    // update the input
    this.question.student[this.inputId] = input;
  }
}

/**
 * Resizable input table for entering a matrix.
 */
export class MatrixInput {
  /**
   * @param {HTMLElement} parent -- parent element where the matrix input is appended to
   * @param {Question} question -- the question
   * @param {string} inputId -- the id for persisting the students input
   * @param {string} expectedMatrixString -- the stringified sample solution
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
    /** @type {Matrix} -- the student must determine the sizing (except for vectors) */
    this.matStudent = new Matrix(
      this.matExpected.m == 1 ? 1 : 3,
      this.matExpected.n == 1 ? 1 : 3
    );
    if (question.showSolution) this.matStudent.fromMatrix(this.matExpected);
    // generate the DOM
    this.genMatrixDom(true);
  }

  /**
   * Generate the DOM (HTMLTable and children)
   * @param {boolean} initial -- true, iff generated the first time
   */
  genMatrixDom(initial) {
    // we need an additional HTMLDivElement that contains both the table for the
    // matrix, as well as the resizing buttons ("+" and "-")
    let div = genDiv();
    this.parent.innerHTML = "";
    this.parent.appendChild(div);
    div.style.position = "relative";
    div.style.display = "inline-block";
    // implement the core matrix as table
    let table = document.createElement("table");
    div.appendChild(table);
    // get the maximum string length of the elements (for estimating the width)
    let maxCellStrlen = this.matExpected.getMaxCellStrlen();
    // populate the table by rows and cells
    for (let i = 0; i < this.matStudent.m; i++) {
      let row = document.createElement("tr");
      table.appendChild(row);
      // insert a column for left parenthesis (rendered by a bordered HTMLDivElement)
      if (i == 0)
        row.appendChild(
          this.generateMatrixParenthesis(true, this.matStudent.m)
        );
      // for each column within the current row
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
          false,
          !initial
        );
      }
      // insert a column for the right (rendered by a bordered HTMLDivElement)
      if (i == 0)
        row.appendChild(
          this.generateMatrixParenthesis(false, this.matStudent.m)
        );
    }
    // add resize buttons (add column, remove column, add row, remove row)
    let text = ["+", "-", "+", "-"]; // button labels
    let deltaM = [0, 0, 1, -1]; // row delta
    let deltaN = [1, -1, 0, 0]; // column delta
    let top = [0, 22, 888, 888]; // signed valued positions, or 888 if invalid
    let bottom = [888, 888, -22, -22];
    let right = [-22, -22, 0, 22];
    let available = [
      // vectors are only resizable in one direction
      this.matExpected.n != 1,
      this.matExpected.n != 1,
      this.matExpected.m != 1,
      this.matExpected.m != 1,
    ];
    let hidden = [
      // hide the buttons, if there are too many/less rows/cols
      this.matStudent.n >= 10,
      this.matStudent.n <= 1,
      this.matStudent.m >= 10,
      this.matStudent.m <= 1,
    ];
    // render the (potentially) 4 buttons
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
          // set values from input to matrix elements
          for (let u = 0; u < this.matStudent.m; u++) {
            for (let v = 0; v < this.matStudent.n; v++) {
              let idx = u * this.matStudent.n + v;
              let id = this.inputId + "-" + idx;
              let value = this.question.student[id];
              this.matStudent.v[idx] = value;
              delete this.question.student[id];
            }
          }
          // resize matrix (and reuse old values if feasible)
          this.matStudent.resize(
            this.matStudent.m + deltaM[i],
            this.matStudent.n + deltaN[i],
            ""
          );
          // generate DOM
          this.genMatrixDom(false);
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
    // TODO: rounded border, if the langauge is e.g. "de"
    let cell = document.createElement("td");
    cell.style.width = "3px";
    for (let side of ["Top", left ? "Left" : "Right", "Bottom"]) {
      cell.style["border" + side + "Width"] = "2px";
      cell.style["border" + side + "Style"] = "solid";
    }
    if (this.question.language == "de") {
      if (left) cell.style.borderTopLeftRadius = "5px";
      else cell.style.borderTopRightRadius = "5px";
      if (left) cell.style.borderBottomLeftRadius = "5px";
      else cell.style.borderBottomRightRadius = "5px";
    }
    cell.rowSpan = rowSpan;
    return cell;
  }
}
