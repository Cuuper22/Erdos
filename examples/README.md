# Example Problems

This directory contains sample Lean 4 theorem proving problems for testing the Erdos solver.

These files are intentionally **unsolved**: every theorem ends in a `sorry` placeholder. That is the input format the solver expects — it replaces the `sorry` with a candidate proof, compiles it, and validates the result. Do not commit completed proofs here; a solved example would give the solver nothing to do (and `sorry` is only banned in LLM *output*, not in the original problem files).

## Files

- `test_theorem.lean` - Basic arithmetic theorem
- `basic_algebra.lean` - Simple algebraic identities
- `number_theory.lean` - Elementary number theory problems
- `intermediate.lean` - Moderately challenging theorems (induction, cases, omega)
- `manifest.json` - Problem queue entries for the files above

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

1. Create a new `.lean` file with your theorem statement, leaving the proof as `sorry`
2. Add an entry to `examples/manifest.json`
3. Test with the solver

## Related manifests

The root `manifest.json` points at these same example files, so `python -m src.solver --manifest manifest.json` works out of the box. The root `manifest.remote.json` is different: it is a preserved sample of the remote "campaign" manifest format (referencing `FormalConjectures/Erdos/*.lean` paths from the google-deepmind/formal-conjectures repository, which is not vendored here). Nothing in `src/` reads it — keep it as a format reference for future remote campaigns.
