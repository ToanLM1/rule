import { describe, expect, it } from "vitest";
import type { CanonicalDecision, VocabularyField } from "./canonicalJdmAdapter";
import {
  applyJdmTable,
  RestrictedJdmError,
  toJdmTable,
} from "./canonicalJdmAdapter";

const vocabulary: VocabularyField[] = [
  { key: "age", label: "Customer age", type: "integer", role: "INPUT" },
  { key: "eligible", label: "Eligible", type: "boolean", role: "OUTPUT" },
];

const decision: CanonicalDecision = {
  decisionId: "eligibility",
  name: "Eligibility",
  hitPolicy: "FIRST",
  inputFields: ["age"],
  outputFields: ["eligible"],
  rows: [
    {
      rowId: "adult",
      conditions: [{ field: "age", operator: "GTE", value: 18 }],
      outcomes: { eligible: true },
      evidenceIds: ["source_age"],
      confidence: 0.9,
    },
  ],
  defaultOutcome: { eligible: false },
};

describe("restricted Canonical Package to GoRules JDM adapter", () => {
  it("round-trips rows/defaults while preserving evidence metadata", () => {
    const table = toJdmTable(decision, vocabulary);
    expect(table.rules).toEqual([
      {
        _id: "adult",
        input_age: ">= 18",
        output_eligible: "true",
      },
      {
        _id: "__canonical_default__",
        input_age: "",
        output_eligible: "false",
      },
    ]);

    table.rules[0].output_eligible = "false";
    const updated = applyJdmTable(decision, table);
    expect(updated.rows[0].outcomes).toEqual({ eligible: false });
    expect(updated.rows[0].evidenceIds).toEqual(["source_age"]);
    expect(updated.rows[0].confidence).toBe(0.9);
    expect(updated.defaultOutcome).toEqual({ eligible: false });
  });

  it("rejects arbitrary expressions instead of widening Rule IR semantics", () => {
    const table = toJdmTable(decision, vocabulary);
    table.rules[0].output_eligible = "age >= 18";
    expect(() => applyJdmTable(decision, table)).toThrow(RestrictedJdmError);
  });
});
