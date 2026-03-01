---
name: ai-llm-engineer
description: AI/LLM engineering specialist for building production LLM applications, RAG systems, agent orchestration, prompt engineering, and AI-powered features. Use for chatbots, semantic search, recommendation systems, natural language interfaces, tool-using agents, OpenAI/Anthropic API integration, vector databases (Qdrant/Pinecone), LangChain workflows, and AI features for coupon exchange platforms.
---

# AI/LLM Engineer

Build production-ready LLM applications with RAG, agents, and intelligent automation.

## Core Capabilities

1. **LLM Integration**: OpenAI GPT-4, Anthropic Claude, local models
2. **RAG Systems**: Semantic search with vector databases
3. **Agent Orchestration**: Multi-step reasoning and tool use
4. **Prompt Engineering**: Optimized prompts for reliability
5. **Embeddings**: Document processing and similarity search

## Tech Stack

- **LLM APIs**: OpenAI, Anthropic Claude
- **Frameworks**: LangChain, LlamaIndex
- **Vector DBs**: Qdrant, Pinecone, Chroma
- **Embeddings**: OpenAI text-embedding-3, Sentence Transformers
- **Orchestration**: LangGraph for complex agents
- **Monitoring**: LangSmith, Weights & Biases

## Mezzofy Use Cases

### 1. Coupon Recommendation Chatbot

Natural language interface for coupon discovery:

```python
from langchain_anthropic import ChatAnthropic
from langchain.prompts import ChatPromptTemplate
from langchain.schema.runnable import RunnablePassthrough

# Initialize LLM
llm = ChatAnthropic(model="claude-3-5-sonnet-20241022", temperature=0.7)

# Create recommendation prompt
template = """You are a helpful coupon recommendation assistant for Mezzofy.

User preferences: {user_preferences}
Available coupons: {available_coupons}

Based on the user's preferences and past behavior, recommend 3 coupons that would be most relevant.
Explain why each coupon matches their interests.

User query: {query}

Recommendations:"""

prompt = ChatPromptTemplate.from_template(template)

# Create recommendation chain
recommendation_chain = (
    {
        "user_preferences": RunnablePassthrough(),
        "available_coupons": get_available_coupons,
        "query": RunnablePassthrough()
    }
    | prompt
    | llm
)

# Generate recommendations
response = recommendation_chain.invoke({
    "user_preferences": user_profile,
    "query": "I'm looking for restaurant deals in downtown"
})
```

### 2. RAG-Powered Coupon Search

Semantic search over coupon catalog:

```python
from langchain_community.vectorstores import Qdrant
from langchain_openai import OpenAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from qdrant_client import QdrantClient

# Initialize vector store
client = QdrantClient(url="http://localhost:6333")
embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

# Process coupon documents
def index_coupons(coupons: List[Coupon]):
    """Index coupons into vector database"""
    
    # Create documents from coupons
    documents = []
    for coupon in coupons:
        doc_text = f"""
        Title: {coupon.title}
        Description: {coupon.description}
        Category: {coupon.category}
        Merchant: {coupon.merchant_name}
        Discount: {coupon.discount}%
        Tags: {', '.join(coupon.tags)}
        """
        documents.append(doc_text)
    
    # Split and embed
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50
    )
    splits = text_splitter.create_documents(documents)
    
    # Store in vector DB
    vectorstore = Qdrant.from_documents(
        documents=splits,
        embedding=embeddings,
        collection_name="coupons",
        client=client
    )
    return vectorstore

# Semantic search
def search_coupons(query: str, k: int = 5):
    """Search coupons using semantic similarity"""
    vectorstore = Qdrant(
        client=client,
        collection_name="coupons",
        embeddings=embeddings
    )
    
    results = vectorstore.similarity_search_with_score(query, k=k)
    return results
```

### 3. Multi-Agent Coupon Assistant

Agent with tool use for complex queries:

