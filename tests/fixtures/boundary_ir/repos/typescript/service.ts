import { formatName } from './format';
import type { Formatter } from './format';

export class Renderer implements Formatter {
  render(value: string): string {
    return formatName(value);
  }
}

export function run(value: string): string {
  const cleaned = formatName(value);
  const duplicate = helper(cleaned);
  return missingCall(duplicate);
}
