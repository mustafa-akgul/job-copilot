# shared-types

Reserved for codegen output. Phase 1 will generate this from the FastAPI
OpenAPI schema (`openapi-typescript` or `orval`) and the extension will
import from `@job-copilot/shared-types` instead of its local
`src/types/shared.ts`.

Until then the extension keeps a hand-maintained copy in
`apps/extension/src/types/shared.ts`. Keep both in sync if you edit the
Pydantic schemas in `apps/backend/src/job_copilot_api/schemas/`.
