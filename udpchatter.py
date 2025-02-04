import socket
import threading
import time
from queue import Queue

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception as e:
        print(f"Error getting local IP: {e}")
        return None

class GroupChat:
    def __init__(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind(('0.0.0.0', 25225))
        self.socket.settimeout(2)
        self.members = {}          # {(ip, port): is_online}
        self.heartbeat_failures = {}  # {(ip, port): failure_count}
        self.chat_history = []
        self.lock = threading.Lock()
        self.message_queue = Queue()
        self.running = True
        
        # 启动核心线程
        threading.Thread(target=self.receive_processor, daemon=True).start()
        threading.Thread(target=self.heartbeat_monitor, daemon=True).start()
        threading.Thread(target=self.message_dispatcher, daemon=True).start()

    def receive_processor(self):
        """统一的消息接收处理中心"""
        while self.running:
            try:
                data, addr = self.socket.recvfrom(1024)
                try:
                    msg = data.decode('utf-8')
                except UnicodeDecodeError:
                    continue
                
                # 处理加入请求
                if msg == 'JOIN_REQUEST':
                    self.handle_join_request(addr)
                
                # 处理心跳确认
                elif msg == 'HEARTBEAT_ACK':
                    with self.lock:
                        if addr in self.members:
                            self.members[addr] = True
                            self.heartbeat_failures[addr] = 0
                
                # 处理成员信息同步
                elif msg.startswith('MEMBER_INFO:'):
                    self.handle_member_info(msg[12:])
                
                # 处理新成员通知
                elif msg.startswith('NEW_MEMBER:'):
                    self.handle_new_member(msg[11:])
                
                # 处理普通消息
                else:
                    self.handle_normal_message(data, addr)
            
            except socket.timeout:
                continue
            except Exception as e:
                print(f"Receive error: {str(e)}")

    def handle_join_request(self, addr):
        """处理加入请求"""
        print(f"Received join request from {addr[0]}:{addr[1]}")
        try:
            # 发送加入确认
            self.socket.sendto('JOIN_ACCEPT'.encode(), addr)
            # 同步现有信息
            with self.lock:
                if addr not in self.members:
                    self.members[addr] = True
                    self.heartbeat_failures[addr] = 0
            self.sync_chat_history(addr)
            self.sync_member_list(addr)
            self.broadcast_new_member(addr)
        except Exception as e:
            print(f"Join request handling failed: {str(e)}")

    def handle_member_info(self, info_str):
        """处理成员列表同步"""
        try:
            members = [tuple(m.split(',')) for m in info_str.split(';') if m]
            with self.lock:
                for m in members:
                    member_addr = (m[0], int(m[1]))
                    if member_addr not in self.members:
                        self.members[member_addr] = True
                        self.heartbeat_failures[member_addr] = 0
        except Exception as e:
            print(f"Invalid member info: {str(e)}")

    def handle_new_member(self, member_str):
        """处理新成员通知"""
        try:
            ip, port = member_str.split(',')
            member_addr = (ip, int(port))
            with self.lock:
                if member_addr not in self.members:
                    self.members[member_addr] = True
                    self.heartbeat_failures[member_addr] = 0
                    print(f"Discovered new member: {ip}:{port}")
        except Exception as e:
            print(f"Invalid new member format: {str(e)}")

    def handle_normal_message(self, data, addr):
        """处理普通聊天消息"""
        try:
            msg = data.decode('utf-8')
            display_msg = f"{self.get_member_name(addr)}: {msg}"
            with self.lock:
                self.chat_history.append(display_msg)
            print(display_msg)
            self.message_queue.put((data, addr))  # 加入消息分发队列
        except UnicodeDecodeError:
            print(f"Received invalid message from {addr[0]}:{addr[1]}")

    def message_dispatcher(self):
        """消息分发线程"""
        while self.running:
            if not self.message_queue.empty():
                data, sender_addr = self.message_queue.get()
                self.broadcast_message(data, sender_addr)

    def connect_to_group(self, target_ip):
        """连接到现有群组"""
        target_addr = (target_ip, 25225)
        print(f"Attempting to connect to {target_ip}...")
        
        # 发送3次加入请求
        for attempt in range(3):
            try:
                self.socket.sendto('JOIN_REQUEST'.encode(), target_addr)
                data, addr = self.socket.recvfrom(1024)
                if data.decode() == 'JOIN_ACCEPT':
                    with self.lock:
                        self.members[target_addr] = True
                        self.heartbeat_failures[target_addr] = 0
                    print("Connection established successfully!")
                    self.sync_member_list(target_addr)
                    return True
            except socket.timeout:
                print(f"Attempt {attempt+1}/3 failed")
            except Exception as e:
                print(f"Connection error: {str(e)}")
                return False
        print("Failed to connect after 3 attempts")
        return False

    def sync_member_list(self, target_addr):
        """同步成员列表"""
        try:
            # 请求成员列表
            self.socket.sendto('REQUEST_MEMBERS'.encode(), target_addr)
            data, addr = self.socket.recvfrom(1024)
            if data.startswith(b'MEMBER_INFO:'):
                self.handle_member_info(data[12:].decode())
        except Exception as e:
            print(f"Member sync failed: {str(e)}")

    def broadcast_message(self, data, sender_addr=None):
        """广播消息给所有成员"""
        with self.lock:
            recipients = [m for m, online in self.members.items() if online]
        
        for member in recipients:
            if sender_addr is None or member != sender_addr:
                try:
                    self.socket.sendto(data, member)
                except Exception as e:
                    print(f"Failed to send to {member[0]}:{str(e)}")

    def sync_chat_history(self, target_addr):
        """同步聊天记录"""
        try:
            with self.lock:
                history = '\n'.join(self.chat_history[-10:])  # 同步最近10条
                self.socket.sendto(f'CHAT_HISTORY:{history}'.encode(), target_addr)
        except Exception as e:
            print(f"History sync failed: {str(e)}")

    def heartbeat_monitor(self):
        """心跳检测线程"""
        while self.running:
            with self.lock:
                members = list(self.members.keys())
            
            for member in members:
                try:
                    # 发送心跳包
                    self.socket.sendto('HEARTBEAT'.encode(), member)
                    self.socket.settimeout(1)
                    data, addr = self.socket.recvfrom(1024)
                    if data.decode() == 'HEARTBEAT_ACK':
                        with self.lock:
                            self.members[member] = True
                            self.heartbeat_failures[member] = 0
                except socket.timeout:
                    with self.lock:
                        self.heartbeat_failures[member] = self.heartbeat_failures.get(member, 0) + 1
                        if self.heartbeat_failures[member] >= 3:
                            print(f"Member {member[0]}:{member[1]} is offline")
                            del self.members[member]
                            del self.heartbeat_failures[member]
                except Exception as e:
                    print(f"Heartbeat error: {str(e)}")
            
            time.sleep(5)

    def get_member_name(self, addr):
        """获取成员显示名称"""
        return f"{addr[0]}:{addr[1]}"

    def shutdown(self):
        """关闭资源"""
        self.running = False
        self.socket.close()

def main():
    local_ip = get_local_ip()
    print(f"Your local IP: {local_ip if local_ip else 'Unknown'}")
    
    chat = GroupChat()
    
    while True:
        action = input("\nOptions:\n1. Join group\n2. Send message\n3. Exit\nChoose: ")
        
        if action == '1':
            target_ip = input("Enter target IP: ").strip()
            if chat.connect_to_group(target_ip):
                print("Successfully joined group!")
            else:
                print("Failed to join group")
        
        elif action == '2':
            if not chat.members:
                print("Not connected to any group!")
                continue
            message = input("Enter message: ")
            chat.message_queue.put((message.encode(), None))  # None表示来自自己
            with chat.lock:
                chat.chat_history.append(f"You: {message}")
        
        elif action == '3':
            chat.shutdown()
            print("Exiting...")
            break
        
        else:
            print("Invalid option")

if __name__ == "__main__":
    main()