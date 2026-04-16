"""Register admin scheduler tasks with the Carbon Agent platform.

This script is run once during platform setup to register all
admin tasks with the scheduler system.
"""
import asyncio
import os
import sys

# Add parent to path so we can import from the orchestrator
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from admin_agent.scheduler_tasks import ALL_TASKS


async def register_tasks():
    """Register all admin tasks with the Carbon Agent scheduler."""
    from carbon_agent.scheduler import create_scheduled_task

    results = []
    for task in ALL_TASKS:
        try:
            task_id = await create_scheduled_task(
                name=task["name"],
                system_prompt=task["system_prompt"],
                prompt=task["prompt"],
                schedule=task["schedule"],
                dedicated_context=True,
            )
            results.append({"name": task["name"], "id": task_id, "status": "registered"})
            print(f"Registered: {task['name']} -> {task_id}")
        except Exception as e:
            results.append({"name": task["name"], "error": str(e), "status": "failed"})
            print(f"Failed: {task['name']} -> {e}")

    print(f"\nRegistered {len([r for r in results if r['status'] == 'registered'])} tasks")
    return results


if __name__ == "__main__":
    asyncio.run(register_tasks())
