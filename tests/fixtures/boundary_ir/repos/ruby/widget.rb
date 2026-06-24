class Widget
  def initialize(count)
    @count = count
  end

  def render
    helper(@count)
  end

  def helper(value)
    value + 1
  end
end
