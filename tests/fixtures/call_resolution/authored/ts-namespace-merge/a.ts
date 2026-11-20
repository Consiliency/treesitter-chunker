export function NS() { return 1; }
export namespace NS { export function inner() { return 2; } }
export function use() { return NS(); }
