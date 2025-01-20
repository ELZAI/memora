from typing import Dict, List, Optional

import neo4j
import shortuuid
from typing_extensions import override

from ..base import BaseGraphDB


class Neo4jAgent(BaseGraphDB):

    @override
    async def create_agent(
        self, org_id: str, agent_name: str, user_id: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Creates a new agent in the Neo4j graph database.

        Args:
            org_id (str): Short UUID string identifying the organization.
            agent_name (str): name for the agent.
            user_id (Optional[str]): Optional Short UUID of the user. This is used when the agent is created
                specifically for a user, indicating that both the organization and the
                user will have this agent.

        Returns:
            Dict[str, str] containing:

                + org_id: Short UUID string
                + user_id: Optional Short UUID string
                + agent_id: Short UUID string
                + agent_name: Agent name
                + created_at: ISO format timestamp
        """

        agent_id = shortuuid.uuid()

        async def create_agent_tx(tx):
            if user_id:
                result = await tx.run(
                    """
                    MATCH (o:Org {org_id: $org_id}), (u:User {org_id: $org_id, user_id: $user_id})
                    CREATE (a:Agent {
                        org_id: $org_id,
                        user_id: $user_id,
                        agent_id: $agent_id,
                        agent_name: $agent_name,
                        created_at: datetime()
                    })
                    CREATE (o)-[:HAS_AGENT]->(a)
                    CREATE (u)-[:HAS_AGENT]->(a)
                    RETURN a{.org_id, .user_id, .agent_id, .agent_name, created_at: toString(a.created_at)} as agent
                """,
                    org_id=org_id,
                    user_id=user_id,
                    agent_id=agent_id,
                    agent_name=agent_name,
                )
            else:
                result = await tx.run(
                    """
                    MATCH (o:Org {org_id: $org_id})
                    CREATE (a:Agent {
                        org_id: $org_id,
                        agent_id: $agent_id,
                        agent_name: $agent_name,
                        created_at: datetime()
                    })
                    CREATE (o)-[:HAS_AGENT]->(a)
                    RETURN a{.org_id, .agent_id, .agent_name, created_at: toString(a.created_at)} as agent
                """,
                    org_id=org_id,
                    agent_id=agent_id,
                    agent_name=agent_name,
                )

            record = await result.single()
            return record["agent"]

        async with self.driver.session(
            database=self.database, default_access_mode=neo4j.WRITE_ACCESS
        ) as session:
            agent_data = await session.execute_write(create_agent_tx)
            return agent_data

    @override
    async def update_agent(
        self, org_id: str, agent_id: str, new_agent_name: str
    ) -> Dict[str, str]:
        """
        Updates an existing agent in the Neo4j graph database.

        Args:
            org_id (str): Short UUID string identifying the organization.
            agent_id (str): Short UUID string identifying the agent to update.
            new_agent_name (str): New name for the agent.

        Returns:
            Dict[str, str] containing:

                + org_id: Short UUID string
                + agent_id: Short UUID string
                + agent_name: Agent name
        """

        async def update_agent_tx(tx):
            result = await tx.run(
                """
                MATCH (a:Agent {org_id: $org_id, agent_id: $agent_id})
                SET a.agent_name = $new_agent_name
                RETURN a{.org_id, .agent_id, .agent_name} as agent
            """,
                org_id=org_id,
                agent_id=agent_id,
                new_agent_name=new_agent_name,
            )

            record = await result.single()
            return record["agent"]

        async with self.driver.session(
            database=self.database, default_access_mode=neo4j.WRITE_ACCESS
        ) as session:
            agent_data = await session.execute_write(update_agent_tx)
            return agent_data

    @override
    async def delete_agent(self, org_id: str, agent_id: str) -> None:
        """
        Deletes an agent from the Neo4j graph database.

        Args:
            org_id (str): Short UUID string identifying the organization.
            agent_id (str): Short UUID string identifying the agent to delete.
        """

        async def delete_agent_tx(tx):
            # Using node key (org_id, agent_id) for faster lookup
            await tx.run(
                """
                MATCH (a:Agent {org_id: $org_id, agent_id: $agent_id})
                DETACH DELETE a
            """,
                org_id=org_id,
                agent_id=agent_id,
            )

        async with self.driver.session(
            database=self.database, default_access_mode=neo4j.WRITE_ACCESS
        ) as session:
            await session.execute_write(delete_agent_tx)

    @override
    async def get_agent(self, org_id: str, agent_id: str) -> Dict[str, str]:
        """
        Gets a specific agent belonging to the specified organization from the Neo4j graph database.

        Args:
            org_id (str): Short UUID string identifying the organization.
            agent_id (str): Short UUID string identifying the agent to retrieve.

        Returns:
            Dict[str, str] containing:

                + org_id: Short UUID string
                + user_id: Optional Short UUID string if agent is associated with a user [:HAS_AGENT].
                + agent_id: Short UUID string
                + agent_name: Agent name
                + created_at: ISO format timestamp
        """

        async def get_agent_tx(tx):
            result = await tx.run(
                """
                MATCH (a:Agent {org_id: $org_id, agent_id: $agent_id})
                RETURN a{.org_id, .user_id, .agent_id, .agent_name, created_at: toString(a.created_at)} as agent
            """,
                org_id=org_id,
                agent_id=agent_id,
            )
            record = await result.single()
            return record["agent"]

        async with self.driver.session(
            database=self.database, default_access_mode=neo4j.READ_ACCESS
        ) as session:
            return await session.execute_read(get_agent_tx)

    @override
    async def get_all_org_agents(self, org_id: str) -> List[Dict[str, str]]:
        """
        Gets all agents belonging to the specified organization from the Neo4j graph database.

        Args:
            org_id (str): Short UUID string identifying the organization.

        Returns:
            A List[Dict[str, str]], each containing:

                + org_id: Short UUID string
                + agent_id: Short UUID string
                + agent_name: Agent name
                + created_at: ISO format timestamp
        """

        async def get_org_agents_tx(tx):
            result = await tx.run(
                """
                MATCH (o:Org {org_id: $org_id})-[:HAS_AGENT]->(a:Agent)
                RETURN a{.org_id, .agent_id, .agent_name, created_at: toString(a.created_at)} as agent
            """,
                org_id=org_id,
            )
            records = await result.value("agent", [])
            return records

        async with self.driver.session(
            database=self.database, default_access_mode=neo4j.READ_ACCESS
        ) as session:
            agents = await session.execute_read(get_org_agents_tx)
            return agents

    @override
    async def get_all_user_agents(
        self, org_id: str, user_id: str
    ) -> List[Dict[str, str]]:
        """
        Gets all agents for a user within an organization from the Neo4j graph database.

        Args:
            org_id (str): Short UUID string identifying the organization.
            user_id (str): Short UUID string identifying the user.

        Returns:
            A List[Dict[str, str]], each containing:

                + org_id: Short UUID string
                + user_id: Short UUID string
                + agent_id: Short UUID string
                + agent_name: Agent name
                + created_at: ISO format timestamp
        """

        async def get_user_agents_tx(tx):
            result = await tx.run(
                """
                MATCH (u:User {org_id: $org_id, user_id: $user_id})-[:HAS_AGENT]->(a:Agent)
                RETURN a{.org_id, .user_id, .agent_id, .agent_name, created_at: toString(a.created_at)} as agent
            """,
                org_id=org_id,
                user_id=user_id,
            )
            records = await result.value("agent", [])
            return records

        async with self.driver.session(
            database=self.database, default_access_mode=neo4j.READ_ACCESS
        ) as session:
            agents = await session.execute_read(get_user_agents_tx)
            return agents
