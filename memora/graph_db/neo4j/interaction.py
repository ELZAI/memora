from typing_extensions import override
import uuid
import shortuuid
import neo4j
from typing import Dict, List, Tuple, Callable, Awaitable

from memora.schema.save_memory_schema import MemoriesAndInteraction

from ..base import BaseGraphDB


class Neo4jInteraction(BaseGraphDB):

    async def _add_messages_to_interaction_from_top(self, tx, org_id: str, user_id: str, interaction_id: str, messages: List[Dict[str, str]])-> None:
        """Add messages to an interaction from the very top, linking the first message to the interaction."""

        await tx.run("""
                    MATCH (interaction:Interaction {
                        org_id: $org_id, 
                        user_id: $user_id, 
                        interaction_id: $interaction_id
                    })

                    CREATE (msg1:MessageBlock {msg_position: 0, role: $messages[0].role, content: $messages[0].content})
                    CREATE (interaction)-[:FIRST_MESSAGE]->(msg1)

                    // Step 1: Create the remaining message nodes and collect them in a list.
                    WITH msg1
                    UNWIND RANGE(1, SIZE($messages) - 1) AS idx
                    CREATE (msg:MessageBlock {msg_position: idx, role: $messages[idx].role, content: $messages[idx].content})

                    // Step 2: Create a chain with the messages all connected via IS_NEXT from the first message.
                    WITH msg1, COLLECT(msg) AS nodeList
                    WITH [msg1] + nodeList AS nodeList

                    UNWIND RANGE(1, SIZE(nodeList) - 1) AS idx
                    WITH nodeList[idx] AS currentNode, nodeList[idx - 1] AS previousNode
                    CREATE (previousNode)-[:IS_NEXT]->(currentNode)

                """, org_id=org_id, user_id=user_id, 
                interaction_id=interaction_id,
                messages=messages)

    async def _append_messages_to_interaction(self, tx, org_id: str, user_id: str, interaction_id: str, messages: List[Dict[str, str]])->None:
        """Finds the last message in the interaction and links (append) this chain of new messages to it."""

        await tx.run("""
                    // Find the last message in the interaction.
                    MATCH p=(interaction: Interaction {org_id: $org_id, user_id: $user_id, interaction_id: $interaction_id})-[r:FIRST_MESSAGE|IS_NEXT*]->(m:MessageBlock)
                    WHERE NOT (m)-[:IS_NEXT]->()

                    // Create the update messages from truncation point.
                    UNWIND RANGE(m.msg_position+1, SIZE($messages) - 1) AS idx
                    CREATE (msg:MessageBlock {msg_position: idx, role: $messages[idx].role, content: $messages[idx].content})

                    // Create a chain with the update messages all connected via IS_NEXT.
                    WITH m, COLLECT(msg) AS nodeList
                    WITH [m] + nodeList AS nodeList
                    UNWIND RANGE(1, SIZE(nodeList) - 1) AS idx
                    WITH nodeList[idx] AS currentNode, nodeList[idx - 1] AS previousNode
                    CREATE (previousNode)-[:IS_NEXT]->(currentNode)
                """,
                org_id=org_id, user_id=user_id, 
                interaction_id=interaction_id,
                messages=messages)

    async def _add_memories_with_their_source_links(self, tx, org_id: str, user_id: str, agent_id: str, interaction_id: str, memories_and_interaction: MemoriesAndInteraction, new_memory_ids: List[str], new_contrary_memory_ids: List[str]):
        """Add all memories and link to their source message and interaction."""

        await tx.run("""
                // Retrieve all messages in the interaction, and the users memory collection.
                MATCH (interaction: Interaction {org_id: $org_id, user_id: $user_id, interaction_id: $interaction_id})-[r:FIRST_MESSAGE|IS_NEXT*]->(m:MessageBlock)
                MATCH (user:User {org_id: $org_id, user_id: $user_id})-[:HAS_MEMORIES]->(mc)

                WITH collect(m) as messages, interaction, mc

                // Create the memory nodes.
                UNWIND $memories_and_source as memory_tuple
                CREATE (memory:Memory {
                    org_id: $org_id, 
                    user_id: $user_id, 
                    agent_id: $agent_id,
                    interaction_id: $interaction_id, 
                    memory_id: memory_tuple[0],  
                    memory: memory_tuple[1], 
                    obtained_at: datetime($interaction_date)
                })
                
                // Link to interaction
                CREATE (interaction)<-[:INTERACTION_SOURCE]-(memory)

                // Link to user's memory collection
                CREATE (mc)-[:INCLUDES]->(memory)

                // For each memory, Link to it's source message in the interaction.
                WITH memory, memory_tuple[2] as all_memory_source_msg_pos, messages
                UNWIND all_memory_source_msg_pos as source_msg_pos

                WITH messages[source_msg_pos] as message_node, memory
                CREATE (message_node)<-[:MESSAGE_SOURCE]-(memory)

            """, org_id=org_id, user_id=user_id, agent_id=agent_id,
            interaction_id=interaction_id,
            interaction_date=memories_and_interaction.interaction_date.isoformat(),
            memories_and_source=[
                    (memory_id, memory_obj.memory, memory_obj.source_msg_block_pos) 
                    for memory_id, memory_obj in 
                    zip(
                        (new_memory_ids + new_contrary_memory_ids), # All memory ids
                        (memories_and_interaction.memories + memories_and_interaction.contrary_memories) # All memories
                    )
                ]
            )

    async def _link_update_contrary_memories_to_existing_memories(self, tx, org_id: str, user_id: str, new_contrary_memory_ids: List[str], memories_and_interaction: MemoriesAndInteraction):

        await tx.run("""
                UNWIND $contrary_and_existing_ids as contrary_and_existing_id_tuple
                MATCH (new_contrary_memory:Memory {org_id: $org_id, user_id: $user_id, memory_id: contrary_and_existing_id_tuple[0]})
                MATCH (old_memory:Memory {org_id: $org_id, user_id: $user_id, memory_id: contrary_and_existing_id_tuple[1]})
                
                MERGE (new_contrary_memory)<-[:CONTRARY_UPDATE]-(old_memory)

            """, org_id=org_id, user_id=user_id,
                contrary_and_existing_ids=[
                        (contrary_memory_id, contrary_memory_obj.existing_contrary_memory_id) 
                        for contrary_memory_id, contrary_memory_obj in 
                        zip(new_contrary_memory_ids, memories_and_interaction.contrary_memories)
                    ]
            )

    @override
    async def save_interaction_with_memories(
        self,
        org_id: str,
        agent_id: str, 
        user_id: str,
        memories_and_interaction: MemoriesAndInteraction,
        vector_db_add_memories_fn: Callable[..., Awaitable[None]]
    ) -> Tuple[str, str]:
        
        interaction_id = shortuuid.uuid()
        new_memory_ids = [str(uuid.uuid4()) for _ in range(len(memories_and_interaction.memories))]
        new_contrary_memory_ids = [str(uuid.uuid4()) for _ in range(len(memories_and_interaction.contrary_memories))]

        async def save_tx(tx):

            # Create interaction and connect to date of occurance.
            await tx.run("""
                MATCH (u:User {org_id: $org_id, user_id: $user_id})-[:INTERACTIONS_IN]->(ic)
                CREATE (interaction:Interaction {
                    org_id: $org_id,
                    user_id: $user_id,
                    agent_id: $agent_id,
                    interaction_id: $interaction_id,
                    created_at: datetime($interaction_date),
                    updated_at: datetime($interaction_date)
                })
                CREATE (ic)-[:HAD_INTERACTION]->(interaction)

                WITH interaction, u
                MERGE (d:Date {
                    org_id: $org_id,
                    user_id: $user_id,
                    date: date(datetime($interaction_date))
                })
                CREATE (interaction)-[:HAS_OCCURRENCE_ON]->(d)

            """, org_id=org_id, user_id=user_id, agent_id=agent_id,
            interaction_id=interaction_id, 
            interaction_date=memories_and_interaction.interaction_date.isoformat())

            # Add the messages to the interaction.
            await self._add_messages_to_interaction_from_top(tx, org_id, user_id, interaction_id, memories_and_interaction.interaction)

            if new_memory_ids or new_contrary_memory_ids:
                # Add the all memories (new & new contrary) and connect to their interaction message source.
                await self._add_memories_with_their_source_links(tx, org_id, user_id, agent_id, interaction_id, memories_and_interaction, new_memory_ids, new_contrary_memory_ids)

            if new_contrary_memory_ids:
                # Link the new contary memories as updates to the old memory they contradicted.
                await self._link_update_contrary_memories_to_existing_memories(tx, org_id, user_id, new_contrary_memory_ids, memories_and_interaction)

            if new_memory_ids or new_contrary_memory_ids:
                # Add memories to vector DB within this transcation function to ensure data consistency (They succeed or fail together).
                await vector_db_add_memories_fn(
                        org_id=org_id, user_id=user_id, agent_id=agent_id,
                        memory_ids=(new_memory_ids + new_contrary_memory_ids), # All memory ids
                        memories=[memory_obj.memory for memory_obj in (memories_and_interaction.memories + memories_and_interaction.contrary_memories)], # All memories                            
                        obtained_at=memories_and_interaction.interaction_date.isoformat()
                        )

            return interaction_id, memories_and_interaction.interaction_date.isoformat()

        async with self.driver.session(database=self.database, default_access_mode=neo4j.WRITE_ACCESS) as session:
            return await session.execute_write(save_tx)

    @override
    async def update_interaction_and_memories(
        self,
        org_id: str,
        agent_id: str,
        user_id: str,
        interaction_id: str,
        updated_memories_and_interaction: MemoriesAndInteraction,
        vector_db_add_memories_fn: Callable[..., Awaitable[None]]
    ) -> Tuple[str, str]:

        new_memory_ids = [str(uuid.uuid4()) for _ in range(len(updated_memories_and_interaction.memories))]
        new_contrary_memory_ids = [str(uuid.uuid4()) for _ in range(len(updated_memories_and_interaction.contrary_memories))]
        
        # First get the existing messages.
        existing_messages: List[Dict[str, str]] = await self.get_interaction_messages(org_id, user_id, interaction_id)

        # Start comparing existing messages with the new ones to know where to truncate from and append new ones, if needed.

        truncate_from = -1 if existing_messages else 0 # if there are no existing messages, it means we can add from the top.

        for i in range(len(existing_messages)):
            if (
                (existing_messages[i]["role"] != updated_memories_and_interaction.interaction[i]["role"]) 
                or
                (existing_messages[i]["content"] != updated_memories_and_interaction.interaction[i]["content"])
            ):
                truncate_from = i
                break
        

        async def update_tx(tx):
                    
            if truncate_from == -1:
                # No need for truncation just append the latest messages.
                await self._append_messages_to_interaction(tx, org_id, user_id, interaction_id, updated_memories_and_interaction.interaction)
            
            elif truncate_from == 0: # Add messages from the top with the first message linked to the interaction.
                await self._add_messages_to_interaction_from_top(tx, org_id, user_id, interaction_id, updated_memories_and_interaction.interaction)
            
            elif truncate_from > 0:
                # Truncate messages from `truncate_from` to the end.
                await tx.run(f"""
                    MATCH (interaction: Interaction {{org_id: $org_id, user_id: $user_id, interaction_id: $interaction_id}})-[r:FIRST_MESSAGE|IS_NEXT*{truncate_from}]->(m:MessageBlock)
                    MATCH (m)-[:IS_NEXT*]->(n)
                    DETACH DELETE n
                """, 
                org_id=org_id, user_id=user_id, 
                interaction_id=interaction_id)

                # Replace from truncated point (now last message) with the new messages.
                await self._append_messages_to_interaction(tx, org_id, user_id, interaction_id, updated_memories_and_interaction.interaction)
        
            if new_memory_ids or new_contrary_memory_ids:
                await self._add_memories_with_their_source_links(tx, org_id, user_id, agent_id, interaction_id, updated_memories_and_interaction, new_memory_ids, new_contrary_memory_ids)

            if new_contrary_memory_ids:
                await self._link_update_contrary_memories_to_existing_memories(tx, org_id, user_id, new_contrary_memory_ids, updated_memories_and_interaction)

            # Update the interaction agent, updated_at datetime, and connect occurance to the particular date.
            await tx.run("""
                MATCH (i:Interaction {
                    org_id: $org_id,
                    user_id: $user_id,
                    interaction_id: $interaction_id
                })
                SET i.updated_at = datetime($updated_date), i.agent_id = $agent_id
                MERGE (d:Date {
                    org_id: $org_id,
                    user_id: $user_id,
                    date: date(datetime($updated_date))
                })
                MERGE (i)-[:HAS_OCCURRENCE_ON]->(d)
            """, org_id=org_id, user_id=user_id, agent_id=agent_id, 
            interaction_id=interaction_id, 
            updated_date=updated_memories_and_interaction.interaction_date.isoformat())

            if new_memory_ids or new_contrary_memory_ids:
                # Add memories to vector DB within this transcation function to ensure data consistency (They succeed or fail together).
                await vector_db_add_memories_fn(
                        org_id=org_id, user_id=user_id, agent_id=agent_id,
                        memory_ids=(new_memory_ids + new_contrary_memory_ids), # All memory ids
                        memories=[memory_obj.memory for memory_obj in (updated_memories_and_interaction.memories + updated_memories_and_interaction.contrary_memories)], # All memories                            
                        obtained_at=updated_memories_and_interaction.interaction_date.isoformat()
                        )

            return interaction_id, updated_memories_and_interaction.interaction_date.isoformat()

        async with self.driver.session(database=self.database, default_access_mode=neo4j.WRITE_ACCESS) as session:
            return await session.execute_write(update_tx)

    @override
    async def get_interaction_messages(
        self,
        org_id: str,
        user_id: str,
        interaction_id: str
    ) -> List[Dict[str, str]]:

        async def get_messages_tx(tx):

            result = await tx.run("""
                // Traverse the interaction and retrieve the messages.
                MATCH (interaction: Interaction {
                    org_id: $org_id, 
                    user_id: $user_id, 
                    interaction_id: $interaction_id
                    })-[r:FIRST_MESSAGE|IS_NEXT*]->(m:MessageBlock)

                return m{.*} as messages
            """, org_id=org_id, user_id=user_id, interaction_id=interaction_id)

            records = await result.value("messages", [])
            return records

        async with self.driver.session(database=self.database, default_access_mode=neo4j.READ_ACCESS) as session:
            return await session.execute_read(get_messages_tx)

    @override
    async def get_all_interaction_memories(
        self,
        org_id: str,
        user_id: str,
        interaction_id: str
    ) -> List[Dict[str, str]]:
        
        async def get_memories_tx(tx):
            result = await tx.run("""
                MATCH (i:Interaction {
                    org_id: $org_id,
                    user_id: $user_id,
                    interaction_id: $interaction_id
                })<-[:INTERACTION_SOURCE]-(m:Memory)
                RETURN m{.memory_id, .memory, obtained_at: toString(m.obtained_at)} as memory
            """, org_id=org_id, user_id=user_id, interaction_id=interaction_id)
            
            records = await result.value("memory", [])
            return records

        async with self.driver.session(database=self.database, default_access_mode=neo4j.READ_ACCESS) as session:
            return await session.execute_read(get_memories_tx)

    @override
    async def delete_user_interaction_and_its_memories(
        self,
        org_id: str,
        user_id: str,
        interaction_id: str,
        vector_db_delete_memories_by_id_fn: Callable[..., Awaitable[None]]
    ) -> None:

        interaction_memories = await self.get_all_interaction_memories(org_id, user_id, interaction_id)
        interaction_memories_ids = [memory["memory_id"] for memory in interaction_memories]
        
        async def delete_tx(tx):
            # Delete the interaction, its messages and memories.
            await tx.run("""
                MATCH (interaction: Interaction {
                    org_id: $org_id, 
                    user_id: $user_id, 
                    interaction_id: $interaction_id
                    })-[r:FIRST_MESSAGE|IS_NEXT*]->(message:MessageBlock)

                OPTIONAL MATCH (interaction)<-[:MESSAGE_SOURCE]-(memory)
                OPTIONAL MATCH (interaction)-[:HAS_OCCURRENCE_ON]->(date:Date) WHERE NOT (date)<-[:HAS_OCCURRENCE_ON]-()

                DETACH DELETE interaction, message, memory, date
            """, org_id=org_id, user_id=user_id, interaction_id=interaction_id)

            # Delete memories from vector DB.
            await vector_db_delete_memories_by_id_fn(interaction_memories_ids)

        async with self.driver.session(database=self.database, default_access_mode=neo4j.WRITE_ACCESS) as session:
            await session.execute_write(delete_tx)

    @override
    async def delete_all_user_interactions_and_their_memories(
        self,
        org_id: str,
        user_id: str,
        vector_db_delete_all_user_memories_fn: Callable[..., Awaitable[None]]
    ) -> None:
        
        async def delete_all_tx(tx):
            await tx.run("""
                MATCH (u:User {org_id: $org_id, user_id: $user_id})-[:INTERACTIONS_IN]->(ic)-[:HAD_INTERACTION]->(interaction:Interaction)
                
                OPTIONAL MATCH (interaction)<-[:INTERACTION_SOURCE]-(memory:Memory)
                OPTIONAL MATCH (interaction)-[:HAS_OCCURRENCE_ON]->(date:Date)
                OPTIONAL MATCH (interaction)-[:FIRST_MESSAGE|IS_NEXT*]->(messages:MessageBlock)

                DETACH DELETE interaction, memory, date, messages
            """, org_id=org_id, user_id=user_id)

            await vector_db_delete_all_user_memories_fn(org_id, user_id)

        async with self.driver.session(database=self.database, default_access_mode=neo4j.WRITE_ACCESS) as session:
            await session.execute_write(delete_all_tx)

