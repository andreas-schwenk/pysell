/*******************************************************************************
 * pySELL - Python based Simple E-Learning Language
 * AUTHOR:  Andreas Schwenk <mailto:contact@compiler-construction.com>
 * LICENSE: GPLv3
 ******************************************************************************/

import { courseInfo1, courseInfo2, courseInfo3 } from "./lang.js";
import { Question } from "./question.js";

/**
 * @param {Object.<Object,Object>} quizSrc
 * @param {boolean} debug
 */
export function init(quizSrc, debug) {
  if (debug) document.getElementById("debug").style.display = "block";
  document.getElementById("date").innerHTML = new Date()
    .toISOString()
    .split("T")[0];
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
  let idx = 1;
  for (let questionSrc of quizSrc.questions) {
    questionSrc.title = "" + idx + ". " + questionSrc.title;
    let question = new Question(questionSrc, debug);
    question.showSolution = debug;
    questions.push(question);
    question.populateDom(questionsDiv);
    if (debug && questionSrc.error.length == 0) question.checkBtn.click();
    idx++;
  }
}
