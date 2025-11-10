# CDK Bootstrap Steps (Dev)

This documents exactly what was done to bootstrap the AWS account/region for CDK deployments.

## Prereqs
- Activated your Python venv: `/Users/saikamat/Local Documents/python_environments/pytorchenv/bin/activate`
- Directory: `aws-cloud/podcast_stack`

## Steps Executed

1) Ensure project venv exists and install CDK Python deps
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2) Use local (project-scoped) CDK CLI via npx
```bash
npx --yes aws-cdk --version
```

3) Fix CDK stack issues (so synth/bootstrap can run)
- Replaced `sfn.LambdaInvoke` with `tasks.LambdaInvoke` in `podcast_stack/podcast_stack_stack.py`
- Imported `aws_cdk as cdk` to allow `cdk.CfnOutput`

4) Bootstrap the target account/region
```bash
ACCOUNT_ID=$( /usr/local/bin/aws sts get-caller-identity --query Account --output text )
npx --yes aws-cdk bootstrap aws://$ACCOUNT_ID/us-east-1
```

Result: CDKToolkit stack created in account `054367266223`, region `us-east-1`.

## Notes
- If using a named AWS profile, append `--profile <name>` to the bootstrap command.
- Bootstrap is required once per account+region.
- Ensure `aws-cloud/podcast_stack/app.py` has your account ID and region for dev/prod stacks.
