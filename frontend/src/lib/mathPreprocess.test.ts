import { describe, expect, it } from "vitest";
import { preprocessMathUnicode } from "./mathPreprocess";

describe("mathPreprocess", () => {
	it("replaces Unicode math symbols inside inline math", () => {
		const input = "Let $x ∈ A$ be an element.";
		// '∈' -> '\in ' (with space)
		// input: $x(space)∈(space)A$
		// output: $x(space)\in (space)(space)A$ -> $x \in  A$
		const expected = "Let $x \\in  A$ be an element.";
		expect(preprocessMathUnicode(input)).toBe(expected);
	});

	it("replaces Unicode math symbols inside block math", () => {
		const input = "Consider:\n$$x ≤ y$$\nwhere $y ≥ 0$.";
		// '≤' -> '\leq '
		// '≥' -> '\geq '
		const expected = "Consider:\n$$x \\leq  y$$\nwhere $y \\geq  0$.";
		expect(preprocessMathUnicode(input)).toBe(expected);
	});

	it("does not replace symbols outside of math delimiters", () => {
		const input = "The symbol ∈ is called 'element of'.";
		expect(preprocessMathUnicode(input)).toBe(input);
	});

	it("does not replace symbols inside code blocks", () => {
		const input = "Code: `x ∈ A` and block:\n```\ny ⊆ Z\n```";
		expect(preprocessMathUnicode(input)).toBe(input);
	});

	it("handles mixed content correctly", () => {
		const input = "In math $a ≠ b$, but in code `a ≠ b`.";
		const expected = "In math $a \\neq  b$, but in code `a ≠ b`.";
		expect(preprocessMathUnicode(input)).toBe(expected);
	});

	it("replaces multiple symbols in one math block", () => {
		const input = "Limit: $∆x → 0$ with $∞$.";
		const expectedActual =
			"Limit: $\\Delta x \\rightarrow  0$ with $\\infty $.";
		expect(preprocessMathUnicode(input)).toBe(expectedActual);
	});

	it("handles complex LaTeX commands correctly", () => {
		const input = "Sum: $∑_{i=1}^n x_i$";
		const expected = "Sum: $\\sum _{i=1}^n x_i$";
		expect(preprocessMathUnicode(input)).toBe(expected);
	});
});
