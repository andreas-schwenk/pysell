/*******************************************************************************
 * pySELL - Python based Simple E-Learning Language
 * AUTHOR:  Andreas Schwenk <mailto:contact@compiler-construction.com>
 * LICENSE: GPLv3
 ******************************************************************************/

import {
  genButton,
  genDiv,
  genInputField,
  genLi,
  genMathSpan,
  genSpan,
  genUl,
} from "./dom.js";
import { evalQuestion } from "./eval.js";
import {
  iconSquareChecked,
  iconSquareUnchecked,
  iconPlay,
  iconCircleUnchecked,
  iconCircleChecked,
} from "./icons.js";
import { MatrixInput, TermInput } from "./input.js";
import { Matrix, Term, range } from "./math.js";

export let QuestionState = {
  init: 0, // not evaluated
  errors: 1, // evaluated with errors
  passed: 2, // evaluated with no errors
};

export class Question {
  /**
   * @param {HTMLElement} parentDiv
   * @param {Object.<Object,Object>} src
   * @param {string} language
   * @param {boolean} debug
   */
  constructor(parentDiv, src, language, debug) {
    /** @type {number} */
    this.state = QuestionState.init;
    /** @type {string} */
    this.language = language;
    /** @type {Object.<Object,Object>} */
    this.src = src;
    /** @type {boolean} */
    this.debug = debug;
    /** @type {number[]} */
    this.instanceOrder = range(src.instances.length, true);
    /** @type {number} */
    this.instanceIdx = 0;
    /** @type {number} */
    this.choiceIdx = 0; // distinct index for every multi or single choice
    /** @type {number} */
    this.gapIdx = 0; // distinct index for every gap field
    /** @type {Object.<string,string>} */
    this.expected = {};
    /** @type {Object.<string,string>} */
    this.types = {}; // variable types of this.expected
    /** @type {Object.<string,string>} */
    this.student = {};
    /** @type {Object.<Object,HTMLInputElement>} */
    this.gapInputs = {}; // html input elements (currently ONLY used for type gap)
    /** @type {HTMLElement} */
    this.parentDiv = parentDiv;
    /** @type {HTMLDivElement} */
    this.questionDiv = null;
    /** @type {HTMLDivElement} */
    this.feedbackDiv = null;
    /** @type {HTMLDivElement} */
    this.titleDiv = null;
    /** @type {HTMLButtonElement} */
    this.checkAndRepeatBtn = null;
    /** @type {string} */
    this.checkAndRepeatBtnState = "check";
    /** @type {boolean} */
    this.showSolution = false;
    /** @type {HTMLSpanElement} */
    this.feedbackSpan = null;
    /** @type {number} */
    this.numCorrect = 0;
    /** @type {number} */
    this.numChecked = 0;
  }

  reset() {
    this.instanceIdx = (this.instanceIdx + 1) % this.src.instances.length;
  }

  /**
   * @returns {Object.<string,Object>}
   */
  getCurrentInstance() {
    return this.src.instances[this.instanceOrder[this.instanceIdx]];
  }

  editedQuestion() {
    this.state = QuestionState.init;
    this.updateVisualQuestionState();
    this.questionDiv.style.color = "black";
    this.checkAndRepeatBtn.innerHTML = iconPlay;
    this.checkAndRepeatBtn.style.display = "block";
    this.checkAndRepeatBtn.style.color = "black";
    this.checkAndRepeatBtnState = "check";
  }

  updateVisualQuestionState() {
    let color1 = "black";
    let color2 = "transparent";
    switch (this.state) {
      case QuestionState.init:
        color1 = "rgb(0,0,0)";
        color2 = "transparent";
        break;
      case QuestionState.passed:
        color1 = "rgb(0,150,0)";
        color2 = "rgba(0,150,0, 0.025)";
        break;
      case QuestionState.errors:
        color1 = "rgb(150,0,0)";
        color2 = "rgba(150,0,0, 0.025)";
        if (this.numChecked >= 5) {
          this.feedbackSpan.innerHTML =
            "" + this.numCorrect + " / " + this.numChecked;
        }
        break;
    }
    this.questionDiv.style.color =
      this.feedbackSpan.style.color =
      this.titleDiv.style.color =
      this.checkAndRepeatBtn.style.backgroundColor =
      this.questionDiv.style.borderColor =
        color1;
    this.questionDiv.style.backgroundColor = color2;
  }

