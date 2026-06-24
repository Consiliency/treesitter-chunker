namespace App;

public interface IRenderer
{
    int Render();
}

public class Widget : IRenderer
{
    private int count;

    public Widget(int count)
    {
        this.count = count;
    }

    public int Render()
    {
        return Helper(count);
    }

    private int Helper(int value)
    {
        return value + 1;
    }
}

public enum Color
{
    Red,
    Green,
    Blue
}
