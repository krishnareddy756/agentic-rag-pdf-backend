"""
LangGraph Agent Definition
Multi-step reasoning agent with tools
"""
import json
import logging
from typing import Any, Dict, List, Annotated
from datetime import datetime
import re

from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from pydantic import BaseModel

from src.backend.agent.tools import (
    DocumentRetriever, TableAnalyzer, Calculator, 
    retrieve_documents, find_relevant_tables, perform_calculation, get_page_content
)
from src.config import MODEL, TEMPERATURE, OPENAI_API_KEY

logger = logging.getLogger(__name__)

class AgentState(BaseModel):
    """State for the agent graph"""
    query: str
    messages: List[Dict] = []
    thought_process: List[Dict] = []
    tools_used: List[Dict] = []
    final_answer: str = ""
    facts_cited: List[Dict] = []
    iteration: int = 0


class CyberIrelandAgent:
    """Agent for querying Cyber Ireland PDF"""
    
    def __init__(self, retriever: DocumentRetriever, analyzer: TableAnalyzer):
        self.retriever = retriever
        self.analyzer = analyzer
        self.calculator = Calculator()
        self.llm = ChatOpenAI(
            model=MODEL,
            temperature=TEMPERATURE,
            api_key=OPENAI_API_KEY
        )
        self.execution_log = []
        self.graph = self._build_graph()
    
    def _build_graph(self):
        """Build the LangGraph state machine"""
        workflow = StateGraph(AgentState)
        
        # Add nodes
        workflow.add_node("plan", self._plan_node)
        workflow.add_node("retrieve", self._retrieve_node)
        workflow.add_node("analyze", self._analyze_node)
        workflow.add_node("calculate", self._calculate_node)
        workflow.add_node("answer", self._answer_node)
        workflow.add_node("verify", self._verify_node)
        
        # Add edges
        workflow.add_edge(START, "plan")
        workflow.add_edge("plan", "retrieve")
        workflow.add_edge("retrieve", "analyze")
        workflow.add_conditional_edges("analyze", self._should_calculate, 
                                       {"yes": "calculate", "no": "answer"})
        workflow.add_edge("calculate", "answer")
        workflow.add_edge("answer", "verify")
        workflow.add_edge("verify", END)
        
        return workflow.compile()
    
    def _plan_node(self, state: AgentState) -> Dict[str, Any]:
        """Plan the query strategy"""
        log_entry = {
            "step": "plan",
            "timestamp": datetime.now().isoformat(),
            "query": state.query
        }
        
        system_prompt = """You are an expert analyst for the Cyber Ireland 2022 Report.
        
Analyze the user's query and determine:
1. What specific information is needed
2. Whether calculations are required
3. What pages/tables might contain the answer
4. What citations will be needed

Respond in JSON format with: {
    "information_needed": [],
    "requires_calculation": boolean,
    "potential_tables": [],
    "potential_pages": [],
    "strategy": "description"
}"""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Query: {state.query}"}
        ]
        
        response = self.llm.invoke(messages)
        plan_text = response.content
        
        # Parse plan
        try:
            plan_json = json.loads(plan_text)
            log_entry["plan"] = plan_json
        except:
            log_entry["plan"] = {"raw": plan_text}
        
        state.thought_process.append(log_entry)
        return {"thought_process": state.thought_process}
    
    def _retrieve_node(self, state: AgentState) -> Dict[str, Any]:
        """Retrieve relevant documents"""
        log_entry = {
            "step": "retrieve",
            "timestamp": datetime.now().isoformat(),
        }
        
        # Retrieve documents
        results = retrieve_documents(state.query, self.retriever, k=10)
        log_entry["retrieved_chunks"] = len(results)
        log_entry["chunks"] = results[:3]  # Log top 3
        
        state.thought_process.append(log_entry)
        
        return {"thought_process": state.thought_process}
    
    def _analyze_node(self, state: AgentState) -> Dict[str, Any]:
        """Analyze and extract relevant information"""
        log_entry = {
            "step": "analyze",
            "timestamp": datetime.now().isoformat(),
        }
        
        # Look for tables if needed
        if "south" in state.query.lower() or "regional" in state.query.lower():
            tables = find_relevant_tables("region", self.analyzer)
            log_entry["tables_found"] = len(tables)
            log_entry["tables"] = tables[:1]  # Log first table
        
        state.thought_process.append(log_entry)
        
        return {"thought_process": state.thought_process}
    
    def _should_calculate(self, state: AgentState) -> str:
        """Determine if calculation is needed"""
        keywords = ["cagr", "growth rate", "calculate", "formula", "math"]
        if any(kw in state.query.lower() for kw in keywords):
            return "yes"
        return "no"
    
    def _calculate_node(self, state: AgentState) -> Dict[str, Any]:
        """Perform calculations"""
        log_entry = {
            "step": "calculate",
            "timestamp": datetime.now().isoformat(),
        }
        
        # Extract numbers from retrieved documents
        # This will be populated based on the query
        log_entry["calculation_performed"] = "pending"
        
        state.thought_process.append(log_entry)
        
        return {"thought_process": state.thought_process}
    
    def _answer_node(self, state: AgentState) -> Dict[str, Any]:
        """Generate final answer with citations"""
        log_entry = {
            "step": "answer",
            "timestamp": datetime.now().isoformat(),
        }
        
        system_prompt = """You are analyzing the Cyber Ireland 2022 Report.
        
Based on the analysis steps above, provide a clear, factual answer that:
1. Answers the user's query directly
2. Cites specific pages and sections
3. Includes exact numbers where applicable
4. Explicitly states if data is not found

Format: Clear statement followed by citations."""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Query: {state.query}\n\nAnalysis: {json.dumps(state.thought_process, indent=2)}"}
        ]
        
        response = self.llm.invoke(messages)
        answer = response.content
        
        log_entry["answer"] = answer
        state.final_answer = answer
        state.thought_process.append(log_entry)
        
        # Extract citations
        page_refs = re.findall(r"page\s+(\d+)", answer, re.IGNORECASE)
        state.facts_cited = [{"page": int(p)} for p in page_refs]
        
        return {
            "final_answer": state.final_answer,
            "thought_process": state.thought_process,
            "facts_cited": state.facts_cited
        }
    
    def _verify_node(self, state: AgentState) -> Dict[str, Any]:
        """Verify answer quality"""
        log_entry = {
            "step": "verify",
            "timestamp": datetime.now().isoformat(),
        }
        
        # Check for citations
        has_citations = len(state.facts_cited) > 0
        is_specific = any(str(i).isdigit() for i in state.final_answer.split())
        
        log_entry["has_citations"] = has_citations
        log_entry["is_specific"] = is_specific
        log_entry["quality_score"] = 0.8 if has_citations else 0.5
        
        state.thought_process.append(log_entry)
        
        return {"thought_process": state.thought_process}
    
    async def query(self, user_query: str) -> Dict[str, Any]:
        """Execute query through the graph"""
        initial_state = AgentState(query=user_query)
        
        result = self.graph.invoke({"query": user_query, "messages": [], "thought_process": []})
        
        execution_record = {
            "timestamp": datetime.now().isoformat(),
            "query": user_query,
            "answer": result.get("final_answer", ""),
            "thought_process": result.get("thought_process", []),
            "facts_cited": result.get("facts_cited", [])
        }
        
        self.execution_log.append(execution_record)
        
        return execution_record
    
    def save_logs(self, output_path: str):
        """Save execution logs"""
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(self.execution_log, f, indent=2, ensure_ascii=False)
