import socket
import threading
import time


class GroupChat:
    def __init__(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind(('0.0.0.0', 25225))
        self.members = {}
        self.chat_history = []
        self.lock = threading.Lock()
        self.heartbeat_interval = 5
        threading.Thread(target=self.heartbeat_monitor).start()

    def receive_message(self):
        while True:
            try:
                data, addr = self.socket.recvfrom(1024)
                try:
                    msg = data.decode('utf-8')
                except UnicodeDecodeError:
                    print(f"Failed to decode message from {addr}, possible encoding issue.")
                    continue
                if msg.startswith('HEARTBEAT'):
                    self.members[addr] = True
                    continue
                with self.lock:
                    self.chat_history.append(f"{self.get_member_name(addr)}: {msg}")
                print(f"{self.get_member_name(addr)}: {msg}")
                self.broadcast_message(data, addr)
            except Exception as e:
                print(f"Receive error: {e}")

    def send_message(self):
        while True:
            msg = input("Enter your message (or 'exit' to quit): ")
            if msg.lower() == 'exit':
                break
            try:
                data = msg.encode('utf-8')
            except UnicodeEncodeError:
                print("Failed to encode your message, possible encoding issue.")
                continue
            with self.lock:
                self.chat_history.append(f"You: {msg}")
            self.broadcast_message(data)

    def broadcast_message(self, data, sender_addr=None):
        with self.lock:
            for member, is_online in self.members.items():
                if sender_addr is None or member!= sender_addr and is_online:
                    self.socket.sendto(data, member)

    def connect_to_group(self, target_ip):
        target_address = (target_ip, 25225)
        try:
            self.socket.sendto(b'JOIN_REQUEST', target_address)
            self.socket.settimeout(2)
            self.socket.recvfrom(1024)
            self.socket.settimeout(None)
            with self.lock:
                self.members[target_address] = True
            self.sync_chat_history(target_address)
            self.sync_members(target_address)
            self.broadcast_new_member(target_address)
            print(f"Joined the group successfully.")
        except Exception as e:
            print(f"Connection error: {e}")

    def sync_chat_history(self, new_member):
        for entry in self.chat_history:
            try:
                data = entry.encode('utf-8')
            except UnicodeEncodeError:
                print(f"Failed to encode chat history entry for {new_member}, possible encoding issue.")
                continue
            self.socket.sendto(data, new_member)

    def sync_members(self, new_member):
        member_info = ';'.join([','.join(map(str, member)) for member, is_online in self.members.items() if
                                member!= new_member and is_online])
        try:
            self.socket.sendto(b'MEMBER_INFO:' + member_info.encode('utf-8'), new_member)
        except UnicodeEncodeError:
            print(f"Failed to encode member info for {new_member}, possible encoding issue.")

    def broadcast_new_member(self, new_member):
        with self.lock:
            new_member_info = ','.join(map(str, new_member))
            try:
                data = b'NEW_MEMBER:' + new_member_info.encode('utf-8')
            except UnicodeEncodeError:
                print(f"Failed to encode new member info for {new_member}, possible encoding issue.")
                return
            self.socket.sendto(data, new_member)
            for member, is_online in self.members.items():
                if member!= new_member and is_online:
                    self.socket.sendto(data, member)

    def handle_new_member(self):
        while True:
            try:
                data, addr = self.socket.recvfrom(1024)
                if data.startswith(b'JOIN_REQUEST'):
                    self.socket.sendto(b'JOIN_ACCEPT', addr)
                    with self.lock:
                        self.members[addr] = True
                    self.sync_chat_history(addr)
                    self.sync_members(addr)
                    self.broadcast_new_member(addr)
            except Exception as e:
                print(f"New member error: {e}")

    def heartbeat_monitor(self):
        while True:
            with self.lock:
                for member in list(self.members.keys()):
                    try:
                        self.socket.sendto(b'HEARTBEAT', member)
                        self.socket.settimeout(1)
                        self.socket.recvfrom(1024)
                        self.members[member] = True
                    except socket.timeout:
                        self.members[member] = False
                        print(f"{member} is offline.")
                        self.reconnect()
                    finally:
                        self.socket.settimeout(None)
            time.sleep(self.heartbeat_interval)

    def reconnect(self):
        with self.lock:
            online_members = [member for member, is_online in self.members.items() if is_online]
            if online_members:
                new_target = online_members[0]
                self.connect_to_group(new_target[0])

    def get_member_name(self, addr):
        return f"Member at {addr[0]}:{addr[1]}"


def main():
    chat = GroupChat()
    threading.Thread(target=chat.receive_message).start()
    threading.Thread(target=chat.handle_new_member).start()

    while True:
        action = input("Enter 'join' to join a group, 'send' to send a message, or 'exit' to quit: ")
        if action.lower() == 'join':
            target_ip = input("Enter the IP address of a group member: ")
            chat.connect_to_group(target_ip)
        elif action.lower() =='send':
            if not chat.members:
                print("You are not in a group yet. Please join a group first.")
            else:
                threading.Thread(target=chat.send_message).start()
        elif action.lower() == 'exit':
            chat.socket.close()
            break


if __name__ == "__main__":
    main()


