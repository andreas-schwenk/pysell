/*******************************************************************************
 * pySELL - Python based Simple E-Learning Language
 * AUTHOR:  Andreas Schwenk <mailto:contact@compiler-construction.com>
 * LICENSE: GPLv3
 ******************************************************************************/

/**
 * @param {HTMLElement[]} children
 * @returns {HTMLDivElement}
 */
export function genDiv(children = []) {
  let div = document.createElement("div");
  div.append(...children);
  return div;
}

/**
 * @param {HTMLElement[]} children
 * @returns {HTMLUListElement}
 */
export function genUl(children = []) {
  let ul = document.createElement("ul");
  ul.append(...children);
  return ul;
}

/**
 * @param {HTMLElement} child
 * @returns {HTMLLIElement}
 */
export function genLi(child) {
  let li = document.createElement("li");
  li.appendChild(child);
  return li;
}

/**
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
 * @returns {HTMLButtonElement}
 */
export function genButton() {
  let button = document.createElement("button");
  button.type = "button";
  button.classList.add("button");
  return button;
}

/**
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
 * @param {string} tex
 * @returns {HTMLSpanElement}
 */
export function genMathSpan(tex, displayStyle = false) {
  let span = document.createElement("span");
  // @ts-ignore
  katex.render(tex, span, {
    throwOnError: false,
    displayMode: displayStyle,
    macros: {
      "\\RR": "\\mathbb{R}",
      "\\NN": "\\mathbb{N}",
      "\\QQ": "\\mathbb{Q}",
      "\\ZZ": "\\mathbb{Z}",
    },
  });
  return span;
}
