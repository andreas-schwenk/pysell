/*******************************************************************************
 * pySELL - Python based Simple E-Learning Language
 * AUTHOR:  Andreas Schwenk <mailto:contact@compiler-construction.com>
 * LICENSE: GPLv3
 ******************************************************************************/

/**
 * This file implements the evaluation of a question.
 */

import { levenshteinDistance } from "./ext.js";
import { iconCheck, iconRepeat } from "./icons.js";
import { feedbackErr, feedbackOK } from "./lang.js";
import { Matrix, Term } from "./math.js";
import { compareODE } from "./math_ODE.js";
import { Question, QuestionState } from "./question.js";

/**
 * Evaluates a given question and automatically renders a colored feedback,
 * as well as a large feedback message.
 * @param {Question} question
 */
export function evalQuestion(question) {
  // reset the feedback text
  question.feedbackSpan.innerHTML = "";
  // reset the number of checked and corrected inputs
  question.numChecked = 0;
  question.numCorrect = 0;
  // evaluate each input field
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
        // boolean types primarily occur in single/multiple choice questions.
        // boolean values are stringified as "true" and "false".
        question.numChecked++;
        if (student === expected) question.numCorrect++;
        break;
      case "string": {
        // gap question
        question.numChecked++;
        let inputField = question.gapInputs[id];
        let s = student.trim().toUpperCase();
        let e = expected.trim().toUpperCase().split("|");
        let ok = false;
        for (let ei of e) {
          let d = levenshteinDistance(s, ei);
          // treat answer as OK, if the Levenshtein distance is zero or one.
          if (d <= 1) {
            ok = true;
            question.numCorrect++;
            // in case that the answer is accepted, we need to update the
            // input text to be in correspondence with the sample solution
            question.gapInputs[id].value = ei;
            question.student[id] = ei;
            break;
          }
        }
        // give a visual feedback within the input field
        inputField.style.color = ok ? "black" : "white";
        inputField.style.backgroundColor = ok ? "transparent" : "maroon";
        break;
      }
      case "int":
        // integral values are compared numerically
        // (casting to float is useless and just for safety...)
        question.numChecked++;
        if (Math.abs(parseFloat(student) - parseFloat(expected)) < 1e-9)
          question.numCorrect++;
        break;
      case "float":
      case "term": {
        // floating point solutions are treated as terms, since students
        // may provided closed formulas (e.g. "e" instead of "2.71...")
        question.numChecked++;
        try {
          // parse the expected and student solution, as both are given by strings
          let u = Term.parse(expected);
          let v = Term.parse(student);
          let ok = false;
          if (question.src["is_ode"]) ok = compareODE(u, v);
          else ok = Term.compare(u, v);
          if (ok) question.numCorrect++;
        } catch (e) {
          // if term parsing fails, we just don't count the answer
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
        // types "vector", "complex", and "set" are all given by a single
        // string, with its elements separated by ","
        // e.g. type: "vector", value: "1,2,3"   for [1,2,3]
        //      type: "complex", value: "2,3"    for 2+3i
        //      type: "set", value "1,2,3"       for {1,2,3}
        let expectedList = expected.split(",");
        question.numChecked += expectedList.length;
        let studentList = [];
        for (let i = 0; i < expectedList.length; i++)
          studentList.push(question.student[id + "-" + i]);
        if (type === "set") {
          // set: search, if for every element of the expected solution,
          // a corresponding student solution can be found
          for (let i = 0; i < expectedList.length; i++) {
            try {
              let u = Term.parse(expectedList[i]);
              for (let j = 0; j < studentList.length; j++) {
                let v = Term.parse(studentList[j]);
                if (Term.compare(u, v)) {
                  question.numCorrect++;
                  break;
                }
              }
            } catch (e) {
              // if term parsing fails, we just don't count the answer
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
              if (Term.compare(u, v)) question.numCorrect++;
            } catch (e) {
              // if term parsing fails, we just don't count the answer
              if (question.debug) {
                console.log(e);
              }
            }
          }
        }
        break;
      }
      case "matrix": {
        // matrices are given as string in the form
        //   "[[2,4,12,3],[1,11,11,1],[17,10,14,3]]" (example for a 3x4 matrix)
        // each element can also be a term
        let mat = new Matrix(0, 0);
        mat.fromString(expected); // parse expected
        question.numChecked += mat.m * mat.n;
        for (let i = 0; i < mat.m; i++) {
          for (let j = 0; j < mat.n; j++) {
            let idx = i * mat.n + j;
            student = question.student[id + "-" + idx];
            let e = mat.v[idx];
            try {
              let u = Term.parse(e);
              let v = Term.parse(student);
              if (Term.compare(u, v)) question.numCorrect++;
            } catch (e) {
              // if term parsing fails, we just don't count the answer
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
  }
  // the question is passed, if ALL answer fields are correct
  question.state =
    question.numCorrect == question.numChecked
      ? QuestionState.passed
      : QuestionState.errors;
  question.updateVisualQuestionState();
  // blend in a large feedback text (e.g. "awesome")
  let choices =
    question.state === QuestionState.passed
      ? feedbackOK[question.language]
      : feedbackErr[question.language];
  let text = choices[Math.floor(Math.random() * choices.length)];
  question.feedbackPopupDiv.innerHTML = text;
  question.feedbackPopupDiv.style.color =
    question.state === QuestionState.passed ? "green" : "maroon";
  question.feedbackPopupDiv.style.display = "block";
  setTimeout(() => {
    question.feedbackPopupDiv.style.display = "none";
  }, 500);
  // change the question button
  if (question.state === QuestionState.passed) {
    if (question.src.instances.length > 0) {
      // if the student passed and there are other question instances,
      // provide the ability to repeat the question
      question.checkAndRepeatBtn.innerHTML = iconRepeat;
    } else question.checkAndRepeatBtn.style.display = "none";
  } else {
    // in case of non-passing, the check button must be provided (kept)
    question.checkAndRepeatBtn.innerHTML = iconCheck;
  }
}
