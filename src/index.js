import {
  iconCheckBoxChecked,
  iconCheckBoxUnchecked,
  iconPlay,
} from "./icons.js";

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

class Question {
  /**
   * @param {Object.<Object,Object>} src
   */
  constructor(src) {
    this.src = src;
    this.instanceIdx = Math.floor(Math.random() * src.instances.length);
    this.choiceIdx = 0; // distinct index for every multi or single choice
    this.expectedValues = {};
    this.expectedTypes = {};
    this.studentValues = {};
    this.qDiv = null;
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
    let titleDiv = document.createElement("div");
    this.qDiv.appendChild(titleDiv);
    titleDiv.classList.add("questionTitle");
    titleDiv.innerHTML = this.src["title"];
    // generate question text
    for (let c of this.src.text.children)
      this.qDiv.appendChild(this.generateText(c));
    // generate button row
    let buttonDiv = document.createElement("div");
    this.qDiv.appendChild(buttonDiv);
    buttonDiv.classList.add("buttonRow");
    // (a) check button
    let checkBtn = document.createElement("button");
    buttonDiv.appendChild(checkBtn);
    checkBtn.type = "button";
    checkBtn.classList.add("button");
    //checkBtn.innerHTML = "check";
    checkBtn.innerHTML = iconPlay;
    // (b) spacing
    let space = document.createElement("span");
    space.innerHTML = "&nbsp;&nbsp;&nbsp;";
    buttonDiv.appendChild(space);
    // (c) feedback text
    let feedbackSpan = document.createElement("span");
    buttonDiv.appendChild(feedbackSpan);
    feedbackSpan.innerHTML = "";
    // evaluation
    checkBtn.addEventListener("click", () => {
      let numChecked = 0;
      let numCorrect = 0;
      for (let id in this.expectedValues) {
        console.log("comparing answer " + id);
        let type = this.expectedTypes[id];
        console.log("type = " + type);
        let student = this.studentValues[id];
        console.log("student = " + student);
        let expected = this.expectedValues[id];
        console.log("expected = " + expected);
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
          checkBtn.style.backgroundColor =
          this.qDiv.style.borderColor =
            "rgb(0,150,0)";
        this.qDiv.style.backgroundColor = "rgba(0,150,0, 0.05)";
      } else {
        feedbackSpan.style.color =
          checkBtn.style.backgroundColor =
          this.qDiv.style.borderColor =
            "rgb(150,0,0)";
        this.qDiv.style.backgroundColor = "rgba(150,0,0, 0.05)";
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
        let span = document.createElement("span");
        let str = this.generateMathString(node);
        // @ts-ignore
        katex.render(str, span, {
          throwOnError: false,
        });
        return span;
      }
      case "input": {
        let span = document.createElement("span");

        let varId = node.data;
        let expected = this.src.instances[this.instanceIdx][varId];
        this.expectedValues[varId] = expected.value;
        this.expectedTypes[varId] = expected.type;

        let input = document.createElement("input");
        input.type = "text";
        input.classList.add("inputField");
        span.appendChild(input);

        input.addEventListener("keyup", () => {
          this.studentValues[varId] = input.value.trim();
        });

        let space = document.createElement("span");
        space.innerHTML = "&nbsp;";
        span.appendChild(space);

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
      // TODO: single-choice
      case "multi-choice": {
        let table = document.createElement("table");
        let n = node.children.length;
        let order = shuffledIndices(n);
        for (let i = 0; i < n; i++) {
          let idx = order[i];
          let answer = node.children[idx];
          let answerId = "mc-" + this.choiceIdx + "-" + idx;

          let expectedValue = answer.children[0].data;
          this.expectedValues[answerId] = expectedValue;
          this.expectedTypes[answerId] = "bool";
          this.studentValues[answerId] = "false";
          let text = this.generateText(answer.children[1], true);

          let tr = document.createElement("tr");
          table.appendChild(tr);
          tr.style.cursor = "pointer";
          let tdCheckBox = document.createElement("td");
          tr.appendChild(tdCheckBox);
          tdCheckBox.innerHTML = iconCheckBoxUnchecked;
          let tdText = document.createElement("td");
          tr.appendChild(tdText);
          tdText.appendChild(text);

          tr.addEventListener("click", () => {
            this.studentValues[answerId] =
              this.studentValues[answerId] === "true" ? "false" : "true";
            if (this.studentValues[answerId] === "true") {
              tdCheckBox.innerHTML = iconCheckBoxChecked;
            } else {
              tdCheckBox.innerHTML = iconCheckBoxUnchecked;
            }
          });
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
 */
export function init(quizSrc) {
  document.getElementById("title").innerHTML = quizSrc.title;
  document.getElementById("author").innerHTML = quizSrc.author;
  /** @type {Question[]} */
  let questions = [];
  /** @type {HTMLElement} */
  let questionsDiv = document.getElementById("questions");
  for (let questionSrc of quizSrc.questions) {
    let question = new Question(questionSrc);
    questions.push(question);
    question.populateDom(questionsDiv);
  }
}
