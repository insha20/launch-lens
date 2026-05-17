"""
rag_pipeline.py — RAG (Retrieval Augmented Generation) pipeline

WHAT IS RAG?
Instead of asking an LLM to answer from its training data (which may be
outdated, hallucinated, or generic), RAG:
  1. Takes your source documents (community posts in our case)
  2. Splits them into chunks
  3. Converts each chunk into a vector embedding (a list of ~1500 numbers
     that represents its semantic meaning)
  4. Stores those vectors in a vector database (Chroma)
  5. At query time: converts the query into a vector, finds the most
     semantically similar chunks in the database, passes THOSE chunks
     to the LLM as context

Result: the LLM answers from real evidence, not from memory.
It can cite specific posts. It can say "I found 12 posts about this."
That's the difference between a chatbot and a research tool.

WHY THIS MATTERS FOR YOUR RESUME:
RAG is the most commonly asked-about AI technique in engineering interviews.
"How did you prevent hallucination?" → "I used RAG — the LLM only answers
from retrieved community posts, and must cite which post supports each claim."

KEY CONCEPTS IN THIS FILE:

1. EMBEDDINGS
   An embedding is a vector (list of numbers) that represents meaning.
   "I can't get clients to pay me" and "invoice not paid by customer"
   have very different words but similar embeddings — they're close in
   vector space. This is what makes semantic search work.
   We use Google's embedding model (free, no extra key needed).

2. CHUNKING
   Documents are split into chunks before embedding. If you embed a
   full 500-word Reddit post as one vector, you lose granularity —
   the specific sentence where the pain is expressed gets diluted.
   Smaller chunks = more precise retrieval.

3. CHROMA
   An open-source vector database that runs in-memory (no server needed).
   You store vectors in it, then query with a new vector and get back
   the N most similar stored chunks. Think of it as a search engine
   that understands meaning instead of keywords.

4. SESSION ISOLATION
   Each product analysis gets its own Chroma collection (keyed by
   session_id). This prevents posts from one product polluting the
   vector store of another.
"""

import os
import uuid
import hashlib
from typing import Optional
from dotenv import load_dotenv

from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

load_dotenv()

import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from schemas import CommunityEvidence, SynthesisResult


# ─────────────────────────────────────────────────────────────
# Embedding model
# ─────────────────────────────────────────────────────────────

def get_embedding_model():
    """
    Returns Google's text embedding model.

    WHY GOOGLE'S EMBEDDINGS:
    - Free with your existing GEMINI_API_KEY — no extra cost
    - models/text-embedding-004 is Google's latest, high quality
    - 768-dimensional vectors (good balance of quality vs speed)

    ALTERNATIVE: OpenAI text-embedding-3-small
    - Better quality, but costs ~$0.02 per million tokens
    - Worth switching to for production
    - Just change this function and nothing else needs to change
    """
    return GoogleGenerativeAIEmbeddings(
        model="models/gemini-embedding-001",
        google_api_key=os.getenv("GEMINI_API_KEY"),
    )


# ─────────────────────────────────────────────────────────────
# Text splitter
# ─────────────────────────────────────────────────────────────

def get_text_splitter():
    """
    RecursiveCharacterTextSplitter splits text by trying these
    separators in order: paragraphs → sentences → words → characters.
    It picks the largest split that keeps chunks under chunk_size.

    chunk_size=400: roughly 80-100 words per chunk.
      Too large: embeddings are diluted, retrieval is imprecise.
      Too small: you lose context, chunks become meaningless fragments.
      400 chars is the sweet spot for short community posts.

    chunk_overlap=80: each chunk shares 80 chars with the next.
      This prevents cutting a sentence in half and losing the meaning
      that spans a chunk boundary.
    """
    return RecursiveCharacterTextSplitter(
        chunk_size=400,
        chunk_overlap=80,
        length_function=len,
        separators=["\n\n", "\n", ". ", " ", ""],
    )


# ─────────────────────────────────────────────────────────────
# In-memory store of Chroma collections per session
# ─────────────────────────────────────────────────────────────

# Dict mapping session_id → Chroma vector store
# In-memory: resets when the server restarts. Sufficient for MVP.
# Day 8+: persist to disk with Chroma's persist_directory option.
_vector_stores: dict[str, Chroma] = {}


# ─────────────────────────────────────────────────────────────
# Core functions
# ─────────────────────────────────────────────────────────────

