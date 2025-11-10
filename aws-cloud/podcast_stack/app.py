#!/usr/bin/env python3
"""
AWS CDK App for Podcast Transcript Summarizer
"""

import aws_cdk as cdk
from podcast_stack.podcast_stack_stack import PodcastStackStack

app = cdk.App()
PodcastStackStack(app, "PodcastStackStack-dev", env=cdk.Environment(account="054367266223", region="us-east-1"))
PodcastStackStack(app, "PodcastStackStack-prod", env=cdk.Environment(account="054367266223", region="us-east-1"))

app.synth()

