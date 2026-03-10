theorem nat_add_assoc (a b c : Nat) : (a + b) + c = a + (b + c) := by
  exact Nat.add_assoc a b c

theorem nat_mul_zero (n : Nat) : n * 0 = 0 := by
  exact Nat.mul_zero n

theorem nat_succ_ne_zero (n : Nat) : n + 1 ≠ 0 := by
  simpa using Nat.succ_ne_zero n

theorem bool_and_comm (a b : Bool) : (a && b) = (b && a) := by
  cases a <;> cases b <;> rfl

theorem list_length_nil : ([] : List Nat).length = 0 := by
  rfl

theorem nat_le_succ (n : Nat) : n ≤ n + 1 := by
  simpa using Nat.le_succ n