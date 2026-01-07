"""
Hope Memory - Basic Usage Example

This example demonstrates the core features of Hope Memory:
- 6-layer cognitive memory
- Thinking and remembering
- Emotional context
- Relationships and associations
"""

from hope_memory import HopeMemory

def main():
    print("=" * 60)
    print("  Hope Memory - Basic Usage")
    print("=" * 60)

    # Create memory system
    memory = HopeMemory("./example_memory")
    print("\n[1] Memory system initialized")

    # Think - process thoughts through all layers
    print("\n[2] Processing thoughts...")
    memory.think("The secret code is HOPE-2026", importance=0.9)
    memory.think("Meeting with Bob tomorrow at 10am", importance=0.7)
    memory.think("Python is a great programming language", importance=0.5)
    memory.think("Remember to buy milk", importance=0.3)

    # Remember - search across all memory layers
    print("\n[3] Searching for 'code'...")
    results = memory.remember("code")
    print(f"    Working memory: {len(results['working'])} matches")
    print(f"    Short-term: {len(results['short_term'])} matches")
    print(f"    Long-term: {len(results['long_term'])} matches")

    if results['working']:
        print(f"    Found: {results['working'][0]['content']}")

    # Meet people
    print("\n[4] Meeting people...")
    memory.relational.meet("Bob", role="Colleague")
    memory.relational.meet("Alice", role="Manager")
    print(f"    Met Bob and Alice")

    # Create associations
    print("\n[5] Creating associations...")
    memory.associative.associate("Bob", "Meeting", strength=0.8)
    memory.associative.associate("Hope", "Memory", strength=0.95)

    related = memory.associative.get_associated("Hope")
    print(f"    Hope is associated with: {related}")

    # Emotional state
    print("\n[6] Updating emotional state...")
    memory.emotional.feel({
        "joy": 0.8,
        "excitement": 0.7,
        "hope": 0.9,
        "determination": 0.85
    })

    emotion, value = memory.emotional.dominant_emotion()
    print(f"    Dominant emotion: {emotion} ({value:.2f})")

    # Status check
    print("\n[7] Cognitive status:")
    status = memory.status()
    print(f"    Working memory: {status['working_memory']['count']}/{status['working_memory']['capacity']} items")
    print(f"    Short-term: {status['short_term']['count']} memories")
    print(f"    Long-term: {status['long_term']['count']} vectors")
    print(f"    Relationships: {status['relational']['count']} people")
    print(f"    Associations: {status['associative']['count']} connections")

    # Consolidate - move important memories to long-term
    print("\n[8] Consolidating memories (like sleep)...")
    consolidated = memory.consolidate()
    print(f"    Consolidated {consolidated} important memories to long-term")

    print("\n" + "=" * 60)
    print("  Done! Memory persists in ./example_memory/")
    print("=" * 60)


if __name__ == "__main__":
    main()