  populateDom() {
    this.parentDiv.innerHTML = "";
    // generate question div
    this.questionDiv = genDiv();
    this.parentDiv.appendChild(this.questionDiv);
    this.questionDiv.classList.add("question");
    // feedback overlay
    this.feedbackDiv = genDiv();
    this.feedbackDiv.classList.add("questionFeedback");
    this.questionDiv.appendChild(this.feedbackDiv);
    this.feedbackDiv.innerHTML = "awesome";
    // debug text (source line)
    if (this.debug && "src_line" in this.src) {
      let title = genDiv();
      title.classList.add("debugInfo");
      title.innerHTML = "Source code: lines " + this.src["src_line"] + "..";
      this.questionDiv.appendChild(title);
    }
    // generate question title
    this.titleDiv = genDiv();
    this.questionDiv.appendChild(this.titleDiv);
    this.titleDiv.classList.add("questionTitle");
    this.titleDiv.innerHTML = this.src["title"];
    // error?
    if (this.src["error"].length > 0) {
      let errorSpan = genSpan(this.src["error"]);
      this.questionDiv.appendChild(errorSpan);
      errorSpan.style.color = "red";
      return;
    }
    // generate question text
    for (let c of this.src.text.children)
      this.questionDiv.appendChild(this.generateText(c));
    // generate button row
    let buttonDiv = genDiv();
    this.questionDiv.appendChild(buttonDiv);
    buttonDiv.classList.add("buttonRow");
    // (a) check button
    let hasCheckButton = Object.keys(this.expected).length > 0;
    if (hasCheckButton) {
      this.checkAndRepeatBtn = genButton();
      buttonDiv.appendChild(this.checkAndRepeatBtn);
      this.checkAndRepeatBtn.innerHTML = iconPlay;
    }
    // (c) spacing
    let space = genSpan("&nbsp;&nbsp;&nbsp;");
    buttonDiv.appendChild(space);
    // (d) feedback text
    this.feedbackSpan = genSpan("");
    buttonDiv.appendChild(this.feedbackSpan);
    // debug text (variables, python src, text src)
    if (this.debug) {
      if (this.src.variables.length > 0) {
        // variables title
        let title = genDiv();
        title.classList.add("debugInfo");
        title.innerHTML = "Variables generated by Python Code";
        this.questionDiv.appendChild(title);
        // variables
        let varDiv = genDiv();
        varDiv.classList.add("debugCode");
        this.questionDiv.appendChild(varDiv);
        let instance = this.getCurrentInstance();
        let html = "";
        let variables = [...this.src["variables"]];
        variables.sort();
        for (let v of variables) {
          let type = instance[v].type;
          let value = instance[v].value;
          switch (type) {
            case "vector":
              value = "[" + value + "]";
              break;
            case "set":
              value = "{" + value + "}";
              break;
          }
          html += type + " " + v + " = " + value + "<br/>";
        }
        varDiv.innerHTML = html;
      }
      // syntax highlighted source code
      let sources = ["python_src_html", "text_src_html"];
      let titles = ["Python Source Code", "Text Source Code"];
      for (let i = 0; i < sources.length; i++) {
        let key = sources[i];
        if (key in this.src && this.src[key].length > 0) {
          // title
          let title = genDiv();
          title.classList.add("debugInfo");
          title.innerHTML = titles[i];
          this.questionDiv.appendChild(title);
          // source code
          let code = genDiv();
          code.classList.add("debugCode");
          this.questionDiv.append(code);
          code.innerHTML = this.src[key];
        }
      }
    }
    // evaluation
    if (hasCheckButton) {
      this.checkAndRepeatBtn.addEventListener("click", () => {
        if (this.state == QuestionState.passed) {
          this.state = QuestionState.init;
          //this.debug = false;
          //this.showSolution = false;
          this.reset();
          this.populateDom();
        } else {
          evalQuestion(this);
        }
      });
    }
  }

