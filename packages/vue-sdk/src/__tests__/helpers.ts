import { defineComponent, inject } from 'vue'
import { mount } from '@vue/test-utils'
import { createJanua, JANUA_KEY, type JanuaVue } from '../plugin'

export const BASE_URL = 'http://localhost:4100'

export function withSetup<T>(composable: () => T): { result: T; janua: JanuaVue } {
  let result!: T
  let janua!: JanuaVue
  const TestComponent = defineComponent({
    setup() {
      janua = inject(JANUA_KEY) as JanuaVue
      result = composable()
      return {}
    },
    render() {
      return null
    },
  })
  const plugin = createJanua({ baseURL: BASE_URL })
  mount(TestComponent, { global: { plugins: [plugin] } })
  return { result, janua }
}
