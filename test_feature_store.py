from os import getenv

from feature_store import FeatureStore

GREEN = "\033[92m"
RESET = "\033[0m"


def test_feature_store():
    persist_directory = getenv("CHROMA_DB_PATH", "./chroma_db")
    print(f"Loading feature store from: {persist_directory}")
    feature_store = FeatureStore(persist_directory=persist_directory)

    test_queries = [
        "OAuth setup",
        "Google auth setup",
        "password reset",
    ]

    for i, query in enumerate(test_queries, 1):
        print(f"\n{GREEN}[Test {i}] Query: '{query}'{RESET}")
        results = feature_store.search(query, n_results=1)
        print(results[:500] + "..." if len(results) > 500 else results)


if __name__ == "__main__":
    test_feature_store()