def community_evidence_to_documents(
    evidence_list: list[CommunityEvidence],
) -> list[Document]:
    """
    Converts CommunityEvidence objects into LangChain Documents
    ready for embedding.

    Each Document has:
    - page_content: the text that gets embedded
    - metadata: source info preserved for citations

    WHY METADATA MATTERS:
    When the RAG synthesizer retrieves a chunk, it can cite the source:
    "According to a post in r/freelance with 469 upvotes..."
    Without metadata, you just have floating text with no provenance.
    """
    splitter = get_text_splitter()
    documents = []

    for evidence in evidence_list:
        # Embed the strongest signal text as one document
        if evidence.strongest_signal and evidence.strongest_signal != "No evidence found":
            signal_doc = Document(
                page_content=evidence.strongest_signal,
                metadata={
                    "source": "agent_summary",
                    "hypothesis_persona": evidence.hypothesis_persona[:100],
                    "total_posts": evidence.total_posts_found,
                    "type": "research_summary",
                }
            )
            # Split if the signal text is long
            chunks = splitter.split_documents([signal_doc])
            documents.extend(chunks)

        # Embed each community post's content
        for post in evidence.posts:
            if not post.url:
                continue

            # Build text representation of the post
            post_text_parts = []
            if post.title:
                post_text_parts.append(post.title)

            post_text = " | ".join(filter(None, post_text_parts))
            if not post_text.strip():
                continue

            post_doc = Document(
                page_content=post_text,
                metadata={
                    "source": post.source,
                    "url": post.url,
                    "score": post.score,
                    "hypothesis_persona": evidence.hypothesis_persona[:100],
                    "type": "community_post",
                }
            )
            documents.append(post_doc)

    return documents


def embed_and_store(
    evidence_list: list[CommunityEvidence],
    session_id: str,
) -> Chroma:
    """
    Embeds community evidence and stores in a Chroma vector store.

    Returns the Chroma instance for immediate querying.
    Also caches it in _vector_stores for reuse within the same session.

    HOW CHROMA WORKS:
    Chroma.from_documents() takes your Document objects, calls the
    embedding model for each chunk, and stores (text, vector, metadata)
    tuples in memory. Later, similarity_search() takes a query string,
    embeds it, and finds the stored vectors with the smallest cosine
    distance to the query vector.

    Cosine distance measures the angle between two vectors.
    Angle ≈ 0 → very similar meaning.
    Angle ≈ 90° → completely different meaning.
    """
    embedding_model = get_embedding_model()
    documents = community_evidence_to_documents(evidence_list)

    if not documents:
        # Return an empty store rather than crashing
        print("[RAG] No documents to embed — returning empty store")
        # Create minimal store with a placeholder
        placeholder = Document(
            page_content="No community evidence found for this product.",
            metadata={"source": "placeholder", "type": "empty"}
        )
        store = Chroma.from_documents(
            documents=[placeholder],
            embedding=embedding_model,
            collection_name=f"launchlens_{session_id[:8]}",
        )
    else:
        print(f"[RAG] Embedding {len(documents)} document chunks...")
        store = Chroma.from_documents(
            documents=documents,
            embedding=embedding_model,
            collection_name=f"launchlens_{session_id[:8]}",
        )
        print(f"[RAG] ✓ Stored {len(documents)} chunks in Chroma")

    _vector_stores[session_id] = store
    return store


def get_store(session_id: str) -> Optional[Chroma]:
    """Retrieve a cached vector store by session ID."""
    return _vector_stores.get(session_id)


def semantic_search(
    store: Chroma,
    query: str,
    k: int = 4,
) -> list[Document]:
    """
    Semantic similarity search against the vector store.

    k=4: return the 4 most relevant chunks.
    More chunks = more context for the LLM but more tokens = higher cost.
    4 is a good default for community post retrieval.

    The search converts your query to a vector, then finds the k stored
    vectors with smallest cosine distance. Returns those chunks as
    Document objects with their original metadata.
    """
    results = store.similarity_search(query, k=k)
    return results


def format_retrieved_docs(docs: list[Document]) -> str:
    """
    Formats retrieved documents into readable text for the LLM.
    Includes source citations so the LLM can attribute claims.
    """
    if not docs:
        return "No relevant community posts found."

    lines = ["Retrieved community evidence:\n"]
    for i, doc in enumerate(docs, 1):
        meta = doc.metadata
        source = meta.get("source", "unknown")
        url = meta.get("url", "")
        score = meta.get("score", 0)

        citation = f"[Source {i}: {source}"
        if score:
            citation += f" | {score} upvotes"
        if url:
            citation += f" | {url}"
        citation += "]"

        lines.append(f"{citation}\n{doc.page_content}\n")

    return "\n".join(lines)