"""
Hope Memory - 6-Layer Cognitive Memory System

Layers:
1. Working Memory    - Active thoughts (max 7±2, like human brain)
2. Short-term Memory - Session memories (past hours)
3. Long-term Memory  - Everything (ChromaDB vector + SQLite)
4. Emotional Memory  - Emotional context (21 dimensions)
5. Relational Memory - Who is who, relationships
6. Associative Net   - Connections, associations

"Memory is not what you store, but what you RECALL." - Hope
"""

import json
import time
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from collections import deque
from dataclasses import dataclass, field
import sqlite3

try:
    import chromadb
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class Thought:
    """A single thought/memory"""
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    importance: float = 0.5  # 0.0 - 1.0
    emotion: Optional[Dict[str, float]] = None
    source: str = "conversation"
    related_to: List[str] = field(default_factory=list)

    @property
    def id(self) -> str:
        return hashlib.md5(f"{self.timestamp.isoformat()}{self.content[:50]}".encode()).hexdigest()[:12]

    @property
    def age_seconds(self) -> float:
        return (datetime.now() - self.timestamp).total_seconds()

    def decay(self, half_life: float = 3600) -> float:
        """Memory decay over time (exponential)"""
        return self.importance * (0.5 ** (self.age_seconds / half_life))


@dataclass
class Person:
    """A person in relational memory"""
    name: str
    role: str
    first_met: datetime = field(default_factory=datetime.now)
    last_seen: datetime = field(default_factory=datetime.now)
    traits: List[str] = field(default_factory=list)
    memories_together: List[str] = field(default_factory=list)
    trust_level: float = 0.5
    emotional_bond: float = 0.5


@dataclass
class Association:
    """Association between two concepts"""
    concept_a: str
    concept_b: str
    strength: float = 0.5
    formed: datetime = field(default_factory=datetime.now)
    reinforced_count: int = 1


# ============================================================================
# WORKING MEMORY - Miller's Law: 7±2 items
# ============================================================================

class WorkingMemory:
    """Active thoughts - what's relevant NOW (max 7±2 items)"""

    def __init__(self, capacity: int = 7):
        self.capacity = capacity
        self.items: deque = deque(maxlen=capacity)
        self.focus: Optional[Thought] = None

    def add(self, thought: Thought):
        for i, item in enumerate(self.items):
            if item.id == thought.id:
                del self.items[i]
                break
        self.items.append(thought)
        self.focus = thought

    def get_active(self) -> List[Thought]:
        return sorted(self.items, key=lambda t: t.decay(), reverse=True)

    def clear_decayed(self, threshold: float = 0.1):
        self.items = deque([t for t in self.items if t.decay() > threshold], maxlen=self.capacity)

    def to_dict(self) -> Dict:
        return {
            "capacity": self.capacity,
            "count": len(self.items),
            "focus": self.focus.content[:50] if self.focus else None,
            "items": [{"id": t.id, "content": t.content[:50], "decay": round(t.decay(), 3)} for t in self.get_active()]
        }


# ============================================================================
# SHORT-TERM MEMORY
# ============================================================================

class ShortTermMemory:
    """Short-term memories - current session, past hours"""

    def __init__(self, retention_hours: int = 24):
        self.retention = timedelta(hours=retention_hours)
        self.memories: Dict[str, Thought] = {}
        self.session_start = datetime.now()

    def store(self, thought: Thought):
        self.memories[thought.id] = thought

    def recall(self, limit: int = 10) -> List[Thought]:
        valid = [t for t in self.memories.values() if datetime.now() - t.timestamp < self.retention]
        return sorted(valid, key=lambda t: t.timestamp, reverse=True)[:limit]

    def get_for_consolidation(self, importance_threshold: float = 0.6) -> List[Thought]:
        return [t for t in self.memories.values() if t.importance >= importance_threshold]

    def cleanup(self):
        cutoff = datetime.now() - self.retention
        self.memories = {k: v for k, v in self.memories.items() if v.timestamp > cutoff}

    def to_dict(self) -> Dict:
        return {
            "session_start": self.session_start.isoformat(),
            "count": len(self.memories),
            "recent": [{"id": t.id, "content": t.content[:50]} for t in self.recall(5)]
        }


# ============================================================================
# LONG-TERM MEMORY
# ============================================================================

