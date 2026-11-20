export function t() { return 1; }
export function g() { t = other; return t(); }
function other() { return 3; }
