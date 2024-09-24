/*******************************************************************************
 * pySELL - Python based Simple E-Learning Language
 * AUTHOR:  Andreas Schwenk <mailto:contact@compiler-construction.com>
 * LICENSE: GPLv3
 ******************************************************************************/

import { genDiv } from "./dom.js";
import { evalQuestion } from "./eval.js";
import {
  courseInfo1,
  courseInfo2,
  courseInfo3,
  dataPolicy,
  evalNowText,
  pointsText,
  timerInfoText,
} from "./lang.js";
import { Question, QuestionState } from "./question.js";

/**
 * This file is the entry point of the quiz website and populates the DOM.
 */

/**
 * @param {Object.<Object,Object>} quizSrc -- JSON object as output from sell.py
 * @param {boolean} debug -- true for enabling extensive debugging features
 */
export function init(quizSrc, debug) {
  new Quiz(quizSrc, debug);
}

/**
 * Question management.
 */
export class Quiz {
  /**
   *
   * @param {Object.<Object,Object>} quizSrc -- JSON object as output from sell.py
   * @param {boolean} debug -- true for enabling extensive debugging features
   */
  constructor(quizSrc, debug) {
    /** @type {Object.<Object,Object>} */
    this.quizSrc = quizSrc;

    // default to English, if the provided language abbreviation is unknown
    if (["en", "de", "es", "it", "fr"].includes(this.quizSrc.lang) == false)
      this.quizSrc.lang = "en";

    /** @type {boolean} */
    this.debug = debug;

    // if debugging is enabled, show a DEBUG info at the start of the page
    if (this.debug) document.getElementById("debug").style.display = "block";

    /** @type {Question[]} -- the questions */
    this.questions = [];

    /** @type {number} -- positive value := limited time */
    this.timeLeft = quizSrc.timer;
    /** @type {boolean} -- whether the quiz is time limited */
    this.timeLimited = quizSrc.timer > 0;

    this.fillPageMetadata();

    if (this.timeLimited) {
      document.getElementById("timer-info").style.display = "block";
      document.getElementById("timer-info-text").innerHTML =
        timerInfoText[this.quizSrc.lang];
      document.getElementById("start-btn").addEventListener("click", () => {
        document.getElementById("timer-info").style.display = "none";
        this.generateQuestions();
        this.runTimer();
      });
    } else {
      this.generateQuestions();
    }
  }

  /**
   * Shows the quiz' meta data.
   */
  fillPageMetadata() {
    document.getElementById("date").innerHTML = this.quizSrc.date;
    document.getElementById("title").innerHTML = this.quizSrc.title;
    document.getElementById("author").innerHTML = this.quizSrc.author;
    document.getElementById("courseInfo1").innerHTML =
      courseInfo1[this.quizSrc.lang];
    let reload =
      '<span onclick="location.reload()" style="text-decoration: none; font-weight: bold; cursor: pointer">' +
      courseInfo3[this.quizSrc.lang] +
      "</span>";
    document.getElementById("courseInfo2").innerHTML = courseInfo2[
      this.quizSrc.lang
    ].replace("*", reload);

    document.getElementById("data-policy").innerHTML =
      dataPolicy[this.quizSrc.lang];
  }

  /**
   * Generates the questions.
   */
  generateQuestions() {
    /** @type {HTMLElement} */
    let questionsDiv = document.getElementById("questions");
    let idx = 1; // question index 1, 2, ...
    for (let questionSrc of this.quizSrc.questions) {
      questionSrc.title = "" + idx + ". " + questionSrc.title;
      let div = genDiv();
      questionsDiv.appendChild(div);
      let question = new Question(
        div,
        questionSrc,
        this.quizSrc.lang,
        this.debug
      );
      question.showSolution = this.debug;
      this.questions.push(question);
      question.populateDom(this.timeLimited);
      if (this.debug && questionSrc.error.length == 0) {
        // if the debug version is active, evaluate the question immediately
        if (question.hasCheckButton) question.checkAndRepeatBtn.click();
      }
      idx++;
    }
  }

  /**
   * Runs the timer countdown.
   */
  runTimer() {
    // button to evaluate quiz immediately
    document.getElementById("stop-now").style.display = "block";
    document.getElementById("stop-now-btn").innerHTML =
      evalNowText[this.quizSrc.lang];
    document.getElementById("stop-now-btn").addEventListener("click", () => {
      this.timeLeft = 1;
    });
    // create and show timer
    let timerDiv = document.getElementById("timer");
    timerDiv.style.display = "block";
    timerDiv.innerHTML = formatTime(this.timeLeft);
    // tick every second
    let interval = setInterval(() => {
      this.timeLeft--;
      timerDiv.innerHTML = formatTime(this.timeLeft);
      // stop, if no time is left
      if (this.timeLeft <= 0) {
        this.stopTimer(interval);
      }
    }, 1000);
  }

  stopTimer(interval) {
    document.getElementById("stop-now").style.display = "none";
    clearInterval(interval);
    let score = 0;
    let maxScore = 0;
    for (let question of this.questions) {
      let pts = question.src["points"];
      maxScore += pts;
      evalQuestion(question);
      if (question.state === QuestionState.passed) score += pts;
      question.editingEnabled = false;
    }
    document.getElementById("questions-eval").style.display = "block";
    //document.getElementById("questions-eval-text").innerHTML =
    //  evalText[quizSrc.lang] + ":";
    let p = document.getElementById("questions-eval-percentage");
    p.innerHTML =
      maxScore == 0
        ? ""
        : "" +
          score +
          " / " +
          maxScore +
          " " +
          pointsText[this.quizSrc.lang] +
          " " +
          "<br/><br/>" +
          Math.round((score / maxScore) * 100) +
          " %";
  }
}

/**
 * @param {number} seconds
 * @returns {string}
 */
function formatTime(seconds) {
  let mins = Math.floor(seconds / 60);
  let secs = seconds % 60;
  return mins + ":" + ("" + secs).padStart(2, "0");
}
