import socket
import threading
import time
import tkinter as tk
from tkinter import ttk


class GroupChat:
    def __init__(self, root):
        self.root = root
        self.root.title("Group Chat")
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind(('0.0.0.0', 25225))
        self.members = {}
        self.chat_history = []
        self.lock = threading.Lock()
        self.heartbeat_interval = 5
        threading.Thread(target=self.heartbeat_monitor).start()

        self.create_widgets()
        threading.Thread(target=self.receive_message).start()
        threading.Thread(target=self.handle_new_member).start()

    def create_widgets(self):
        self.root.configure(bg='#f0f0f5')

        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TLabel', background='#f0f0f5')
        style.configure('TButton', background='#007acc', foreground='white')
        style.map('TButton', background=[('active', '#005ea3')])

        self.chat_display = tk.Text(self.root, height=20, width=80, bg='white', fg='black')
        self.chat_display.grid(row=0, column=0, columnspan=2, pady=10, padx=10, sticky='nsew')

        self.join_label = ttk.Label(self.root, text="Enter IP to join:")
        self.join_label.grid(row=1, column=0, pady=5, padx=10, sticky='w')

        self.join_entry = ttk.Entry(self.root, width=30)
        self.join_entry.grid(row=1, column=1, pady=5, padx=10, sticky='w')

        self.join_button = ttk.Button(self.root, text="Join Group", command=self.join_group)
        self.join_button.grid(row=2, column=0, pady=5, padx=10)

        self.send_label = ttk.Label(self.root, text="Enter message:")
        self.send_label.grid(row=3, column=0, pady=5, padx=10, sticky='w')

        self.send_entry = ttk.Entry(self.root, width=80)
        self.send_entry.grid(row=3, column=1, pady=5, padx=10, sticky='w')

        self.send_button = ttk.Button(self.root, text="Send Message", command=self.send_message)
        self.send_button.grid(row=4, column=0, columnspan=2, pady=5, padx=10)

        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(1, weight=1)

    def receive_message(self):
        while True:
            try:
                data, addr = self.socket.recvfrom(1024)
                try:
                    msg = data.decode('utf-8')
                except UnicodeDecodeError:
                    self.append_to_chat(f"Failed to decode message from {addr}, possible encoding issue.")
                    continue
                if msg.startswith('HEARTBEAT'):
                    self.members[addr] = True
                    continue
                with self.lock:
                    self.chat_history.append(f"{self.get_member_name(addr)}: {msg}")
                self.append_to_chat(f"{self.get_member_name(addr)}: {msg}")
                self.broadcast_message(data, addr)
            except Exception as e:
                self.append_to_chat(f"Receive error: {e}")

    def send_message(self):
        msg = self.send_entry.get()
        self.send_entry.delete(0, tk.END)
        if not msg:
            return
        try:
            data = msg.encode('utf-8')
        except UnicodeEncodeError:
            self.append_to_chat("Failed to encode your message, possible encoding issue.")
            return
        with self.lock:
            self.chat_history.append(f"You: {msg}")
        self.broadcast_message(data)
        self.append_to_chat(f"You: {msg}")

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
            self.append_to_chat(f"Joined the group successfully.")
        except Exception as e:
            self.append_to_chat(f"Connection error: {e}")

    def sync_chat_history(self, new_member):
        for entry in self.chat_history:
            try:
                data = entry.encode('utf-8')
            except UnicodeDecodeError:
                self.append_to_chat(f"Failed to encode chat history entry for {new_member}, possible encoding issue.")
                continue
            self.socket.sendto(data, new_member)

    def sync_members(self, new_member):
        member_info = ';'.join([','.join(map(str, member)) for member, is_online in self.members.items() if
                                member!= new_member and is_online])
        try:
            self.socket.sendto(b'MEMBER_INFO:' + member_info.encode('utf-8'), new_member)
        except UnicodeEncodeError:
            self.append_to_chat(f"Failed to encode member info for {new_member}, possible encoding issue.")

    def broadcast_new_member(self, new_member):
        with self.lock:
            new_member_info = ','.join(map(str, new_member))
            try:
                data = b'NEW_MEMBER:' + new_member_info.encode('utf-8')
            except UnicodeEncodeError:
                self.append_to_chat(f"Failed to encode new member info for {new_member}, possible encoding issue.")
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
                self.append_to_chat(f"New member error: {e}")

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
                        self.append_to_chat(f"{member} is offline.")
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

    def join_group(self):
        target_ip = self.join_entry.get()
        self.join_entry.delete(0, tk.END)
        if not target_ip:
            return
        self.connect_to_group(target_ip)

    def append_to_chat(self, message):
        self.chat_display.insert(tk.END, message + '\n')
        self.chat_display.see(tk.END)


def main():
    root = tk.Tk()
    app = GroupChat(root)
    root.mainloop()


if __name__ == "__main__":
    main()


