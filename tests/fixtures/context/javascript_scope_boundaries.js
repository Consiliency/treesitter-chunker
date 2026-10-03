const obj = { method() {} };
const Foo = class { helper() {} };
export default class { other() {} };

if (true) {
    const hidden = 1;
    var hoisted = 2;
}

switch (hoisted) {
    case 0:
        const caseLocal = 3;
        var switchVar = 4;
        break;
}

function run() {
    const local = 1;
    if (true) {
        var innerVar = 2;
        const innerLet = 3;
    }
    return local;
}
