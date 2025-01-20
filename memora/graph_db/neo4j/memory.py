from typing import Dict, List, Optional

import neo4j
from typing_extensions import override

from ..base import BaseGraphDB


class Neo4jMemory(BaseGraphDB):

    @override
    async def fetch_user_memories_resolved(
        self, org_user_mem_ids: List[Dict[str, str]]
    ) -> List[Dict[str, str]]:
        """
        Fetches memories from the Neo4j GraphDB by their IDs, resolves any contrary updates, and replaces user/agent placeholders with actual names.

        This method performs several operations:
          1. Retrieves memories using (org_id, user_id, memory_ids)
          2. If a memory has a CONTRARY_UPDATE relationship, uses the newer memory version
          3. Replaces user_id & agent_id placeholders (e.g 'user_abc123' or 'agent_xyz789') in memories with actual user names / agent labels

        Args:
            org_user_mem_ids (List[Dict[str, str]]): List of Dicts containing org, user, and memory ids of the memories to fetch and process

        Returns:
            List[Dict[str, str]] containing memory details:

                + memory_id: UUID string identifying the memory
                + memory: String content of the resolved memory
                + obtained_at: ISO format timestamp of when the memory was obtained

        Example:
            ```python
            >>> org_user_mem_ids = [{'memory_id': '443ac3a8-fe87-49a4-93d2-05d3eb58ddeb', 'org_id': 'gmDr4sUiWMNqbGAiV8ijbU', 'user_id': 'CcyKXxhi2skEcDpRzNZim7'}, ...]
            >>> memories = graphInstance.fetch_memories_resolved(org_user_mem_ids)
            >>> print([memoryObj['memory'] for memoryObj in memories])
            ["John asked for help with a wedding ring", "Sarah is allergic to peanuts"]
            ```

        Note:
            Org, user, and memory IDs are typically retrieved from a vector database before being passed to this method.
        """

        results = await self.fetch_user_memories_resolved_batch([org_user_mem_ids])
        return results[0]

    @override
    async def fetch_user_memories_resolved_batch(
        self, batch_org_user_mem_ids: List[List[Dict[str, str]]]
    ) -> List[List[Dict[str, str]]]:
        """
        Fetches memories from the Neo4j GraphDB by their IDs, resolves any contrary updates, and replaces user/agent placeholders with actual names.

        This method performs several operations:
          1. Retrieves memories using (org_id, user_id, memory_ids)
          2. If a memory has a CONTRARY_UPDATE relationship, uses the newer memory version
          3. Replaces user_id & agent_id placeholders (e.g 'user_abc123' or 'agent_xyz789') in memories with actual user names / agent labels

        Args:
            batch_org_user_mem_ids (List[List[Dict[str, str]]]): List of lists containing Dicts with org, user, and memory ids of the memories to fetch and process

        Returns:
            List[List[Dict[str, str]]] with memory details:

                + memory_id: UUID string identifying the memory
                + memory: String content of the resolved memory
                + obtained_at: ISO format timestamp of when the memory was obtained

        Example:
            ```python
            >>> batch_org_user_mem_ids = [[{"memory_id": "413ac3a8-fe87-49a4-93d2-05d3eb58ddeb", "org_id": "gmDr4sUiWMNqbGAiV8ijbU", "user_id": "CcyKXxhi2skEcDpRzNZim7"}, ...], [{...}, ...]]
            >>> batch_memories = graphInstance.fetch_memories_resolved_batch(batch_org_user_mem_ids)
            >>> print([[memoryObj['memory'] for memoryObj in memories] for memories in batch_memories])
            [["John asked for help with a wedding ring", "Sarah is allergic to peanuts"], ["John is about to propose to Sarah"]]
            ```

        Note:
            Batch org, user, and memory IDs are typically retrieved from a vector database before being passed to this method.
        """

        async def fetch_resolved_batch_tx(tx):
            result = await tx.run(
                """
                UNWIND $batch_ids AS ids_dict_list

                CALL (ids_dict_list) {

                    UNWIND ids_dict_list AS ids_dict
                    MATCH (memory:Memory {org_id: ids_dict.org_id, user_id: ids_dict.user_id, memory_id: ids_dict.memory_id})
                                  
                    // Use the most up to date contrary update memory if it exists
                    OPTIONAL MATCH (memory)-[:CONTRARY_UPDATE*]->(contraryMemory:Memory) WHERE NOT (contraryMemory)-[:CONTRARY_UPDATE]->()
                    WITH coalesce(contraryMemory, memory) AS memoryToReturn
                                  
                    MATCH (user:User {org_id: memoryToReturn.org_id, user_id: memoryToReturn.user_id})              
                    MATCH (agent:Agent {org_id: memoryToReturn.org_id, agent_id: memoryToReturn.agent_id})
                                  
                    // Case-insensitive 'user_' or 'agent_' followed by UUID and optional ('s) placeholders are replaced with actual names
                    RETURN collect(DISTINCT memoryToReturn{
                                                .memory_id, 
                                                memory: apoc.text.replace(
                                                    apoc.text.replace(memoryToReturn.memory, '(?i)user_[a-z0-9\\-]+(?:\\'s)?', user.user_name), 
                                                    '(?i)agent_[a-z0-9\\-]+(?:\\'s)?',  agent.agent_name
                                                ),
                                                obtained_at: toString(memoryToReturn.obtained_at)
                                            }) as resolved_memories
                }
                RETURN resolved_memories

            """,
                batch_ids=batch_org_user_mem_ids,
            )

            records = await result.value("resolved_memories", [])
            return records

        async with self.driver.session(
            database=self.database, default_access_mode=neo4j.READ_ACCESS
        ) as session:
            return await session.execute_read(fetch_resolved_batch_tx)

    @override
    async def get_user_memory(
        self, org_id: str, user_id: str, memory_id: str
    ) -> Dict[str, str]:
        """
        Retrieves a specific memory.

        Args:
            org_id (str): Short UUID string identifying the organization
            user_id (str): Short UUID string identifying the user
            memory_id (str): UUID string identifying the memory

        Returns:
            Dict[str, str] containing memory details:

                + memory_id: UUID string identifying the memory
                + memory: String content of the memory
                + obtained_at: ISO format timestamp of when the memory was obtained
        """

        async def get_memory_tx(tx):
            result = await tx.run(
                """
                MATCH (m:Memory {org_id: $org_id, user_id: $user_id, memory_id: $memory_id})
                MATCH (user:User {org_id: m.org_id, user_id: m.user_id})              
                MATCH (agent:Agent {org_id: m.org_id, agent_id: m.agent_id})
                RETURN m{
                        .memory_id, 
                        memory: apoc.text.replace(
                            apoc.text.replace(m.memory, '(?i)user_[a-z0-9\\-]+(?:\\'s)?', user.user_name), 
                            '(?i)agent_[a-z0-9\\-]+(?:\\'s)?',  agent.agent_name
                        ), 
                        obtained_at: toString(m.obtained_at)
                    } as memory
            """,
                org_id=org_id,
                user_id=user_id,
                memory_id=memory_id,
            )
            record = await result.single()
            return record["memory"]

        async with self.driver.session(
            database=self.database, default_access_mode=neo4j.READ_ACCESS
        ) as session:
            return await session.execute_read(get_memory_tx)

    @override
    async def get_user_memory_history(
        self, org_id: str, user_id: str, memory_id: str
    ) -> List[Dict[str, str]]:
        """
        Retrieves the history of a specific memory.

        Args:
            org_id (str): Short UUID string identifying the organization
            user_id (str): Short UUID string identifying the user
            memory_id (str): UUID string identifying the memory

        Returns:
            List[Dict[str, str]] containing the history of memory details in descending order (starting with the current version, to the oldest version):

                + memory_id: UUID string identifying the memory
                + memory: String content of the memory
                + obtained_at: ISO format timestamp of when the memory was obtained
        """

        async def get_memory_history_tx(tx):
            result = await tx.run(
                """
                MATCH path=(m:Memory {org_id: $org_id, user_id: $user_id, memory_id: $memory_id})<-[:CONTRARY_UPDATE*0..]-(olderMemory:Memory)
                WHERE NOT (olderMemory)<-[:CONTRARY_UPDATE]-()
                WITH nodes(path) AS memory_history
                UNWIND memory_history AS memory
                MATCH (user:User {org_id: memory.org_id, user_id: memory.user_id})              
                MATCH (agent:Agent {org_id: memory.org_id, agent_id: memory.agent_id})
                RETURN memory{
                        .memory_id, 
                        memory: apoc.text.replace(
                            apoc.text.replace(memory.memory, '(?i)user_[a-z0-9\\-]+(?:\\'s)?', user.user_name), 
                            '(?i)agent_[a-z0-9\\-]+(?:\\'s)?',  agent.agent_name
                        ), 
                        obtained_at: toString(memory.obtained_at)
                    } as memory
            """,
                org_id=org_id,
                user_id=user_id,
                memory_id=memory_id,
            )
            records = await result.value("memory", [])
            return records

        async with self.driver.session(
            database=self.database, default_access_mode=neo4j.READ_ACCESS
        ) as session:
            return await session.execute_read(get_memory_history_tx)

    @override
    async def get_all_user_memories(
        self, org_id: str, user_id: str, agent_id: Optional[str] = None
    ) -> List[Dict[str, str]]:
        """
        Retrieves all memories associated with a specific user.

        Args:
            org_id (str): Short UUID string identifying the organization
            user_id (str): Short UUID string identifying the user
            agent_id (Optional[str]): Optional short UUID string identifying the agent. If provided, only memories obtained from
                interactions with this agent are returned.
                Otherwise, all memories associated with the user are returned.

        Returns:
            List[Dict[str, str]] containing memory details:

                + memory_id: UUID string identifying the memory
                + memory: String content of the memory
                + obtained_at: ISO format timestamp of when the memory was obtained
        """

        async def get_all_memories_tx(tx):

            if agent_id:  # Filter to only memories from interactions with this agent.
                result = await tx.run(
                    """
                    MATCH (user:User {org_id: $org_id, user_id: $user_id})-[:HAS_MEMORIES]->(mc:MemoryCollection)
                    MATCH (mc)-[:INCLUDES]->(m:Memory)
                    WHERE m.agent_id = $agent_id
                    WITH m, user             
                    MATCH (agent:Agent {org_id: m.org_id, agent_id: m.agent_id})
                    RETURN m{
                        .memory_id, 
                        memory: apoc.text.replace(
                            apoc.text.replace(m.memory, '(?i)user_[a-z0-9\\-]+(?:\\'s)?', user.user_name), 
                            '(?i)agent_[a-z0-9\\-]+(?:\\'s)?',  agent.agent_name
                        ), 
                        obtained_at: toString(m.obtained_at)
                    } as memory
                """,
                    org_id=org_id,
                    user_id=user_id,
                    agent_id=agent_id,
                )

            else:  # Fetch all.
                result = await tx.run(
                    """
                    MATCH (user:User {org_id: $org_id, user_id: $user_id})-[:HAS_MEMORIES]->(mc:MemoryCollection)
                    MATCH (mc)-[:INCLUDES]->(m:Memory)
                    WITH m, user            
                    MATCH (agent:Agent {org_id: m.org_id, agent_id: m.agent_id})
                    RETURN m{
                        .memory_id, 
                        memory: apoc.text.replace(
                            apoc.text.replace(m.memory, '(?i)user_[a-z0-9\\-]+(?:\\'s)?', user.user_name), 
                            '(?i)agent_[a-z0-9\\-]+(?:\\'s)?',  agent.agent_name
                        ), 
                        obtained_at: toString(m.obtained_at)
                    } as memory
                """,
                    org_id=org_id,
                    user_id=user_id,
                )

            records = await result.value("memory", [])
            return records

        async with self.driver.session(
            database=self.database, default_access_mode=neo4j.READ_ACCESS
        ) as session:
            return await session.execute_read(get_all_memories_tx)

    @override
    async def delete_user_memory(
        self,
        org_id: str,
        user_id: str,
        memory_id: str,
    ) -> None:
        """
        Deletes a specific memory.

        Args:
            org_id (str): Short UUID string identifying the organization
            user_id (str): Short UUID string identifying the user
            memory_id (str): UUID string identifying the memory to delete

        Note:
            If the graph database is associated with a vector database, the memory is also deleted there for data consistency.
        """

        async def delete_memory_tx(tx):
            await tx.run(
                """
                MATCH (m:Memory {org_id: $org_id, user_id: $user_id, memory_id: $memory_id})
                DETACH DELETE m
            """,
                org_id=org_id,
                user_id=user_id,
                memory_id=memory_id,
            )

            if (
                self.associated_vector_db
            ):  # If the graph database is associated with a vector database
                # Delete memory from vector DB.
                await self.associated_vector_db.delete_memory(memory_id)

        async with self.driver.session(
            database=self.database, default_access_mode=neo4j.WRITE_ACCESS
        ) as session:
            await session.execute_write(delete_memory_tx)

    @override
    async def delete_all_user_memories(
        self,
        org_id: str,
        user_id: str,
    ) -> None:
        """
        Deletes all memories of a specific user.

        Args:
            org_id (str): Short UUID string identifying the organization
            user_id (str): Short UUID string identifying the user

        Note:
            If the graph database is associated with a vector database, the memories are also deleted there for data consistency.
        """

        async def delete_all_memories_tx(tx):
            await tx.run(
                """
                MATCH (u:User {org_id: $org_id, user_id: $user_id})-[:HAS_MEMORIES]->(mc:MemoryCollection)
                MATCH (mc)-[:INCLUDES]->(memory:Memory)
                DETACH DELETE memory
            """,
                org_id=org_id,
                user_id=user_id,
            )

            if (
                self.associated_vector_db
            ):  # If the graph database is associated with a vector database
                # Delete all memories from vector DB.
                await self.associated_vector_db.delete_all_user_memories(
                    org_id, user_id
                )

        async with self.driver.session(
            database=self.database, default_access_mode=neo4j.WRITE_ACCESS
        ) as session:
            await session.execute_write(delete_all_memories_tx)
