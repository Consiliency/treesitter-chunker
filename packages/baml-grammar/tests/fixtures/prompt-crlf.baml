function old_prompt(text: string) -> string {
    client: "openai/gpt-5.6-luna"
    prompt: #"Say ${text}"#
}

function multiline_prompt(name: string) -> string {
    client: "openai/gpt-5.6-luna"
    prompt: `Hello ${name}
Répondez avec ${ctx.output_format()}
Done.`
}

function adjacent(text: string) -> string {
    client: "openai/gpt-5.6-luna"
    prompt: `Value: ${text}`
}
