from typing_extensions import override
import shortuuid
import neo4j

from ..base import BaseGraphDB

from typing import Dict, List


class Neo4jOrganization(BaseGraphDB):

    @override
    async def create_organization(self, org_name: str) -> Dict[str, str]:
        """
        Creates a new organization in the Neo4j graph database.

        Args:
            org_name (str): The name of the organization to create.

        Returns:
            Dict[str, str] containing:

                + org_id: Short UUID string
                + org_name: Organization name
                + created_at: ISO format timestamp
        """

        org_id = shortuuid.uuid()

        async def create_org_tx(tx):
            result = await tx.run(
                """
                CREATE (o:Org {
                    org_id: $org_id,
                    org_name: $org_name,
                    created_at: datetime()
                })
                RETURN o{.org_id, .org_name, created_at: toString(o.created_at)} as org
            """,
                org_id=org_id,
                org_name=org_name,
            )

            record = await result.single()
            return record["org"]

        async with self.driver.session(
            database=self.database, default_access_mode=neo4j.WRITE_ACCESS
        ) as session:
            org_data = await session.execute_write(create_org_tx)
            return org_data

    @override
    async def update_organization(
        self, org_id: str, new_org_name: str
    ) -> Dict[str, str]:
        """
        Updates an existing organization in the Neo4j graph database.

        Args:
            org_id (str): The Short UUID of the organization to update.
            new_org_name (str): The new name for the organization.

        Returns:
            Dict[str, str] containing:

                + org_id: Short UUID string
                + org_name: Organization name
        """

        async def update_org_tx(tx):
            result = await tx.run(
                """
                MATCH (o:Org {org_id: $org_id})
                SET o.org_name = $new_org_name
                RETURN o{.org_id, .org_name} as org
            """,
                org_id=org_id,
                new_org_name=new_org_name,
            )

            record = await result.single()
            return record["org"]

        async with self.driver.session(
            database=self.database, default_access_mode=neo4j.WRITE_ACCESS
        ) as session:
            org_data = await session.execute_write(update_org_tx)
            return org_data

    @override
    async def delete_organization(self, org_id: str) -> None:
        """
        Deletes an organization from the Neo4j graph database.

        Warning:
            This operation will delete all nodes and relationships from this organization
            including users, agents, memories, interactions etc.

        Args:
            org_id (str): Short UUID string identifying the organization to delete.
        """

        async def delete_org_tx(tx):
            # Delete all nodes and relationships associated with the org
            await tx.run(
                """
                CALL apoc.periodic.iterate("
                MATCH (o:Org {org_id: $org_id})
                CALL apoc.path.subgraphNodes(o, {}) YIELD node
                RETURN node",
                "DETACH DELETE node",
                {batchSize: 1000, parallel: true, params: {org_id: $org_id}})
            """,
                org_id=org_id,
            )

        async with self.driver.session(
            database=self.database, default_access_mode=neo4j.WRITE_ACCESS
        ) as session:
            await session.execute_write(delete_org_tx)

    @override
    async def get_organization(self, org_id: str) -> Dict[str, str]:
        """
        Gets a specific organization from the Neo4j graph database.

        Args:
            org_id (str): Short UUID string identifying the organization to retrieve.

        Returns:
            Dict[str, str] containing:

                + org_id: Short UUID string
                + org_name: Organization name
                + created_at: ISO format timestamp
        """

        async def get_org_tx(tx):
            result = await tx.run(
                """
                MATCH (o:Org {org_id: $org_id})
                RETURN o{.org_id, .org_name, created_at: toString(o.created_at)} as org
            """,
                org_id=org_id,
            )
            record = await result.single()
            return record["org"]

        async with self.driver.session(
            database=self.database, default_access_mode=neo4j.READ_ACCESS
        ) as session:
            org_data = await session.execute_read(get_org_tx)
            return org_data

    @override
    async def get_all_organizations(self) -> List[Dict[str, str]]:
        """
        Gets all organizations from the graph database.

        Returns:
            List[Dict[str, str]] each containing:

                + org_id: Short UUID string
                + org_name: Organization name
                + created_at: ISO format timestamp
        """

        async def get_all_org_tx(tx):
            result = await tx.run(
                """
                MATCH (o:Org)
                RETURN o{.org_id, .org_name, created_at: toString(o.created_at)} as org
            """
            )
            records = await result.value("org", [])
            return records

        async with self.driver.session(
            database=self.database, default_access_mode=neo4j.READ_ACCESS
        ) as session:
            org_data = await session.execute_read(get_all_org_tx)
            return org_data
