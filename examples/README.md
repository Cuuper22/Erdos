# Example Problems

This directory contains sample Lean 4 theorem proving problems for testing the Erdos solver.

## Files

- `test_theorem.lean` - Basic arithmetic theorem
- `basic_algebra.lean` - Simple algebraic identities
- `number_theory.lean` - Elementary number theory problems

## Usage

To run the solver on these examples:

```bash
# Test a single problem
python -m src.solver --manifest examples/manifest.json --problem-id basic_001

# Test all examples
python -m src.solver --manifest examples/manifest.json
```

## Problem Difficulty Levels

- **Easy**: Solvable with basic tactics (rfl, simp, omega)
- **Medium**: Requires multiple steps or tactical combinations
- **Hard**: Needs advanced reasoning or lemma application

## Adding New Problems

1. Create a new `.lean` file with your theorem
2. Add an entry to `examples/manifest.json`
3. Test with the solver
