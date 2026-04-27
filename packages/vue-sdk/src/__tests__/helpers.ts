import { defineComponent } from 'vue'
import { mount } from '@vue/test-utils'
import { createJanua } from '../plugin'

export const BASE_URL = 'http://localhost:4100'

export function withSetup<T>(composable: () => T): { result: T } {
  let result!: T
  const TestComponent = defineComponent({
    setup() {
      result = composable()
      return {}
    },
    render() {
      return null
    },
  })
  const plugin = createJanua({ baseURL: BASE_URL })
  mount(TestComponent, { global: { plugins: [plugin] } })
  return { result }
}
