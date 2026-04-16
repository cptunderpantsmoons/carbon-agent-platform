# Admin Carbon Agent

This directory contains the configuration for the admin Carbon Agent instance
that manages the multi-user platform.

## How It Works

The admin agent runs as a standard Carbon Agent instance with additional
scheduled tasks that interact with the orchestrator API. It stays in the
loop by:

1. **Health Monitoring**: Every 5 minutes, checks platform health and
   resolves issues automatically
2. **Idle Cleanup**: Every 5 minutes, spins down idle agent instances
   to save costs
3. **Daily Reports**: Every day at 9 AM, generates a platform status report
4. **Volume Audits**: Every Monday at 2 AM, audits persistent volumes
   for cleanup

## Setup

1. Deploy the admin Carbon Agent as a standard instance
2. Register the scheduler tasks from `scheduler_tasks.py`
3. Set environment variables:
   - `ADMIN_AGENT_API_KEY` - shared with the orchestrator
   - `ORCHESTRATOR_URL` - internal URL of the orchestrator service

## Interaction

You can also interact with the admin agent directly:
- "Show me the platform health"
- "List all users"
- "Create a new user for alice@example.com"
- "Spin down all idle sessions"
- "How much are we spending this month?"

The agent translates these natural language commands into orchestrator
API calls and returns the results.