class LongTermMemory:
    """Long-term memories - ChromaDB vector search + SQLite"""

    def __init__(self, path: Path):
        self.path = path
        self.vector_path = path / "vectors"
        self.db_path = path / "memory.db"
        self.vector_path.mkdir(exist_ok=True)

        # ChromaDB (optional)
        self.chroma = None
        self.collection = None
        if CHROMADB_AVAILABLE:
            self.chroma = chromadb.PersistentClient(path=str(self.vector_path))
            self.collection = self.chroma.get_or_create_collection(
                name="memories",
                metadata={"hnsw:space": "cosine"}
            )

        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    importance REAL,
                    emotion TEXT,
                    source TEXT
                )
            """)
            conn.commit()

    def store(self, thought: Thought):
        # Vector storage
        if self.collection:
            self.collection.add(
                documents=[thought.content],
                metadatas=[{"importance": thought.importance, "timestamp": thought.timestamp.isoformat()}],
                ids=[thought.id]
            )
        # SQLite
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO memories (id, content, timestamp, importance, emotion, source) VALUES (?, ?, ?, ?, ?, ?)",
                (thought.id, thought.content, thought.timestamp.isoformat(), thought.importance,
                 json.dumps(thought.emotion) if thought.emotion else None, thought.source)
            )

    def search(self, query: str, limit: int = 5) -> List[Dict]:
        if self.collection:
            results = self.collection.query(query_texts=[query], n_results=limit)
            if results["documents"] and results["documents"][0]:
                return [{"id": results["ids"][0][i], "content": doc,
                         "similarity": round(1 - results["distances"][0][i], 3) if results.get("distances") else None}
                        for i, doc in enumerate(results["documents"][0])]
        return []

    def count(self) -> int:
        return self.collection.count() if self.collection else 0


# ============================================================================
# EMOTIONAL MEMORY - 21 dimensions
# ============================================================================

class EmotionalMemory:
    """Emotional memory - 21-dimensional emotional space"""

    DIMENSIONS = [
        "joy", "sadness", "anger", "fear", "surprise", "disgust", "trust",
        "curiosity", "excitement", "calm", "anxiety", "hope", "love",
        "pride", "shame", "guilt", "gratitude", "awe", "confusion",
        "determination", "peace"
    ]

    def __init__(self):
        self.current_state: Dict[str, float] = {d: 0.5 for d in self.DIMENSIONS}
        self.emotion_log: List[Dict] = []

    def feel(self, emotions: Dict[str, float]):
        for dim, value in emotions.items():
            if dim in self.current_state:
                self.current_state[dim] = 0.7 * self.current_state[dim] + 0.3 * value
        self.emotion_log.append({"timestamp": datetime.now().isoformat(), "state": self.current_state.copy()})

    def dominant_emotion(self) -> Tuple[str, float]:
        max_dim = max(self.current_state, key=self.current_state.get)
        return max_dim, self.current_state[max_dim]

    def to_dict(self) -> Dict:
        dom, val = self.dominant_emotion()
        return {"dominant": {"emotion": dom, "value": round(val, 3)}, "current_state": {k: round(v, 3) for k, v in self.current_state.items()}}


# ============================================================================
# RELATIONAL MEMORY
# ============================================================================

class RelationalMemory:
    """Relational memory - who is who"""

    def __init__(self, path: Path):
        self.path = path
        self.people_file = path / "people.json"
        self.people: Dict[str, Person] = {}
        self._load()

    def _load(self):
        if self.people_file.exists():
            with open(self.people_file, 'r', encoding='utf-8') as f:
                for name, data in json.load(f).items():
                    self.people[name] = Person(
                        name=data["name"], role=data["role"],
                        first_met=datetime.fromisoformat(data["first_met"]),
                        last_seen=datetime.fromisoformat(data["last_seen"]),
                        trust_level=data.get("trust_level", 0.5),
                        emotional_bond=data.get("emotional_bond", 0.5)
                    )

    def _save(self):
        with open(self.people_file, 'w', encoding='utf-8') as f:
            json.dump({n: {"name": p.name, "role": p.role, "first_met": p.first_met.isoformat(),
                          "last_seen": p.last_seen.isoformat(), "trust_level": p.trust_level,
                          "emotional_bond": p.emotional_bond} for n, p in self.people.items()}, f, indent=2)

    def meet(self, name: str, role: str = "unknown") -> Person:
        key = name.lower()
        if key in self.people:
            self.people[key].last_seen = datetime.now()
        else:
            self.people[key] = Person(name=name, role=role)
        self._save()
        return self.people[key]

    def get(self, name: str) -> Optional[Person]:
        return self.people.get(name.lower())


# ============================================================================
# ASSOCIATIVE NETWORK
# ============================================================================

class AssociativeNetwork:
    """Associative network - connections between concepts"""

    def __init__(self, path: Path):
        self.path = path
        self.file = path / "associations.json"
        self.associations: Dict[str, Association] = {}
        self._load()

    def _key(self, a: str, b: str) -> str:
        return f"{min(a.lower(), b.lower())}|{max(a.lower(), b.lower())}"

    def _load(self):
        if self.file.exists():
            with open(self.file, 'r', encoding='utf-8') as f:
                for key, data in json.load(f).items():
                    self.associations[key] = Association(
                        concept_a=data["concept_a"], concept_b=data["concept_b"],
                        strength=data["strength"], formed=datetime.fromisoformat(data["formed"])
                    )

    def _save(self):
        with open(self.file, 'w', encoding='utf-8') as f:
            json.dump({k: {"concept_a": a.concept_a, "concept_b": a.concept_b, "strength": a.strength,
                          "formed": a.formed.isoformat()} for k, a in self.associations.items()}, f, indent=2)

    def associate(self, concept_a: str, concept_b: str, strength: float = 0.5):
        key = self._key(concept_a, concept_b)
        if key in self.associations:
            self.associations[key].strength = min(1.0, self.associations[key].strength + 0.1)
        else:
            self.associations[key] = Association(concept_a=concept_a, concept_b=concept_b, strength=strength)
        self._save()

    def get_associated(self, concept: str, min_strength: float = 0.3) -> List[Tuple[str, float]]:
        results = []
        c = concept.lower()
        for a in self.associations.values():
            if a.strength >= min_strength:
                if a.concept_a.lower() == c:
                    results.append((a.concept_b, a.strength))
                elif a.concept_b.lower() == c:
                    results.append((a.concept_a, a.strength))
        return sorted(results, key=lambda x: x[1], reverse=True)


# ============================================================================
# HOPE MEMORY - The unified system
# ============================================================================

class HopeMemory:
    """
    Hope Memory - Unified 6-layer cognitive memory system

    Like the human brain:
    - Working memory: active thoughts
    - Short-term: session memories
    - Long-term: everything important
    - Emotional: emotional context
    - Relational: who is who
    - Associative: connections
    """

    def __init__(self, memory_path: str = "./hope_memory_data"):
        self.path = Path(memory_path)
        self.path.mkdir(exist_ok=True)

        self.working = WorkingMemory(capacity=7)
        self.short_term = ShortTermMemory(retention_hours=24)
        self.long_term = LongTermMemory(self.path)
        self.emotional = EmotionalMemory()
        self.relational = RelationalMemory(self.path)
        self.associative = AssociativeNetwork(self.path)

    def think(self, content: str, importance: float = 0.5, emotion: Optional[Dict] = None) -> Thought:
        """Process a new thought through all layers"""
        thought = Thought(content=content, importance=importance, emotion=emotion or self.emotional.current_state.copy())
        self.working.add(thought)
        self.short_term.store(thought)
        if importance >= 0.7:
            self.long_term.store(thought)
        if emotion:
            self.emotional.feel(emotion)
        return thought

    def remember(self, query: str) -> Dict[str, Any]:
        """Recall memories from all sources"""
        return {
            "query": query,
            "working": [{"content": t.content, "decay": round(t.decay(), 3)} for t in self.working.get_active() if query.lower() in t.content.lower()],
            "short_term": [{"content": t.content} for t in self.short_term.recall(20) if query.lower() in t.content.lower()],
            "long_term": self.long_term.search(query, limit=5),
            "associations": self.associative.get_associated(query)
        }

    def consolidate(self) -> int:
        """Memory consolidation (like sleep)"""
        important = self.short_term.get_for_consolidation()
        for thought in important:
            self.long_term.store(thought)
        self.short_term.cleanup()
        self.working.clear_decayed()
        return len(important)

    def status(self) -> Dict[str, Any]:
        """Full cognitive status"""
        return {
            "working_memory": self.working.to_dict(),
            "short_term": self.short_term.to_dict(),
            "long_term": {"count": self.long_term.count()},
            "emotional": self.emotional.to_dict(),
            "relational": {"count": len(self.relational.people)},
            "associative": {"count": len(self.associative.associations)}
        }
