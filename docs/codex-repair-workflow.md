# Reports to reviewed code fixes

HarnessSync collects reports and crash references without an in-app AI model. Codex
Cloud can work on repository files separately; it does not automatically read the
support database or receive reports. The owner chooses what to share and when to release.

## One-time cloud setup

1. In Codex web or desktop, choose **Work in → Cloud → Select environment** and create
   or choose an environment for `milesjo-cloud-project/HarnessSync`. Connect GitHub if prompted.
2. Let Codex prepare the Python project. Use Python 3.12+ and `requirements-dev.txt`;
   `bash scripts/setup_codex_cloud.sh` installs dependencies and runs the tests. If the
   environment offers a custom setup command, use that command there. Otherwise ask the
   environment setup agent to run it. It needs no app API keys or production secrets.
3. Review the environment's setup/test results and publish the environment when ready.
   This publishes a development environment, not the Streamlit app.

See [official Codex Cloud setup](https://learn.chatgpt.com/docs/cloud) for current controls.
Cloud access and usage depend on your ChatGPT plan and limits; this is not a promise
of unlimited free runs. No per-request model service is required in HarnessSync itself.

## For each problem

1. Review the private ticket under **Help & report a problem → Owner support dashboard**.
2. Expand **Prepare a fix with Codex Cloud**. Read and edit the repair brief to remove
   any remaining private details. Common emails, tokens, passwords and database URLs
   are redacted, but automated redaction cannot recognize every sensitive detail.
3. Download the reviewed Markdown brief and paste its text into a Codex Cloud task
   for this repository. No report is uploaded merely by opening or downloading it.
4. Ask Codex to reproduce, fix, and test the failure on a branch, then prepare a diff
   or draft PR. `AGENTS.md` describes the repository and the default release boundary.
5. Review the diff and test evidence. GitHub CI must pass both Tests and Docker build.
6. When you decide to publish, manually merge the approved PR into `main`.
7. Check the live app's affected flow, then update the ticket's status and owner reply.

## What "manual publishing" means here

The existing Streamlit deployment watches `main`. A merge to `main` automatically
updates the app; GitHub Pages also publishes `/docs` from `main`. Keeping the fix on
a PR branch holds it for review. Codex should not merge it for you by default.

If you later want to merge development changes without deploying them, move the
Streamlit deployment to a separate release branch and deliberately promote tested
commits into it. That requires changing the hosted app's branch configuration; it
is not enabled by these repository changes. Do not assume a reboot creates a release gate.

Reports, owner replies, crash grouping, and retryable email notifications continue
to work without Ollama, an AI API key, or a running personal computer.
