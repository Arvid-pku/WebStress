export OPENAI_BASE_URL=http://127.0.0.1:30000/v1
export OPENAI_API_KEY=EMPTY
export LLM_MODEL=default


export SIMULATOR_OPENAI_BASE_URL=https://litellm.oit.duke.edu/v1
export SIMULATOR_OPENAI_API_KEY=sk-Ay4jrZcS2qDNxtGT9QLlJQ
export SIMULATOR_MODEL=gpt-5
export AGENT_OPENAI_BASE_URL=http://127.0.0.1:30000/v1
export AGENT_OPENAI_API_KEY=EMPTY
export AGENT_MODEL=default
export JUDGE_OPENAI_BASE_URL=https://litellm.oit.duke.edu/v1
export JUDGE_OPENAI_API_KEY=sk-Ay4jrZcS2qDNxtGT9QLlJQ
export JUDGE_MODEL=gpt-5
export PROPOSER_OPENAI_API_KEY=sk-Ay4jrZcS2qDNxtGT9QLlJQ
export PROPOSER_OPENAI_BASE_URL=https://litellm.oit.duke.edu/v1
export PROPOSER_MODEL=gpt-5
export COMPILER_OPENAI_API_KEY=sk-Ay4jrZcS2qDNxtGT9QLlJQ
export COMPILER_OPENAI_BASE_URL=https://litellm.oit.duke.edu/v1
export COMPILER_MODEL=gpt-5

python orchestrator.py --steps 20 --sim-mode diverse  --log-profile both --log-state-snapshots --instr-jsonl instructions/osworld_small.jsonl  --fidelity medium --success-threshold 0.9