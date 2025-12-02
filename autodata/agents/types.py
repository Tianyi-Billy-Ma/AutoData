from typing import Annotated, TypedDict

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict, total=False):
    sender: str
    next: str
    messages: Annotated[list[HumanMessage | AIMessage], add_messages]
    user_task: str


WORKER_INFO = {
    "BlueprintAgent": "BlueprintAgent generates blueprints for data collection python scripts using information from tool and browser agents",
    "BrowserAgent": "Web agent for web browsing.",
    "EngineerAgent": "writes code based on information and requirements",
    "PlanAgent": "creates comprehensive data collection strategies and coordinates the overall workflow for web data collection tasks",
    "HumanAgent": "interacts with the user to review steps and provide feedback/approval",
    "TestAgent": "debugs, executes, and tests code",
    "ToolAgent": "run and execute one of the binded tools",
    "ValidationAgent": "validates results and ensures quality standards",
}
