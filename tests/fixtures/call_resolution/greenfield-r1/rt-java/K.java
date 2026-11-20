public class K {
    int only_a() { return 1; }
    int only_b() { return 2; }
    int f(int a) {
        return only_a();
    }
    int f(String s) {
        return only_b();
    }
    int g() { return f(1); }
}
