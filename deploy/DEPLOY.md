# Deploying to AWS Lambda

## Prerequisites

```bash
pip install aws-sam-cli
aws configure          # set your AWS credentials & default region
```

## One-time setup

```bash
# From the project root
cd deploy

sam build --template template.yaml

sam deploy --guided \
  --parameter-overrides \
    TelegramBotToken=<your_bot_token> \
    TelegramChatId=<your_chat_id>
```

`--guided` walks you through stack name, region, S3 bucket for SAM artifacts, etc.
After the first deploy, subsequent deploys can use just:

```bash
sam build && sam deploy
```

## What gets created

| Resource | Purpose |
|---|---|
| `schengen-appointment-watcher` Lambda | Runs every 60 min via EventBridge |
| EventBridge Rule `schengen-watcher-schedule` | Triggers Lambda on `rate(60 minutes)` |
| S3 bucket `schengen-watcher-snapshot-<account-id>` | Stores `snapshot.json` with versioning |
| Secrets Manager `schengen-watcher/telegram` | Holds bot token + chat ID securely |
| CloudWatch Alarm `schengen-watcher-errors` | Alerts if Lambda throws an error |

## Environment variables set on Lambda automatically

| Variable | Value |
|---|---|
| `STATE_BUCKET` | S3 bucket name (auto-wired) |
| `STATE_KEY` | `snapshot.json` |
| `SECRETS_ARN` | Secrets Manager ARN (auto-wired) |
| `AWS_LAMBDA_FUNCTION_NAME` | Set by Lambda runtime (used to skip file logging) |

## Change poll interval

Edit `PollIntervalMinutes` in `template.yaml` (default: 60) and redeploy.
Or pass it as a parameter override:

```bash
sam deploy --parameter-overrides PollIntervalMinutes=5
```

## View logs

```bash
sam logs -n schengen-appointment-watcher --tail
# or
aws logs tail /aws/lambda/schengen-appointment-watcher --follow
```

## Test the Lambda manually

```bash
aws lambda invoke \
  --function-name schengen-appointment-watcher \
  --payload '{}' \
  response.json && cat response.json
```

## Tear down

```bash
aws cloudformation delete-stack --stack-name <your-stack-name>
# Also empty and delete the S3 bucket manually (CloudFormation won't delete non-empty buckets)
```
