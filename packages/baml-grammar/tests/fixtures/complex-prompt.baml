function summarize(name: string, items: string[]) -> string {
    client: "openai/gpt-5.6-luna"
    prompt: `Hello, ${name}.
First item: ${ let first = items[0]; first }
${for (let item in items)}- ${item}
${endfor}`
}
