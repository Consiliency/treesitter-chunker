export function t() { return 1; }
export function g() { return globalThis.t() + window.t(); }
