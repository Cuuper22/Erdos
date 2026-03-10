theorem add_comm (a b : Nat) : a + b = b + a := by
  exact Nat.add_comm a b

theorem mul_one (n : Nat) : n * 1 = n := by
  exact Nat.mul_one n

theorem add_zero (n : Nat) : n + 0 = n := by
  exact Nat.add_zero n

theorem mul_comm (a b : Nat) : a * b = b * a := by
  exact Nat.mul_comm a b