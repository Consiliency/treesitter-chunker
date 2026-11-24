probe();
function ordinary(a) { return a; }
function* declared(a) { yield a; }
export function* exported(a) { yield a; }
const expression = function* named(a) { yield a; };
function outer() {
    return async function* (
        config = {limit: 1}
    ) { yield config; };
}
const object = { *method(a) { yield a; } };
