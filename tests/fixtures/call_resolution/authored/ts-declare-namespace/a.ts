declare namespace N { function f(x: number): void; }
namespace N { export function use() { return f(1); } }
export {};
