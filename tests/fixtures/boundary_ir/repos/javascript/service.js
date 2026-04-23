import { formatName } from './format.js';

export class Renderer {
  render(value) {
    return formatName(value);
  }
}

export function run(value) {
  const cleaned = formatName(value);
  const duplicate = helper(cleaned);
  return missingCall(duplicate);
}
