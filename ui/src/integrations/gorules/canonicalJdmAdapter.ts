import type { DecisionTableType, TableSchemaItem } from "@gorules/jdm-editor";
import type { CanonicalPackageRevision } from "../../api";

export type CanonicalDecision =
  CanonicalPackageRevision["package"]["decisions"][number];
export type VocabularyField =
  CanonicalPackageRevision["package"]["vocabulary"][number];

const DEFAULT_ROW_ID = "__canonical_default__";
const INPUT_PREFIX = "input_";
const OUTPUT_PREFIX = "output_";

export class RestrictedJdmError extends Error {}

export function toJdmTable(
  decision: CanonicalDecision,
  vocabulary: VocabularyField[],
): DecisionTableType {
  const fields = new Map(vocabulary.map((field) => [field.key, field]));
  const inputs = decision.inputFields.map((key) =>
    column(`${INPUT_PREFIX}${key}`, key, fields),
  );
  const outputs = decision.outputFields.map((key) =>
    column(`${OUTPUT_PREFIX}${key}`, key, fields),
  );
  const rules = decision.rows.map((row) => {
    const result: Record<string, string> = { _id: row.rowId };
    for (const key of decision.inputFields) {
      const condition = row.conditions.find((item) => item.field === key);
      result[`${INPUT_PREFIX}${key}`] = condition
        ? conditionToUnary(condition.operator, condition.value)
        : "";
    }
    for (const key of decision.outputFields) {
      result[`${OUTPUT_PREFIX}${key}`] = scalarToExpression(row.outcomes[key]);
    }
    return result;
  });

  if (decision.hitPolicy !== "COLLECT") {
    const defaultOutcome = decision.defaultOutcome ?? {};
    rules.push({
      _id: DEFAULT_ROW_ID,
      ...Object.fromEntries(inputs.map((item) => [item.id, ""])),
      ...Object.fromEntries(
        outputs.map((item) => [
          item.id,
          scalarToExpression(defaultOutcome[item.field ?? ""]),
        ]),
      ),
    });
  }

  return {
    hitPolicy: decision.hitPolicy === "COLLECT" ? "collect" : "first",
    inputs,
    outputs,
    rules,
  };
}

export function applyJdmTable(
  original: CanonicalDecision,
  table: DecisionTableType,
): CanonicalDecision {
  assertStableColumns(original, table);
  const originalRows = new Map(original.rows.map((row) => [row.rowId, row]));
  let defaultOutcome: Record<string, unknown> | undefined;
  const rows: CanonicalDecision["rows"] = [];

  for (const rule of table.rules) {
    const rowId = String(rule._id ?? "").trim();
    const hasConditions = original.inputFields.some(
      (field) => String(rule[`${INPUT_PREFIX}${field}`] ?? "").trim() !== "",
    );
    if (!hasConditions) {
      if (original.hitPolicy === "COLLECT") {
        throw new RestrictedJdmError(
          "COLLECT decisions cannot contain a catch-all/default row.",
        );
      }
      if (defaultOutcome) {
        throw new RestrictedJdmError("Only one catch-all/default row is allowed.");
      }
      defaultOutcome = Object.fromEntries(
        original.outputFields.map((field) => [
          field,
          expressionToScalar(
            String(rule[`${OUTPUT_PREFIX}${field}`] ?? ""),
            `default.${field}`,
          ),
        ]),
      );
      continue;
    }
    if (!rowId || rowId === DEFAULT_ROW_ID) {
      throw new RestrictedJdmError("Every business rule row needs a stable Rule ID.");
    }
    const previous = originalRows.get(rowId);
    rows.push({
      rowId,
      conditions: original.inputFields.flatMap((field) => {
        const value = String(rule[`${INPUT_PREFIX}${field}`] ?? "").trim();
        return value ? [unaryToCondition(field, value)] : [];
      }),
      outcomes: Object.fromEntries(
        original.outputFields.map((field) => [
          field,
          expressionToScalar(
            String(rule[`${OUTPUT_PREFIX}${field}`] ?? ""),
            `${rowId}.${field}`,
          ),
        ]),
      ),
      evidenceIds: previous?.evidenceIds ?? [],
      ...(previous?.confidence == null
        ? {}
        : { confidence: previous.confidence }),
      ...(previous?.notes ? { notes: previous.notes } : {}),
    });
  }

  if (!rows.length) {
    throw new RestrictedJdmError("A decision requires at least one business rule row.");
  }
  if (original.hitPolicy !== "COLLECT" && !defaultOutcome) {
    throw new RestrictedJdmError(
      "FIRST/UNIQUE decisions require one catch-all row for the default outcome.",
    );
  }

  return {
    ...original,
    rows,
    ...(original.hitPolicy === "COLLECT"
      ? { defaultOutcome: undefined }
      : { defaultOutcome }),
  };
}

