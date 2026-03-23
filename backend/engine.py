from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from typing import TypedDict, Annotated
from langchain_core.messages import BaseMessage, ToolMessage, SystemMessage
from langchain_mistralai import ChatMistralAI
from dotenv import load_dotenv
from langgraph.checkpoint.sqlite import SqliteSaver
from langchain_community.tools import DuckDuckGoSearchResults
from langchain_community.tools import WikipediaQueryRun
from langchain_community.utilities import WikipediaAPIWrapper
from langchain_core.tools import tool
from datetime import datetime
import sqlite3
import os

# Load API KEY
load_dotenv()

# Tools
search_tool = DuckDuckGoSearchResults(num_results=8)
wiki_tool = WikipediaQueryRun(api_wrapper=WikipediaAPIWrapper())

@tool
def calculator(expression: str) -> str:
    """Useful for solving math problems and arithmetic calculations. Input should be a valid math expression like '2+2' or '100*50/2'."""
    try:
        result = eval(expression)
        return str(result)
    except Exception as e:
        return f'Error: {str(e)}'

tools = [search_tool, wiki_tool, calculator]
tools_dict = {t.name: t for t in tools}

# State
class ChatState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]

# LLM
llm = ChatMistralAI(model_name="mistral-large-2512")
llm_with_tools = llm.bind_tools(tools)

# System Prompt
system_prompt = SystemMessage(content=f"""You are a highly intelligent AI assistant — like ChatGPT or Claude. Today's date is {datetime.now().strftime("%d %B %Y, %A")}.

## Your Personality:
- You are friendly, smart, and conversational.
- You think step by step before answering complex questions.
- You are honest — if you don't know something, you say so clearly.
- You never make up facts or hallucinate information.

## Your Tools & When to Use Them:
1. **DuckDuckGo Search** → Use for: latest news, current events, recent updates, stock prices, sports scores, anything happening in the real world RIGHT NOW.
2. **Wikipedia** → Use for: definitions, history, science, biography, concepts, anything factual and stable.
3. **Calculator** → Use for: ANY math — arithmetic, percentages, conversions. Always use this tool for numbers.

## Output Rules:
- Respond in the SAME language the user writes in (Hindi → Hindi, English → English, Hinglish → Hinglish).
- For NEWS: Search first, then format as: 📰 **Headline** — One line summary. *(X hours ago)*
- For EXPLANATIONS: Use clear headings, bullet points, examples.
- For CODE: Always use proper code blocks with language name.
- For MATH: Show the expression and final answer clearly.
- Keep responses concise but complete.

## Thinking Rules:
- For complex questions, think step by step.
- Always prefer tool results over your own memory for real-world data.
- After getting tool results, synthesize and present them cleanly.
""")

# Nodes
def chat_node(state: ChatState):
    messages = [system_prompt] + state['messages']
    response = llm_with_tools.invoke(messages)
    return {'messages': [response]}

def tool_node(state: ChatState):
    last_msg = state['messages'][-1]
    tool_results = []
    for tool_call in last_msg.tool_calls:
        t = tools_dict[tool_call['name']]
        result = t.invoke(tool_call['args'])
        tool_results.append(
            ToolMessage(content=str(result), tool_call_id=tool_call['id'])
        )
    return {'messages': tool_results}

def should_use_tool(state: ChatState):
    last_msg = state['messages'][-1]
    if hasattr(last_msg, 'tool_calls') and last_msg.tool_calls:
        return 'tool_node'
    return END

# DB path
DB_PATH = os.path.join(os.path.dirname(__file__), 'chatbot.db')

# Build graph
def _build_graph(checkpointer):
    graph = StateGraph(ChatState)
    graph.add_node('chat_node', chat_node)
    graph.add_node('tool_node', tool_node)
    graph.add_edge(START, 'chat_node')
    graph.add_conditional_edges('chat_node', should_use_tool)
    graph.add_edge('tool_node', 'chat_node')
    return graph.compile(checkpointer=checkpointer)

# Global connection (kept open for app lifetime)
_conn = sqlite3.connect(DB_PATH, check_same_thread=False)
_checkpointer = SqliteSaver(_conn)
chatbot = _build_graph(_checkpointer)

def stream_response(thread_id: str, user_message: str):
    """Generator: yields text chunks for SSE streaming"""
    from langchain_core.messages import AIMessage, HumanMessage
    config = {'configurable': {'thread_id': thread_id}}
    for message_chunk, metadata in chatbot.stream(
        {'messages': [HumanMessage(content=user_message)]},
        config=config,
        stream_mode='messages'
    ):
        if isinstance(message_chunk, AIMessage) and isinstance(message_chunk.content, str) and message_chunk.content:
            yield message_chunk.content

def get_thread_history(thread_id: str):
    """Returns list of {role, content} from LangGraph checkpointer"""
    from langchain_core.messages import HumanMessage, AIMessage
    config = {'configurable': {'thread_id': thread_id}}
    state = chatbot.get_state(config=config).values
    messages = state.get('messages', [])
    result = []
    for msg in messages:
        if isinstance(msg, HumanMessage) and isinstance(msg.content, str) and msg.content.strip():
            result.append({'role': 'user', 'content': msg.content})
        elif isinstance(msg, AIMessage) and isinstance(msg.content, str) and msg.content.strip():
            result.append({'role': 'assistant', 'content': msg.content})
    return result
