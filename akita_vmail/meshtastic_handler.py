# -*- coding: utf-8 -*-
"""
File: meshtastic_handler.py
Description: Handles interaction with the Meshtastic device via the
             meshtastic-python library. Manages connection, sending,
             receiving, and processing of mesh packets according to the
             defined protocol. Reads config via protocol module.
"""
import meshtastic
import meshtastic.serial_interface
import meshtastic.tcp_interface
import meshtastic.util
from pubsub import pub
import serial.tools.list_ports
import serial
from datetime import datetime
import time
import threading
import logging
import queue

# Import protocol helpers (use runtime getters to avoid module-level constant binding)
try:
    from protocol import (
        BROADCAST_ADDR, create_chunk_payload, create_ack_payload,
        create_test_payload, create_complete_voice_payload,
        parse_payload, verify_chunk_crc, verify_complete_voice_crc,
        split_data_into_chunks, generate_unique_id,
        MSG_TYPE_VOICE_CHUNK, MSG_TYPE_ACK, MSG_TYPE_TEST,
        MSG_TYPE_COMPLETE_VOICE, get_private_app_port, get_chunk_retry_count, get_chunk_retry_delay
    )
except ImportError as e:
     logging.critical(f"FATAL: Cannot import from protocol module: {e}. Ensure protocol.py is present.")
     # Cannot proceed without protocol definitions
     raise SystemExit("Missing protocol definitions")