function column(
  id: string,
  key: string,
  fields: Map<string, VocabularyField>,
): TableSchemaItem {
  const field = fields.get(key);
  if (!field) throw new RestrictedJdmError(`Unknown vocabulary field: ${key}`);
  return {
    id,
    name: field.label,
    field: key,
  };
}

function assertStableColumns(
  decision: CanonicalDecision,
  table: DecisionTableType,
): void {
  const actualInputs = table.inputs.map((item) => item.field);
  const actualOutputs = table.outputs.map((item) => item.field);
  if (
    JSON.stringify(actualInputs) !== JSON.stringify(decision.inputFields) ||
    JSON.stringify(actualOutputs) !== JSON.stringify(decision.outputFields)
  ) {
    throw new RestrictedJdmError(
      "Vocabulary columns are governed outside the table editor.",
    );
  }
}

function conditionToUnary(operator: string, value: unknown): string {
  const literal = scalarToExpression(value);
  const operators: Record<string, string> = {
    EQ: "==",
    NE: "!=",
    GT: ">",
    GTE: ">=",
    LT: "<",
    LTE: "<=",
  };
  if (operators[operator]) return `${operators[operator]} ${literal}`;
  if (operator === "IN" && Array.isArray(value)) {
    return value.map(scalarToExpression).join(", ");
  }
  if (operator === "BETWEEN" && Array.isArray(value) && value.length === 2) {
    return `[${scalarToExpression(value[0])}..${scalarToExpression(value[1])}]`;
  }
  throw new RestrictedJdmError(
    `Operator ${operator} is outside the constrained GoRules editor profile.`,
  );
}

function unaryToCondition(
  field: string,
  expression: string,
): CanonicalDecision["rows"][number]["conditions"][number] {
  const comparison = expression.match(/^(==|!=|>=|<=|>|<)\s*(.+)$/s);
  if (comparison) {
    const operators: Record<string, string> = {
      "==": "EQ",
      "!=": "NE",
      ">": "GT",
      ">=": "GTE",
      "<": "LT",
      "<=": "LTE",
    };
    return {
      field,
      operator: operators[comparison[1]],
      value: expressionToScalar(comparison[2], field),
    };
  }
  const range = expression.match(/^\[(.+)\.\.(.+)]$/s);
  if (range) {
    return {
      field,
      operator: "BETWEEN",
      value: [
        expressionToScalar(range[1], field),
        expressionToScalar(range[2], field),
      ],
    };
  }
  const list = splitList(expression);
  if (list.length > 1) {
    return {
      field,
      operator: "IN",
      value: list.map((item) => expressionToScalar(item, field)),
    };
  }
  throw new RestrictedJdmError(
    `${field}: use ==, !=, >, >=, <, <=, [min..max], or a comma-separated list.`,
  );
}

function splitList(expression: string): string[] {
  const values: string[] = [];
  let quote = "";
  let start = 0;
  for (let index = 0; index < expression.length; index += 1) {
    const character = expression[index];
    if ((character === '"' || character === "'") && expression[index - 1] !== "\\") {
      quote = quote === character ? "" : quote || character;
    } else if (character === "," && !quote) {
      values.push(expression.slice(start, index).trim());
      start = index + 1;
    }
  }
  values.push(expression.slice(start).trim());
  return values.filter(Boolean);
}

function scalarToExpression(value: unknown): string {
  if (typeof value === "string") return JSON.stringify(value);
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  if (value == null) return "";
  throw new RestrictedJdmError("Only scalar business values are editable.");
}

function expressionToScalar(expression: string, location: string): unknown {
  const value = expression.trim();
  if (!value) {
    throw new RestrictedJdmError(`${location}: a literal value is required.`);
  }
  if (value === "true") return true;
  if (value === "false") return false;
  if (/^-?(?:\d+|\d*\.\d+)$/.test(value)) return Number(value);
  if (
    (value.startsWith('"') && value.endsWith('"')) ||
    (value.startsWith("'") && value.endsWith("'"))
  ) {
    if (value.startsWith("'")) {
      return value.slice(1, -1).replaceAll("\\'", "'");
    }
    try {
      return JSON.parse(value);
    } catch {
      throw new RestrictedJdmError(`${location}: invalid quoted string.`);
    }
  }
  throw new RestrictedJdmError(
    `${location}: expressions/functions are disabled; enter a literal value.`,
  );
}
