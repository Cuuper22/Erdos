-- Intermediate theorems requiring induction, cases, or omega

theorem nat_add_assoc (a b c : Nat) : (a + b) + c = a + (b + c) := by
  sorry

theorem nat_mul_zero (n : Nat) : n * 0 = 0 := by
  sorry

theorem nat_succ_ne_zero (n : Nat) : n + 1 ≠ 0 := by
  sorry

theorem bool_and_comm (a b : Bool) : (a && b) = (b && a) := by
  sorry

theorem list_length_nil : ([] : List Nat).length = 0 := by
  sorry

theorem nat_le_succ (n : Nat) : n ≤ n + 1 := by
  sorry
