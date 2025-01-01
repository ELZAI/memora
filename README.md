![Memora](https://drive.google.com/uc?export=view&id=1u1nyA8OQBCYtAIbYtbRCtmF7Z-YJZ1AZ)

**[📚 Checkout Documentation](https://elzai.github.io/memora/)**

When we interact with people 🗣️👂, we naturally remember details from past interactions 💭, feelings 😜😢, and shared experiences 🤝. That's what makes us human. **We're bringing this same ability to AI, helping it recall just like us.**

## Key Features

- **Temporal Memory Recall**: Enables AI to remember timestamped memories from past interactions.
- **Multi-Tenancy**: Accommodates multiple organizations, agents, and users.
- **Flexible Name Handling**: Uses placeholders for easy updates to user and agent names.
- **Scalability**: Designed to handle millions of users, interactions, and memories.
- **Developer-Friendly**: Modular architecture for easy customization and feature integration.

## Quick Start
Before using Memora, you'll need to set up the following:

1. **Neo4j Database**  
     - Option A: [Install Neo4j locally](https://neo4j.com/docs/operations-manual/current/installation/)  
     - Option B: Use [Neo4j AuraDB](https://neo4j.com/cloud/platform/aura-graph-database/) (managed cloud solution)  

2. **Qdrant Vector Database**  
     - Option A: [Install Qdrant locally](https://qdrant.tech/documentation/quick-start/)  
     - Option B: Use [Qdrant Cloud](https://qdrant.tech/documentation/cloud/) (managed solution)  

3. **LLM Provider API Key**  
   Choose one of the following providers and obtain an API key:  
     - [OpenAI](https://platform.openai.com/)  
     - [Azure OpenAI](https://azure.microsoft.com/en-us/products/cognitive-services/openai-service)  
     - [Together AI](https://www.together.ai/)  
     - [Groq](https://groq.com/)


## **Installation**

Install Memora using pip:

```bash
pip install memora-core
```

## **Basic Setup**

Here's how to initialize Memora with the databases and an LLM provider:

```python
from memora import Memora
from qdrant_client import AsyncQdrantClient
from memora.vector_db import QdrantDB
from memora.graph_db import Neo4jGraphInterface
from memora.llm_backends import GroqBackendLLM

# Initialize databases
vector_db = QdrantDB(async_client=AsyncQdrantClient(url="QDRANT_URL", api_key="QDRANT_API_KEY"))

graph_db = Neo4jGraphInterface(uri="Neo4jURI", username="Username", password="Password", database="DBName")

# Only call setup on the very first run - (creates necessary indexes, contraints, etc.)
await vector_db.setup()
await graph_db.setup()


# Initialize Memora with Groq as the LLM provider
memora = Memora(
    vector_db=vector_db,
    graph_db=graph_db,
    # Fast model for memory search queries / filtering.
    memory_search_model=GroqBackendLLM(api_key="GROQ_API_KEY", model="llama-3.1-8b-instant"),
    # Powerful model for memory extraction
    extraction_model=GroqBackendLLM(api_key="GROQ_API_KEY", model="llama-3.3-70b-specdec", max_tokens=8000)
)

```

### **Creating An Organization, User, and Agent**

```python
# Create an organization
org = await memora.graph.create_organization("My Organization")
org_id = org['org_id'] # Short UUID e.g 'gmDr4sUiWMCqbGAiV8jjbU'

# Create a user in the organization
user = await memora.graph.create_user(org_id, "Alice")
user_id = user['user_id'] # Short UUID e.g '89sSRXoz53gdWPJoTEEass'

# Create an agent belonging to the organization and user (optionally).
agent = await memora.graph.create_agent(org_id, "Jenny, Personal AI", user_id=user_id)
agent_id = agent['agent_id'] # Short UUID e.g 'CcyKXxhi2skEcDpRzNZim7'

```

## **Core Operations**

### **1. Saving an Interaction and its Memories**

```python
# Example interaction
interaction = [
    {"role": "user", "content": "I had another peanut incident today; it confirms I am allergic."},
    {"role": "assistant", "content": "Oh Jake, I'm sorry to hear that. Are you okay? I'll make sure to keep peanuts 🥜 away from any future food-related situations."},
    {"role": "user", "content": "Yes, I'm okay, though it stressed out Sarah, my wife, which isn't cool because she is due in December."},
    {"role": "assistant", "content": "I'm glad you're fine now, and that's wonderful news about Sarah's pregnancy! Congratulations to you both. When in December is she due?"},
    {"role": "user", "content": "December 15th."},
    {"role": "assistant", "content": "Congrats again, and feel free to bombard me with every baby question you have 👶🍼, we're raising this baby together LOL 😉"}
]

# Save the interaction and its memories
interaction_id, created_at_timestamp = await memora.save_or_update_interaction_and_memories(
    org_id=org_id,
    user_id=user_id,
    agent_id=agent_id,
    interaction=interaction,
    current_datetime=datetime.now()
)

```

### **2. Updating An Existing Interaction and its Memories**

The updated interaction will be compared with the existing one:

  - If differences are found, truncates existing record from that point and
    replaces with updated version. Old memories from truncated message(s)
    remain but are not linked to the truncated message(s).
  - If no differences, appends new messages from the update.

```python
updated_interaction = interaction + [
    {"role": "user", "content": "Thanks! We're pretty sure it's a girl, but we'll know for certain at the next ultrasound."},
    {"role": "assistant", "content": "The anticipation must be building. Do you have any name ideas?."}
]

# Update the existing interaction (In this case it simply appends the new messages)
interaction_id, updated_at_timestamp = await memora.save_or_update_interaction_and_memories(
    org_id=org_id,
    user_id=user_id,
    agent_id=agent_id,
    interaction=updated_interaction,
    interaction_id=interaction_id,  # Pass the existing interaction_id to update
    current_datetime=datetime.now()
)
```

### **3. Searching Memories**

```python
from memora.vector_db.base import MemorySearchScope

# Returns a consolidated list of results for all queries (sorted by relevance), instead of individual lists per query.
memories = await memora.search_memories_as_one(
    org_id=org_id,
    user_id=user_id,
    search_queries=["Who is my wife?", "When is my wife due?"],
    search_across_agents=True
)
# memories: [{"memory_id": "uuid string", "memory": "Jake married Sarah on August 12th, 2023", obtained_at: "iso timestamp"},{"memory_id": "uuid string", "memory": "Jake's wife Sarah is due on December 15th", obtained_at: "iso timestamp"}, ...]



# Perform a batch search for memories, obtaining a list of results for each query, and can specify the search scope
batch_memories = await memora.search_memories_as_batch(
    org_id=org_id,
    search_queries=["user's allergies", "user's family details"],
    user_id=user_id,
    memory_search_scope=MemorySearchScope.USER,  # Can be "user" or "organization"
    search_across_agents=True
)
# batch_memories: [[{"memory_id": "uuid string", "memory": "Jake has confirmed he is allergic to peanuts", obtained_at: "iso timestamp"}, ...], [{"memory_id": "uuid string", "memory": "Jake's wife Sarah is due on December 15th", obtained_at: "iso timestamp"}, ...]]
```

### **4. Recall Memories for a User's Message in Interaction**

```python
recalled_memories, memory_ids = await memora.recall_memories_for_message(
    org_id,
    user_id,
    latest_msg="Sarah is really in pain more nowdays, so both of us can't sleep.",
    # Optional: Add previous messages in the interaction for context.
    preceding_msg_for_context=[],
    # Optional: Exclude previously recalled memories (e.g They are already in the conversation). See sample personal assistant in the documentation.
    filter_out_memory_ids_set={'4b9df118-fa11-4e29-abfd-3b02587aa251'}  
)

# recalled_memories: [{"memory": "Jake's wife Sarah is due on December 15th", "obtained_at": "iso timestamp"}, {"memory": "Jake and Sarah are pretty confident the baby’s a girl but will confirm at the next ultrasound.", "obtained_at": "iso timestamp"}, ...]

# memory_ids: ["uuid string", "uuid string", ...]
```


### **5. Managing Memories**

```python
# Get all memories for a user
all_memories = await memora.graph.get_all_user_memories(org_id, user_id)

# Get memories from a specific interaction
interaction_memories = await memora.graph.get_all_interaction_memories(org_id, user_id, interaction_id)

# Get the history of a specific memory, this contains all updates of a memory in descending order (starting with the latest version to the oldest)
history = await memora.graph.get_user_memory_history(org_id, user_id, "memory_uuid")

# Delete a specific memory
await memora.graph.delete_user_memory(org_id, user_id, "memory_uuid")

... # See documentation for more methods.
```


## **A Simple Example**

```python
from openai import AsyncOpenAI

... # Preceding code where you have initialized memora, and stored org_id and user_id in variables.

# Async client initialization
client = AsyncOpenAI(api_key="YourOpenAIAPIKey")

messages=[{ "role": "system", "content": "You are jake's assistant, given memories in 'memory recall: ...'"}]

user_message = "Hello, what is my wife's name ?"
recalled_memories, _ = await memora.recall_memories_for_message(org_id, user_id, latest_msg=user_message)

include_memory_in_message = """
    memory recall: {memories}\n---\nmessage: {message}
""".format(memories=str(recalled_memories), message=user_message)

messages.append({'role': 'user', 'content': include_memory_in_message})
response = await client.chat.completions.create(model="gpt-4o", messages=messages)

print(f">>> Assistant Reply: {response.choices[0].message.content}")

```

## Contributing

We welcome contributions! Please see our [Contributing Guidelines](https://github.com/ELZAI/memora/blob/main/CONTRIBUTING.md) for more information on how to get involved.

## License

Memora is released under the [Apache License 2.0](https://github.com/ELZAI/memora/blob/main/LICENSE).
