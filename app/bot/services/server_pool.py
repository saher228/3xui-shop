import logging
from dataclasses import dataclass
from typing import Optional

from py3xui import AsyncApi
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from app.config import Config
from app.db.models import Server, User

logger = logging.getLogger(__name__)


@dataclass
class Connection:
    server: Server
    api: AsyncApi


class ServerPoolService:
    def __init__(self, config: Config, session: async_sessionmaker) -> None:
        self.config = config
        self.session = session
        self._servers: dict[int, Connection] = {}
        logger.info("Server Pool Service initialized.")

    async def _add_server(self, server: Server, session: Optional[AsyncSession] = None) -> None:
        if server.id not in self._servers:
            api = AsyncApi(
                host=server.host,
                username=self.config.xui.USERNAME,
                password=self.config.xui.PASSWORD,
                token=self.config.xui.TOKEN,
                logger=logging.getLogger(f"xui_{server.name}"),
            )
            try:
                await api.login()
                server.online = True
                server_conn = Connection(server=server, api=api)
                self._servers[server.id] = server_conn
                logger.info(f"Server {server.name} ({server.host}) added to pool successfully.")
            except Exception as exception:
                server.online = False
                logger.error(f"Failed to add server {server.name} ({server.host}): {exception}")

            async def _update_server_status(s: AsyncSession):
                await Server.update(session=s, name=server.name, online=server.online)

            if session:
                await _update_server_status(session)
            else:
                async with self.session() as new_session:
                    await _update_server_status(new_session)

    def _remove_server(self, server: Server) -> None:
        if server.id in self._servers:
            try:
                del self._servers[server.id]
            except Exception as exception:
                logger.error(f"Failed to remove server {server.name}: {exception}")

    async def refresh_server(self, server: Server, session: Optional[AsyncSession] = None) -> None:
        if server.id in self._servers:
            self._remove_server(server)
        await self._add_server(server, session=session)
        logger.info(f"Server {server.name} reinitialized successfully.")

    async def get_inbound_id(self, api: AsyncApi) -> int | None:
        try:
            inbounds = await api.inbound.get_list()
        except Exception as exception:
            logger.error(f"Failed to fetch inbounds: {exception}")
            return None
        return inbounds[0].id

    async def get_connection(self, user: User, session: Optional[AsyncSession] = None) -> Connection | None:
        await self.sync_servers(session=session)

        if not user.server_id:
            logger.debug(f"User {user.tg_id} not assigned to any server.")
            return None

        if user.server_id not in self._servers:
            logger.warning(f"Server {user.server_id} not found in active pool. Attempting to reconnect.")
            async with self.session() as session:
                server_from_db = await Server.get_by_id(session=session, id=user.server_id)
            if server_from_db:
                await self._add_server(server_from_db)
            else:
                logger.error(f"Server {user.server_id} for user {user.tg_id} not found in DB either.")
                return None
            
        connection = self._servers.get(user.server_id)

        if not connection:
            available_servers = list(self._servers.keys())
            logger.critical(
                f"Server {user.server_id} not found in pool even after sync/reconnect attempt. "
                f"User assigned server: {user.server_id}, "
                f"Available servers in pool: {available_servers}"
            )
            return None

        async with self.session() as session:
            refreshed_server = await Server.get_by_id(session=session, id=user.server_id)
            if refreshed_server:
                connection.server = refreshed_server
            else:
                logger.error(f"Could not refresh server data for {user.server_id} from DB.")
        return connection

    async def sync_servers(self, session: Optional[AsyncSession] = None) -> None:
        db_servers = []
        if session:
            db_servers = await Server.get_all(session)
        else:
            async with self.session() as new_session:
                db_servers = await Server.get_all(new_session)

        if not db_servers and not self._servers:
            logger.warning("No servers found in the database.")
            return

        db_server_map = {server.id: server for server in db_servers}

        for server_id in list(self._servers.keys()):
            if server_id not in db_server_map:
                self._remove_server(self._servers[server_id].server)

        for server_id, conn in list(self._servers.items()):
            if db_server := db_server_map.get(server_id):
                conn.server = db_server
            await self.refresh_server(conn.server, session=session)

        for server in db_servers:
            if server.id not in self._servers:
                await self._add_server(server, session=session)

        logger.info(f"Sync complete. Currently active servers: {len(self._servers)}")

    async def assign_server_to_user(self, user: User, session: AsyncSession, location: Optional[str] = None) -> User | None:
        server = await self.get_available_server(session=session, location=location)
        if not server:
            logger.error(f"Failed to assign server to user {user.tg_id}: No available server found for location '{location}'.")
            return None
        
        user.server_id = server.id
        logger.info(f"User {user.tg_id} assigned to server {server.id} ({server.name}) in location '{location or 'any'}'.")
        return user

    async def get_all_servers(self) -> list[Server]:
        """Get all servers from the database."""
        async with self.session() as session:
            return await Server.get_all(session)

    async def get_available_server(
        self, session: Optional[AsyncSession] = None, location: Optional[str] = None
    ) -> Server | None:
        """Get an available server, optionally filtered by location."""
        await self.sync_servers(session=session)

        available_servers = [
            conn.server
            for conn in self._servers.values()
            if conn.server.online
            and (location is None or conn.server.location == location)
        ]

        if not available_servers:
            return None

        # Приоритет для сервера "Тут указывать название сервера который будет выдаваться первым для пробной подписки"
        priority_server = next(
            (
                s
                for s in available_servers
                if s.name == "🇳🇱 Нидерланды"
                and s.current_clients < s.max_clients
            ),
            None,
        )
        if priority_server:
            logger.debug(
                f"Found priority server with free slots: {priority_server.name} "
                f"(clients: {priority_server.current_clients}/{priority_server.max_clients})"
            )
            return priority_server

        servers_with_free_slots = [
            server
            for server in available_servers
            if server.current_clients < server.max_clients
        ]

        if servers_with_free_slots:
            server = sorted(servers_with_free_slots, key=lambda s: s.current_clients)[
                0
            ]
            logger.debug(
                f"Found server with free slots: {server.name} "
                f"(clients: {server.current_clients}/{server.max_clients})"
            )
            return server

        if available_servers:
            server = sorted(available_servers, key=lambda s: s.current_clients)[0]
            logger.warning(
                f"No servers with free slots. Using least loaded server: {server.name} "
                f"(clients: {server.current_clients}/{server.max_clients})"
            )
            return server

        logger.critical("No available servers found in pool")
        return None

    async def get_location_name_by_index(self, location_idx_str: str) -> str | None:
        """Get location name from its index in the sorted list of unique locations."""
        try:
            location_idx = int(location_idx_str)
        except (ValueError, TypeError):
            logger.error(f"Invalid location index string: {location_idx_str}")
            return None

        all_servers = await self.get_all_servers()
        unique_locations = sorted(list(set(s.location for s in all_servers if s.location and s.online)))

        if not 0 <= location_idx < len(unique_locations):
            logger.error(f"Location index {location_idx} out of bounds (max: {len(unique_locations)-1})")
            return None

        return unique_locations[location_idx]
