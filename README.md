# CodeJudge

A local portfolio prototype for online code execution and evaluation. FastAPI accepts submissions, PostgreSQL stores their status and results, Redis queues jobs, and a worker runs each submission in a disposable Docker container. A static dashboard submits code and displays results.

> **Security scope:** This is a local portfolio prototype, not a public service for arbitrary users. The worker has access to the Docker socket, which gives it substantial control over the host. The demo does not include authentication, per-user quotas, production rate limiting, or a hardened multi-tenant execution boundary. Keep it on your own machine. A real service needs a separately reviewed isolation boundary, such as dedicated disposable VMs or a runner cluster.

## Architecture

```text
Browser → FastAPI → PostgreSQL stores submission
                 → Redis queue → Worker → Isolated runtime container
Browser ← polls submission status ← PostgreSQL stores result
```

## Features

- Executes Python, JavaScript, Java, and C++ submissions
- Processes submissions asynchronously through Redis
- Stores submission status and results in PostgreSQL
- Compares program output with expected output
- Captures standard output, errors, verdict, exit code, and runtime
- Applies a 5-second wall-time limit, 256 MiB memory limit, 0.5 CPU limit, and 64-process limit
- Runs code without network access, with a read-only root filesystem and dropped Linux capabilities
- Uses a separate Docker volume for each submission and removes it afterward

Each submission has one input and one expected output. This prototype is for local demonstration; its container setup is not a production sandbox for hostile multi-tenant workloads.

## Requirements

- Docker Desktop with Docker Compose v2
- Python, to serve the dashboard locally
- Git, if you want to publish the project

## Run locally

1. Open PowerShell or a terminal in the project root—the folder containing `docker-compose.yml`.

2. Build and start the API, worker, PostgreSQL, and Redis:

   ```powershell
   docker compose up --build -d
   ```

   On the first run, Docker downloads the required images. Check that the services started:

   ```powershell
   docker compose ps
   ```

3. Serve the dashboard from the project root:

   ```powershell
   python -m http.server 8080 --directory dashboard
   ```

   Leave this terminal open. Visit [http://localhost:8080](http://localhost:8080).

4. Submit the default Python example. Try the other languages by selecting them in the dashboard. Keep the input and expected output as `Hello, judge!` for the echo examples.

5. Open the API documentation at [http://localhost:8000/docs](http://localhost:8000/docs). The health endpoint is [http://localhost:8000/health](http://localhost:8000/health).

6. To stop the Docker services:

   ```powershell
   docker compose down
   ```

   To also delete the local database volume and its data:

   ```powershell
   docker compose down -v
   ```

## API example

Submit a Python program with `curl`:

```bash
curl -X POST http://localhost:8000/submissions \
  -H "Content-Type: application/json" \
  -d '{"language":"python","source":"print(input())","stdin":"hello\n","expected_output":"hello"}'
```

The response includes a submission ID. Check its result at `GET /submissions/{id}`. A completed submission has status `done`; its result includes the verdict, output, errors, exit code, and runtime in milliseconds.

## Project roadmap

- Add authentication, user quotas, problem management, and multiple test cases
- Add queue retries, dead-letter handling, and graceful worker shutdown
- Measure queue wait time separately from execution time
- Add Prometheus metrics and Grafana dashboards
- Add integration tests, CI, a threat model, and a demo video
- Replace Docker-socket execution with a dedicated, reviewed runner isolation boundary

## Resume bullets

Use only claims that match what you have implemented and measured:

- Built a multi-language online judge for Python, JavaScript, Java, and C++ using FastAPI, Redis, PostgreSQL, and Docker.
- Ran submissions in disposable containers with network isolation and CPU, memory, process, and wall-time limits.

Add performance numbers only after running a documented load test. Keep the security limitations visible, and do not present this local prototype as a production sandbox.