  /**
   * @param {Object.<Object,Object>} node
   * @returns {string}
   */
  generateMathString(node) {
    let s = "";
    switch (node.type) {
      case "math":
      case "display-math":
        for (let c of node.children) s += this.generateMathString(c);
        break;
      case "text":
        return node.data;
      case "var": {
        let instance = this.getCurrentInstance();
        let type = instance[node.data].type;
        let value = instance[node.data].value;
        switch (type) {
          case "vector":
            // TODO: elements as terms -> toTexStrings
            return "\\left[" + value + "\\right]";
          case "set":
            // TODO: elements as terms -> toTexStrings
            return "\\left\\{" + value + "\\right\\}";
          case "complex": {
            let tk = value.split(",");
            let real = parseFloat(tk[0]);
            let imag = parseFloat(tk[1]);
            let s = "";
            if (Math.abs(real) > 1e-9) s += real;
            if (Math.abs(imag) > 1e-9) s += (imag < 0 ? "-" : "+") + imag + "i";
            return s;
          }
          case "matrix": {
            // e.g. "[[1,2,3],[4,5,6]]" -> "\begin{pmatrix}1&2&3\\4%5%6\end{pmatrix}"
            let mat = new Matrix(0, 0);
            mat.fromString(value);
            s = mat.toTeXString(node.data.includes("augmented"));
            return s;
          }
          case "term": {
            try {
              s = Term.parse(value).toTexString();
            } catch (e) {
              // failed, so keep input...
            }
            break;
          }
          default:
            s = value;
        }
      }
    }
    return s;
  }

  /**
   * TODO: remove code after migration input input.js
   * @param {HTMLInputElement} input
   */
  validateTermInput(input) {
    let ok = true;
    let value = input.value;
    if (value.length > 0) {
      try {
        Term.parse(value);
      } catch (e) {
        ok = false;
      }
    }
    input.style.color = ok ? "black" : "maroon";
    //input.style.fontStyle = ok ? "normal" : "italic";
  }

