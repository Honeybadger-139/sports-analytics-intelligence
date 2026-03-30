"""
Multi-Agent System for NBA sports analytics queries.

WHY MULTI-AGENT?
-----------------
The single chatbot handles simple queries well:
  "Who leads in scoring?" → SQLQueryTool → done.

But complex queries require multiple capabilities simultaneously:
  "Compare LeBron's scoring trend vs the team's win rate, and tell me if
   he's playing tomorrow" → [stats query] + [time-series analysis] + [RAG news]

A single LLM call can't reliably do all three without hallucinating.
The solution: decompose the query, route each sub-task to a specialist,
then synthesise the answers.

ARCHITECTURE:
  Supervisor Agent
      │ analyses the query, decides which specialists to invoke
      │
      ├── StatsAgent     (SQL + team stats tools)
      ├── NewsAgent      (RAG retriever tool)
      └── PredictionAgent (prediction + explainability tools)

WHY LANGGRAPH FOR THIS?
  - Supervisor is a stateful node that decides routing dynamically
  - Each specialist can loop (retry, get more context)
  - Results are merged in a final synthesis node
  - The graph is inspectable — you can trace exactly which agent ran what

APPROACH COMPARISON:
  A. Sequential pipeline (query → stats → news → prediction → combine)
     Pros: Simple. Cons: Always runs all agents even when not needed.

  B. Supervisor with dynamic routing (our approach)
     Pros: Efficient, only runs needed agents. Cons: More complex.

  C. ReAct agent (single LLM with all tools, decides step by step)
     Pros: Most flexible. Cons: Unpredictable paths, harder to debug.

  Choice: B — Supervisor is the production sweet spot.

INTERVIEW ANGLE:
  Junior:  "I called multiple APIs and combined the results"
  Senior:  "I built a supervisor-specialist architecture. The supervisor
            analyses the query intent and routes to specialist agents. Each
            specialist has access to specific tools and can retry. The graph
            is stateful — intermediate results accumulate across agents.
            This beats a ReAct agent here because our tools are typed and
            our routing is predictable — easier to monitor and debug."

  Awe moment: "The specialists use the same LangChain tools we built for
               the single chatbot. Adding multi-agent capability required
               zero changes to the tools — just a new orchestration layer."

Part of: SCR-319 — Module 6.3 Multi-Agent System
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, TypedDict

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# ── Graph state ───────────────────────────────────────────────────────────────


class AgentGraphState(TypedDict, total=False):
    """Shared state across all agents in the multi-agent graph."""
    query: str                          # original user query
    session_id: Optional[str]          # for memory
    sport: str

    # Supervisor routing decision
    route_to_stats: bool
    route_to_news: bool
    route_to_prediction: bool
    supervisor_reasoning: str

    # Specialist outputs
    stats_result: str
    news_result: str
    prediction_result: str

    # Synthesis
    final_reply: str
    agents_used: List[str]
    confidence: float


# ── Supervisor decision model ─────────────────────────────────────────────────


class SupervisorDecision(BaseModel):
    """Typed output of the supervisor routing step."""
    route_to_stats: bool = Field(
        default=False,
        description="True if query asks about statistics, standings, records, or analytics",
    )
    route_to_news: bool = Field(
        default=False,
        description="True if query asks about news, injuries, availability, or upcoming games",
    )
    route_to_prediction: bool = Field(
        default=False,
        description="True if query asks for predictions, win probabilities, or 'who will win'",
    )
    reasoning: str = Field(
        default="",
        description="One sentence explaining the routing decision",
    )


# ── Multi-Agent Orchestrator ──────────────────────────────────────────────────


class MultiAgentOrchestrator:
    """
    Supervisor-specialist multi-agent system for NBA analytics.

    Exposes a single `run(query, session_id)` method that:
      1. Routes the query via supervisor analysis
      2. Invokes relevant specialist agents in parallel (simulated sequentially)
      3. Synthesises answers into a single coherent reply

    Public API mirrors LangGraphChatService.reply() for drop-in compatibility.
    """

    def __init__(self, db: Session, sport: str = "nba") -> None:
        self.db = db
        self.sport = sport
        self._tools: Optional[Dict] = None
        self._graph = self._build_graph()
        self.last_metadata: Dict[str, Any] = {}

    @property
    def active_engine(self) -> str:
        return "multi_agent" if self._graph is not None else "fallback"

    def _get_tools(self) -> Dict:
        if self._tools is None:
            try:
                from src.intelligence.langchain_tools import get_tool_map
                self._tools = get_tool_map(db=self.db, sport=self.sport)
            except Exception as exc:
                logger.warning("Multi-agent tools unavailable: %s", exc)
                self._tools = {}
        return self._tools

    # ── Graph construction ────────────────────────────────────────────────────

    def _build_graph(self):
        try:
            from langgraph.graph import END, StateGraph
        except ImportError as exc:
            logger.warning("LangGraph unavailable for multi-agent: %s", exc)
            return None

        def supervisor_node(state: AgentGraphState) -> AgentGraphState:
            """
            Analyse the query and decide which specialist agents to invoke.
            PHASE 10 UPGRADE: True LLM Supervisor instead of heuristic keywords.
            """
            from langchain_google_genai import ChatGoogleGenerativeAI
            from langchain_core.prompts import ChatPromptTemplate
            from pydantic import BaseModel, Field
            from src import config
            
            query = state.get("query", "")
            
            # Using Gemini as the Supervisor to demonstrate Agentic Routing
            try:
                llm = ChatGoogleGenerativeAI(model=config.GEMINI_MODEL, temperature=0.0)
                
                class RouteDecision(BaseModel):
                    next_agent: str = Field(description="One of: 'stats', 'news', 'prediction', or 'synthesizer'")
                    reasoning: str = Field(description="Why this routing decision was made")
                
                prompt = ChatPromptTemplate.from_messages([
                    ("system", "You are the Supervisor Agent for an NBA Analytics Platform. "
                               "Your job is to route the user's query to the correct sub-agent.\n"
                               "- 'stats': For historical data, points, rebounds, standing, or numerical database queries.\n"
                               "- 'news': For injury reports, recent articles, trades, or unplayed game schedules.\n"
                               "- 'prediction': For win probabilities or what factors decide a game.\n"
                               "- 'synthesizer': If the query is just a greeting or already fully answered.\n"
                               "Based on the query, choose exactly one primary next_agent."),
                    ("user", "Query: {query}")
                ])
                
                chain = prompt | llm.with_structured_output(RouteDecision)
                decision = chain.invoke({"query": query})
                
                next_node = decision.next_agent.lower()
                reasoning = decision.reasoning
            except Exception as e:
                logger.warning(f"LLM Supervisor failed, falling back to heuristic: {e}")
                next_node = "stats"
                reasoning = "Fallback routing"

            logger.info("Supervisor decision: %s (%s)", next_node, reasoning)

            return {
                "route_to_stats": next_node == "stats",
                "route_to_news": next_node == "news",
                "route_to_prediction": next_node == "prediction",
                "supervisor_reasoning": reasoning,
                "agents_used": [],
            }

        def data_analyst_node(state: AgentGraphState) -> AgentGraphState:
            """
            Data Analyst Sub-Agent (formerly StatsAgent).
            
            Executes read-only SQL queries against PostgreSQL to generate
            dataframes and statistics strings.
            """
            if not state.get("route_to_stats"):
                return {}

            query = state.get("query", "")
            tools = self._get_tools()
            result = ""
            agents_used = list(state.get("agents_used") or [])

            try:
                # The Data Analyst Agent relies on the SQL tools to safely query the DB
                logger.info("[Data Analyst Agent] Running execute_read_only_sql equivalent...")
                sql_tool = tools.get("sql_query_tool")
                if sql_tool:
                    result = sql_tool.run(query)

                # Augment with exact Team Stats API tool
                if len(result) < 50 or "couldn't" in result.lower():
                    team_tool = tools.get("team_stats_tool")
                    if team_tool:
                        team_result = team_tool.run(query[:50])
                        if team_result and "No stats" not in team_result:
                            result = f"{result}\n{team_result}".strip()

                agents_used.append("data_analyst")
            except Exception as exc:
                logger.warning("Data Analyst Agent failed: %s", exc)
                result = "Stats data temporarily unavailable."

            return {"stats_result": result, "agents_used": agents_used}

        def news_agent_node(state: AgentGraphState) -> AgentGraphState:
            """
            News specialist: uses RAGRetrieverTool.

            Handles: injury reports, player availability, upcoming games, trades.
            """
            if not state.get("route_to_news"):
                return {}

            query = state.get("query", "")
            tools = self._get_tools()
            agents_used = list(state.get("agents_used") or [])

            try:
                rag_tool = tools.get("rag_retriever_tool")
                if rag_tool:
                    result = rag_tool.run(query)
                else:
                    result = "News retrieval unavailable."
                agents_used.append("news")
            except Exception as exc:
                logger.warning("NewsAgent failed: %s", exc)
                result = "News data temporarily unavailable."

            return {"news_result": result, "agents_used": agents_used}

        def prediction_agent_node(state: AgentGraphState) -> AgentGraphState:
            """
            Prediction specialist: uses PredictionTool + ExplainabilityTool.

            Handles: win probability, matchup analysis, model explanations.
            """
            if not state.get("route_to_prediction"):
                return {}

            query = state.get("query", "")
            tools = self._get_tools()
            agents_used = list(state.get("agents_used") or [])

            try:
                pred_tool = tools.get("prediction_tool")
                result = ""
                if pred_tool:
                    # Extract team names from query for prediction tool
                    result = pred_tool.run(
                        home_team=self._extract_home_team(query),
                        away_team=self._extract_away_team(query),
                    )

                # Add explainability if "why" in query
                if "why" in query.lower() or "factor" in query.lower() or "explain" in query.lower():
                    explain_tool = tools.get("explainability_tool")
                    if explain_tool:
                        exp_result = explain_tool.run(
                            home_team=self._extract_home_team(query),
                            away_team=self._extract_away_team(query),
                        )
                        result = f"{result}\n\n{exp_result}".strip()

                agents_used.append("prediction")
            except Exception as exc:
                logger.warning("PredictionAgent failed: %s", exc)
                result = "Prediction service temporarily unavailable."

            return {"prediction_result": result, "agents_used": agents_used}

        def synthesiser_node(state: AgentGraphState) -> AgentGraphState:
            """
            Synthesizer Sub-Agent.
            
            Uses an LLM to take the raw outputs of the Data Analyst, News Researcher, 
            and Prediction Agent, and format them into a single, cohesive human-readable response.
            """
            from langchain_google_genai import ChatGoogleGenerativeAI
            from langchain_core.prompts import ChatPromptTemplate
            from src import config
            
            parts = []
            agents_used = state.get("agents_used", [])
            confidence = 0.5

            if state.get("stats_result"):
                parts.append(f"DATA ANALYST RESULTS: {state['stats_result']}")
                confidence = max(confidence, 0.75)

            if state.get("news_result"):
                parts.append(f"NEWS RESEARCHER RESULTS: {state['news_result']}")
                confidence = max(confidence, 0.70)

            if state.get("prediction_result"):
                parts.append(f"ML PREDICTION RESULTS: {state['prediction_result']}")
                confidence = max(confidence, 0.65)

            if not parts:
                final_reply = "I couldn't find relevant information for that query. Try asking about team stats, recent news, or game predictions."
                confidence = 0.1
            else:
                try:
                    llm = ChatGoogleGenerativeAI(model=config.GEMINI_MODEL, temperature=0.2)
                    prompt = ChatPromptTemplate.from_messages([
                        ("system", "You are the Synthesizer Sub-Agent. Consolidate the following raw sub-agent reports into a single, cohesive, engaging answer for the user. Do not leak internal agent names (like 'Data Analyst Agent said'), just present the final facts directly."),
                        ("user", "User Question: {query}\n\nAgent Reports:\n{reports}")
                    ])
                    chain = prompt | llm
                    response = chain.invoke({"query": state.get("query"), "reports": "\n\n".join(parts)})
                    final_reply = response.content
                except Exception as e:
                    logger.warning(f"LLM Synthesizer failed, falling back to concatenation: {e}")
                    final_reply = "\n\n---\n\n".join(parts)

            return {
                "final_reply": final_reply,
                "agents_used": agents_used,
                "confidence": round(confidence, 2),
            }

        # ── Build graph ───────────────────────────────────────────────────────
        g = StateGraph(AgentGraphState)
        g.add_node("supervisor", supervisor_node)
        g.add_node("stats_agent", data_analyst_node)
        g.add_node("news_agent", news_agent_node)
        g.add_node("prediction_agent", prediction_agent_node)
        g.add_node("synthesiser", synthesiser_node)

        g.set_entry_point("supervisor")

        # The Supervisor maps out which agent to call next dynamically
        def router(state):
            # If the user just said "hi" or it's not a direct data question, just synthesize
            if not state.get("route_to_stats") and not state.get("route_to_news") and not state.get("route_to_prediction"):
                return "synthesiser"
            if state.get("route_to_stats"): return "stats_agent"
            if state.get("route_to_news"): return "news_agent"
            return "prediction_agent"

        g.add_conditional_edges("supervisor", router)
        
        # In a generic multi-agent setup, they all flow to the synthesizer to finalize the response
        g.add_edge("stats_agent", "synthesiser")
        g.add_edge("news_agent", "synthesiser")
        g.add_edge("prediction_agent", "synthesiser")
        g.add_edge("synthesiser", END)

        logger.info("Multi-agent graph compiled (Supervisor + Data Analyst + Researcher + Predictor).")
        return g.compile()

    # ── Public API ────────────────────────────────────────────────────────────

    def run(
        self,
        query: str,
        session_id: Optional[str] = None,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> str:
        """
        Run the multi-agent system on a query.

        Args:
            query: User's natural language question
            session_id: Optional session ID for memory
            history: Optional conversation history

        Returns:
            Synthesised reply string
        """
        if not self._graph:
            return self._fallback_reply(query)

        try:
            result = self._graph.invoke({
                "query": query,
                "session_id": session_id,
                "sport": self.sport,
            })

            final_reply = str(result.get("final_reply", "")).strip()
            agents_used = result.get("agents_used", [])
            confidence = float(result.get("confidence", 0.5))

            self.last_metadata = {
                "agents_used": agents_used,
                "confidence": confidence,
                "engine": "multi_agent",
                "supervisor_reasoning": result.get("supervisor_reasoning", ""),
                "tool_path": "->".join(agents_used) + "->synthesiser",
            }

            logger.info(
                "Multi-agent query complete | agents=%s | confidence=%.2f",
                agents_used, confidence,
            )

            return final_reply or self._fallback_reply(query)

        except Exception as exc:
            logger.error("Multi-agent system failed: %s", exc)
            return self._fallback_reply(query)

    # ── Helper methods ────────────────────────────────────────────────────────

    def _fallback_reply(self, query: str) -> str:
        """Simple fallback when the graph is unavailable."""
        try:
            from src.intelligence.langchain_tools import get_tool_map
            tools = get_tool_map(self.db, self.sport)
            sql_tool = tools.get("sql_query_tool")
            if sql_tool:
                return sql_tool.run(query)
        except Exception:
            pass
        return "I couldn't process that query. Please try rephrasing."

    @staticmethod
    def _extract_home_team(query: str) -> str:
        """
        Naive home team extractor. Production would use NER (Module 6.7).
        For now, extracts the first capitalised team-like token.
        """
        nba_teams = [
            "Lakers", "Warriors", "Celtics", "Heat", "Bulls", "Knicks",
            "Nets", "Clippers", "Nuggets", "Bucks", "76ers", "Suns",
            "Mavericks", "Timberwolves", "Cavaliers", "Pistons", "Pacers",
            "Raptors", "Magic", "Hornets", "Pelicans", "Thunder", "Grizzlies",
            "Jazz", "Kings", "Spurs", "Rockets", "Trail Blazers", "Hawks", "Wizards",
        ]
        query_lower = query.lower()
        for team in nba_teams:
            if team.lower() in query_lower:
                return team
        return "Home Team"

    @staticmethod
    def _extract_away_team(query: str) -> str:
        """Extract away team from query (finds second team mention)."""
        nba_teams = [
            "Lakers", "Warriors", "Celtics", "Heat", "Bulls", "Knicks",
            "Nets", "Clippers", "Nuggets", "Bucks", "76ers", "Suns",
            "Mavericks", "Timberwolves", "Cavaliers", "Pistons", "Pacers",
            "Raptors", "Magic", "Hornets", "Pelicans", "Thunder", "Grizzlies",
            "Jazz", "Kings", "Spurs", "Rockets", "Trail Blazers", "Hawks", "Wizards",
        ]
        query_lower = query.lower()
        found = []
        for team in nba_teams:
            if team.lower() in query_lower:
                found.append(team)
        return found[1] if len(found) >= 2 else "Away Team"
