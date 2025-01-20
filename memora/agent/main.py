import logging
import re
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple

from memora.graph_db.base import BaseGraphDB
from memora.llm_backends.base import BaseBackendLLM
from memora.prompts import (
    COMPARE_EXISTING_AND_NEW_MEMORIES_INPUT_TEMPLATE,
    COMPARE_EXISTING_AND_NEW_MEMORIES_SYSTEM_PROMPT,
    EXTRACTION_MSG_BLOCK_FORMAT,
    FILTER_RETRIEVED_MEMORIES_SYSTEM_PROMPT,
    MEMORY_EXTRACTION_SYSTEM_PROMPT,
    MEMORY_EXTRACTION_UPDATE_SYSTEM_PROMPT,
    MSG_MEMORY_SEARCH_PROMPT,
    MSG_MEMORY_SEARCH_TEMPLATE,
)
from memora.schema import (
    ContraryMemoryToStore,
    MemoriesAndInteraction,
    MemoryComparisonResponse,
    MemoryExtractionResponse,
    MemoryToStore,
)
from memora.vector_db.base import BaseVectorDB, MemorySearchScope


class Memora:
    """
    This class orchestrates all necessary memory operations and offers a unified interface for utilizing the Memory Agent.
    """

    def __init__(
        self,
        vector_db: BaseVectorDB,
        graph_db: BaseGraphDB,
        memory_search_model: BaseBackendLLM,
        extraction_model: BaseBackendLLM,
        enable_logging: bool = False,
    ):
        """
        Initialize the Memora instance.

        Args:
            vector_db (BaseVectorDB): Vector database.
            graph_db (BaseGraphDB): Graph database.
            memory_search_model (BaseBackendLLM): Model for memory search queries and Optional final filtering.
            extraction_model (BaseBackendLLM): Model for memory extraction operations.
            enable_logging (bool): Whether to enable console logging.

        Note:
            The graph database will be associated with the vector database.
        """

        self.memory_search_model = memory_search_model
        self.extraction_model = extraction_model
        self.vector_db = vector_db
        self.graph = graph_db

        # Associate the vector database with the graph database.
        self.graph.associated_vector_db = self.vector_db

        self.logger = logging.getLogger(__name__)
        if enable_logging:
            logging.basicConfig(level=logging.INFO)

    async def close(self) -> None:
        """Close and clean up resources used by Memora."""

        await self.vector_db.close()
        await self.graph.close()
        await self.memory_search_model.close()
        await self.extraction_model.close()
        self.logger.info("Memora resources cleaned.")

    async def generate_memory_search_queries(
        self,
        message: str,
        preceding_messages_for_context: List[Dict[str, str]] = [],
        current_datetime: datetime = datetime.now(),
    ) -> List[str]:
        """
        Generate memory search queries based on the given message and context.

        Args:
            message (str): The message to recall memories for.
            preceding_messages_for_context (List[Dict[str, str]]): Preceding messages for context.
            current_datetime (datetime): Current datetime.

        Returns:
            List[str]: List of generated memory search queries.
        """

        current_day_of_week = current_datetime.strftime("%A")
        response = await self.memory_search_model(
            messages=[
                {"role": "system", "content": MSG_MEMORY_SEARCH_PROMPT},
                {
                    "role": "user",
                    "content": MSG_MEMORY_SEARCH_TEMPLATE.format(
                        day_of_week=current_day_of_week,
                        current_datetime_str=current_datetime.isoformat(),
                        message_of_user=str(message),
                        preceding_messages=str(preceding_messages_for_context),
                    ),
                },
                {
                    "role": "assistant",
                    "content": "&& MEMORY_SEARCH &&",
                },  # For Guided Response.
            ]
        )

        arguments_pattern = re.compile(r"<<(.*?)>>", re.DOTALL)
        arguments_passed = arguments_pattern.findall(response)
        memory_search_queries = (
            [arg.strip() for arg in arguments_passed] if arguments_passed else []
        )

        self.logger.info(f"Generated memory search queries: {memory_search_queries}")

        return memory_search_queries

    async def filter_retrieved_memories_with_model(
        self,
        message: str,
        search_queries_used: List[str],
        retrieved_memories: List[Dict[str, str]],
        current_datetime: datetime = datetime.now(),
    ) -> Set[str] | None:
        """
        Filter retrieved memories using the memory search model.

        Args:
            message (str): The message that triggered the search queries and retrieved memories.
            search_queries_used (List[str]): List of search queries used.
            retrieved_memories (List[Dict[str, str]]): List of retrieved memories.
            current_datetime (datetime): Current datetime.

        Returns:
            Set[str] | None: Distinct Set of selected memory IDs (that passed the filter), or None if LLM was unable to analyze and select.
        """

        self.logger.info(f"Starting memory filtering for message: {message[:100]}...")
        self.logger.debug(f"Number of search queries used: {len(search_queries_used)}")
        self.logger.debug(
            f"Number of retrieved memories to filter: {len(retrieved_memories)}"
        )

        current_day_of_week = current_datetime.strftime("%A")
        self.logger.debug(
            f"Current day of week: {current_day_of_week}, datetime: {current_datetime.isoformat()}"
        )

        self.logger.info("Calling memory search model for filtering...")
        response = await self.memory_search_model(
            messages=[
                {
                    "role": "system",
                    "content": FILTER_RETRIEVED_MEMORIES_SYSTEM_PROMPT.format(
                        day_of_week=current_day_of_week,
                        current_datetime_str=current_datetime.isoformat(),
                        latest_room_message=str(message),
                        memory_search_queries="\n- ".join(search_queries_used),
                    ),
                },
                {"role": "user", "content": str(retrieved_memories)},
                {
                    "role": "assistant",
                    "content": "REASONS AND JUST memory_id enclosed in (<< >>):\n- Reason: ",
                },  # For Guided Response.
            ]
        )

        selected_id_pattern = re.compile(r"<<(.*?)>>", re.DOTALL)
        selected_memories_ids = selected_id_pattern.findall(response)

        if (
            not selected_memories_ids
        ):  # The LLM misbehaved not extracting any memory_ids or << NONE >>.
            self.logger.warning(
                "No memory IDs were extracted from the model response, due to LLM misbehavior."
            )
            return None

        # The LLM is undeterministic and can select the same memory_ids multiple times.
        filtered_ids = set(
            [
                str(selection).strip()
                for selection in selected_memories_ids
                if str(selection).strip().lower() != "none"
            ]
        )
        self.logger.info(
            f"Memory filtering complete. Selected {len(filtered_ids)} unique memories"
        )
        self.logger.debug(f"Selected memory IDs: {filtered_ids}")

        return filtered_ids

    async def search_memories_as_one(
        self,
        org_id: str,
        user_id: str,
        search_queries: List[str],
        filter_out_memory_ids_set: Set[str] = set(),
        agent_id: Optional[str] = None,
        search_across_agents: bool = True,
    ) -> List[Dict[str, str]]:
        """
        Retrieve memories corresponding to the search queries for a message.

        Args:
            org_id (str): Organization ID.
            user_id (str): User ID.
            search_queries (List[str]): List of search queries.
            filter_out_memory_ids_set (Set[str]): Set of memory IDs to filter out.
            agent_id (Optional[str]): Agent ID.
            search_across_agents (bool): Whether to search memories across all agents.

        Returns:
            List[Dict[str, str]]: List of retrieved memories.
        """

        self.logger.info(f"Searching memories for user {user_id} in org {org_id}")
        self.logger.debug(f"Search queries: {search_queries}")
        self.logger.debug(
            f"Agent context - agent_id: {agent_id}, memories_across_agents: {search_across_agents}"
        )

        batch_results = await self.vector_db.search_memories(
            queries=search_queries,
            memory_search_scope=MemorySearchScope.USER,
            org_id=org_id,
            user_id=user_id,
            agent_id=agent_id if not search_across_agents else None,
        )

        # Flatten and sort memories by score across the batch results
        sorted_memories = sorted(
            (memory for result in batch_results for memory in result),
            key=lambda x: x["score"],
            reverse=True,
        )

        # Extract the (org, user and memory ids), filtering out the ones to be excluded
        org_user_mem_ids = [
            {
                "memory_id": memory["memory_id"],
                "user_id": memory["user_id"],
                "org_id": memory["org_id"],
            }
            for memory in sorted_memories
            if memory["memory_id"] not in filter_out_memory_ids_set
        ]

        if not org_user_mem_ids:
            self.logger.info(
                "No memories retrieved or left after filtering out `filter_out_memory_ids_set`"
            )
            return []

        return await self.graph.fetch_user_memories_resolved(org_user_mem_ids)

    async def search_memories_as_batch(
        self,
        org_id: str,
        search_queries: List[str],
        filter_out_memory_ids_set: Set[str] = set(),
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        memory_search_scope: MemorySearchScope = MemorySearchScope.USER,
        search_across_agents: bool = True,
    ) -> List[List[Dict[str, str]]]:
        """
        Retrieve memories corresponding to a list of search queries.

        Args:
            org_id (str): Organization ID.
            search_queries (List[str]): List of search queries.
            filter_out_memory_ids_set (Set[str]): Set of memory IDs to filter out.
            user_id (Optional[str]): User ID.
            agent_id (Optional[str]): Agent ID.
            memory_search_scope (MemorySearchScope): Scope of memory search.
            search_across_agents (bool): Whether to search memories across all agents.

        Returns:
            List[List[Dict[str, str]]]: Batch results of retrieved memories.
        """

        self.logger.info(f"Batch searching memories in org {org_id}")
        self.logger.debug(
            f"Search context - user_id: {user_id}, agent_id: {agent_id}, scope: {memory_search_scope}"
        )
        self.logger.debug(f"Number of search queries: {len(search_queries)}")

        batch_results = await self.vector_db.search_memories(
            queries=search_queries,
            memory_search_scope=memory_search_scope,
            org_id=org_id,
            user_id=user_id,
            agent_id=agent_id if not search_across_agents else None,
        )

        batch_org_user_mem_ids = [
            [
                {
                    "memory_id": memory["memory_id"],
                    "user_id": memory["user_id"],
                    "org_id": memory["org_id"],
                }
                for memory in result
                if memory["memory_id"] not in filter_out_memory_ids_set
            ]
            for result in batch_results
        ]

        if not any(batch_org_user_mem_ids):
            self.logger.info(
                "No memories retrieved or left after filtering out `filter_out_memory_ids_set`"
            )
            return []

        return await self.graph.fetch_user_memories_resolved_batch(
            batch_org_user_mem_ids
        )

    async def save_or_update_interaction_and_memories(
        self,
        org_id: str,
        user_id: str,
        agent_id: str,
        interaction: List[Dict[str, str]],
        interaction_id: Optional[str] = None,
        current_datetime: datetime = datetime.now(),
        extract_agent_memories: bool = False,
        update_across_agents: bool = True,
        max_retries: int = 3,
    ) -> Tuple[str, str]:
        """
        Save a new interaction or update an existing one, and the extracted memories.

        Args:
            org_id (str): Organization ID.
            user_id (str): User ID.
            agent_id (str): Agent ID.
            interaction (List[Dict[str, str]]): List of interaction messages.
            interaction_id (Optional[str]): Interaction ID for updates.
            current_datetime (datetime): Current datetime.
            extract_agent_memories (bool): Whether to extract agent memories.
            update_across_agents (bool): Whether to update memories across all agents.
            max_retries (int): Maximum number of retries.

        Returns:
            Tuple[str, str] containing:

                + interaction_id: Short UUID string
                + created_at or updated_at: ISO timestamp

        Raises:
            Exception: If saving the interaction and its memories fails after max retries.
        """
        operation = "Updating" if interaction_id else "Saving"
        self.logger.info(f"{operation} interaction for user {user_id} in org {org_id}")
        self.logger.debug(
            f"Interaction context - agent_id: {agent_id}, extract_agent_memories: {extract_agent_memories}"
        )
        self.logger.debug(f"Interaction size: {len(interaction)} messages")

        for retry in range(max_retries + 1):
            try:
                self.logger.debug(f"Attempt {retry + 1}/{max_retries + 1}")
                user, agent = await self._get_user_and_agent(org_id, user_id, agent_id)

                if interaction_id:
                    self.logger.debug(
                        f"Fetching previously extracted memories for interaction {interaction_id}"
                    )
                    previously_extracted_memories: List[Dict[str, str]] = (
                        await self.graph.get_all_interaction_memories(
                            org_id, user_id, interaction_id
                        )
                    )
                    self.logger.debug(
                        f"Found {len(previously_extracted_memories)} previously extracted memories"
                    )

                    system_content = MEMORY_EXTRACTION_UPDATE_SYSTEM_PROMPT.format(
                        day_of_week=current_datetime.strftime("%A"),
                        current_datetime_str=current_datetime.isoformat(),
                        agent_name=agent["agent_name"],
                        user_name=user["user_name"],
                        extract_for_agent=(
                            f"and {agent['agent_name']}"
                            if extract_agent_memories
                            else ""
                        ),
                        previous_memories=str(previously_extracted_memories),
                        schema=MemoryExtractionResponse.model_json_schema(),
                    )
                else:

                    system_content = MEMORY_EXTRACTION_SYSTEM_PROMPT.format(
                        day_of_week=current_datetime.strftime("%A"),
                        current_datetime_str=current_datetime.isoformat(),
                        agent_name=agent["agent_name"],
                        user_name=user["user_name"],
                        extract_for_agent=(
                            f"and {agent['agent_name']}"
                            if extract_agent_memories
                            else ""
                        ),
                        schema=MemoryExtractionResponse.model_json_schema(),
                    )

                self.logger.debug("Preparing messages for memory extraction")
                messages = [{"role": "system", "content": system_content}]
                messages += [
                    {
                        "role": msg["role"],
                        "content": EXTRACTION_MSG_BLOCK_FORMAT.format(
                            message_id=i, content=msg["content"]
                        ),
                    }
                    for i, msg in enumerate(interaction)
                ]

                self.logger.info("Extracting memories from interaction")
                response: MemoryExtractionResponse = await self.extraction_model(
                    messages=messages, output_schema_model=MemoryExtractionResponse
                )

                candidate_memories, candidate_memories_msg_sources = (
                    self._process_extracted_memories(response, user, agent)
                )
                self.logger.debug(
                    f"Extracted {len(candidate_memories)} candidate memories"
                )

                if not candidate_memories:
                    self.logger.info("No useful information extracted for memories")
                    if interaction_id:
                        return await self.graph.update_interaction_and_memories(
                            org_id,
                            agent_id,
                            user_id,
                            interaction_id,
                            updated_memories_and_interaction=MemoriesAndInteraction(
                                interaction=interaction,
                                interaction_date=current_datetime,
                                memories=[],
                                contrary_memories=[],
                            ),
                        )
                    else:
                        return await self.graph.save_interaction_with_memories(
                            org_id,
                            agent_id,
                            user_id,
                            memories_and_interaction=MemoriesAndInteraction(
                                interaction=interaction,
                                interaction_date=current_datetime,
                                memories=[],
                                contrary_memories=[],
                            ),
                        )

                self.logger.info("Searching for existing related memories")
                existing_memories = await self.search_memories_as_one(
                    org_id=org_id,
                    user_id=user_id,
                    search_queries=candidate_memories,
                    agent_id=agent_id,
                    search_across_agents=update_across_agents,
                )

                if not existing_memories:
                    self.logger.info("No related existing memories found")
                    if interaction_id:
                        return await self.graph.update_interaction_and_memories(
                            org_id,
                            agent_id,
                            user_id,
                            interaction_id,
                            updated_memories_and_interaction=MemoriesAndInteraction(
                                interaction=interaction,
                                interaction_date=current_datetime,
                                memories=[
                                    MemoryToStore(
                                        memory=memory, source_msg_block_pos=source_msgs
                                    )
                                    for memory, source_msgs in zip(
                                        candidate_memories,
                                        candidate_memories_msg_sources,
                                    )
                                ],
                                contrary_memories=[],
                            ),
                        )
                    else:
                        return await self.graph.save_interaction_with_memories(
                            org_id,
                            agent_id,
                            user_id,
                            memories_and_interaction=MemoriesAndInteraction(
                                interaction=interaction,
                                interaction_date=current_datetime,
                                memories=[
                                    MemoryToStore(
                                        memory=memory, source_msg_block_pos=source_msgs
                                    )
                                    for memory, source_msgs in zip(
                                        candidate_memories,
                                        candidate_memories_msg_sources,
                                    )
                                ],
                                contrary_memories=[],
                            ),
                        )

                candidate_memories = [
                    {"memory": memory, "POS_ID": i}
                    for i, memory in enumerate(candidate_memories)
                ]
                messages = [
                    {
                        "role": "system",
                        "content": COMPARE_EXISTING_AND_NEW_MEMORIES_SYSTEM_PROMPT.format(
                            day_of_week=current_datetime.strftime("%A"),
                            current_datetime_str=current_datetime.isoformat(),
                            agent_placeholder=f"agent_{agent['agent_id']}",
                            user_placeholder=f"user_{user['user_id']}",
                            schema=MemoryComparisonResponse.model_json_schema(),
                        ),
                    },
                    {
                        "role": "user",
                        "content": COMPARE_EXISTING_AND_NEW_MEMORIES_INPUT_TEMPLATE.format(
                            existing_memories_string=str(existing_memories),
                            new_memories_string=str(candidate_memories),
                        ),
                    },
                ]

                response: MemoryComparisonResponse = await self.extraction_model(
                    messages=messages, output_schema_model=MemoryComparisonResponse
                )

                new_memories = []
                for memory in response.new_memories:
                    try:
                        new_memories.append(
                            (
                                memory.memory,
                                candidate_memories_msg_sources[
                                    memory.source_candidate_pos_id
                                ],
                            )
                        )
                    except Exception:
                        continue

                new_contrary_memories = []
                for memory in response.contrary_memories:
                    try:
                        new_contrary_memories.append(
                            (
                                memory.memory,
                                candidate_memories_msg_sources[
                                    memory.source_candidate_pos_id
                                ],
                                memory.contradicted_memory_id,
                            )
                        )
                    except Exception:
                        continue

                if interaction_id:
                    return await self.graph.update_interaction_and_memories(
                        org_id,
                        agent_id,
                        user_id,
                        interaction_id,
                        updated_memories_and_interaction=MemoriesAndInteraction(
                            interaction=interaction,
                            interaction_date=current_datetime,
                            memories=[
                                MemoryToStore(
                                    memory=memory_tuple[0],
                                    source_msg_block_pos=memory_tuple[1],
                                )
                                for memory_tuple in new_memories
                            ],
                            contrary_memories=[
                                ContraryMemoryToStore(
                                    memory=memory_tuple[0],
                                    source_msg_block_pos=memory_tuple[1],
                                    existing_contrary_memory_id=memory_tuple[2],
                                )
                                for memory_tuple in new_contrary_memories
                            ],
                        ),
                    )
                else:
                    return await self.graph.save_interaction_with_memories(
                        org_id,
                        agent_id,
                        user_id,
                        memories_and_interaction=MemoriesAndInteraction(
                            interaction=interaction,
                            interaction_date=current_datetime,
                            memories=[
                                MemoryToStore(
                                    memory=memory_tuple[0],
                                    source_msg_block_pos=memory_tuple[1],
                                )
                                for memory_tuple in new_memories
                            ],
                            contrary_memories=[
                                ContraryMemoryToStore(
                                    memory=memory_tuple[0],
                                    source_msg_block_pos=memory_tuple[1],
                                    existing_contrary_memory_id=memory_tuple[2],
                                )
                                for memory_tuple in new_contrary_memories
                            ],
                        ),
                    )

            except Exception:
                if retry == max_retries:
                    self.logger.error(
                        f"Failed to save/update interaction after {max_retries} retries",
                        exc_info=True,
                    )
                    raise
                else:
                    self.logger.warning(
                        f"Attempt {retry + 1} failed, retrying...", exc_info=True
                    )
                    continue

    async def _get_user_and_agent(
        self, org_id: str, user_id: str, agent_id: str
    ) -> Tuple[Dict, Dict]:
        """
        Fetch user and agent data.

        Args:
            org_id (str): Organization ID.
            user_id (str): User ID.
            agent_id (str): Agent ID.

        Returns:
            Tuple[Dict, Dict]: Tuple containing the user and agent data.
        """

        self.logger.debug(f"Fetching user {user_id} and agent {agent_id} data")
        user = await self.graph.get_user(org_id, user_id)
        agent = await self.graph.get_agent(org_id, agent_id)

        if not user or not agent:
            raise ValueError(
                f"User or Agent not found: user_id={user_id}, agent_id={agent_id}"
            )

        return user, agent

    def _process_extracted_memories(
        self, response: MemoryExtractionResponse, user: Dict, agent: Dict
    ) -> Tuple[List[str], List[List[int]]]:
        """
        Get every memory extracted, their source messages and insert placeholders for user and agent.

        Args:
            response (MemoryExtractionResponse): Response from the memory extraction model.
            user (Dict): User data.
            agent (Dict): Agent data.

        Returns:
            Tuple[List[str], List[List[int]]]: Extracted memories and their source messages.
        """

        candidate_memories: List[str] = []
        candidate_memories_msg_sources: List[List[int]] = []

        for memory_list in (
            response.memories_first_pass or [],
            response.memories_second_pass or [],
            response.memories_third_pass or [],
        ):
            for memory in memory_list:
                memory_text = memory.memory.replace(
                    "#user_#id#", f"user_{user['user_id']}"
                ).replace("#agent_#id#", f"agent_{agent['agent_id']}")
                candidate_memories.append(memory_text)
                candidate_memories_msg_sources.append(memory.msg_source_ids)

        return candidate_memories, candidate_memories_msg_sources

    async def recall_memories_for_message(
        self,
        org_id: str,
        user_id: str,
        latest_msg: str,
        agent_id: Optional[str] = None,
        preceding_msg_for_context: List[Dict[str, str]] = [],
        current_datetime: datetime = datetime.now(),
        filter_out_memory_ids_set: Set[str] = set(),
        search_memories_across_agents: bool = True,
        enable_final_model_based_memory_filter: bool = False,
    ) -> Tuple[List[Dict[str, str]] | None, List[str] | None]:
        """
        Recall memories for the given message.

        Args:
            org_id (str): Organization ID.
            user_id (str): User ID.
            latest_msg (str): The latest message from user to find memories for.
            agent_id (Optional[str]): Agent ID.
            preceding_msg_for_context (List[Dict[str, str]]): Preceding messages for context.
            current_datetime (datetime): Current datetime.
            filter_out_memory_ids_set (Set[str]): Set of memory IDs to filter out.
            search_memories_across_agents (bool): Whether to search memories across all agents.
            enable_final_model_based_memory_filter (bool): 📝 Experimental feature; enables filtering of retrieved memories using a model. Note that a small model (~ 8B or lower) might not select some memories that are indirectly needed.

        Returns:
            Tuple[List[Dict[str, str]] | None, List[str] | None]:

                + List[Dict[str, str]]: Containing Memories to be recalled (None if no relevant memories found):

                    + memory (str): Memory content
                    + obtained_at (str): ISO format timestamp

                + List[str]: Just the memory IDs (empty list [] if no memory was recalled).
        """

        self.logger.info(
            f"Getting memories for message from user {user_id} in org {org_id}"
        )
        self.logger.debug(
            f"Message context - agent_id: {agent_id}, context messages: {len(preceding_msg_for_context)}"
        )
        self.logger.debug(
            f"Model-based filtering enabled: {enable_final_model_based_memory_filter}"
        )

        self.logger.info("Generating memory search queries")
        search_queries = await self.generate_memory_search_queries(
            message=latest_msg,
            preceding_messages_for_context=preceding_msg_for_context,
            current_datetime=current_datetime,
        )
        self.logger.debug(f"Generated {len(search_queries)} search queries")

        if not search_queries:
            self.logger.warning("No search queries generated")
            search_queries = [latest_msg]  # Use the latest message as a fallback.

        self.logger.info("Searching memories based on generated queries")

        retrieved_memories = await self.search_memories_as_one(
            org_id=org_id,
            user_id=user_id,
            search_queries=search_queries,
            filter_out_memory_ids_set=filter_out_memory_ids_set,
            agent_id=agent_id,
            search_across_agents=search_memories_across_agents,
        )

        if not retrieved_memories:
            self.logger.info("No memories found for the message")
            return None, None

        self.logger.info(f"Retrieved {len(retrieved_memories)} memories")

        if not enable_final_model_based_memory_filter:
            return (
                [
                    {"memory": memory["memory"], "obtained_at": memory["obtained_at"]}
                    for memory in retrieved_memories
                ],  # memories.
                [memory["memory_id"] for memory in retrieved_memories],  # memory ids.
            )

        self.logger.info("Applying model-based memory filtering")
        filtered_memory_ids = await self.filter_retrieved_memories_with_model(
            latest_msg, search_queries, retrieved_memories, current_datetime
        )

        if (
            filtered_memory_ids is None
        ):  # The LLM was unable to filter just needed memories.
            self.logger.info("Model-based filtering failed")
            return (
                [
                    {"memory": memory["memory"], "obtained_at": memory["obtained_at"]}
                    for memory in retrieved_memories
                ],  # memories.
                [memory["memory_id"] for memory in retrieved_memories],  # memory ids.
            )

        if (
            len(filtered_memory_ids) == 0
        ):  # The LLM filtered out all memories (deemed none are needed to be recalled).
            self.logger.info("Model-based filtering returned no memories")
            return None, None

        memory_dict = {memory["memory_id"]: memory for memory in retrieved_memories}
        selected_memories = [
            {"memory": memoryObj["memory"], "obtained_at": memoryObj["obtained_at"]}
            for memory_id in filtered_memory_ids
            if (memoryObj := memory_dict.get(memory_id)) is not None
        ]

        self.logger.info(
            f"Selected {len(selected_memories)} memories after model-based filtering"
        )
        return selected_memories, filtered_memory_ids
