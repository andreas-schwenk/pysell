/*******************************************************************************
 * pySELL - Python based Simple E-Learning Language
 * AUTHOR:  Andreas Schwenk <mailto:contact@compiler-construction.com>
 * LICENSE: GPLv3
 ******************************************************************************/

import { genDiv } from "./dom.js";
import { courseInfo1, courseInfo2, courseInfo3 } from "./lang.js";
import { Question } from "./question.js";

/**
 * This file is the entry point of the quiz website and populates the DOM.
 */

/**
 * @param {Object.<Object,Object>} quizSrc -- JSON object as output from sell.py
 * @param {boolean} debug -- true for enabling extensive debugging features
 */
export function init(quizSrc, debug) {
  // default to English, if the provided language abbreviation is unknown
  if (["en", "de", "es", "it", "fr"].includes(quizSrc.lang) == false)
    quizSrc.lang = "en";
  // if debugging is enabled, show a DEBUG info at the start of the page
  if (debug) document.getElementById("debug").style.display = "block";
  // show the quiz' meta data
  document.getElementById("date").innerHTML = quizSrc.date;
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

  // generate questions
  /** @type {Question[]} */
  let questions = [];
  /** @type {HTMLElement} */
  let questionsDiv = document.getElementById("questions");
  let idx = 1; // question index 1, 2, ...
  for (let questionSrc of quizSrc.questions) {
    questionSrc.title = "" + idx + ". " + questionSrc.title;
    let div = genDiv();
    questionsDiv.appendChild(div);
    let question = new Question(div, questionSrc, quizSrc.lang, debug);
    question.showSolution = debug;
    questions.push(question);
    question.populateDom();
    if (debug && questionSrc.error.length == 0) {
      // if the debug version is active, evaluate the question immediately
      question.checkAndRepeatBtn.click();
    }
    idx++;
  }
}