  /**
   * @param {Object.<Object,Object>} node
   * @param {boolean} spanInsteadParagraph
   * @returns {HTMLElement}
   */
  generateText(node, spanInsteadParagraph = false) {
    switch (node.type) {
      case "paragraph":
      case "span": {
        let e = document.createElement(
          node.type == "span" || spanInsteadParagraph ? "span" : "p"
        );
        for (let c of node.children) e.appendChild(this.generateText(c));
        return e;
      }
      case "text": {
        return genSpan(node.data);
      }
      case "code": {
        let span = genSpan(node.data);
        span.classList.add("code");
        return span;
      }
      case "italic":
      case "bold": {
        let span = genSpan("");
        span.append(...node.children.map((c) => this.generateText(c)));
        if (node.type === "bold") span.style.fontWeight = "bold";
        else span.style.fontStyle = "italic";
        return span;
      }
      case "math":
      case "display-math": {
        let tex = this.generateMathString(node);
        return genMathSpan(tex, node.type === "display-math");
      }
      case "gap": {
        let span = genSpan("");
        let width = Math.max(node.data.length * 14, 24);
        let input = genInputField(width);
        let id = "gap-" + this.gapIdx;
        this.gapInputs[id] = input;
        this.expected[id] = node.data;
        this.types[id] = "string";
        input.addEventListener("keyup", () => {
          this.editedQuestion();
          input.value = input.value.toUpperCase();
          this.student[id] = input.value.trim();
        });
        if (this.showSolution)
          this.student[id] = input.value = this.expected[id];
        this.gapIdx++;
        span.appendChild(input);
        return span;
      }
      case "input":
      case "input2": {
        let suppressParentheses = node.type === "input2";
        let span = genSpan("");
        span.style.verticalAlign = "text-bottom";
        let id = node.data;
        let expected = this.getCurrentInstance()[id];
        this.expected[id] = expected.value;
        this.types[id] = expected.type;
        if (!suppressParentheses)
          switch (expected.type) {
            case "set":
              span.append(genMathSpan("\\{"), genSpan(" "));
              break;
            case "vector":
              span.append(genMathSpan("["), genSpan(" "));
              break;
          }
        if (expected.type === "vector" || expected.type === "set") {
          // vector or set
          let elements = expected.value.split(",");
          let n = elements.length;
          for (let i = 0; i < n; i++) {
            if (i > 0) span.appendChild(genSpan(" , "));
            let elementId = id + "-" + i;
            new TermInput(
              span,
              this,
              elementId,
              elements[i].length,
              elements[i],
              false
            );
          }
        } else if (expected.type === "matrix") {
          let parentDiv = genDiv();
          span.appendChild(parentDiv);
          new MatrixInput(parentDiv, this, id, expected.value);
        } else if (expected.type === "complex") {
          // complex number in normal form
          let elements = expected.value.split(",");
          new TermInput(
            span,
            this,
            id + "-0",
            elements[0].length,
            elements[0],
            false
          );
          span.append(genSpan(" "), genMathSpan("+"), genSpan(" "));
          new TermInput(
            span,
            this,
            id + "-1",
            elements[1].length,
            elements[1],
            false
          );
          span.append(genSpan(" "), genMathSpan("i"));
        } else {
          let integersOnly = expected.type === "int";
          new TermInput(
            span,
            this,
            id,
            expected.value.length,
            expected.value,
            integersOnly
          );
        }
        if (!suppressParentheses)
          switch (expected.type) {
            case "set":
              span.append(genSpan(" "), genMathSpan("\\}"));
              break;
            case "vector":
              span.append(genSpan(" "), genMathSpan("]"));
              break;
          }
        return span;
      }
      case "itemize": {
        return genUl(node.children.map((c) => genLi(this.generateText(c))));
      }
      case "single-choice":
      case "multi-choice": {
        let mc = node.type == "multi-choice";
        let table = document.createElement("table");
        let n = node.children.length;
        let shuffled = this.debug == false;
        let order = range(n, shuffled);
        let iconCorrect = mc ? iconSquareChecked : iconCircleChecked;
        let iconIncorrect = mc ? iconSquareUnchecked : iconCircleUnchecked;
        let checkboxes = [];
        let answerIDs = [];
        for (let i = 0; i < n; i++) {
          let idx = order[i];
          let answer = node.children[idx];
          let answerId = "mc-" + this.choiceIdx + "-" + idx;
          answerIDs.push(answerId);
          let expectedValue =
            answer.children[0].type == "bool"
              ? answer.children[0].data
              : this.getCurrentInstance()[answer.children[0].data].value;
          this.expected[answerId] = expectedValue;
          this.types[answerId] = "bool";
          this.student[answerId] = this.showSolution ? expectedValue : "false";
          let text = this.generateText(answer.children[1], true);
          // dom
          let tr = document.createElement("tr");
          table.appendChild(tr);
          tr.style.cursor = "pointer";
          let tdCheckBox = document.createElement("td");
          checkboxes.push(tdCheckBox);
          tr.appendChild(tdCheckBox);
          tdCheckBox.innerHTML =
            this.student[answerId] == "true" ? iconCorrect : iconIncorrect;
          let tdText = document.createElement("td");
          tr.appendChild(tdText);
          tdText.appendChild(text);
          if (mc) {
            // multi-choice
            tr.addEventListener("click", () => {
              this.editedQuestion();
              this.student[answerId] =
                this.student[answerId] === "true" ? "false" : "true";
              if (this.student[answerId] === "true")
                tdCheckBox.innerHTML = iconCorrect;
              else tdCheckBox.innerHTML = iconIncorrect;
            });
          } else {
            // single-choice
            tr.addEventListener("click", () => {
              this.editedQuestion();
              for (let id of answerIDs) this.student[id] = "false";
              this.student[answerId] = "true";
              for (let i = 0; i < answerIDs.length; i++) {
                let idx = order[i];
                checkboxes[idx].innerHTML =
                  this.student[answerIDs[idx]] == "true"
                    ? iconCorrect
                    : iconIncorrect;
              }
            });
          }
        }
        this.choiceIdx++;
        return table;
      }
      default: {
        let span = genSpan("UNIMPLEMENTED(" + node.type + ")");
        span.style.color = "red";
        return span;
      }
    }
  }
}
