/*******************************************************************************
 * pySELL - Python based Simple E-Learning Language
 * AUTHOR:  Andreas Schwenk <mailto:contact@compiler-construction.com>
 * LICENSE: GPLv3
 ******************************************************************************/

/**
 * This file implements the question and its behavior, i.e. it controls most
 * of the magic.
 */

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
  iconCheck,
  iconCircleUnchecked,
  iconCircleChecked,
} from "./icons.js";
import { GapInput, MatrixInput, TermInput } from "./input.js";
import { Matrix, Term, TermNode, range } from "./math.js";

/**
 * The state of a question.
 */
export let QuestionState = {
  init: 0, // not evaluated
  errors: 1, // evaluated with errors
  passed: 2, // evaluated with no errors
};

/**
 * The quiz question.
 * For better understanding, create a JSON file of a quiz, e.g. via
 * "python3 sell.py -J examples/ex1.txt"
 */
export class Question {
  /**
   * @param {HTMLElement} parentDiv -- a parental div, where the question is put in
   * @param {Object.<Object,Object>} src -- the JSON-based question description
   * @param {string} language -- the natural langauge id (used for user info)
   * @param {boolean} debug -- debugging mode enabled? (true for "*_DEBUG.html")
   */
  constructor(parentDiv, src, language, debug) {
    /** @type {number} -- the state of the question */
    this.state = QuestionState.init;
    /** @type {string} -- the natural langauge identifier */
    this.language = language;
    /** @type {Object.<Object,Object>} -- the JSON-based description */
    this.src = src;
    /** @type {boolean} -- debugging enabled? */
    this.debug = debug;
    /** @type {number[]} -- the order of instances (each instance is a set of random variables) */
    this.instanceOrder = range(src.instances.length, true);
    /** @type {number} -- the current index in this.instanceOrder */
    this.instanceIdx = 0;
    /** @type {number} -- distinct index for every multiple or single choice */
    this.choiceIdx = 0;
    /** @type {number} -- distinct index for every gap field */
    this.gapIdx = 0;
    /** @type {Object.<string,string>} -- the expected solution (variable -> stringified solution) */
    this.expected = {};
    /** @type {Object.<string,string>} -- the type of each variable (e.g. "matrix", "int", ...) */
    this.types = {}; // variable types of this.expected
    /** @type {Object.<string,string>} -- the current answer(s) set by the student */
    this.student = {};
    /** @type {Object.<Object,HTMLInputElement>} - input elements for gaps for setting feedback colors */
    this.gapInputs = {};
    /** @type {HTMLElement} -- a parental div, where the question is put in  */
    this.parentDiv = parentDiv;
    /** @type {HTMLDivElement} -- the root HTMLDivElement of the current question */
    this.questionDiv = null;
    /** @type {HTMLDivElement} -- HTMLDivElement for the feedback popup (e.g. "awesome") */
    this.feedbackPopupDiv = null;
    /** @type {HTMLDivElement} -- HTMLDivElement for the title */
    this.titleDiv = null;
    /** @type {HTMLButtonElement} -- HTMLButtonElement for the eval/repeat button */
    this.checkAndRepeatBtn = null;
    /** @type {boolean} -- show the solution? */
    this.showSolution = false;
    /** @type {HTMLSpanElement} -- HTMLSpanElement for the feedback text next to the button */
    this.feedbackSpan = null;
    /** @type {number} -- number of correct answers */
    this.numCorrect = 0;
    /** @type {number} -- number of checked answers */
    this.numChecked = 0;
  }

  /**
   * Gets the next instance.
   */
  reset() {
    this.instanceIdx = (this.instanceIdx + 1) % this.src.instances.length;
  }

  /**
   * Gets the current instance.
   * @returns {Object.<string,Object>}
   */
  getCurrentInstance() {
    // TODO: check where this method is used. If this method returns undefined,
    // then consider this!!!
    let idx = this.instanceOrder[this.instanceIdx];
    return this.src.instances[idx];
  }

