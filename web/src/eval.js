/*******************************************************************************
 * pySELL - Python based Simple E-Learning Language
 * AUTHOR:  Andreas Schwenk <mailto:contact@compiler-construction.com>
 * LICENSE: GPLv3
 ******************************************************************************/

import { levenshteinDistance } from "./ext.js";
import { iconPlay, iconRepeat } from "./icons.js";
import { feedbackErr, feedbackOK } from "./lang.js";
import { Matrix, Term } from "./math.js";
import { Question, QuestionState } from "./question.js";

/**
 * @param {Question} question
 */
export function evalQuestion(question) {
  question.feedbackSpan.innerHTML = "";
  question.numChecked = 0;
  question.numCorrect = 0;
  for (let id in question.expected) {
    //console.log("comparing answer " + id);
    let type = question.types[id];
    //console.log("type = " + type);
    let student = question.student[id];
    //console.log("student = " + student);
    let expected = question.expected[id];
    //console.log("expected = " + expected);
    switch (type) {
      case "bool":
        if (student === expected) question.numCorrect++;
        break;
      case "string": {
        // gap question
        let inputField = question.gapInputs[id];
        let s = student.trim().toUpperCase();
        let e = expected.trim().toUpperCase();
        let d = levenshteinDistance(s, e);
        let ok = d <= 1;
        if (ok) {
          question.gapInputs[id].value = e;
          question.student[id] = e;
        }
        if (ok) question.numCorrect++;
        inputField.style.color = ok ? "black" : "white";
        inputField.style.backgroundColor = ok ? "transparent" : "maroon";
        break;
      }
      case "int":
        if (Math.abs(parseFloat(student) - parseFloat(expected)) < 1e-9)
          question.numCorrect++;
        break;
      case "float":
      case "term": {
        try {
          let u = Term.parse(expected);
          let v = Term.parse(student);
          if (u.compare(v)) question.numCorrect++;
        } catch (e) {
          if (question.debug) {
            console.log("term invalid");
            console.log(e);
          }
        }
        break;
      }
      case "vector":
      case "complex":
      case "set": {
        let expectedList = expected.split(",");
        question.numChecked += expectedList.length - 1;
        let studentList = [];
        for (let i = 0; i < expectedList.length; i++)
          studentList.push(question.student[id + "-" + i]);
        if (type === "set") {
          // set
          for (let i = 0; i < expectedList.length; i++) {
            try {
              let u = Term.parse(expectedList[i]);
              for (let j = 0; j < studentList.length; j++) {
                let v = Term.parse(studentList[j]);
                if (u.compare(v)) {
                  question.numCorrect++;
                  break;
                }
              }
            } catch (e) {
              if (question.debug) {
                console.log(e);
              }
            }
          }
        } else {
          // vector or complex
          for (let i = 0; i < expectedList.length; i++) {
            try {
              let u = Term.parse(studentList[i]);
              let v = Term.parse(expectedList[i]);
              if (u.compare(v)) question.numCorrect++;
            } catch (e) {
              if (question.debug) {
                console.log(e);
              }
            }
          }
        }
        break;
      }
      case "matrix": {
        let mat = new Matrix(0, 0);
        mat.fromString(expected);
        question.numChecked += mat.m * mat.n - 1;
        for (let i = 0; i < mat.m; i++) {
          for (let j = 0; j < mat.n; j++) {
            let idx = i * mat.n + j;
            student = question.student[id + "-" + idx];
            let e = mat.v[idx];
            try {
              let u = Term.parse(e);
              let v = Term.parse(student);
              if (u.compare(v)) question.numCorrect++;
            } catch (e) {
              if (question.debug) {
                console.log(e);
              }
            }
          }
        }
        break;
      }
      default:
        question.feedbackSpan.innerHTML = "UNIMPLEMENTED EVAL OF TYPE " + type;
    }
    question.numChecked++;
  }
  question.state =
    question.numCorrect == question.numChecked
      ? QuestionState.passed
      : QuestionState.errors;
  question.updateVisualQuestionState();
  // feedback text
  let choices =
    question.state === QuestionState.passed
      ? feedbackOK[question.language]
      : feedbackErr[question.language];
  let text = choices[Math.floor(Math.random() * choices.length)];
  question.feedbackDiv.innerHTML = text;
  question.feedbackDiv.style.color =
    question.state === QuestionState.passed ? "green" : "maroon";
  question.feedbackDiv.style.display = "block";
  setTimeout(() => {
    question.feedbackDiv.style.display = "none";
  }, 500);
  // change button to retry button
  if (question.state === QuestionState.passed) {
    //if (question.debug == false) {
    //for (let input of question.allInputs) {
    //input.removeEventListener("click");
    //input.replaceWith(input.cloneNode(true));
    //}
    //}
    if (question.src.instances.length > 0) {
      question.checkAndRepeatBtnState = "repeat";
      question.checkAndRepeatBtn.innerHTML = iconRepeat;
    } else {
      question.checkAndRepeatBtn.style.display = "none";
    }
  } else {
    question.checkAndRepeatBtnState = "check";
    question.checkAndRepeatBtn.innerHTML = iconPlay;
  }
}
