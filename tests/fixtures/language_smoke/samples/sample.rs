fn greet(name: &str) -> String {
    format!("hi {}", name)
}

struct Greeter;

impl Greeter {
    fn add(&self, a: i32, b: i32) -> i32 {
        a + b
    }
}
