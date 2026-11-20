pub struct K;

pub fn outer(xs: &[i32]) -> i32 {
    let f = |y: i32| y + 1;
    let g = |z: i32| {
        let h = |w: i32| w * z;
        h(z)
    };
    f(g(xs[0]))
}

impl K {
    pub fn run(&self, xs: &[i32]) -> i32 {
        xs.iter().map(|i| i + 1).sum()
    }
}
