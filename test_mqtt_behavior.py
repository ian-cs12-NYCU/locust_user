#!/usr/bin/env python3
"""
測試 MQTT 發布/訂閱行為
"""
import paho.mqtt.client as mqtt
import time
import threading

received_count = 0
published_count = 0

def on_connect(client, userdata, flags, rc, properties=None):
    print(f"✅ Connected: rc={rc}")
    # 訂閱 reply topic
    client.subscribe("hello world/reply")
    print(f"📥 Subscribed to 'hello world/reply'")

def on_message(client, userdata, message):
    global received_count
    received_count += 1
    payload = message.payload.decode('utf-8', errors='ignore')
    print(f"📬 Received #{received_count} on '{message.topic}': {payload}")

def on_publish(client, userdata, mid, properties=None, reasonCodes=None):
    global published_count
    published_count += 1

# 創建客戶端
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="test-client")
client.on_connect = on_connect
client.on_message = on_message
client.on_publish = on_publish

print("連線到 10.201.0.123:1883...")
client.connect("10.201.0.123", 1883, 60)
client.loop_start()

time.sleep(2)

if client.is_connected():
    print(f"\n開始測試：發布 10 次訊息到 'hello world'")
    print("=" * 60)
    
    for i in range(10):
        result = client.publish("hello world", f"test message {i+1}")
        print(f"📤 Published #{i+1}: {result}")
        time.sleep(0.5)
    
    print(f"\n等待 5 秒接收回應...")
    time.sleep(5)
    
    print("=" * 60)
    print(f"\n📊 統計：")
    print(f"   已發布: {published_count} 次")
    print(f"   已接收: {received_count} 次")
    print(f"   比率: {received_count}/{published_count} = {received_count/published_count*100 if published_count > 0 else 0:.1f}%")
    
    if received_count == 0:
        print(f"\n⚠️  警告：沒有收到任何回應！")
        print(f"   可能原因：")
        print(f"   1. Responder 沒有運行")
        print(f"   2. Responder 不回應這個格式的訊息")
        print(f"   3. Responder 發布到不同的 topic")
    elif received_count < published_count:
        print(f"\n⚠️  警告：回應數量少於發布數量")
        print(f"   可能原因：")
        print(f"   1. Responder 有選擇性地回應")
        print(f"   2. Responder 有速率限制")
        print(f"   3. 網路延遲或丟包")
    else:
        print(f"\n✅ 正常：每次發布都有回應")

else:
    print("❌ 連線失敗")

client.loop_stop()
client.disconnect()
print("\n測試完成")
