import {
  iconSquareChecked,
  iconSquareUnchecked,
  iconPlay,
  iconCircleUnchecked,
  iconCircleChecked,
} from "./icons.js";
import { courseInfo1, courseInfo2, courseInfo3 } from "./lang.js";

/**
 * @param {number} n
 * @returns {number[]}
 */
function shuffledIndices(n) {
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

/**
 * @returns {HTMLInputElement}
 */
function genInputField() {
  let input = document.createElement("input");
  input.type = "text";
  input.classList.add("inputField");
  return input;
}

/**
 * @param {string} innerHTML
 * @returns {HTMLSpanElement}
 */
function genSpan(innerHTML) {
  let span = document.createElement("span");
  span.innerHTML = innerHTML;
  return span;
}

/**
 * @param {string} tex
 * @returns {HTMLSpanElement}
 */
function genMathSpan(tex) {
  let span = document.createElement("span");
  // @ts-ignore
  katex.render(tex, span, {
    throwOnError: false,
  });
  return span;
}

class Question {
  /**
   * @param {Object.<Object,Object>} src
   */
  constructor(src) {
    this.src = src;
    this.instanceIdx = Math.floor(Math.random() * src.instances.length);
    this.choiceIdx = 0; // distinct index for every multi or single choice
    this.expected = {};
    this.types = {}; // variable types of this.expected
    this.student = {};
    this.qDiv = null;
    this.titleDiv = null;
    this.checkBtn = null;
    this.showSolution = false;
  }

  /**
   * @param {HTMLElement} parent
   */
  populateDom(parent) {
    // generate question div
    this.qDiv = document.createElement("div");
    parent.appendChild(this.qDiv);
    this.qDiv.classList.add("question");
    // generate question title
    this.titleDiv = document.createElement("div");
    this.qDiv.appendChild(this.titleDiv);
    this.titleDiv.classList.add("questionTitle");
    this.titleDiv.innerHTML = this.src["title"];
    // error?
    if (this.src["error"].length > 0) {
      let errorSpan = document.createElement("span");
      this.qDiv.appendChild(errorSpan);
      errorSpan.style.color = "red";
      errorSpan.innerHTML = this.src["error"];
      return;
    }
    // generate question text
    for (let c of this.src.text.children)
      this.qDiv.appendChild(this.generateText(c));
    // generate button row
    let buttonDiv = document.createElement("div");
    this.qDiv.appendChild(buttonDiv);
    buttonDiv.classList.add("buttonRow");
    // (a) check button
    this.checkBtn = document.createElement("button");
    buttonDiv.appendChild(this.checkBtn);
    this.checkBtn.type = "button";
    this.checkBtn.classList.add("button");
    //this.checkBtn.innerHTML = "check";
    this.checkBtn.innerHTML = iconPlay;
    // (b) spacing
    let space = document.createElement("span");
    space.innerHTML = "&nbsp;&nbsp;&nbsp;";
    buttonDiv.appendChild(space);
    // (c) feedback text
    let feedbackSpan = document.createElement("span");
    buttonDiv.appendChild(feedbackSpan);
    // evaluation
    this.checkBtn.addEventListener("click", () => {
      feedbackSpan.innerHTML = "";
      let numChecked = 0;
      let numCorrect = 0;
      for (let id in this.expected) {
        //console.log("comparing answer " + id);
        let type = this.types[id];
        //console.log("type = " + type);
        let student = this.student[id];
        //console.log("student = " + student);
        let expected = this.expected[id];
        //console.log("expected = " + expected);
        switch (type) {
          case "int":
          case "bool":
            if (student == expected) numCorrect++;
            break;
          default:
            feedbackSpan.innerHTML = "UNIMPLEMENTED EVAL OF TYPE " + type;
        }
        numChecked++;
      }
      if (numCorrect == numChecked) {
        feedbackSpan.style.color =
          this.titleDiv.style.color =
          this.checkBtn.style.backgroundColor =
          this.qDiv.style.borderColor =
            "rgb(0,150,0)";
        this.qDiv.style.backgroundColor = "rgba(0,150,0, 0.025)";
      } else {
        this.titleDiv.style.color =
          feedbackSpan.style.color =
          this.checkBtn.style.backgroundColor =
          this.qDiv.style.borderColor =
            "rgb(150,0,0)";
        this.qDiv.style.backgroundColor = "rgba(150,0,0, 0.025)";
        if (numChecked >= 5) {
          feedbackSpan.innerHTML = "" + numCorrect + " / " + numChecked;
        }
      }
    });
  }

  /**
   * @param {Object.<Object,Object>} node
   * @returns {string}
   */
  generateMathString(node) {
    let s = "";
    switch (node.type) {
      case "math": {
        for (let c of node.children) s += this.generateMathString(c);
        break;
      }
      case "text": {
        return node.data;
      }
      case "var": {
        let instance = this.src.instances[this.instanceIdx];
        return instance[node.data].value;
      }
    }
    return s;
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
        let span = document.createElement("span");
        span.innerHTML = node.data;
        return span;
      }
      case "bold": {
        let span = document.createElement("span");
        span.style.fontWeight = "bold";
        for (let c of node.children) span.appendChild(this.generateText(c));
        return span;
      }
      case "math": {
        let str = this.generateMathString(node);
        return genMathSpan(str);
      }
      case "input": {
        let span = document.createElement("span");

        let varId = node.data;
        let expected = this.src.instances[this.instanceIdx][varId];

        if (expected.type == "vector") {
          // vector
          let elements = expected.value.split(",").map((e) => e.trim());
          let n = elements.length;
          span.appendChild(genSpan(" "));
          for (let i = 0; i < n; i++) {
            this.expected[varId + i] = elements[i];
            this.types[varId + i] = "int"; // TODO
            if (i > 0) span.appendChild(genSpan(" , "));
            let input = genInputField();
            span.appendChild(input);
            input.addEventListener("keyup", () => {
              this.student[varId + i] = input.value.trim();
            });
            if (this.showSolution)
              this.student[varId + i] = input.value = elements[i];
          }
          span.appendChild(genSpan(" "));
        } else {
          // scalar
          this.expected[varId] = expected.value;
          this.types[varId] = expected.type;
          let input = genInputField();
          span.appendChild(input);
          input.addEventListener("keyup", () => {
            this.student[varId] = input.value.trim();
          });
          if (this.showSolution)
            this.student[varId] = input.value = expected.value;
        }

        // let space = document.createElement("span");
        // space.innerHTML = "&nbsp;";
        // span.appendChild(space);
        // let feedback = document.createElement("span");
        // feedback.innerHTML = "FEEDBACK";
        // span.appendChild(feedback);
        return span;
      }
      case "itemize": {
        let ul = document.createElement("ul");
        for (let c of node.children) {
          let li = document.createElement("li");
          ul.appendChild(li);
          li.appendChild(this.generateText(c));
        }
        return ul;
      }
      case "single-choice":
      case "multi-choice": {
        let mc = node.type == "multi-choice";
        let table = document.createElement("table");
        let n = node.children.length;
        let order = shuffledIndices(n);
        let iconCorrect = mc ? iconSquareChecked : iconCircleChecked;
        let iconIncorrect = mc ? iconSquareUnchecked : iconCircleUnchecked;
        let checkboxes = [];
        let answerIDs = [];
        for (let i = 0; i < n; i++) {
          let idx = order[i];
          let answer = node.children[idx];
          let answerId = "mc-" + this.choiceIdx + "-" + idx;
          answerIDs.push(answerId);

          let expectedValue = answer.children[0].data;
          this.expected[answerId] = expectedValue;
          this.types[answerId] = "bool";
          this.student[answerId] = this.showSolution ? expectedValue : "false";
          let text = this.generateText(answer.children[1], true);

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
            tr.addEventListener("click", () => {
              this.student[answerId] =
                this.student[answerId] === "true" ? "false" : "true";
              if (this.student[answerId] === "true")
                tdCheckBox.innerHTML = iconCorrect;
              else tdCheckBox.innerHTML = iconIncorrect;
            });
          } else {
            tr.addEventListener("click", () => {
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
        let span = document.createElement("span");
        span.style.color = "red";
        span.innerHTML = "UNIMPLEMENTED(" + node.type + ")";
        return span;
      }
    }
  }
}

/**
 * @param {Object.<Object,Object>} quizSrc
 * @param {boolean} debug
 */
export function init(quizSrc, debug) {
  if (debug) document.getElementById("debug").style.display = "block";
  document.getElementById("title").innerHTML = quizSrc.title;
  document.getElementById("author").innerHTML = quizSrc.author;
  document.getElementById("courseInfo1").innerHTML = courseInfo1[quizSrc.lang];
  let reload =
    '<span onclick="location.reload()" style="text-decoration: underline; font-weight: bold; cursor: pointer">' +
    courseInfo3[quizSrc.lang] +
    "</span>";
  document.getElementById("courseInfo2").innerHTML = courseInfo2[
    quizSrc.lang
  ].replace("*", reload);

  /** @type {Question[]} */
  let questions = [];
  /** @type {HTMLElement} */
  let questionsDiv = document.getElementById("questions");
  for (let questionSrc of quizSrc.questions) {
    let question = new Question(questionSrc);
    question.showSolution = debug;
    questions.push(question);
    question.populateDom(questionsDiv);
    if (debug && questionSrc.error.length == 0) question.checkBtn.click();
  }
}
