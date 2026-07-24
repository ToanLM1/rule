<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from "vue";
import type { DecisionTableType } from "@gorules/jdm-editor";
import type { CanonicalPackageRevision } from "../api";
import { useAppStore } from "../stores/app";
import {
  applyJdmTable,
  RestrictedJdmError,
  toJdmTable,
  type CanonicalDecision,
} from "../integrations/gorules/canonicalJdmAdapter";
import {
  mountDecisionTable,
  type DecisionTableIslandOptions,
} from "../integrations/gorules/DecisionTableIsland";

const props = defineProps<{
  decision: CanonicalDecision;
  vocabulary: CanonicalPackageRevision["package"]["vocabulary"];
  disabled: boolean;
}>();
const emit = defineEmits<{
  change: [value: CanonicalDecision];
  error: [message: string];
}>();
const app = useAppStore();

const host = ref<HTMLElement | null>(null);
let island:
  | { update: (options: DecisionTableIslandOptions) => void; destroy: () => void }
  | undefined;
let table: DecisionTableType | undefined;

function options(): DecisionTableIslandOptions {
  table = toJdmTable(props.decision, props.vocabulary);
  return {
    value: table,
    disabled: props.disabled,
    theme: app.resolvedTheme,
    onChange(next) {
      try {
        const decision = applyJdmTable(props.decision, next);
        table = next;
        emit("change", decision);
      } catch (cause) {
        emit(
          "error",
          cause instanceof RestrictedJdmError
            ? cause.message
            : "The GoRules table contains unsupported rule semantics.",
        );
      }
    },
  };
}

onMounted(async () => {
  if (!host.value) return;
  try {
    island = await mountDecisionTable(host.value, options());
  } catch (cause) {
    emit(
      "error",
      cause instanceof Error ? cause.message : "GoRules editor failed to load.",
    );
  }
});

watch(
  () => [props.decision, props.vocabulary, props.disabled, app.resolvedTheme],
  () => island?.update(options()),
  { deep: true },
);

onBeforeUnmount(() => island?.destroy());
</script>

<template>
  <div class="gorules-editor-shell">
    <div ref="host" class="gorules-editor-host" />
  </div>
</template>
