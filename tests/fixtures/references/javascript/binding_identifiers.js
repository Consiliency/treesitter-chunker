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
