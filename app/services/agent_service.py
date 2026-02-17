from typing import Annotated, TypedDict
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.tools import tool
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from app.core.config import settings
from app.core.database import get_table_schema_text, execute_readonly_sql, get_sync_connection


# --- State ---

class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    sql_query: str
    query_result: dict
    analysis_type_id: int | None


# --- Tools ---

@tool
def query_database(sql: str) -> dict:
    """Execute a read-only SQL query against the SQLite database.
    Use standard SQL syntax compatible with SQLite.
    Only SELECT statements are allowed."""
    return execute_readonly_sql(sql)


@tool
def list_tables() -> str:
    """List all available data tables with their columns and row counts."""
    return get_table_schema_text()


@tool
def sample_table(table_name: str, limit: int = 5) -> dict:
    """Get a sample of rows from a specific table to understand its data."""
    return execute_readonly_sql(
        f'SELECT * FROM "{table_name}" LIMIT {min(limit, 20)}'
    )


# --- Graph construction ---

def _get_analysis_config(analysis_type_id: int | None) -> dict:
    """Load system prompt and guardrails for an analysis type."""
    default = {
        "system_prompt": (
            "Você é um analista de dados especialista. Responda em português do Brasil. "
            "Gere SQL ANSI compatível com SQLite. Explique os resultados de forma clara."
        ),
        "guardrails_input": "",
        "guardrails_output": "",
    }
    if not analysis_type_id:
        return default

    conn = get_sync_connection()
    try:
        cursor = conn.execute(
            "SELECT system_prompt, guardrails_input, guardrails_output "
            "FROM analysis_types WHERE id = ?",
            (analysis_type_id,),
        )
        row = cursor.fetchone()
        if row:
            return {
                "system_prompt": row[0] or default["system_prompt"],
                "guardrails_input": row[1] or "",
                "guardrails_output": row[2] or "",
            }
        return default
    finally:
        conn.close()


def build_agent():
    """Build and compile the LangGraph agent for NL-to-SQL."""
    tools = [query_database, list_tables, sample_table]
    llm = ChatOpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
        temperature=0,
    )
    llm_with_tools = llm.bind_tools(tools)

    def agent_node(state: AgentState):
        config = _get_analysis_config(state.get("analysis_type_id"))
        schema_text = get_table_schema_text()

        system_content = f"""{config['system_prompt']}

## Tabelas Disponíveis
{schema_text}

## Regras
- Gere APENAS consultas SELECT (leitura). Nunca use DROP, DELETE, UPDATE, INSERT.
- Use aspas duplas para nomes de tabelas e colunas quando necessário.
- Sempre use a tool query_database para executar o SQL.
- Se não souber a estrutura, use list_tables ou sample_table primeiro.
- Apresente os resultados de forma organizada com insights.
- Responda SEMPRE em português do Brasil.

## Guardrails de Entrada
{config['guardrails_input']}

## Guardrails de Saída
{config['guardrails_output']}
"""
        messages = [SystemMessage(content=system_content)] + state["messages"]
        response = llm_with_tools.invoke(messages)
        return {"messages": [response]}

    def should_continue(state: AgentState):
        last = state["messages"][-1]
        if hasattr(last, "tool_calls") and last.tool_calls:
            return "tools"
        return END

    tool_node = ToolNode(tools)

    graph = StateGraph(AgentState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node)
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
    graph.add_edge("tools", "agent")

    return graph.compile()


# Singleton compiled agent
_agent = None


def get_agent():
    global _agent
    if _agent is None:
        _agent = build_agent()
    return _agent


def reset_agent():
    """Reset agent (e.g. after schema changes)."""
    global _agent
    _agent = None


async def run_query(question: str, analysis_type_id: int | None = None, context: str | None = None) -> dict:
    """Run a natural language query through the agent."""
    agent = get_agent()

    messages = []
    if context:
        messages.append(HumanMessage(content=f"Contexto anterior: {context}"))
        messages.append(AIMessage(content="Entendido, vou considerar o contexto anterior."))
    messages.append(HumanMessage(content=question))

    result = agent.invoke({
        "messages": messages,
        "sql_query": "",
        "query_result": {},
        "analysis_type_id": analysis_type_id,
    })

    # Extract the final AI response and any SQL/data from tool calls
    final_messages = result["messages"]
    ai_response = ""
    sql_generated = ""
    data = {}

    for msg in final_messages:
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                if tc["name"] == "query_database":
                    sql_generated = tc["args"].get("sql", "")
        if hasattr(msg, "content") and isinstance(msg.content, str):
            if not hasattr(msg, "tool_calls") or not msg.tool_calls:
                if msg.type == "ai":
                    ai_response = msg.content
        if msg.type == "tool" and msg.name == "query_database":
            import json
            try:
                data = json.loads(msg.content) if isinstance(msg.content, str) else msg.content
            except (json.JSONDecodeError, TypeError):
                data = {"raw": str(msg.content)}

    # Save to history
    conn = get_sync_connection()
    try:
        conn.execute(
            "INSERT INTO query_history (question, sql_generated, result_summary, analysis_type_id) VALUES (?, ?, ?, ?)",
            (question, sql_generated, ai_response[:500] if ai_response else "", analysis_type_id),
        )
        conn.commit()
    finally:
        conn.close()

    return {
        "question": question,
        "sql_generated": sql_generated,
        "explanation": ai_response,
        "data": data,
    }
