export interface Formatter {
  render(value: string): string;
}

export function formatName(value: string): string {
  return value.trim();
}
