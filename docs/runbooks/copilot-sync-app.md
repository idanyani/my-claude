# Copilot instructions sync app

The [sync-consumers workflow](../../.github/workflows/sync-consumers.yml) opens a re-sync PR in
every consuming repo whose generated `.github/copilot-instructions.md` went stale. It acts through
a GitHub App owned by the gefen-chat org. The app's installation decides which repos are consumers:
the workflow syncs exactly the repos the installation is granted.

## One-time setup

1. **Create the app.** In the gefen-chat org: Settings --> Developer settings --> GitHub Apps -->
   New GitHub App.
   - Name: your choice; no code depends on it.
   - Homepage URL: `https://github.com/idanyani/my-claude`.
   - Webhook: clear **Active** -- the workflow calls the app, nothing calls back.
   - Repository permissions: **Contents: Read and write** (push the sync branch) and
     **Pull requests: Read and write** (open the PR, arm auto-merge). Metadata: Read-only is added
     automatically.
   - Where can this GitHub App be installed: **Only on this account**.
2. **Collect the credentials.** On the app's General page, copy the **Client ID**, then under
   Private keys click **Generate a private key** and keep the downloaded `.pem`.
3. **Install it.** On the app page: Install App --> gefen-chat --> **Only select repositories**,
   and select each consuming repo (the ones whose CI runs the
   `check-copilot-instructions` action).
4. **Store the credentials in my-claude**, then delete the local key:

   ```bash
   gh variable set SYNC_APP_CLIENT_ID -R idanyani/my-claude --body <client-id>
   gh secret set SYNC_APP_PRIVATE_KEY -R idanyani/my-claude < <downloaded-key>.pem
   rm <downloaded-key>.pem
   ```

5. **Verify.** Run the workflow and watch it:

   ```bash
   gh workflow run sync-consumers.yml -R idanyani/my-claude
   gh run watch -R idanyani/my-claude
   ```

   The log prints one line per consumer: `current`, or the sync PR it opened or updated. Repos that
   allow auto-merge get it armed; the others need a manual merge.

## Onboarding a consumer

Add the repo to the installation (app page --> Configure --> Repository access), then run step 5.
No file in my-claude changes.

## Rotating the key

Generate a new private key on the app page, re-run the `gh secret set` line from step 4, run step 5
to confirm, then delete the old key on the app page.
