import { defineConfig } from '@hey-api/openapi-ts'

export default defineConfig([
  {
    input: './src/api/openapi.json',
    output: './src/api/client',
    parser: { filters: { tags: { exclude: ['workspace'] } } },
  },
  {
    input: './src/api/openapi.json',
    output: './src/api/workspace',
    parser: { filters: { tags: { include: ['workspace'] } } },
  },
])
