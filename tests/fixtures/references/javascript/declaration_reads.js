function rest(...args) { return [...args]; }
let [...elements] = iterable;
let {...fields} = source;
let {[key]: renamed, staticKey: other = fallback} = source;
consume(elements, fields, renamed, other);
[...elements] = iterable;
({...fields} = source);
({staticKey: renamed} = source);
try {} catch (caught) { consume(caught); }
try {} catch ({staticKey: nested}) { consume(nested); }
for (const element of iterable) { consume(element); }
for (let prop in source) { consume(prop); }
let element, prop;
for (element of iterable) { consume(element); }
for (prop in source) { consume(prop); }
function* declared(param) { yield param; }
const expression = function* (argument) { yield argument; };
async function loop(stream) { for await (const value of stream) { consume(value); } }
