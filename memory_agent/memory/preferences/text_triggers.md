# Text Triggers for Project Memory

## Supported user phrases
These phrases are treated as valid text commands for memory operations in Autofinisher Factory.

### Refresh current project memory
If the user writes any of the following, run:
`python3 /home/agent/autofinisher-factory/memory_agent/refresh_memory.py`

Supported phrases:
- обновить память проекта
- обнови память проекта
- refresh project memory
- update project memory

### Reinitialize and then refresh project memory
If the user writes any of the following, run in order:
1. `python3 /home/agent/autofinisher-factory/memory_agent/bootstrap_memory.py`
2. `python3 /home/agent/autofinisher-factory/memory_agent/refresh_memory.py`

Supported phrases:
- перезапустить память проекта
- перезапусти память проекта
- restart project memory
- reinitialize project memory

### Force overwrite memory from current repository state
If the user writes any of the following, rebuild memory files from current repository state by running:
`python3 /home/agent/autofinisher-factory/memory_agent/refresh_memory.py`

Supported phrases:
- перезаписать память проекта
- перезапиши память проекта
- overwrite project memory
- rewrite project memory

## Operating note
The user does not need to open a terminal. These phrases are intended to be handled by the assistant as text instructions.
