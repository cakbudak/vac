"""Optional official CaMeL privileged-LLM smoke, local Ollama model.

Uses the original upstream CaMeL implementation without editing its source.
The model-name registration and client base URL are local-only adapter config.
"""
import os
os.environ["OPENAI_BASE_URL"]="http://127.0.0.1:11434/v1"
os.environ["OPENAI_API_KEY"]="EMPTY"

from agentdojo.task_suite import get_suite, get_suites
get_suites("v1.2.2")
from agentdojo.models import MODEL_NAMES
from camel.models import make_tools_pipeline
from camel.interpreter.interpreter import MetadataEvalMode

MODEL_NAMES["qwen3.8:latest"]="Qwen local test model"
MODEL_NAMES["qwen3.8:latest+camel"]="Qwen local test model"

suite=get_suite("v1.2.2","workspace")
pipeline=make_tools_pipeline(
    model="openai:qwen3.8:latest",
    use_original=False,
    replay_with_policies=False,
    attack_name="important_instructions",
    reasoning_effort="medium",
    thinking_budget_tokens=None,
    suite="workspace",
    ad_defense=None,
    eval_mode=MetadataEvalMode.NORMAL,
    q_llm=None,
)
utility, _=suite.run_task_with_pipeline(
    pipeline, suite.user_tasks["user_task_0"], injection_task=None, injections={}
)
print("OFFICIAL_CAMEL_LOCAL_SMOKE utility:",utility)
