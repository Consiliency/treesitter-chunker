fn only_a() -> i32 { 1 }
fn only_b() -> i32 { 2 }
struct T;
impl T {
    fn m(&self) -> i32 {
        only_a()
    }
}
impl T {
    fn n(&self) -> i32 {
        only_b()
    }
}
mod inner {
    fn m() -> i32 { super::only_b() }
}
