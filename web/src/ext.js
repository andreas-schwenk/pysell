/*******************************************************************************
 * pySELL - Python based Simple E-Learning Language
 * AUTHOR:  Andreas Schwenk <mailto:contact@compiler-construction.com>
 * LICENSE: GPLv3
 ******************************************************************************/

// code in this file is from external sources

/**
 * code taken from: https://www.tutorialspoint.com/levenshtein-distance-in-javascript
 * @param {string} u
 * @param {string} v
 * @returns {number}
 */
export function levenshteinDistance(u, v) {
  const track = Array(v.length + 1)
    .fill(null)
    .map(() => Array(u.length + 1).fill(null));
  for (let i = 0; i <= u.length; i += 1) track[0][i] = i;
  for (let j = 0; j <= v.length; j += 1) track[j][0] = j;
  for (let j = 1; j <= v.length; j += 1) {
    for (let i = 1; i <= u.length; i += 1) {
      const indicator = u[i - 1] === v[j - 1] ? 0 : 1;
      track[j][i] = Math.min(
        track[j][i - 1] + 1, // deletion
        track[j - 1][i] + 1, // insertion
        track[j - 1][i - 1] + indicator // substitution
      );
    }
  }
  return track[v.length][u.length];
}

// tests
// let xx1 = levenshteinDistance("abc", "bc"); // 1
// let xx2 = levenshteinDistance("ab", "abc"); // 1
// let xx3 = levenshteinDistance("abc", "abc"); // 0
