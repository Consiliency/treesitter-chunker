function rest(...args) { return [...args]; }
const [...elements] = iterable;
const {...fields} = source;
const {[key]: renamed, staticKey: other = fallback} = source;
consume(elements, fields, renamed, other);
[...elements] = iterable;
({...fields} = source);
({staticKey: renamed} = source);
try {} catch (caught) { consume(caught); }
try {} catch ({staticKey: nested}) { consume(nested); }
for (const element of iterable) { consume(element); }
for (let prop in source) { consume(prop); }
for (element of iterable) { consume(element); }
for (prop in source) { consume(prop); }
function* declared(param) { yield param; }
const expression = function* (argument) { yield argument; };
async function loop(stream) { for await (const value of stream) { consume(value); } }