class MeshtasticHandler:
    """Manages connection and communication with a Meshtastic device."""

    def __init__(self, log_queue: queue.Queue, receive_callback: callable, config: dict | None = None):
        """
        Initialize the MeshtasticHandler.

        Args:
            log_queue: A queue for sending log messages to the GUI thread.
            receive_callback: Function in GUI class to call on message receipt.
                              Signature: receive_callback(msg_type, data, from_id, packet_id)
        """
        self.log_queue = log_queue
        self.receive_callback = receive_callback
        # Store provided config (fallback to cached config loader if not provided)
        self.config = config
        if self.config is None:
            try:
                from utils import get_config
                self.config = get_config() if get_config else {}
            except Exception:
                self.config = {}

        # Configuration is passed to protocol getters where needed; no module-level refresh.
        self.interface: meshtastic.MeshInterface | None = None # Type hint for clarity
        self.is_connected = False
        self.sending_active = False
        self.send_lock = threading.Lock()
        self._connection_thread = None
        self.node_list = {} # Store node info {nodeId: nodeInfoDict}

    def log(self, message: str, level=logging.INFO):
        """Log messages via the root logger (which uses the queue)."""
        if level == logging.DEBUG: logging.debug(message)
        elif level == logging.INFO: logging.info(message)
        elif level == logging.WARNING: logging.warning(message)
        elif level == logging.ERROR: logging.error(message)
        elif level == logging.CRITICAL: logging.critical(message)
        else: logging.log(level, message)

    def get_available_ports(self) -> list[str]:
        """Get a list of available serial COM ports."""
        try:
            ports = [port.device for port in serial.tools.list_ports.comports()]
            self.log(f"Available serial ports: {ports if ports else 'None found'}", logging.DEBUG)
            return ports
        except Exception as e:
            self.log(f"Error listing serial ports: {e}", logging.ERROR)
            return []

    def connect(self, target: str):
        """Initiate connection to a Meshtastic device in a separate thread."""
        if self.is_connected:
            self.log("Already connected.", logging.WARNING)
            return
        if not target:
            self.log("Connection target (COM port or IP address) is required.", logging.ERROR)
            self.receive_callback('status', 'Connection Failed: No target specified', None, None)
            return

        self.log(f"Starting connection attempt to {target}...")
        # Ensure previous thread finished if any
        if self._connection_thread and self._connection_thread.is_alive():
             self.log("Warning: Previous connection attempt still running.", logging.WARNING)
             return # Avoid multiple connection attempts concurrently

        self._connection_thread = threading.Thread(target=self._connect_worker, args=(target,), daemon=True)
        self._connection_thread.start()

    def _connect_worker(self, target: str):
        """Worker thread function to handle the actual connection logic."""
        success = False
        error_message = ""
        node_info_str = "N/A"
        local_node_list = {}

        try:
            self.log(f"Connecting to Meshtastic target: {target}...", logging.DEBUG)
            # Basic check for IP address format (very rudimentary)
            is_ip_like = '.' in target and all(p.isdigit() for p in target.split('.') if p)
            is_serial = any(s in target.upper() for s in ["COM", "/DEV/TTY", "/DEV/CU."]) or not is_ip_like

            if is_serial:
                self.log(f"Attempting Serial connection to {target}", logging.DEBUG)
                self.interface = meshtastic.serial_interface.SerialInterface(devPath=target, debugOut=None)
            else:
                self.log(f"Attempting TCP connection to {target}", logging.DEBUG)
                self.interface = meshtastic.tcp_interface.TCPInterface(hostname=target)

            self.log("Interface created. Waiting for node info...")
            # Wait for node DB and myInfo to populate (adjust timeout as needed)
            connect_start_time = time.time()
            while time.time() - connect_start_time < 10: # 10 second timeout
                 if self.interface and self.interface.myInfo and self.interface.nodes:
                     break
                 time.sleep(0.5)
            else: # Runs if loop finishes without break
                 self.log("Timed out waiting for node info after connection.", logging.WARNING)
                 # Continue anyway, info might arrive later

            if self.interface and self.interface.myInfo:
                 myinfo = self.interface.myInfo
                 hw_model = meshtastic.util.our_hw_model_name(myinfo.hw_model) if hasattr(myinfo, 'hw_model') else 'Unknown HW'
                 node_info_str = f"Node: !{myinfo.my_node_num:x} ({myinfo.long_name or 'N/A'}) HW:{hw_model}"
                 self.log(f"Successfully connected. {node_info_str}")
                 success = True

                 # Get node list
                 if self.interface.nodes:
                      local_node_list = self.interface.nodes.copy() # Get current nodes
                      self.log(f"Found {len(local_node_list)} nodes in mesh:")
                      for node_id, node_info in local_node_list.items():
                           user = node_info.get('user', {})
                           pos = node_info.get('position', {})
                           metrics = node_info.get('deviceMetrics', {})
                           last_heard = datetime.fromtimestamp(node_info['lastHeard']).strftime('%H:%M:%S') if 'lastHeard' in node_info else 'N/A'
                           node_str = (f"  - !{node_id:<9} ({user.get('longName', 'N/A'):<15} HW:{meshtastic.util.our_hw_model_name(user.get('hwModel')) if user.get('hwModel') else '?'}) "
                                       f"SNR:{metrics.get('snr', 'N/A'):>4.1f} RSSI:{metrics.get('rssi', 'N/A'):>4d} LastHeard:{last_heard}")
                           self.log(node_str)
                 else:
                      self.log("Node list not immediately available.", logging.DEBUG)

            else:
                 error_message = "Interface connected, but failed to get node info."
                 self.log(error_message, logging.WARNING)
                 success = False # Treat failure to get info as connection failure

            if success:
                pub.subscribe(self._on_receive_raw, "meshtastic.receive")
                pub.subscribe(self._on_connection_status, "meshtastic.connection.status")
                # Subscribe to node list changes
                pub.subscribe(self._on_node_update, "meshtastic.node.updated")
                self.log("Subscribed to Meshtastic events.")
                self.is_connected = True
                self.node_list = local_node_list # Store the node list

        except meshtastic.MeshtasticError as e:
            error_message = f"Meshtastic error connecting to {target}: {e}"
            self.log(error_message, logging.ERROR)
        except serial.serialutil.SerialException as e:
             error_message = f"Serial error connecting to {target}: {e}"
             self.log(error_message, logging.ERROR)
        except Exception as e:
            error_message = f"Unexpected error connecting to {target}: {e}"
            self.log(error_message, logging.ERROR)
            import traceback
            self.log(traceback.format_exc(), logging.ERROR)
        finally:
            if not success:
                 if self.interface: self.interface.close()
                 self.interface = None
                 self.is_connected = False

        # --- Notify the main thread about the connection result ---
        status_msg = f"Connected: {node_info_str}" if success else f"Connection Failed: {error_message}"
        self.receive_callback('status', status_msg, node_info_str if success else None, None)


    def disconnect(self):
        """Disconnect from the Meshtastic device and clean up."""
        if not self.is_connected and not self.interface:
            self.log("Not connected.", logging.DEBUG)
            return

        self.log("Disconnecting...")
        was_connected = self.is_connected
        self.is_connected = False # Set flag early

        # Attempt to unsubscribe
        try:
            pub.unsubscribe(self._on_receive_raw, "meshtastic.receive")
            pub.unsubscribe(self._on_connection_status, "meshtastic.connection.status")
            pub.unsubscribe(self._on_node_update, "meshtastic.node.updated")
            self.log("Unsubscribed from Meshtastic events.", logging.DEBUG)
        except Exception as e:
            self.log(f"Error during pubsub unsubscribe: {e}", logging.WARNING)

        if self.interface:
            try:
                self.interface.close()
                self.log("Meshtastic interface closed.")
            except Exception as e:
                self.log(f"Error closing Meshtastic interface: {e}", logging.ERROR)
            finally:
                self.interface = None

        self.sending_active = False
        self.node_list = {} # Clear node list
        if self.send_lock.locked():
            try: self.send_lock.release()
            except RuntimeError: pass

        if was_connected: # Only log/notify if it was actually connected before
             self.log("Disconnected.")
             self.receive_callback('status', 'Disconnected', None, None)


    def _on_connection_status(self, interface, status):
        """Callback for Meshtastic connection status changes."""
        self.log(f"Meshtastic connection status changed: {status}", logging.INFO)
        if "disconnected" in str(status).lower() and self.is_connected:
            self.log("Detected disconnection via status update. Cleaning up.", logging.WARNING)
            # Schedule disconnect in main thread to avoid issues? Or handle here carefully.
            self.disconnect() # Call disconnect to ensure proper cleanup


    def _on_node_update(self, node, interface):
        """Callback when node information is updated."""
        try:
             node_id = node.get('num') # Node number is the key usually
             if node_id is not None:
                  self.node_list[node_id] = node # Update our copy
                  user = node.get('user', {})
                  self.log(f"Node info updated: !{node_id:x} ({user.get('longName', 'N/A')})", logging.DEBUG)
                  # Optionally trigger a GUI update if displaying node list live
                  # self.receive_callback('node_update', self.node_list, None, None)
        except Exception as e:
             self.log(f"Error processing node update: {e}", logging.WARNING)


    def _on_receive_raw(self, packet: dict, interface):
        """Internal callback for raw Meshtastic packets received via pubsub."""
        try:
            if not packet: return
            # Optional: Ignore loopback packets based on config (default: True)
            try:
                from utils import get_config
                cfg = get_config() if get_config else {}
            except Exception:
                cfg = {}
            ignore_loopback = cfg.get('meshtastic', {}).get('ignore_loopback', True)
            if ignore_loopback and self.interface and getattr(self.interface, 'myInfo', None) and packet.get('from') == self.interface.myInfo.my_node_num:
                self.log("Ignoring loopback packet.", logging.DEBUG)
                return

            decoded_packet = packet.get('decoded')
            if not decoded_packet: return

            portnum = decoded_packet.get('portnum')
            payload = decoded_packet.get('payload')
            from_id_num = packet.get('from') # Node number
            from_id_hex = f"!{from_id_num:x}" if isinstance(from_id_num, int) else packet.get('fromId', 'unknown') # Use hex for display
            packet_id = packet.get('id', 'N/A')
            rssi = packet.get('rxRssi', 'N/A')
            snr = packet.get('rxSnr', 'N/A')

            # 1. Our Custom App Data
            try:
                target_port = get_private_app_port(self.config)
            except Exception:
                target_port = None
            if target_port is not None and str(portnum) == str(target_port) and payload:
                self.log(f"Received App Data (Port {portnum}) from {from_id_hex} [RSSI:{rssi} SNR:{snr} ID:{packet_id}] ({len(payload)} bytes)", logging.INFO)
                parsed_data = parse_payload(payload)
                if parsed_data:
                    self.receive_callback('data', parsed_data, from_id_hex, packet_id)
                else:
                    self.log(f"Failed to parse JSON payload from {from_id_hex} on port {portnum}. Raw: {payload[:50]}...", logging.WARNING)

            # 2. Standard Text Messages
            elif portnum == 'TEXT_MESSAGE_APP' and decoded_packet.get('text'):
                text = decoded_packet.get('text')
                self.log(f"Received Text Message from {from_id_hex}: '{text}' [RSSI:{rssi} SNR:{snr} ID:{packet_id}]", logging.INFO)
                self.receive_callback('text', text, from_id_hex, packet_id)

            # 3. Other portnums (ignore by default)

        except Exception as e:
            self.log(f"Error processing received packet in _on_receive_raw: {e}", logging.ERROR)
            import traceback
            self.log(traceback.format_exc(), logging.ERROR)


    def send_data(self, payload_bytes: bytes, description: str = "data") -> bool:
        """Sends a single data payload over Meshtastic using the configured private app port."""
        if not self.is_connected or not self.interface:
            self.log("Cannot send: Not connected.", logging.ERROR)
            return False
        if not payload_bytes:
            self.log("Cannot send: Empty payload.", logging.ERROR)
            return False

        if not self.send_lock.acquire(timeout=1.0):
             self.log(f"Could not acquire send lock for '{description}'.", logging.WARNING)
             return False

        self.sending_active = True
        success = False
        try:
            self.log(f"Sending {description} ({len(payload_bytes)} bytes)...")
            portnum = get_private_app_port()
            self.interface.sendData(
                payload_bytes,
                destinationId=BROADCAST_ADDR,
                portNum=portnum,
                wantAck=True,
                channelIndex=0
            )
            self.log(f"{description.capitalize()} send command issued successfully.")
            success = True
        except meshtastic.MeshtasticError as e:
            self.log(f"Meshtastic error sending {description}: {e}", logging.ERROR)
        except Exception as e:
            self.log(f"Unexpected error sending {description}: {e}", logging.ERROR)
            import traceback
            self.log(traceback.format_exc(), logging.ERROR)
        finally:
            self.sending_active = False
            self.send_lock.release()
        return success


    def send_chunked_message(self, data_to_send: bytes, max_chunk_payload_size: int) -> bool:
        """Splits large data into chunks and sends them sequentially."""
        if not self.is_connected or not self.interface:
            self.log("Cannot send chunks: Not connected.", logging.ERROR)
            return False

        if not self.send_lock.acquire(timeout=5.0):
             self.log("Could not acquire send lock for chunked message.", logging.WARNING)
             return False

        self.sending_active = True
        chunk_id = generate_unique_id()
        all_chunks_sent_successfully = False
        start_time = time.time()

        try:
            chunks = split_data_into_chunks(data_to_send, max_chunk_payload_size)
            total_chunks = len(chunks)
            if total_chunks == 0:
                 self.log("No chunks generated, nothing to send.", logging.WARNING)
                 return False

            self.log(f"Splitting message into {total_chunks} chunks (ID: {chunk_id}). Max JSON payload/chunk: {max_chunk_payload_size} bytes.")

            for i, chunk_data in enumerate(chunks):
                chunk_num = i + 1
                payload_bytes = create_chunk_payload(chunk_id, chunk_num, total_chunks, chunk_data)
                send_success_this_chunk = False

                # Get retry configuration from protocol
                    try:
                        retry_count = get_chunk_retry_count(self.config)
                        retry_delay = get_chunk_retry_delay(self.config)
                    except Exception:
                        retry_count = 2
                        retry_delay = 1.0

                for attempt in range(retry_count + 1):
                    self.log(f"Sending chunk {chunk_num}/{total_chunks} (ID:{chunk_id}, Attempt {attempt+1})...")
                    try:
                        portnum = get_private_app_port(self.config)
                        self.interface.sendData(
                            payload_bytes, destinationId=BROADCAST_ADDR,
                            portNum=portnum, wantAck=True
                        )
                        self.log(f"Chunk {chunk_num} send command issued.")
                        send_success_this_chunk = True
                        break # Exit retry loop
                    except meshtastic.MeshtasticError as e:
                        self.log(f"Meshtastic error sending chunk {chunk_num} (Attempt {attempt+1}): {e}", logging.WARNING)
                    except Exception as e:
                        self.log(f"Unexpected error sending chunk {chunk_num} (Attempt {attempt+1}): {e}", logging.WARNING)

                    if attempt < retry_count:
                        self.log(f"Waiting {retry_delay}s before retrying chunk {chunk_num}...")
                        time.sleep(retry_delay)

                if not send_success_this_chunk:
                    self.log(f"Failed to send chunk {chunk_num} (ID:{chunk_id}) after {retry_count + 1} attempts. Aborting message.", logging.ERROR)
                    return False # Abort sending

                # Wait between chunks
                inter_chunk_delay = 1.0 + (len(payload_bytes) / 200.0) # Example dynamic delay
                inter_chunk_delay = min(inter_chunk_delay, 5.0) # Cap delay
                self.log(f"Waiting {inter_chunk_delay:.2f}s before next chunk...", logging.DEBUG)
                time.sleep(inter_chunk_delay)

            all_chunks_sent_successfully = True
            end_time = time.time()
            self.log(f"All {total_chunks} chunks for message {chunk_id} sent successfully (Total time: {end_time - start_time:.2f}s).")

        except ValueError as e:
             self.log(f"Error preparing chunks for ID {chunk_id}: {e}", logging.ERROR)
        except Exception as e:
            self.log(f"Unexpected error during chunked send for ID {chunk_id}: {e}", logging.ERROR)
            import traceback
            self.log(traceback.format_exc(), logging.ERROR)
        finally:
            self.sending_active = False
            self.send_lock.release()

        return all_chunks_sent_successfully


    def send_ack(self, chunk_id: str, chunk_num: int, destination_id: str):
        """Sends an ACK message for a specific received chunk back to the sender."""
        if not self.is_connected or not self.interface:
            return False

        # Convert hex ID back to node number if possible for destinationId
        dest_node_num = None
        if destination_id.startswith('!'):
             try:
                 dest_node_num = int(destination_id[1:], 16)
             except ValueError:
                 self.log(f"Could not parse destination node ID '{destination_id}' for ACK.", logging.WARNING)
                 # Fallback or handle error - maybe try sending to broadcast? Risky.
                 return False
        else:
             # If it wasn't hex, maybe it's already the node number? Unlikely with current format.
             self.log(f"Unexpected ACK destination format: {destination_id}", logging.WARNING)
             return False


        try:
            payload_bytes = create_ack_payload(chunk_id, chunk_num)
            self.log(f"Sending ACK for chunk {chunk_num} (ID:{chunk_id}) to {destination_id}", logging.DEBUG)
            portnum = get_private_app_port(self.config)
            self.interface.sendData(
                payload_bytes,
                destinationId=dest_node_num, # Send unicast ACK using node number
                portNum=portnum,
                wantAck=False # Don't request ACK for an ACK
            )
            return True
        except meshtastic.MeshtasticError as e:
            self.log(f"Meshtastic error sending ACK for chunk {chunk_num} to {destination_id}: {e}", logging.WARNING)
            return False
        except Exception as e:
            self.log(f"Unexpected error sending ACK for chunk {chunk_num} to {destination_id}: {e}", logging.WARNING)
            return False


    def send_test_message(self, message_text: str) -> bool:
        """Sends a simple test message using the standard send_data method."""
        payload_bytes = create_test_payload(message_text)
        return self.send_data(payload_bytes, description="test message")


    def send_complete_voice_message(self, compressed_data: bytes, timestamp: str) -> bool:
        """Sends a voice message that fits in a single packet using send_data."""
        payload_bytes = create_complete_voice_payload(compressed_data, timestamp)
        return self.send_data(payload_bytes, description="complete voice message")