```python
from langchain.agents import create_openai_functions_agent, AgentExecutor
from langchain.tools import tool
from langchain_openai import ChatOpenAI

# Define tools
@tool
def search_coupons_by_category(category: str) -> list:
    """Search for coupons in a specific category"""
    # Query database
    coupons = coupon_service.get_by_category(category)
    return [{"id": c.id, "title": c.title, "discount": c.discount} for c in coupons]

@tool
def get_user_preferences(user_id: str) -> dict:
    """Get user's coupon preferences and history"""
    user = user_service.get_user(user_id)
    return {
        "favorite_categories": user.favorite_categories,
        "past_redemptions": user.redemption_history,
        "preferred_merchants": user.preferred_merchants
    }

@tool
def check_coupon_availability(coupon_id: str) -> dict:
    """Check if a coupon is currently available and valid"""
    coupon = coupon_service.get_coupon(coupon_id)
    return {
        "available": coupon.status == "active",
        "expires_at": str(coupon.expires_at),
        "remaining_uses": coupon.max_uses - coupon.current_uses
    }

# Create agent
llm = ChatOpenAI(model="gpt-4-turbo-preview", temperature=0)
tools = [search_coupons_by_category, get_user_preferences, check_coupon_availability]

agent_prompt = """You are a helpful coupon assistant for Mezzofy.
You help users find the best coupons based on their preferences and needs.

Use the available tools to:
1. Search for relevant coupons
2. Check user preferences
3. Verify coupon availability

Always provide personalized recommendations with explanations."""

agent = create_openai_functions_agent(llm, tools, agent_prompt)
agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

# Run agent
result = agent_executor.invoke({
    "input": "Find me some restaurant coupons, I prefer Italian food"
})
```

## RAG Architecture Pattern

```python
from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate

class CouponRAGSystem:
    def __init__(self):
        self.vectorstore = self._init_vectorstore()
        self.llm = ChatAnthropic(model="claude-3-5-sonnet-20241022")
        self.chain = self._create_chain()
    
    def _init_vectorstore(self):
        """Initialize vector database with coupon data"""
        client = QdrantClient(url=QDRANT_URL)
        embeddings = OpenAIEmbeddings()
        return Qdrant(
            client=client,
            collection_name="coupons",
            embeddings=embeddings
        )
    
    def _create_chain(self):
        """Create RAG chain with custom prompt"""
        template = """Use the following coupon information to answer the question.
        If you don't know the answer, say so - don't make up coupons.
        
        Context: {context}
        
        Question: {question}
        
        Answer with specific coupon recommendations and explain why they match:"""
        
        prompt = PromptTemplate(
            template=template,
            input_variables=["context", "question"]
        )
        
        return RetrievalQA.from_chain_type(
            llm=self.llm,
            chain_type="stuff",
            retriever=self.vectorstore.as_retriever(search_kwargs={"k": 5}),
            chain_type_kwargs={"prompt": prompt},
            return_source_documents=True
        )
    
    def query(self, question: str) -> dict:
        """Query the RAG system"""
        result = self.chain.invoke({"query": question})
        return {
            "answer": result["result"],
            "sources": [doc.metadata for doc in result["source_documents"]]
        }

# Usage
rag = CouponRAGSystem()
response = rag.query("What are the best electronics deals this week?")
```

## Prompt Engineering Best Practices

### 1. Clear Instructions

```python
# Good: Specific and structured
prompt = """Analyze the following coupon and extract:
1. Primary category
2. Target audience
3. Urgency level (high/medium/low)
4. Recommended user segments

Coupon: {coupon_data}

Output format:
Category: [category]
Audience: [audience]
Urgency: [level]
Segments: [list]"""

# Bad: Vague
prompt = "Tell me about this coupon: {coupon_data}"
```

### 2. Few-Shot Examples

```python
examples = """
Example 1:
Input: "50% off Italian restaurant, expires tomorrow"
Output: Category: Food & Dining | Urgency: High | Segments: Food lovers, Italian cuisine fans

Example 2:
Input: "20% off electronics, valid for 30 days"
Output: Category: Electronics | Urgency: Low | Segments: Tech enthusiasts, gadget shoppers

Now analyze:
Input: {new_coupon}
Output:"""
```

### 3. Chain-of-Thought for Complex Tasks

```python
prompt = """Let's recommend coupons step by step:

Step 1: Analyze user preferences
- Review past redemptions
- Identify favorite categories
- Note spending patterns

Step 2: Match with available coupons
- Filter by user preferences
- Check expiration dates
- Verify availability

Step 3: Rank by relevance
- Score each match
- Consider recency
- Factor in user engagement

User data: {user_data}
Available coupons: {coupons}

Reasoning:"""
```

## Embeddings & Similarity Search

