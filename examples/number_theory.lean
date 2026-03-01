-- Elementary number theory problems

theorem succ_pos (n : Nat) : 0 < n + 1 := by
  sorry

theorem le_refl (n : Nat) : n <= n := by
  sorry

theorem add_le_add_left (a b c : Nat) (h : a <= b) : c + a <= c + b := by
  sorry

theorem nat_zero_or_succ (n : Nat) : n = 0 ∨ ∃ m, n = m + 1 := by
  sorry
