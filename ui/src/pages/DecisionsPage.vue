<script setup lang="ts">
import { useAppStore } from '../stores/app'

const app = useAppStore()
</script>

<template>
  <main class="page-shell">
    <header>
      <p class="eyebrow">Business Rules Platform</p>
      <h1>Decisions</h1>
      <p>Governed rule decisions will appear here.</p>
    </header>
    <section aria-label="API connection" class="connection-card">
      <span>API</span>
      <code>{{ app.apiBaseUrl }}</code>
    </section>
  </main>
</template>

<style scoped>
.page-shell {
  width: min(1120px, calc(100% - 48px));
  margin: 0 auto;
  padding: 64px 0;
}

.eyebrow {
  margin: 0 0 8px;
  color: #52627a;
  font-size: 0.78rem;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

h1 {
  margin: 0;
  font-size: clamp(2rem, 5vw, 4rem);
  letter-spacing: -0.04em;
}

.connection-card {
  display: flex;
  gap: 12px;
  align-items: center;
  margin-top: 40px;
  padding: 18px 20px;
  border: 1px solid #dbe1ea;
  border-radius: 12px;
  background: white;
}

.connection-card span {
  color: #52627a;
  font-weight: 700;
}
</style>
