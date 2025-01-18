from abc import ABC, abstractmethod
from typing import Dict, List, Tuple, Optional
from ..schema.save_memory_schema import MemoriesAndInteraction
from ..vector_db.base import BaseVectorDB


class BaseGraphDB(ABC):
    """
    Abstract base class defining a common interface for different Graph DB implementations.

    This class provides a standardized interface for graph database operations, including
    creating, retrieving, and deleting memory nodes and relationships.
    """

    @abstractmethod
    def get_associated_vector_db(self) -> Optional[BaseVectorDB]:
        """
        The vector database associated with the graph database, these is used inside the graph transactional blocks
        to ensure data consistency when handling memories across both stores (e.g., saving memories to the vector
        store and creating corresponding nodes in the graph db).
        """
        pass

    @abstractmethod
    async def close(self) -> None:
        """Closes the database connection."""
        pass

    # Setup method
    @abstractmethod
    async def setup(self, *args, **kwargs) -> None:
        """
        Sets up the database, e.g., creates indexes, constraints, etc.
        """
        pass

    # Organization methods
    @abstractmethod
    async def create_organization(self, org_name: str) -> Dict[str, str]:
        """
        Creates a new organization in the graph database.

        Args:
            org_name (str): The name of the organization to create.

        Returns:
            Dict[str, str] containing:

                + org_id: Short UUID string
                + org_name: Organization name
                + created_at: ISO format timestamp
        """
        pass

    @abstractmethod
    async def update_organization(
        self, org_id: str, new_org_name: str
    ) -> Dict[str, str]:
        """
        Updates an existing organization in the graph database.

        Args:
            org_id (str): The Short UUID of the organization to update.
            new_org_name (str): The new name for the organization.

        Returns:
            Dict[str, str] containing:

                + org_id: Short UUID string
                + org_name: Organization name
        """
        pass

    @abstractmethod
    async def delete_organization(self, org_id: str) -> None:
        """
        Deletes an organization from the graph database.

        Warning:
            This operation will delete all nodes and relationships from this organization
            including users, agents, memories, interactions etc.

        Args:
            org_id (str): Short UUID string identifying the organization to delete.
        """
        pass

    @abstractmethod
    async def get_organization(self, org_id: str) -> Dict[str, str]:
        """
        Gets a specific organization from the graph database.

        Args:
            org_id (str): Short UUID string identifying the organization to retrieve.

        Returns:
            Dict[str, str] containing:

                + org_id: Short UUID string
                + org_name: Organization name
                + created_at: ISO format timestamp
        """
        pass

    @abstractmethod
    async def get_all_organizations(self) -> List[Dict[str, str]]:
        """
        Gets all organizations from the graph database.

        Returns:
            List[Dict[str, str]] each containing:

                + org_id: Short UUID string
                + org_name: Organization name
                + created_at: ISO format timestamp
        """
        pass

    # Agent methods
    @abstractmethod
    async def create_agent(
        self, org_id: str, agent_label: str, user_id: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Creates a new agent in the graph database.

        Args:
            org_id (str): Short UUID string identifying the organization.
            agent_label (str): Label/name for the agent.
            user_id (Optional[str]): Optional Short UUID of the user. This is used when the agent is created
                specifically for a user, indicating that both the organization and the
                user will have this agent.

        Returns:
            Dict[str, str] containing:

                + org_id: Short UUID string
                + user_id: Optional Short UUID string
                + agent_id: Short UUID string
                + agent_label: Agent label/name
                + created_at: ISO format timestamp
        """
        pass

    @abstractmethod
    async def update_agent(
        self, org_id: str, agent_id: str, new_agent_label: str
    ) -> Dict[str, str]:
        """
        Updates an existing agent in the graph database.

        Args:
            org_id (str): Short UUID string identifying the organization.
            agent_id (str): Short UUID string identifying the agent to update.
            new_agent_label (str): New label/name for the agent.

        Returns:
            Dict[str, str] containing:

                + org_id: Short UUID string
                + agent_id: Short UUID string
                + agent_label: Agent label/name
        """
        pass

    @abstractmethod
    async def delete_agent(self, org_id: str, agent_id: str) -> None:
        """
        Deletes an agent from the graph database.

        Args:
            org_id (str): Short UUID string identifying the organization.
            agent_id (str): Short UUID string identifying the agent to delete.
        """
        pass

    @abstractmethod
    async def get_agent(self, org_id: str, agent_id: str) -> Dict[str, str]:
        """
        Gets a specific agent belonging to the specified organization from the graph database.

        Args:
            org_id (str): Short UUID string identifying the organization.
            agent_id (str): Short UUID string identifying the agent to retrieve.

        Returns:
            Dict[str, str] containing:

                + org_id: Short UUID string
                + user_id: Optional Short UUID string if agent is associated with a user [:HAS_AGENT].
                + agent_id: Short UUID string
                + agent_label: Agent label/name
                + created_at: ISO format timestamp
        """
        pass

    @abstractmethod
    async def get_all_org_agents(self, org_id: str) -> List[Dict[str, str]]:
        """
        Gets all agents belonging to the specified organization from the graph database.

        Args:
            org_id (str): Short UUID string identifying the organization.

        Returns:
            A List[Dict[str, str]], each containing:

                + org_id: Short UUID string
                + agent_id: Short UUID string
                + agent_label: Agent label/name
                + created_at: ISO format timestamp
        """
        pass

    @abstractmethod
    async def get_all_user_agents(
        self, org_id: str, user_id: str
    ) -> List[Dict[str, str]]:
        """
        Gets all agents for a user within an organization from the graph database.

        Args:
            org_id (str): Short UUID string identifying the organization.
            user_id (str): Short UUID string identifying the user.

        Returns:
            A List[Dict[str, str]], each containing:

                + org_id: Short UUID string
                + user_id: Short UUID string
                + agent_id: Short UUID string
                + agent_label: Agent label/name
                + created_at: ISO format timestamp
        """
        pass

    # User methods
    @abstractmethod
    async def create_user(self, org_id: str, user_name: str) -> Dict[str, str]:
        """
        Creates a new user in the graph database.

        Args:
            org_id (str): Short UUID string identifying the organization.
            user_name (str): Name for the user.

        Returns:
            Dict[str, str] containing:

                + org_id: Short UUID string
                + user_id: Short UUID string
                + user_name: User's name
                + created_at: ISO format timestamp
        """
        pass

    @abstractmethod
    async def update_user(
        self, org_id: str, user_id: str, new_user_name: str
    ) -> Dict[str, str]:
        """
        Updates an existing user in the graph database.

        Args:
            org_id (str): Short UUID string identifying the organization.
            user_id (str): Short UUID string identifying the user to update.
            new_user_name (str): The new name for the user.

        Returns:
            Dict[str, str] containing:

                + org_id: Short UUID string
                + user_id: Short UUID string
                + user_name: User's name
        """
        pass

    @abstractmethod
    async def delete_user(self, org_id: str, user_id: str) -> None:
        """
        Deletes a user from the graph database.

        Args:
            org_id (str): Short UUID string identifying the organization.
            user_id (str): Short UUID string identifying the user to delete.
        """
        pass

    @abstractmethod
    async def get_user(self, org_id: str, user_id: str) -> Dict[str, str]:
        """
        Gets a specific user belonging to the specified organization from the graph database.

        Args:
            org_id (str): Short UUID string identifying the organization.
            user_id (str): Short UUID string identifying the user to retrieve.

        Returns:
            Dict[str, str] containing:

                + org_id: Short UUID string
                + user_id: Short UUID string
                + user_name: User's name
                + created_at: ISO format timestamp
        """
        pass

    @abstractmethod
    async def get_all_users(self, org_id: str) -> List[Dict[str, str]]:
        """
        Gets all users belonging to the specified organization from the graph database.

        Args:
            org_id (str): Short UUID string identifying the organization.

        Returns:
            List[Dict[str, str]], each containing:

                + org_id: Short UUID string
                + user_id: Short UUID string
                + user_name: User's name
                + created_at: ISO format timestamp
        """
        pass

    # Interaction methods
    @abstractmethod
    async def save_interaction_with_memories(
        self,
        org_id: str,
        agent_id: str,
        user_id: str,
        memories_and_interaction: MemoriesAndInteraction,
    ) -> Tuple[str, str]:
        """
        Creates a new interaction record with associated memories.

        Args:
            org_id (str): Short UUID string identifying the organization.
            agent_id (str): Short UUID string identifying the agent.
            user_id (str): Short UUID string identifying the user.
            memories_and_interaction (MemoriesAndInteraction): Contains both the interaction and the associated memories.

        Note:
            If the graph database is associated with a vector database, the memories are also stored there for data consistency.

        Returns:
            Tuple[str, str] containing:

                + interaction_id: Short UUID string identifying the created interaction
                + created_at: ISO format timestamp of when the interaction was created
        """
        pass

    @abstractmethod
    async def update_interaction_and_memories(
        self,
        org_id: str,
        agent_id: str,
        user_id: str,
        interaction_id: str,
        updated_memories_and_interaction: MemoriesAndInteraction,
    ) -> Tuple[str, str]:
        """
        Update an existing interaction record and add new memories.

        Compares updated interaction with existing one:
            - If differences are found, truncates existing record from that point and
            replaces with updated version. Old memories from truncated message(s)
            remain but become standalone (no longer linked to truncated messages).
            - If no differences, appends new messages from the update.

        New memories are always added, regardless of interaction changes.

        Args:
            org_id (str): Short UUID string identifying the organization.
            agent_id (str): Short UUID string identifying the agent in the updated interaction.
            user_id (str): Short UUID string identifying the user.
            interaction_id (str): Short UUID string identifying the interaction to update.
            updated_memories_and_interaction (MemoriesAndInteraction): Contains both the updated interaction and the associated new memories.

        Note:
            If the graph database is associated with a vector database, the memories are also stored there for data consistency.

        Returns:
            Tuple[str, str] containing:

                + interaction_id: Short UUID string identifying the updated interaction
                + updated_at: ISO format timestamp of when the update occurred
        """
        pass

    @abstractmethod
    async def get_interaction_messages(
        self, org_id: str, user_id: str, interaction_id: str
    ) -> List[Dict[str, str]]:
        """
        Retrieves all messages associated with a specific interaction.

        Args:
            org_id (str): Short UUID string identifying the organization.
            user_id (str): Short UUID string identifying the user.
            interaction_id (str): Short UUID string identifying the interaction.

        Returns:
            List[Dict[str, str]], each containing message details:

                + role: Role of the message sender (user or agent)
                + content: String content of the message
                + msg_position: Position of the message in the interaction
        """
        pass

    @abstractmethod
    async def get_all_interaction_memories(
        self, org_id: str, user_id: str, interaction_id: str
    ) -> List[Dict[str, str]]:
        """
        Retrieves all memories associated with a specific interaction.

        Args:
            org_id (str): Short UUID string identifying the organization.
            user_id (str): Short UUID string identifying the user.
            interaction_id (str): Short UUID string identifying the interaction.

        Returns:
            List[Dict[str, str]], each containing memory details:

                + memory_id: UUID string identifying the memory
                + memory: String content of the memory
                + obtained_at: ISO format timestamp of when the memory was obtained
        """
        pass

    @abstractmethod
    async def get_all_user_interactions(
        self,
        org_id: str,
        user_id: str,
        with_their_messages: bool = True,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Dict[str, str]]:
        """
        Retrieves all interactions for a specific user in an organization.

        Note:
            Interaction are sorted in descending order by their updated at datetime. (So most recent interactions are first).

        Args:
            org_id (str): Short UUID string identifying the organization.
            user_id (str): Short UUID string identifying the user.
            with_their_messages (bool): Whether to include messages of the interactions.
            skip (int): Number of interactions to skip. (Useful for pagination)
            limit (int): Maximum number of interactions to retrieve. (Useful for pagination)

        Returns:
            List[Dict[str, str]], each dict containing interaction details and messages (or [] if `with_their_messages` is False):

                + interaction: Interaction Data like created_at, updated_at, interaction_id, ...
                + messages: List of messages in order (each message is a dict with role, content, msg_position)
        """
        pass

    @abstractmethod
    async def delete_user_interaction_and_its_memories(
        self,
        org_id: str,
        user_id: str,
        interaction_id: str,
    ) -> None:
        """
        Deletes an interaction record and its associated memories.

        Args:
            org_id (str): Short UUID string identifying the organization.
            user_id (str): Short UUID string identifying the user.
            interaction_id (str): Short UUID string identifying the interaction to delete.

        Note:
            If the graph database is associated with a vector database, the memories are also deleted there for data consistency.
        """
        pass

    @abstractmethod
    async def delete_all_user_interactions_and_their_memories(
        self,
        org_id: str,
        user_id: str,
    ) -> None:
        """
        Deletes all interactions and their associated memories for a specific user in an organization.

        Args:
            org_id (str): Short UUID string identifying the organization
            user_id (str): Short UUID string identifying the user whose interactions should be deleted

        Note:
            If the graph database is associated with a vector database, the memories are also deleted there for data consistency.
        """
        pass

    # Memory methods
    def fetch_user_memories_resolved(
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
        pass

    def fetch_user_memories_resolved_batch(
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
        pass

    @abstractmethod
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
        pass

    @abstractmethod
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
        pass

    @abstractmethod
    async def get_all_user_memories(
        self, org_id: str, user_id: str, agent_id: Optional[str] = None
    ) -> List[Dict[str, str]]:
        """
        Retrieves all memories associated with a specific user.

        Args:
            org_id (str): Short UUID string identifying the organization
            user_id (str): Short UUID string identifying the user
            agent_id (Optional[str]): Optional Short UUID string identifying the agent. If provided, only memories obtained from
                interactions with this agent are returned.
                Otherwise, all memories associated with the user are returned.

        Returns:
            List[Dict[str, str]] containing memory details:

                + memory_id: UUID string identifying the memory
                + memory: String content of the memory
                + obtained_at: ISO format timestamp of when the memory was obtained
        """
        pass

    @abstractmethod
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
        pass

    @abstractmethod
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
        pass
