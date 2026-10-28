# Discord uptime alerts

HarnessSync uses UptimeRobot for external availability monitoring and Discord
notifications. No additional Render worker or disk is required for this setup.
The climbing app does not run an AI agent or accept Discord commands.

1. Create an HTTP/website monitor for `https://harnesssync.onrender.com`.
2. Use a five-minute check interval on the free plan.
3. Under **Integrations & API**, add **Discord**, paste the private channel's
   webhook URL, and enable down and recovery notifications.
4. Attach that Discord alert contact to the HarnessSync monitor and save.
5. Send a test notification and confirm it appears in the intended channel.
   Enable notifications for that channel on your phone as well.

Keep the webhook URL private. It belongs in UptimeRobot's integration settings,
not this repository, chat, or screenshots. Do not create a second paid Render
worker for the same alerts.

Monitoring checks public availability. It does not verify signing in, saving a
climb, offline synchronization, or the production database. A successful Discord
test confirms channel delivery; phone notification settings still matter.

Provider instructions:

- [Free plan](https://help.uptimerobot.com/en/articles/11604710-who-should-use-uptimerobot-s-free-plan)
- [Discord integration](https://uptimerobot.com/integrations/discord-integration/)

The previous custom worker instructions are retained in
[the deployment archive](archive/discord-worker.md) for reference. That worker is
not required or activated by the current setup.
