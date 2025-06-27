from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .server_pool import ServerPoolService

import logging
import uuid
import urllib.parse

from py3xui import Client, Inbound
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
from sqlalchemy import select

from app.bot.models import ClientData
from app.bot.utils.network import extract_base_url
from app.bot.utils.formatting import format_remaining_time
from app.bot.utils.time import (
    add_days_to_timestamp,
    days_to_timestamp,
    get_current_timestamp,
)
from app.config import Config
from app.db.models import Promocode, User, Server
from app.utils.security import SecurityHelper

logger = logging.getLogger(__name__)


class VPNService:
    def __init__(
        self,
        config: Config,
        session: async_sessionmaker,
        server_pool_service: ServerPoolService,
    ) -> None:
        self.config = config
        self.session = session
        self.server_pool_service = server_pool_service
        logger.info("VPN Service initialized.")

    async def is_client_exists(self, user: User, session: Optional[AsyncSession] = None) -> Client | None:
        connection = await self.server_pool_service.get_connection(user, session=session)

        if not connection:
            return None

        try:
            inbounds = await connection.api.inbound.get_list()
            if not inbounds:
                logger.error(f"No inbounds found for user {user.tg_id}")
                return None

            for inbound in inbounds:
                for client in inbound.settings.clients:
                    if client.email == str(user.tg_id):
                        logger.debug(f"Found client {user.tg_id} in inbound {inbound.id} with state: {client.enable}")
                        return client

            logger.critical(f"Client {user.tg_id} not found in any inbound on server {connection.server.name}.")
            return None
        except Exception as e:
            logger.error(f"Error checking client existence for {user.tg_id}: {e}")
            return None

    async def get_limit_ip(self, user: User, client: Client) -> int | None:
        connection = await self.server_pool_service.get_connection(user)

        if not connection:
            return None

        try:
            inbounds: list[Inbound] = await connection.api.inbound.get_list()
        except Exception as exception:
            logger.error(f"Failed to fetch inbounds: {exception}")
            return None

        for inbound in inbounds:
            for inbound_client in inbound.settings.clients:
                if inbound_client.email == client.email:
                    logger.debug(f"Client {client.email} limit ip: {inbound_client.limit_ip}")
                    return inbound_client.limit_ip

        logger.critical(f"Client {client.email} not found in inbounds.")
        return None

    async def get_client_data(self, user: User, session: Optional[AsyncSession] = None) -> ClientData | None:
        logger.debug(f"Starting to retrieve client data for {user.tg_id}.")

        connection = await self.server_pool_service.get_connection(user, session=session)

        if not connection:
            return None

        try:
            client = await connection.api.client.get_by_email(str(user.tg_id))

            if not client:
                logger.critical(
                    f"Client {user.tg_id} not found on server {connection.server.name}."
                )
                return None

            limit_ip = await self.get_limit_ip(user=user, client=client)
            max_devices = -1 if limit_ip == 0 else limit_ip
            traffic_total = client.total
            expiry_time = -1 if client.expiry_time == 0 else client.expiry_time

            if traffic_total <= 0:
                traffic_remaining = -1
                traffic_total = -1
            else:
                traffic_remaining = client.total - (client.up + client.down)

            traffic_used = client.up + client.down
            client_data = ClientData(
                max_devices=max_devices,
                traffic_total=traffic_total,
                traffic_remaining=traffic_remaining,
                traffic_used=traffic_used,
                traffic_up=client.up,
                traffic_down=client.down,
                expiry_timestamp=expiry_time,
                expiry_time_str=format_remaining_time(expiry_time)
            )
            logger.debug(f"Successfully retrieved client data for {user.tg_id}: {client_data}.")
            return client_data
        except Exception as exception:
            logger.error(f"Error retrieving client data for {user.tg_id}: {exception}")
            return None

    async def get_key(self, user: User, session: Optional[AsyncSession] = None) -> str | None:
        if not user.server_id:
            logger.debug(f"Server ID for user {user.tg_id} not found in the provided user object.")
            return None

        server = user.server
        if not server:
            if not session:
                async with self.session() as new_session:
                    server = await Server.get_by_id(new_session, user.server_id)
            else:
                server = await Server.get_by_id(session, user.server_id)

        if not server:
            logger.error(f"Could not find Server with id {user.server_id} for user {user.tg_id}")
            return None

        connection = await self.server_pool_service.get_connection(user, session=session)
        if not connection:
            logger.error(f"Could not establish connection to server for user {user.tg_id}")
            return None
            
        try:
            inbounds = await connection.api.inbound.get_list()
            if not inbounds:
                logger.error(f"No inbounds found on server {server.name} for user {user.tg_id}")
                return None

            inbound = inbounds[0]
            
            port = inbound.port
            protocol = inbound.protocol
            stream_settings = inbound.stream_settings
            if not stream_settings:
                logger.error(f"No stream settings found in inbound for user {user.tg_id}")
                return None
                
            network = stream_settings.network or "tcp"
            security = stream_settings.security or "none"
            
            uuid_ = user.vpn_id
            
            parsed_url = urllib.parse.urlparse(server.host)
            host = parsed_url.hostname or server.host
            
            remarks = f"INZEWORLD VPN-{user.tg_id}"
            encoded_remarks = urllib.parse.quote(remarks)

            key = f"{protocol}://{uuid_}@{host}:{port}?type={network}&security={security}#{encoded_remarks}"
            
            logger.debug(f"Fetched key for {user.tg_id}: {key}.")
            return key

        except Exception as e:
            logger.error(f"Error generating VLESS key for user {user.tg_id}: {e}", exc_info=True)
            return None

    async def create_client(
        self,
        user: User,
        devices: int,
        duration: int,
        session: AsyncSession,
        location_name: Optional[str] = None,
        enable: bool = True,
        flow: str = "",
        total_gb: int = 0,
        inbound_id: int = 1,
        expiry_time_ms: Optional[int] = None,
    ) -> User | None:
        logger.info(f"Attempting to create/update client for user {user.tg_id}...")

        if not user.server_id:
            logger.info(
                f"User {user.tg_id} has no server_id. Attempting to assign one (location hint: {location_name})."
            )
            updated_user = await self.server_pool_service.assign_server_to_user(
                user, session, location_name
            )
            if not updated_user:
                logger.error(f"Failed to assign a server to user {user.tg_id}.")
                return None
            user = updated_user

        connection = await self.server_pool_service.get_connection(
            user, session=session
        )
        if not connection:
            logger.error(
                f"Failed to get connection to assigned server {user.server_id} for user {user.tg_id}."
            )
            return None

        full_client_details = await self.is_client_exists(user, session)
        if full_client_details:
            logger.info(
                f"Client {user.tg_id} already exists in an inbound. Proceeding to update."
            )
            success = await self.update_client(
                user=user,
                devices=devices,
                duration=duration,
                replace_devices=True,
                replace_duration=True,
                enable=True,
            )
            if not success:
                logger.error(f"Failed to update existing client {user.tg_id}.")
                return None

            if user.vpn_id != full_client_details.id:
                user.vpn_id = full_client_details.id
                session.add(user)
                await session.commit()
            return user

        zombie_client_stats = await connection.api.client.get_by_email(str(user.tg_id))
        if zombie_client_stats:
            logger.warning(
                f"Found a zombie client for user {user.tg_id}. Deleting it before creating a new one."
            )
            inbounds = await connection.api.inbound.get_list()
            if inbounds and user.vpn_id:
                inbound_id_for_delete = inbounds[0].id
                try:
                    await connection.api.client.delete(
                        inbound_id=inbound_id_for_delete, client_uuid=user.vpn_id
                    )
                    logger.info(
                        f"Successfully deleted zombie client {user.tg_id} from inbound {inbound_id_for_delete} using stored vpn_id."
                    )
                except Exception as e:
                    logger.error(
                        f"Failed to delete zombie client {user.tg_id} using stored vpn_id {user.vpn_id}: {e}"
                    )
            elif not user.vpn_id:
                logger.error(f"Cannot delete zombie for {user.tg_id}: user.vpn_id is not set.")

        client_uuid = str(uuid.uuid4())
        user.vpn_id = client_uuid

        final_expiry_time_ms = 0
        if expiry_time_ms is not None:
            final_expiry_time_ms = expiry_time_ms
        elif duration > 0:
            final_expiry_time_ms = add_days_to_timestamp(
                timestamp=get_current_timestamp(), days=duration
            )

        client = Client(
            email=str(user.tg_id),
            id=client_uuid,
            enable=enable,
            flow=flow,
            limit_ip=devices,
            total_gb=total_gb,
            expiry_time=final_expiry_time_ms,
        )
        logger.debug(f"Client object for creation: {client}")

        try:
            inbounds = await connection.api.inbound.get_list()
            if not inbounds:
                logger.error("No inbounds found to create the client in.")
                return None

            target_inbound_id = inbounds[0].id
            await connection.api.client.add(inbound_id=target_inbound_id, clients=[client])
            logger.info(
                f"Successfully created new client {user.tg_id} on server {connection.server.name} in inbound {target_inbound_id}."
            )
            return user
        except Exception as e:
            logger.error(f"Error creating client for {user.tg_id}: {e}", exc_info=True)
            return None

    async def delete_client(self, user: User, server_id_override: Optional[int] = None) -> bool:
        """Deletes a client from their assigned server or a specified server."""
        logger.info(f"Attempting to delete client for user {user.tg_id} (VPN ID: {user.vpn_id}).")
        
        target_server_id = server_id_override if server_id_override is not None else user.server_id

        if not target_server_id:
            logger.warning(f"Cannot delete client for user {user.tg_id}: No server_id associated or provided.")
            return False 

        
        connection = None
        if server_id_override:
            logger.warning(f"Deleting client from specific server {server_id_override} needs ServerPoolService.get_connection_by_id(id) or similar.")
            temp_server_for_delete = None
            async with self.session() as session:
                temp_server_for_delete = await Server.get_by_id(session, target_server_id)
            
            if temp_server_for_delete and temp_server_for_delete.online:
                from py3xui import AsyncApi as TempApi
                api_for_delete = TempApi(
                    host=temp_server_for_delete.host,
                    username=self.config.xui.USERNAME,
                    password=self.config.xui.PASSWORD,
                    token=self.config.xui.TOKEN,
                    logger=logging.getLogger(f"xui_delete_{temp_server_for_delete.name}")
                )
                try:
                    await api_for_delete.login()
                    inbounds_on_old_server = await api_for_delete.inbound.get_list()
                    if not inbounds_on_old_server:
                        logger.error(f"No inbounds found on server {target_server_id} for deleting client {user.tg_id}.")
                        return False
                    inbound_id_for_delete = inbounds_on_old_server[0].id

                    await api_for_delete.client.delete(inbound_id=inbound_id_for_delete, client_uuid=user.vpn_id)
                    logger.info(f"Successfully deleted client {user.tg_id} (VPN ID: {user.vpn_id}) from server {target_server_id} (using override). Inbound: {inbound_id_for_delete}")
                    return True
                except Exception as e:
                    logger.error(f"Error deleting client {user.tg_id} from server {target_server_id} (using override): {e}")
                    return False
            else:
                logger.error(f"Server {target_server_id} for override not found or not online.")
                return False
        else:
            connection = await self.server_pool_service.get_connection(user)

        if not connection:
            logger.warning(f"Cannot delete client for user {user.tg_id} on server {target_server_id}: No connection could be established.")
            return False 

        try:
            existing_client = await connection.api.client.get_by_email(str(user.tg_id))
            if not existing_client:
                logger.info(f"Client {user.tg_id} not found on server {connection.server.name} (ID: {connection.server.id}). No deletion needed.")
                return True 

            inbound_id = await self.server_pool_service.get_inbound_id(connection.api)
            if inbound_id is None:
                logger.error(f"Could not determine inbound_id for server {connection.server.name} to delete client {user.tg_id}.")
                return False

            await connection.api.client.delete(inbound_id=inbound_id, client_uuid=user.vpn_id)
            logger.info(f"Successfully deleted client {user.tg_id} (VPN ID: {user.vpn_id}) from server {connection.server.name} (ID: {connection.server.id}). Inbound: {inbound_id}")
            return True
        except Exception as exception:
            logger.error(f"Error deleting client {user.tg_id} from server {connection.server.name} (ID: {connection.server.id}): {exception}")
            return False

    async def update_client(
        self,
        user: User,
        devices: Optional[int] = None,
        duration: Optional[int] = None,
        replace_devices: bool = False,
        replace_duration: bool = False,
        enable: Optional[bool] = None,
        flow: str = "",
        total_gb: Optional[int] = None,
    ) -> bool:
        logger.info(f"Updating client {user.tg_id} | Devices: {devices}, Duration: {duration}")
        connection = await self.server_pool_service.get_connection(user)

        if not connection:
            return False

        try:
            inbounds = await connection.api.inbound.get_list()
            if not inbounds:
                logger.error(f"No inbounds found for user {user.tg_id}")
                return False

            client_inbound_id = None
            existing_client = None

            for inbound in inbounds:
                for client in inbound.settings.clients:
                    if client.email == str(user.tg_id):
                        existing_client = client
                        client_inbound_id = inbound.id
                        break
                if existing_client:
                    break

            if not existing_client or client_inbound_id is None:
                logger.critical(f"Client {user.tg_id} not found in any inbound.")
                return False

            update_data = {
                "email": existing_client.email,
                "id": existing_client.id,
                "enable": existing_client.enable if enable is None else enable,
                "flow": flow if flow else existing_client.flow,
                "limit_ip": devices if devices is not None else existing_client.limit_ip,
                "total_gb": total_gb if total_gb is not None else existing_client.total_gb,
                "expiry_time": existing_client.expiry_time,
                "inbound_id": client_inbound_id
            }

            if duration is not None:
                if duration == 0:
                    update_data["expiry_time"] = 0
                else:
                    current_time = get_current_timestamp()
                    current_expiry = existing_client.expiry_time
                    
                    if current_expiry <= current_time:
                        base_time = current_time
                    else:
                        base_time = current_expiry
                    
                    if not replace_duration:
                        update_data["expiry_time"] = add_days_to_timestamp(timestamp=base_time, days=duration)
                    else:
                        update_data["expiry_time"] = add_days_to_timestamp(timestamp=current_time, days=duration)

            client_to_update = Client(**update_data)

            try:
                await connection.api.client.update(
                    client_uuid=existing_client.id,
                    client=client_to_update
                )
                logger.info(f"Client {user.tg_id} updated successfully in inbound {client_inbound_id}")

                if isinstance(existing_client.id, str) and existing_client.id != user.vpn_id:
                    async with self.session() as session:
                        stmt = select(User).where(User.tg_id == user.tg_id)
                        db_user = (await session.execute(stmt)).scalar_one_or_none()
                        if db_user:
                            db_user.vpn_id = existing_client.id
                            session.add(db_user)
                            await session.commit()
                            logger.info(f"Updated vpn_id in database for user {user.tg_id} to {existing_client.id}")

                return True
            except Exception as e:
                logger.error(f"Error updating client {user.tg_id}: {e}", exc_info=True)
                return False
        except Exception as exception:
            logger.error(f"Error updating client {user.tg_id}: {exception}", exc_info=True)
            return False

    async def create_subscription(self, user: User, devices: int, duration: int, session: AsyncSession, location_name: Optional[str] = None) -> User | None:
        logger.info(f"Processing subscription creation for user {user.tg_id} with location hint '{location_name}'.")

        existing_client = await self.is_client_exists(user, session)
        
        if existing_client:
            logger.info(f"User {user.tg_id} has an existing client. Deciding whether to update or migrate.")
            current_server = await Server.get_by_id(session, user.server_id) if user.server_id else None

            if location_name and current_server and current_server.location != location_name:
                logger.info(f"Migrating user {user.tg_id} from '{current_server.location}' to '{location_name}'.")
                
                old_server_id = user.server_id
                old_vpn_id = user.vpn_id
                if old_server_id and old_vpn_id:
                    user_for_deletion = User(tg_id=user.tg_id, vpn_id=old_vpn_id)
                    delete_success = await self.delete_client(user_for_deletion, server_id_override=old_server_id)
                    if not delete_success:
                        logger.warning(f"Failed to delete client from old server {old_server_id}. A zombie client may be left.")

                user = await self.server_pool_service.assign_server_to_user(user, session, location=location_name)
                if not user:
                    logger.error(f"Failed to assign new server in '{location_name}' for user {user.tg_id}.")
                    return None
                
                zombie_client_on_dest = await self.is_client_exists(user, session)
                if zombie_client_on_dest and zombie_client_on_dest.id:
                    logger.warning(f"Found zombie client {zombie_client_on_dest.id} for user {user.tg_id} on destination server. Deleting.")
                    user_for_zombie_deletion = User(tg_id=user.tg_id, vpn_id=zombie_client_on_dest.id, server_id=user.server_id)
                    delete_zombie_success = await self.delete_client(user_for_zombie_deletion)
                    if not delete_zombie_success:
                        logger.error("Failed to delete zombie client from destination. Subsequent creation might fail.")
                
                logger.info(f"User {user.tg_id} migrated. Proceeding with client creation on new server.")

            else:
                logger.info(f"Reactivating/updating subscription for user {user.tg_id} on the same server.")
                updated = await self.update_client(
                    user=user,
                    devices=devices,
                    duration=duration,
                    replace_devices=True,
                    replace_duration=True,
                    enable=True,
                )
                if not updated:
                    logger.error(f"Failed to update existing client {user.tg_id}.")
                    return None
                
                if user.vpn_id != existing_client.id:
                    user.vpn_id = existing_client.id
                    session.add(user)
                    await session.commit()
                return user

        return await self.create_client(
            user=user,
            devices=devices,
            duration=duration,
            location_name=location_name,
            session=session
        )

    async def extend_subscription(self, user: User, devices: int, duration: int) -> bool:
        return await self.update_client(
            user=user,
            devices=devices,
            duration=duration,
            replace_devices=True,
            replace_duration=False
        )

    async def change_subscription(self, user: User, devices: int, duration: int, session: AsyncSession, location_name: Optional[str] = None) -> bool:
        logger.info(f"Changing subscription for user {user.tg_id}: devices={devices}, duration={duration}, location='{location_name}'.")

        current_server = await Server.get_by_id(session, user.server_id) if user.server_id else None

        if location_name and current_server and current_server.location != location_name:
            logger.info(f"Location change from '{current_server.location}' to '{location_name}' for user {user.tg_id}.")

            current_client_data = await self.get_client_data(user, session=session)
            if not current_client_data:
                logger.error(f"Cannot get current client data for {user.tg_id} to migrate.")
                return False

            old_server_id = user.server_id
            old_vpn_id = user.vpn_id

            user = await self.server_pool_service.assign_server_to_user(user, session, location=location_name)
            if not user:
                logger.error(f"Failed to assign new server in '{location_name}' for {user.tg_id}.")
                return False

            if old_server_id and old_vpn_id:
                logger.info(f"Deleting client {old_vpn_id} from old server {old_server_id}.")
                user_to_delete = User(tg_id=user.tg_id, vpn_id=old_vpn_id)
                delete_success = await self.delete_client(user_to_delete, server_id_override=old_server_id)
                if not delete_success:
                    logger.warning(f"Failed to delete client from old server {old_server_id}. A zombie client might be left.")

            created_user = await self.create_client(
                user=user,
                devices=devices,
                duration=duration,
                session=session,
                enable=not current_client_data.has_subscription_expired
            )
            return created_user is not None
        else: 
            logger.info(f"No location change for user {user.tg_id}, or new location is same as current.")
            return await self.update_client(
                user=user,
                devices=devices,
                duration=duration,
                replace_devices=True,
                replace_duration=False,
            )

    async def process_bonus_days(self, user: User, duration: int, devices: int, session: AsyncSession) -> User | None:
        if await self.is_client_exists(user):
            updated = await self.update_client(
                user=user,
                duration=duration,
                devices=devices,
                replace_devices=True,
                replace_duration=False
            )
            if updated:
                logger.info(f"Updated client {user.tg_id} with additional {duration} days(-s).")
                return user
        else:
            created_user = await self.create_client(user=user, devices=devices, duration=duration, session=session)
            if created_user:
                logger.info(f"Created client {user.tg_id} with additional {duration} days(-s)")
                return created_user

        return None

    async def activate_promocode(self, user: User, promocode: Promocode, session: AsyncSession) -> bool:
        logger.info(f"Activating promocode {promocode.code} for user {user.tg_id}.")

        client_data = await self.get_client_data(user, session=session)

        if not client_data:
            logger.error(f"Failed to activate promocode for {user.tg_id}: no client data.")
            return False

        if client_data.has_subscription_expired:
            logger.error(
                f"Failed to activate promocode for {user.tg_id}: subscription expired."
            )
            return False

        return await self.process_bonus_days(
            user=user, duration=promocode.duration, devices=client_data.max_devices, session=session
        )

    async def change_client_location(
        self,
        user: User,
        new_location_name: str,
        current_devices: int,
        session: AsyncSession,
    ) -> bool:
        logger.info(f"User {user.tg_id}: Initiating location change to '{new_location_name}'. Current devices: {current_devices}")

        if not user.server_id:
            logger.warning(f"User {user.tg_id} has no server_id. Cannot change location.")
            return False

        old_server_id = user.server_id
        old_vpn_id = user.vpn_id

        current_client_data = await self.get_client_data(user, session=session)
        if not current_client_data:
            logger.error(f"User {user.tg_id}: Could not get current client data for location change.")
            return False
        
        original_expiry_time_ms = current_client_data.expiry_timestamp
        original_is_enabled = not current_client_data.has_subscription_expired
        if hasattr(current_client_data, 'enable') and current_client_data.enable is not None:
            original_is_enabled = bool(current_client_data.enable)

        devices_for_xui = current_devices
        if devices_for_xui == -1:
            devices_for_xui = 0

        logger.info(f"User {user.tg_id}: Old server ID: {old_server_id}, Old VPN ID: {old_vpn_id}. Preserved expiry: {original_expiry_time_ms}ms, Enabled: {original_is_enabled}, Devices: {devices_for_xui}")

        expiry_time_to_preserve = original_expiry_time_ms if original_expiry_time_ms and original_expiry_time_ms > 0 else None

        updated_user = await self.server_pool_service.assign_server_to_user(user, session, location=new_location_name)
        if not updated_user:
            logger.warning(f"User {user.tg_id}: No server available in location '{new_location_name}'. Location change failed.")
            return False

        user = updated_user
        new_server = await Server.get_by_id(session, user.server_id)

        logger.info(f"User {user.tg_id}: Assigned to new server {new_server.id} ('{new_server.name}') in '{new_location_name}'.")

        if old_server_id and old_server_id != new_server.id:
            logger.info(f"User {user.tg_id}: Deleting client (VPN ID: {old_vpn_id}) from old server {old_server_id}.")
            delete_success = await self.delete_client(user, server_id_override=old_server_id)
            if not delete_success:
                logger.warning(f"User {user.tg_id}: Failed to delete client from old server {old_server_id}. Proceeding.")
        
        created_user = await self.create_client(
            user=user, 
            devices=devices_for_xui,
            duration=0, 
            session=session,
            location_name=new_server.name, 
            enable=original_is_enabled,
            expiry_time_ms=expiry_time_to_preserve
        )

        if not created_user:
            logger.error(f"User {user.tg_id}: Failed to create client on new server {new_server.id}. Critical failure.")
            return False

        logger.info(f"User {user.tg_id}: Successfully changed location to {new_location_name}.")
        return True

    async def enable_client(self, user: User) -> bool:
        """Enables a client on their assigned server."""
        logger.info(f"Attempting to enable client for user {user.tg_id}.")
        return await self._toggle_client_status(user, enable=True)

    async def disable_client(self, user: User) -> bool:
        """Disables a client on their assigned server."""
        logger.info(f"Attempting to disable client for user {user.tg_id}.")
        return await self._toggle_client_status(user, enable=False)

    async def _toggle_client_status(self, user: User, enable: bool) -> bool:
        """Internal method to enable or disable a client."""
        logger.info(f"Toggling client status for {user.tg_id} to {'enabled' if enable else 'disabled'}")
        
        return await self.update_client(user=user, enable=enable)
