# Serverless ingestion (AWS Lambda)

A serverless front door to the ingestion pipeline: **API Gateway → Lambda →
Redis Stream**. The Lambda (`backend/lambdas/ingest_handler.py`) validates the
payload and `XADD`s it to the same `logs:stream` the FastAPI producer uses; the
consumer (`app/consumer.py`) drains it into OpenSearch. So the async pipeline has
two interchangeable producers — a long-running FastAPI service and an on-demand
Lambda — feeding one consumer.

```
POST /logs/ingest ──▶ API Gateway ──▶ Lambda ──XADD──▶ Redis Stream ──▶ consumer ──▶ OpenSearch
```

## Why Lambda here

Ingestion is bursty and stateless: it validates and enqueues, nothing more. That
is a good fit for Lambda — scale-to-zero, per-request billing, and no server to
run — while the stateful, always-on work (the consumer, alerting) stays on the
container service. Redis must be reachable from the function's VPC (e.g.
ElastiCache); the handler reads `REDIS_HOST` / `REDIS_PORT`.

## Deploy

Requires the AWS SAM CLI and AWS credentials.

```bash
cd backend/serverless
sam build
sam deploy --guided \
  --parameter-overrides \
    RedisHost=<elasticache-endpoint> \
    SubnetIds=<subnet-a,subnet-b> \
    SecurityGroupIds=<sg-id>
```

`sam deploy` prints the `IngestApiUrl`. Test it:

```bash
curl -X POST "$INGEST_API_URL" \
  -H 'Content-Type: application/json' \
  -d '{"service":"payment","level":"ERROR","message":"gateway timeout"}'
# -> 202 {"accepted":1,"stream_ids":["..."]}
```

## Tested

The handler is unit-tested in `backend/tests/test_ingest_handler.py` (payload
validation, batch, base64 bodies, bounded stream, 400/422 error paths) with a
fake Redis — no AWS needed, and it runs in CI.

> **Status:** the handler and SAM template are complete and tested locally. The
> deployment above has not been run against a live AWS account in this repo — the
> honest claim is "wrote and unit-tested a deployable ingestion Lambda + SAM
> template," not "operated it in production." Deploy it to make the stronger claim.
