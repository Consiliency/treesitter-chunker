import defaultName, { original as localName, unchanged } from './dep.js';
import * as utils from './utils.js';

export function run() {
  return localName(defaultName) + unchanged(utils);
}
