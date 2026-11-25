const fs = require('node:fs');
const output = fs.readFileSync('node_modules/fixture-dependency/postinstall.marker');
fs.appendFileSync('postinstall.marker', output);
