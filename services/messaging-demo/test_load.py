import json
import random
import time
import urllib.request
from datetime import datetime

# Configurações do teste
API_URL = "http://localhost:5000/message"
TOTAL_MESSAGES = 1000
DELAY_BETWEEN_REQUESTS = 0.05  # 50ms (para não sobrecarregar o log da aula)

def send_test_message(index):
    # Gera dados randômicos como solicitado
    payload = {
        "name": f"StressTest_{random.randint(100, 999)}",
        "messageNumber": random.randint(100000, 999999)
    }
    
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        API_URL, 
        data=data, 
        headers={'Content-Type': 'application/json'},
        method='POST'
    )
    
    try:
        with urllib.request.urlopen(req) as response:
            if response.status == 200:
                # print(f"[{index+1}/{TOTAL_MESSAGES}] Success: {payload['name']}")
                pass
            else:
                print(f"[{index+1}] Failed with status: {response.status}")
    except Exception as e:
        print(f"[{index+1}] Error: {str(e)}")

if __name__ == "__main__":
    print(f"🚀 Iniciando carga de {TOTAL_MESSAGES} mensagens para teste de DLQ...")
    print(f"Destino: {API_URL}")
    print("Acompanhe o log do consumer e o painel do RabbitMQ!")
    
    start_time = time.time()
    
    for i in range(TOTAL_MESSAGES):
        send_test_message(i)
        if (i + 1) % 100 == 0:
            print(f"✅ Enviadas {i+1} mensagens...")
        time.sleep(DELAY_BETWEEN_REQUESTS)
    
    end_time = time.time()
    print(f"\n✨ Teste concluído em {end_time - start_time:.2f} segundos.")
    print("Verifique a fila 'logs_dlq' no RabbitMQ (localhost:15672).")
