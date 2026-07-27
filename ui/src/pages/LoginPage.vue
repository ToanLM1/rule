<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { PhArrowRight, PhLockKey, PhShieldCheck } from '@phosphor-icons/vue'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const username = ref('')
const password = ref('')
const error = ref('')
const submitting = ref(false)
const redirect = computed(() =>
  typeof route.query.redirect === 'string' && route.query.redirect.startsWith('/')
    ? route.query.redirect
    : '/overview',
)

async function submit() {
  error.value = ''
  submitting.value = true
  try {
    await auth.login(username.value, password.value)
    await router.replace(redirect.value)
  } catch {
    error.value = 'Invalid username or password.'
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <main class="login-page">
    <section class="login-panel">
      <div class="login-brand">
        <span><PhShieldCheck :size="25" weight="duotone" /></span>
        <div><strong>Rule Platform</strong><small>Governed decision delivery</small></div>
      </div>
      <div class="login-copy">
        <p>Secure workspace</p>
        <h1>Sign in to continue</h1>
        <span>Your identity and assigned roles are recorded with every governed change.</span>
      </div>
      <form @submit.prevent="submit">
        <label>
          <span>Username</span>
          <input v-model.trim="username" name="username" autocomplete="username" required autofocus />
        </label>
        <label>
          <span>Password</span>
          <input v-model="password" name="password" type="password" autocomplete="current-password" required />
        </label>
        <p v-if="error" class="login-error" role="alert">{{ error }}</p>
        <button class="primary-button" type="submit" :disabled="submitting">
          <PhLockKey :size="18" />{{ submitting ? 'Signing in…' : 'Sign in' }}<PhArrowRight :size="17" />
        </button>
      </form>
      <footer>Maker–checker separation remains enforced after login.</footer>
    </section>
  </main>
</template>
