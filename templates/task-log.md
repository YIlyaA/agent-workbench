# Task log

File: `session-log/tasks.csv`, one row per task. Add it at the moment you finish.

```
id,date,type,method,est_hours_old_way,my_active_minutes,agent_runtime_minutes,start,end,tests_green,review_findings,rolled_back,outcome
T-001,2026-10-16,bugfix,agent,1.5,25,40,10:05,11:10,yes,1,no,order status bug fixed with regression test
```

- `method`: `agent` or `old`.
- `my_active_minutes`: time I really spent (reading, steering, reviewing). Not the agent's waiting time.
- `outcome`: one plain sentence a user would understand.
