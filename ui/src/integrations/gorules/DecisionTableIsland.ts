import React from "react";
import { createRoot, type Root } from "react-dom/client";
import {
  DecisionTable,
  JdmConfigProvider,
  type DecisionTableType,
} from "@gorules/jdm-editor";
import initZenWasm from "@gorules/zen-engine-wasm";
import zenWasmUrl from "@gorules/zen-engine-wasm/dist/zen_engine_wasm_bg.wasm?url";
import "@gorules/jdm-editor/dist/style.css";

let wasmPromise: Promise<unknown> | undefined;

export type DecisionTableIslandOptions = {
  value: DecisionTableType;
  disabled: boolean;
  theme: "light" | "dark";
  onChange: (value: DecisionTableType) => void;
};

export async function mountDecisionTable(
  element: HTMLElement,
  options: DecisionTableIslandOptions,
): Promise<{ update: (next: DecisionTableIslandOptions) => void; destroy: () => void }> {
  wasmPromise ??= initZenWasm(zenWasmUrl);
  await wasmPromise;
  const root = createRoot(element);
  render(root, options);
  return {
    update(next) {
      render(root, next);
    },
    destroy() {
      root.unmount();
    },
  };
}

function render(root: Root, options: DecisionTableIslandOptions): void {
  const rowCount = options.value.rules.length;
  const tableHeight = Math.min(420, Math.max(270, 168 + rowCount * 54));

  root.render(
    React.createElement(
      JdmConfigProvider,
      { theme: { mode: options.theme } },
      React.createElement(DecisionTable, {
        value: options.value,
        onChange: options.onChange,
        disabled: options.disabled,
        disableHitPolicy: true,
        permission: "edit:rules",
        mode: "business",
        tableHeight,
        minColWidth: 132,
        colWidth: 176,
        mountDialogsOnBody: true,
      }),
    ),
  );
}
