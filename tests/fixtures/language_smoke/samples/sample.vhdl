entity adder is
  port (a : in bit; b : in bit; c : out bit);
end entity adder;

architecture rtl of adder is
begin
  c <= a and b;
end architecture rtl;
