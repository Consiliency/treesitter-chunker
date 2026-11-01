// Binding identifiers versus uses for treesitter-chunker#293.
import Default from "./module.js";

const LIMIT = 3;

const callback = function namedExpression(first) {
  return first ? namedExpression(0) : first;
};

const single = param => param;

function withDefault(option = LIMIT) {
  return option;
}

const [head, , tail] = [1, 2, 3];

function fromArray([alpha, beta]) {
  return alpha + beta;
}

const value = 1;
const shorthand = { value, LIMIT };

console.log(Default, callback, single, withDefault, head, tail, fromArray, shorthand);

const generatorExpression = function* namedGen() {
  yield namedGen;
};
const defaulted = (fallback = LIMIT) => fallback;
const [first = LIMIT] = [];
for (const [key, entry] of [[1, 2]]) {
  console.log(key, entry);
}
try {
  console.log(generatorExpression, defaulted, first);
} catch ([caught]) {
  console.log(caught);
}

let left = 1;
let right = 2;
[left, right] = [right, left];
[left = LIMIT] = [];
for ([left, right] of [[1, 2]]) {
  console.log(left, right);
}