  /**
   * Sets the question to be edited recently. Visually, the font and border
   * color is set to black.
   */
  editedQuestion() {
    this.state = QuestionState.init;
    this.updateVisualQuestionState();
    this.questionDiv.style.color = "black";
    this.checkAndRepeatBtn.innerHTML = iconCheck;
    this.checkAndRepeatBtn.style.display = "block";
    this.checkAndRepeatBtn.style.color = "black";
  }

  /**
   * Sets the color scheme of the question, based on passing or errors.
   */
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

  /**
   * Generate the DOM of the question.
   * @returns {void}
   */
  populateDom() {
    this.parentDiv.innerHTML = "";
    // generate question div
    this.questionDiv = genDiv();
    this.parentDiv.appendChild(this.questionDiv);
    this.questionDiv.classList.add("question");
    // feedback overlay
    this.feedbackPopupDiv = genDiv();
    this.feedbackPopupDiv.classList.add("questionFeedback");
    this.questionDiv.appendChild(this.feedbackPopupDiv);
    this.feedbackPopupDiv.innerHTML = "awesome";
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
    // generate image, if applicable
    // TODO: reuse code of generating node type "image"
    let instance = this.getCurrentInstance();
    if (instance != undefined && "__svg_image" in instance) {
      let base64data = instance["__svg_image"].v;
      let imageDiv = genDiv();
      this.questionDiv.appendChild(imageDiv);
      let img = document.createElement("img");
      imageDiv.appendChild(img);
      img.classList.add("img");
      img.src = "data:image/svg+xml;base64," + base64data;
    }

    // generate question text
    for (let c of this.src.text.c)
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
      this.checkAndRepeatBtn.innerHTML = iconCheck;
      this.checkAndRepeatBtn.style.backgroundColor = "black";
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
          let type = instance[v].t;
          let value = instance[v].v;
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
          this.reset();
          this.populateDom();
        } else {
          evalQuestion(this);
        }
      });
    }
  }

  /**
   * Generates TeX source recursively.
   * @param {Object.<Object,Object>} node
   * @returns {string}
   */
  generateMathString(node) {
    let s = "";
    switch (node.t) {
      case "math":
      case "display-math":
        for (let c of node.c) {
          let sc = this.generateMathString(c);
          if (c.t === "var" && s.includes("!PM")) {
            // replace the last occurred "!PM" (plus-minus sign)
            // with the sign of the variable. The sign of the variable itself
            // is vanished.
            // TODO: test for non-integers
            if (sc.startsWith("{-")) {
              sc = "{" + sc.substring(2);
              s = s.replaceAll("!PM", "-");
            } else s = s.replaceAll("!PM", "+");
          }
          s += sc;
        }
        break;
      case "text":
        return node.d;
      case "plus_minus": {
        s += " !PM ";
        break;
      }
      case "var": {
        let instance = this.getCurrentInstance();
        let type = instance[node.d].t;
        let value = instance[node.d].v;
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
            return TermNode.const(real, imag).toTexString();
          }
          case "matrix": {
            // e.g. "[[1,2,3],[4,5,6]]" -> "\begin{pmatrix}1&2&3\\4%5%6\end{pmatrix}"
            let mat = new Matrix(0, 0);
            mat.fromString(value);
            s = mat.toTeXString(
              node.d.includes("augmented"),
              this.language != "de"
            );
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
    return node.t === "plus_minus" ? s : "{" + s + "}";
  }

  /**
   * Generates paragraphs, enumerations, ...
   * @param {Object.<Object,Object>} node
   * @param {boolean} spanInsteadParagraph
   * @returns {HTMLElement}
   */
  generateText(node, spanInsteadParagraph = false) {
    switch (node.t) {
      case "paragraph":
      case "span": {
        let e = document.createElement(
          node.t == "span" || spanInsteadParagraph ? "span" : "p"
        );
        for (let c of node.c) e.appendChild(this.generateText(c));
        return e;
      }
      case "text": {
        return genSpan(node.d);
      }
      case "code": {
        let span = genSpan(node.d);
        span.classList.add("code");
        return span;
      }
      case "italic":
      case "bold": {
        let span = genSpan("");
        span.append(...node.c.map((c) => this.generateText(c)));
        if (node.t === "bold") span.style.fontWeight = "bold";
        else span.style.fontStyle = "italic";
        return span;
      }
      case "math":
      case "display-math": {
        let tex = this.generateMathString(node);
        return genMathSpan(tex, node.t === "display-math");
      }
      case "string_var": {
        let span = genSpan("");
        let instance = this.getCurrentInstance();
        let type = instance[node.d].t;
        let value = instance[node.d].v;
        if (type === "string") span.innerHTML = value;
        else {
          span.innerHTML = "EXPECTED VARIABLE OF TYPE STRING";
          span.style.color = "red";
        }
        return span;
      }
      case "gap": {
        let span = genSpan("");
        new GapInput(span, this, "", node.d);
        return span;
      }
      case "input":
      case "input2": {
        // "input2" is an alternative mode, that simple turns off rendering
        // of parenthesis around sets / vectors
        let suppressParentheses = node.t === "input2";
        // outer span, where everything is put in
        let span = genSpan("");
        span.style.verticalAlign = "text-bottom";
        // identifier of the input variable
        let id = node.d;
        // expected value (stringified)
        let expected = this.getCurrentInstance()[id];
        // set expected value and type locally
        this.expected[id] = expected.v;
        this.types[id] = expected.t;
        // render parentheses around set / vector input (NOT for "input2")
        if (!suppressParentheses)
          switch (expected.t) {
            case "set":
              span.append(genMathSpan("\\{"), genSpan(" "));
              break;
            case "vector":
              span.append(genMathSpan("["), genSpan(" "));
              break;
          }
        if (expected.t === "string") {
          // gap question
          new GapInput(span, this, id, this.expected[id]);
        } else if (expected.t === "vector" || expected.t === "set") {
          // vector or set
          let elements = expected.v.split(",");
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
        } else if (expected.t === "matrix") {
          let parentDiv = genDiv();
          span.appendChild(parentDiv);
          new MatrixInput(parentDiv, this, id, expected.v);
        } else if (expected.t === "complex") {
          // complex number in normal form
          let elements = expected.v.split(",");
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
          let integersOnly = expected.t === "int";
          new TermInput(
            span,
            this,
            id,
            expected.v.length,
            expected.v,
            integersOnly
          );
        }
        // render parentheses around set / vector input (NOT for "input2")
        if (!suppressParentheses)
          switch (expected.t) {
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
        return genUl(node.c.map((c) => genLi(this.generateText(c))));
      }
      case "single-choice":
      case "multi-choice": {
        let mc = node.t == "multi-choice";
        let table = document.createElement("table");
        let n = node.c.length;
        let shuffled = this.debug == false;
        let order = range(n, shuffled);
        let iconCorrect = mc ? iconSquareChecked : iconCircleChecked;
        let iconIncorrect = mc ? iconSquareUnchecked : iconCircleUnchecked;
        let checkboxes = [];
        let answerIDs = [];
        for (let i = 0; i < n; i++) {
          let idx = order[i];
          let answer = node.c[idx];
          let answerId = "mc-" + this.choiceIdx + "-" + idx;
          answerIDs.push(answerId);
          let expectedValue =
            answer.c[0].t == "bool"
              ? answer.c[0].d
              : this.getCurrentInstance()[answer.c[0].d].v;
          this.expected[answerId] = expectedValue;
          this.types[answerId] = "bool";
          this.student[answerId] = this.showSolution ? expectedValue : "false";
          let text = this.generateText(answer.c[1], true);
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
      case "image": {
        let imageDiv = genDiv();
        let path = node.d;
        let pathTokens = path.split(".");
        let fileExtension = pathTokens[pathTokens.length - 1];
        let width = node.c[0].d;
        let b64 = node.c[1].d;
        let img = document.createElement("img");
        imageDiv.appendChild(img);
        img.classList.add("img");
        img.style.width = width + "%";
        let dataTypes = {
          svg: "svg+xml",
          png: "png",
          jpg: "jpeg",
        };
        img.src = "data:image/" + dataTypes[fileExtension] + ";base64," + b64;
        return imageDiv;
      }
      default: {
        // put error, in case the implementation in "sell.py" is more advances
        // than the web version :-)
        let span = genSpan("UNIMPLEMENTED(" + node.t + ")");
        span.style.color = "red";
        return span;
      }
    }
  }
}
