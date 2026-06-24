package app;

public class Widget {
    private int count;

    public Widget(int count) {
        this.count = count;
    }

    public int render() {
        return helper(count);
    }

    private int helper(int value) {
        return value + 1;
    }
}

enum Color {
    RED,
    GREEN,
    BLUE
}
