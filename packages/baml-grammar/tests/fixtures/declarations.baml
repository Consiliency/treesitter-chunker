class Box<T> {
    value: T
    function get(self) -> T { self.value }
}

enum Level { Junior, Senior }

interface Named {
    function label(self) -> string throws never;
}

implements Named for Box<string> {
    function label(self) -> string throws never { "box" }
}

client<llm> GPT4 {
    provider: openai,
    options: { model: "gpt-4o" },
}

generator ts_target {
    output_type: "typescript/node",
    output_dir: "typescript_demo",
}

retry_policy SafeRetry { max_retries: 2 }

template_string Persona(role: string) #"You are {{ role }}."#

test "box label" { assert.equal("box", "box") }

testset "box tests" {
    test "exists" { assert.equal(1, 1) }
}
