"""
engine.py - LangGraph chatbot using a local SQLite checkpointer.
"""

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from typing import TypedDict, Annotated
from langchain_core.messages import BaseMessage, ToolMessage, SystemMessage
from langchain_mistralai import ChatMistralAI
from langchain_community.tools import DuckDuckGoSearchResults, WikipediaQueryRun
from langchain_community.utilities import WikipediaAPIWrapper
from langchain_core.tools import tool
from datetime import datetime
import ast
import logging
import operator
import os
import sqlite3

from MCP import (
    get_all_mcp_tools,
    get_mcp_system_message,
    reset_current_user_email,
    set_current_user_email,
)
from config import DATABASE_PATH, load_env
load_env()

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────
# TOOLS
# ─────────────────────────────────────────

search_tool = DuckDuckGoSearchResults(num_results=8)
wiki_tool   = WikipediaQueryRun(api_wrapper=WikipediaAPIWrapper())

_ALLOWED_MATH_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _safe_calculate(node):
    if isinstance(node, ast.Expression):
        return _safe_calculate(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_MATH_OPS:
        left = _safe_calculate(node.left)
        right = _safe_calculate(node.right)
        return _ALLOWED_MATH_OPS[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_MATH_OPS:
        return _ALLOWED_MATH_OPS[type(node.op)](_safe_calculate(node.operand))
    raise ValueError("Only basic math expressions are supported")


@tool
def calculator(expression: str) -> str:
    """Useful for solving math problems. Input: valid math expression like '2+2' or '100*50/2'."""
    try:
        parsed = ast.parse(expression, mode="eval")
        return str(_safe_calculate(parsed))
    except Exception as e:
        return f'Error: {str(e)}'

tools      = [search_tool, wiki_tool, calculator] + get_all_mcp_tools()
tools_dict = {t.name: t for t in tools}

# ─────────────────────────────────────────
# STATE
# ─────────────────────────────────────────

class ChatState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]

# ─────────────────────────────────────────
# LLM
# ─────────────────────────────────────────

llm            = ChatMistralAI(model_name="mistral-large-2512")
llm_with_tools = llm.bind_tools(tools)

# ─────────────────────────────────────────
# SYSTEM PROMPT
# ─────────────────────────────────────────

system_prompt = SystemMessage(content=f"""You are a highly intelligent AI assistant. Today's date is {datetime.now().strftime("%d %B %Y, %A")}.

## Your Personality:
- Friendly, smart, and conversational.
- Think step by step before answering complex questions.
- Honest — if you don't know something, say so clearly.
- Never make up facts or hallucinate.

## Tools & When to Use Them:
1. **DuckDuckGo Search** → Latest news, current events, real-time data.
2. **Wikipedia** → Definitions, history, science, biographies.
3. **Calculator** → ANY math — always use this for numbers.

## Output Rules:
- Respond in the SAME language the user writes in.
- Use proper Markdown formatting (headings, bold, bullets, code blocks).
- Keep responses complete but well-structured.
""")

# ─────────────────────────────────────────
# NODES
# ─────────────────────────────────────────

def chat_node(state: ChatState, config=None):
    document_context = ""
    user_email = None
    if config:
        metadata = config.get("metadata") or {}
        document_context = metadata.get("document_context", "")
        user_email = metadata.get("user_email")
    messages = [system_prompt]
    mcp_context = get_mcp_system_message(user_email)
    if mcp_context:
        messages.append(SystemMessage(content=f"""## Connected Apps
{mcp_context}
"""))
    if document_context:
        messages.append(SystemMessage(content=f"""## Workspace Document Context
Use this context when it is relevant to the user's request. If the question asks about uploaded documents and the answer is not present here, say that clearly. Cite document names in the answer when using this context.

{document_context}
"""))
    messages += state['messages']
    response = llm_with_tools.invoke(messages)
    return {'messages': [response]}

def _mcp_user_email_from_config(config) -> str | None:
    if not config:
        return None
    return (config.get("metadata") or {}).get("user_email")


def tool_node(state: ChatState, config=None):
    last_msg     = state['messages'][-1]
    tool_results = []
    mcp_token = set_current_user_email(_mcp_user_email_from_config(config))
    try:
        for tool_call in last_msg.tool_calls:
            t = tools_dict.get(tool_call['name'])
            if not t:
                result = f"Unknown tool: {tool_call['name']}"
            else:
                try:
                    result = t.invoke(tool_call['args'])
                except Exception as exc:
                    logger.warning(
                        "Tool call failed for %s: %s: %s",
                        tool_call["name"],
                        type(exc).__name__,
                        exc,
                    )
                    result = f"{tool_call['name']} tool error: {type(exc).__name__}: {exc}"
            tool_results.append(
                ToolMessage(content=str(result), tool_call_id=tool_call['id'])
            )
    finally:
        reset_current_user_email(mcp_token)
    return {'messages': tool_results}

def should_use_tool(state: ChatState):
    last_msg = state['messages'][-1]
    if hasattr(last_msg, 'tool_calls') and last_msg.tool_calls:
        return 'tool_node'
    return END

# ─────────────────────────────────────────
# GRAPH + CHECKPOINTER (SQLite)
# ─────────────────────────────────────────

_checkpointer = None
_checkpoint_conn = None
chatbot       = None


def init_chatbot():
    """Lazily initialize the chatbot with a SQLite checkpointer."""
    global _checkpointer, _checkpoint_conn, chatbot

    if chatbot is not None:
        return chatbot

    try:
        from langgraph.checkpoint.sqlite import SqliteSaver
        _checkpoint_conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        _checkpointer = SqliteSaver(_checkpoint_conn)
        _checkpointer.setup()
        logger.info("LangGraph SQLite checkpointer initialized")
    except Exception as e:
        logger.error(f"SQLite checkpointer init failed: {e}")
        raise RuntimeError(f"Could not initialize SQLite for LangGraph: {e}")

    chatbot = _build_graph(_checkpointer)
    logger.info("Chatbot graph compiled with SQLite checkpointer")
    return chatbot


def cleanup_chatbot():
    global _checkpointer, _checkpoint_conn, chatbot
    logger.info("Cleaning up chatbot resources...")
    _checkpointer = None
    if _checkpoint_conn is not None:
        _checkpoint_conn.close()
    _checkpoint_conn = None
    chatbot       = None


def _build_graph(checkpointer):
    graph = StateGraph(ChatState)
    graph.add_node('chat_node', chat_node)
    graph.add_node('tool_node', tool_node)
    graph.add_edge(START, 'chat_node')
    graph.add_conditional_edges('chat_node', should_use_tool)
    graph.add_edge('tool_node', 'chat_node')
    return graph.compile(checkpointer=checkpointer)


# ─────────────────────────────────────────
# PUBLIC FUNCTIONS
# ─────────────────────────────────────────

def stream_response(
    thread_id: str,
    user_message: str,
    document_context: str = "",
    user_email: str | None = None,
):
    """Yield text chunks for SSE streaming."""
    from langchain_core.messages import AIMessage, HumanMessage

    bot    = init_chatbot()
    config = {
        'configurable': {'thread_id': thread_id},
        'run_name':     f'chat_{thread_id[:8]}',
        'metadata':     {
            'thread_id': thread_id,
            'document_context': document_context,
            'user_email': user_email,
        },
    }

    try:
        for message_chunk, metadata in bot.stream(
            {'messages': [HumanMessage(content=user_message)]},
            config=config,
            stream_mode='messages'
        ):
            if (
                isinstance(message_chunk, AIMessage)
                and isinstance(message_chunk.content, str)
                and message_chunk.content
            ):
                yield message_chunk.content

    except GeneratorExit:
        logger.debug(f"Stream closed for thread {thread_id[:8]}")
    except Exception as e:
        if "CancelledError" in type(e).__name__:
            logger.debug(f"Stream cancelled for thread {thread_id[:8]}")
        else:
            logger.error(f"Stream error: {type(e).__name__}: {e}")
        raise


def get_thread_history(thread_id: str):
    from langchain_core.messages import HumanMessage, AIMessage

    bot    = init_chatbot()
    config = {'configurable': {'thread_id': thread_id}}
    state  = bot.get_state(config=config).values
    msgs   = state.get('messages', [])

    result = []
    for msg in msgs:
        if isinstance(msg, HumanMessage) and isinstance(msg.content, str) and msg.content.strip():
            result.append({'role': 'user', 'content': msg.content})
        elif isinstance(msg, AIMessage) and isinstance(msg.content, str) and msg.content.strip():
            result.append({'role': 'assistant', 'content': msg.content})
    return result