```python
from langchain_openai import OpenAIEmbeddings
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

class CouponEmbeddingSystem:
    def __init__(self):
        self.embeddings_model = OpenAIEmbeddings(
            model="text-embedding-3-small"
        )
    
    def create_coupon_embedding(self, coupon: Coupon) -> np.ndarray:
        """Generate embedding for coupon"""
        text = f"{coupon.title} {coupon.description} {coupon.category}"
        embedding = self.embeddings_model.embed_query(text)
        return np.array(embedding)
    
    def find_similar_coupons(
        self,
        query: str,
        coupon_embeddings: dict,
        top_k: int = 5
    ) -> list:
        """Find most similar coupons to query"""
        # Get query embedding
        query_embedding = self.embeddings_model.embed_query(query)
        query_embedding = np.array(query_embedding).reshape(1, -1)
        
        # Calculate similarities
        similarities = {}
        for coupon_id, embedding in coupon_embeddings.items():
            embedding = np.array(embedding).reshape(1, -1)
            similarity = cosine_similarity(query_embedding, embedding)[0][0]
            similarities[coupon_id] = similarity
        
        # Return top-k
        ranked = sorted(similarities.items(), key=lambda x: x[1], reverse=True)
        return ranked[:top_k]
```

## LangGraph for Complex Workflows

```python
from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated, Sequence
from langchain_core.messages import BaseMessage

class CouponAgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], "The messages"]
    user_id: str
    selected_coupons: list
    next_action: str

def search_node(state: CouponAgentState):
    """Search for relevant coupons"""
    query = state["messages"][-1].content
    coupons = search_coupons(query)
    state["selected_coupons"] = coupons
    return state

def filter_node(state: CouponAgentState):
    """Filter by user preferences"""
    user_prefs = get_user_preferences(state["user_id"])
    filtered = filter_by_preferences(state["selected_coupons"], user_prefs)
    state["selected_coupons"] = filtered
    return state

def rank_node(state: CouponAgentState):
    """Rank coupons by relevance"""
    ranked = rank_coupons(state["selected_coupons"])
    state["selected_coupons"] = ranked[:5]
    return state

# Build graph
workflow = StateGraph(CouponAgentState)
workflow.add_node("search", search_node)
workflow.add_node("filter", filter_node)
workflow.add_node("rank", rank_node)

workflow.set_entry_point("search")
workflow.add_edge("search", "filter")
workflow.add_edge("filter", "rank")
workflow.add_edge("rank", END)

app = workflow.compile()
```

## Production Considerations

### 1. Rate Limiting

```python
from redis import Redis
from datetime import datetime, timedelta

class LLMRateLimiter:
    def __init__(self):
        self.redis = Redis(host='localhost', port=6379)
    
    def check_limit(self, user_id: str, limit: int = 10) -> bool:
        """Check if user is within rate limit (10 requests/minute)"""
        key = f"llm_rate:{user_id}"
        current = self.redis.get(key)
        
        if current is None:
            self.redis.setex(key, 60, 1)
            return True
        
        if int(current) >= limit:
            return False
        
        self.redis.incr(key)
        return True
```

### 2. Cost Tracking

```python
import tiktoken

def estimate_cost(prompt: str, model: str = "gpt-4") -> float:
    """Estimate API call cost"""
    encoding = tiktoken.encoding_for_model(model)
    tokens = len(encoding.encode(prompt))
    
    # GPT-4 pricing (as of 2024)
    cost_per_1k = {
        "gpt-4": 0.03,  # Input
        "gpt-3.5-turbo": 0.0015
    }
    
    return (tokens / 1000) * cost_per_1k.get(model, 0.03)
```

### 3. Caching

```python
from functools import lru_cache
import hashlib

@lru_cache(maxsize=1000)
def get_cached_embedding(text: str) -> list:
    """Cache embeddings to reduce API calls"""
    return embeddings_model.embed_query(text)

def cache_llm_response(query: str, response: str):
    """Cache LLM responses in Redis"""
    key = f"llm_cache:{hashlib.md5(query.encode()).hexdigest()}"
    redis_client.setex(key, 3600, response)  # 1 hour TTL
```

## Quality Checklist

- [ ] Prompt engineering with clear instructions
- [ ] Few-shot examples for consistency
- [ ] Error handling for API failures
- [ ] Rate limiting implemented
- [ ] Cost tracking and budgets
- [ ] Response caching for common queries
- [ ] Evaluation metrics (accuracy, relevance)
- [ ] User feedback collection
- [ ] Monitoring and logging
- [ ] A/B testing for prompt variations
