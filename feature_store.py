import os
from datetime import datetime
from typing import Dict, List, Optional

import chromadb
from sentence_transformers import SentenceTransformer


class FeatureStore:
    """
    Feature store for Better Auth documentation using ChromaDB.
    Provides semantic search capabilities over embedded documentation.
    """

    COLLECTION_NAME = "better_auth_docs"

    def __init__(self, persist_directory: Optional[str] = None):
        """
        Initialize the feature store with ChromaDB.

        Args:
            persist_directory (Optional[str]): Directory path for ChromaDB persistence.
        """
        if persist_directory:
            os.makedirs(persist_directory, exist_ok=True)
            self.client = chromadb.PersistentClient(path=persist_directory)
        else:
            self.client = chromadb.Client()

        self.collection = self.client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            metadata={"description": "Better Auth documentation embeddings"},
        )

        self.embedding_model = SentenceTransformer("all-mpnet-base-v2")

    def search(
        self,
        query: str,
        n_results: int = 5,
        route: Optional[str] = None,
    ) -> str:
        """
        Perform semantic search across documents. Can search all docs or filter by route.

        Args:
            query (str): User's search query.
            n_results (int): Number of results to return (default: 5).
            route (Optional[str]): Filter by specific doc route (e.g., "/llms.txt/docs/auth/google.md").

        Returns:
            str: Relevant context as a formatted string.
        """
        query_embedding = self.embedding_model.encode(query).tolist()

        where_clause = {}
        if route:
            where_clause["route"] = route

        query_kwargs = {"query_embeddings": [query_embedding], "n_results": n_results}
        if where_clause:
            query_kwargs["where"] = where_clause

        results = self.collection.query(**query_kwargs)

        if not results["ids"] or not results["ids"][0]:
            return f"No relevant context found for query '{query}'."

        formatted_docs = []

        for i, _ in enumerate(results["ids"][0]):
            route = results["metadatas"][0][i].get("route", "unknown")
            formatted_docs.append(f"[{route}]\n\n{results['documents'][0][i]}")

        return "\n\n---\n\n".join(formatted_docs)

    def upsert_docs(self, docs: List[Dict[str, str]]) -> int:
        """
        Upsert documents in ChromaDB. Stores one embedding per document.

        Args:
            docs (List[Dict[str, str]]): List of document dictionaries:
                - route: Document route
                - description: Document description
                - content: Document content

        Returns:
            int: Number of documents added/updated
        """
        all_docs = []
        all_embeddings = []
        all_metadatas = []
        all_ids = []

        timestamp = datetime.now().isoformat()

        for doc in docs:
            route = doc["route"]
            description = doc.get("description", "")
            content = doc.get("content", "")

            # Create document representation for embedding: description + content
            doc_parts = []
            if description:
                doc_parts.append(description)
            if content:
                doc_parts.append(content)

            doc_text = "\n\n".join(doc_parts)

            embedding = self.embedding_model.encode(doc_text).tolist()

            metadata = {
                "route": route,
                "description": description,
                "timestamp": timestamp,
            }

            all_ids.append(route)  # Use route as ID
            all_embeddings.append(embedding)
            all_metadatas.append(metadata)
            all_docs.append(content)

        # Delete existing documents to avoid duplicates
        routes = list(set(doc["route"] for doc in docs))
        for route in routes:
            try:
                self.collection.delete(where={"route": route})
            except Exception:
                pass

        if all_docs:
            self.collection.add(
                ids=all_ids,
                embeddings=all_embeddings,
                documents=all_docs,
                metadatas=all_metadatas,
            )

        return len(all_docs)
