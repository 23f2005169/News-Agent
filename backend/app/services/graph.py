"""Neo4j graph helpers."""
from __future__ import annotations

import os
from functools import lru_cache
from typing import Optional

from neo4j import GraphDatabase
from neo4j._sync.driver import Driver


@lru_cache(maxsize=1)
def get_graph_driver() -> Optional[Driver]:
    uri = os.getenv("NEO4J_URI")
    username = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD")
    if not uri or not password:
        return None
    return GraphDatabase.driver(uri, auth=(username, password))
