# MAKE_LIST - Build and Deploy Process

This is a sample MAKE_LIST file demonstrating a typical build and deploy workflow.

## Build Steps

1. Clean previous build artifacts [Make: make clean]
2. Run linting checks [Make: make lint]
3. Execute unit tests [Make: make test-unit]
4. Execute integration tests [Make: make test-integration]
5. Build the application [Make: make build]
6. Create Docker image [Make: make docker-build]
7. Push to registry [Make: make docker-push]
8. Deploy to staging environment [Tool: deploy_staging]

## Prerequisites
- Docker must be installed and running
- Access credentials configured for registry
- Staging environment must be provisioned
