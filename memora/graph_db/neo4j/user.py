import shortuuid
import neo4j
from typing import Dict, List
from typing_extensions import override

from ..base import BaseGraphDB

class Neo4jUser(BaseGraphDB):

    @override
    async def create_user(self, org_id: str, user_name: str) -> Dict[str, str]:
        
        user_id = shortuuid.uuid()
        
        async def create_user_tx(tx):
            result = await tx.run("""
                MATCH (o:Org {org_id: $org_id})
                CREATE (u:User {
                    org_id: $org_id,
                    user_id: $user_id,
                    user_name: $user_name,
                    created_at: datetime()
                })
                CREATE (u)-[:BELONGS_TO]->(o)
                CREATE (ic:InteractionCollection {
                    org_id: $org_id,
                    user_id: $user_id
                })
                CREATE (mc:MemoryCollection {
                    org_id: $org_id,
                    user_id: $user_id
                })
                CREATE (u)-[:INTERACTIONS_IN]->(ic)
                CREATE (u)-[:HAS_MEMORIES]->(mc)
                RETURN u{.org_id, .user_id, .user_name, created_at: toString(u.created_at)} as user
            """, org_id=org_id, user_id=user_id, user_name=user_name)
            record = await result.single()
            return record["user"]

        async with self.driver.session(database=self.database, default_access_mode=neo4j.WRITE_ACCESS) as session:
            user_data = await session.execute_write(create_user_tx)
            return user_data

    @override
    async def delete_user(self, org_id: str, user_id: str) -> None:

        async def delete_user_tx(tx):
            await tx.run("""
                MATCH (u:User {org_id: $org_id, user_id: $user_id})
                OPTIONAL MATCH (u)-[:INTERACTIONS_IN]->(interactioncollection)
                OPTIONAL MATCH (interactioncollection)-[:HAD_INTERACTION]->(interaction)
                OPTIONAL MATCH (interaction)-[:FIRST_MESSAGE|IS_NEXT*]->(message)
                OPTIONAL MATCH (u)-[:HAS_MEMORIES]->(memcollection)
                OPTIONAL MATCH (memcollection)-[:INCLUDES]->(memory)
                OPTIONAL MATCH (interaction)-[:HAS_OCCURRENCE_ON]->(date)
                DETACH DELETE u, interactioncollection, interaction, message, memcollection, memory, date
            """, org_id=org_id, user_id=user_id)

        async with self.driver.session(database=self.database, default_access_mode=neo4j.WRITE_ACCESS) as session:
            await session.execute_write(delete_user_tx)

    @override
    async def get_all_users(self, org_id: str) -> List[Dict[str, str]]:

        async def get_users_tx(tx):
            result = await tx.run("""
                MATCH (o:Org {org_id: $org_id})<-[:BELONGS_TO]-(u:User)
                RETURN u{.org_id, .user_id, .user_name, created_at: toString(u.created_at)} as user
            """, org_id=org_id)
            records = await result.fetch()
            return [record["user"] for record in records]

        async with self.driver.session(database=self.database, default_access_mode=neo4j.READ_ACCESS) as session:
            users = await session.execute_read(get_users_tx)
            return users