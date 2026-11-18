"""按固定模板版本汇总真实运行记录与定时调度，避免将发布数量当作运行数量。"""
from datetime import datetime, timezone


def summarize(templates, deployments, schedules, runs):
    result = {}
    for template in templates:
        deployment = deployments.get(template['node'])
        history = [run for run in runs if run.parameters.get('template_id') == template['id']]
        matching = []
        if deployment:
            for schedule in schedules.get(template['node'], []):
                parameters = dict(deployment.parameters or {}, **(schedule.parameters or {}))
                if parameters.get('template_id') == template['id']:
                    matching.append(schedule)
        latest = history[0] if history else None
        result[template['id']] = {
            'running': sum(run.state_type.value in ('RUNNING', 'CANCELLING') for run in history if run.state_type),
            'queued': sum(run.state_type.value in ('SCHEDULED', 'PENDING', 'PAUSED') for run in history if run.state_type),
            'latest': {'id': str(latest.id), 'state': latest.state_type.value if latest.state_type else 'UNKNOWN',
                       'at': (latest.end_time or latest.start_time or latest.expected_start_time).isoformat()} if latest else None,
            'schedule': ('enabled' if not deployment.paused and any(item.active for item in matching) else 'paused') if matching else 'none',
        }
    return {'checked_at': datetime.now(timezone.utc).isoformat(), 'templates': result}


async def read_status(client, templates):
    from prefect.client.schemas.filters import DeploymentFilter
    from prefect.client.schemas.sorting import FlowRunSort
    deployments, schedules = {}, {}
    for node in sorted({item['node'] for item in templates}):
        deployment = await client.read_deployment_by_name('website-collect/' + node)
        deployments[node] = deployment
        schedules[node] = await client.read_deployment_schedules(deployment.id)
    runs = []
    if deployments:
        for offset in range(0, 10000, 200):
            page = await client.read_flow_runs(
                deployment_filter=DeploymentFilter(id={'any_': [item.id for item in deployments.values()]}),
                sort=FlowRunSort.EXPECTED_START_TIME_DESC, limit=200, offset=offset)
            runs.extend(page)
            if len(page) < 200:
                break
        else:
            raise RuntimeError('运行记录超出汇总范围，请在 Prefect 查看完整状态')
    return summarize(templates, deployments, schedules, runs)
