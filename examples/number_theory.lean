theorem succ_pos (n : Nat) : 0 < n + 1 := by
  simpa [Nat.succ_eq_add_one] using Nat.succ_pos n

theorem le_refl (n : Nat) : n <= n := by
  exact Nat.le_refl n

theorem add_le_add_left (a b c : Nat) (h : a <= b) : c + a <= c + b := by
  exact Nat.add_le_add_left h c

theorem nat_zero_or_succ (n : Nat) : n = 0 ∨ ∃ m, n = m + 1 := by
  cases n with
  | zero =>
      left
      rfl
  | succ m =>
      right
      exact ⟨m, rfl⟩