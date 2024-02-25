/*******************************************************************************
 * pySELL - Python based Simple E-Learning Language
 * AUTHOR:  Andreas Schwenk <mailto:contact@compiler-construction.com>
 * LICENSE: GPLv3
 ******************************************************************************/

/**
 * This file provides functions to generate HTML elements in a shorter notation.
 * Also CSS classes are assigned in some cases.
 */

/**
 * Generates a HTMLDivElement and optionally assigns child elements to it.
 * @param {HTMLElement[]} children
 * @returns {HTMLDivElement}
 */
export function genDiv(children = []) {
  let div = document.createElement("div");
  div.append(...children);
  return div;
}

/**
 * Generates a HTMLUListElement and optionally assigns child elements to it.
 * @param {HTMLElement[]} children
 * @returns {HTMLUListElement}
 */
export function genUl(children = []) {
  let ul = document.createElement("ul");
  ul.append(...children);
  return ul;
}

/**
 * Generates a HTMLLIElement and optionally assigns a child element to it.
 * @param {HTMLElement} child
 * @returns {HTMLLIElement}
 */
export function genLi(child) {
  let li = document.createElement("li");
  li.appendChild(child);
  return li;
}

/**
 * Generates a HTMLInputElement.
 * @param {number} width
 * @returns {HTMLInputElement}
 */
export function genInputField(width) {
  let input = document.createElement("input");
  input.spellcheck = false;
  input.type = "text";
  input.classList.add("inputField");
  input.style.width = width + "px";
  return input;
}

/**
 * Generates a HTMLButtonElement.
 * @returns {HTMLButtonElement}
 */
export function genButton() {
  let button = document.createElement("button");
  button.type = "button";
  button.classList.add("button");
  return button;
}

/**
 * Generates a HTMLSpanElement.
 * @param {string} innerHTML
 * @param {HTMLElement[]} [children=[]]
 * @returns {HTMLSpanElement}
 */
export function genSpan(innerHTML, children = []) {
  let span = document.createElement("span");
  if (children.length > 0) span.append(...children);
  else span.innerHTML = innerHTML;
  return span;
}

/**
 * Renders a TeX-bases equation to an existing HTML element using "katex".
 * @param {HTMLElement} element
 * @param {string} tex
 * @param {boolean} [displayStyle=false]
 */
export function updateMathElement(element, tex, displayStyle = false) {
  // @ts-ignore
  katex.render(tex, element, {
    throwOnError: false,
    displayMode: displayStyle,
    macros: {
      "\\RR": "\\mathbb{R}",
      "\\NN": "\\mathbb{N}",
      "\\QQ": "\\mathbb{Q}",
      "\\ZZ": "\\mathbb{Z}",
      "\\CC": "\\mathbb{C}",
    },
  });
}

/**
 * Renders a TeX-bases equation to a new HTML element using "katex".
 * @param {string} tex
 * @param {boolean} [displayStyle=false]
 * @returns {HTMLSpanElement}
 */
export function genMathSpan(tex, displayStyle = false) {
  let span = document.createElement("span");
  updateMathElement(span, tex, displayStyle);
  return span;
}
