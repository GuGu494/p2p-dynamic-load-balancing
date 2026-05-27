import subprocess
import time
import os
import sys
import json

def run_test():
    print("=== INICIANDO SIMULAÇÃO DE BALANCEAMENTO DE CARGA P2P ===")
    
    # Python executable
    python_exe = sys.executable

    # Environment configs for Master B (Lender - port 54322, underloaded)
    env_master_b = os.environ.copy()
    env_master_b["P2P_PORT"] = "54322"
    env_master_b["P2P_SERVER_UUID"] = "Master_B"
    env_master_b["P2P_EMPTY_TASKS"] = "true"
    env_master_b["P2P_DISABLE_GENERATOR"] = "true"
    env_master_b["P2P_NEIGHBORS"] = json.dumps([
        {"id": "Master_A", "host": "127.0.0.1", "port": 54321}
    ])

    # Environment configs for Worker 1 (starts on Master B)
    env_worker = os.environ.copy()
    env_worker["P2P_PORT"] = "54322"
    env_worker["P2P_WORKER_UUID"] = "W-Test-1"
    env_worker["P2P_HEARTBEAT_INTERVAL"] = "2" # faster heartbeats for testing

    # Environment configs for Master A (Borrower - port 54321, saturated)
    env_master_a = os.environ.copy()
    env_master_a["P2P_PORT"] = "54321"
    env_master_a["P2P_SERVER_UUID"] = "Master_A"
    env_master_a["P2P_NUM_TASKS"] = "11" # 11 tasks (saturated, threshold is 10)
    env_master_a["P2P_DISABLE_GENERATOR"] = "true"
    env_master_a["P2P_NEIGHBORS"] = json.dumps([
        {"id": "Master_B", "host": "127.0.0.1", "port": 54322}
    ])

    # Start Master B
    print("[Manger] Iniciando Master B (Porta 54322)...")
    proc_b = subprocess.Popen([python_exe, "-u", "src/master.py"], env=env_master_b, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    
    # Start Worker
    print("[Manger] Iniciando Worker (conectado a Master B)...")
    proc_w = subprocess.Popen([python_exe, "-u", "src/worker.py"], env=env_worker, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    
    time.sleep(3) # Wait for Worker to register on Master B

    # Start Master A
    print("[Manger] Iniciando Master A (Porta 54321, Saturado com 11 tarefas)...")
    proc_a = subprocess.Popen([python_exe, "-u", "src/master.py"], env=env_master_a, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    # Function to print process outputs
    def print_stream(name, proc):
        import select
        # Use simple line reads for windows/cross-platform compatibility
        # To avoid blocking, we will read line by line with a timeout or in a separate thread
        import threading
        def target():
            for line in iter(proc.stdout.readline, ''):
                print(f"[{name}] {line.strip()}")
        t = threading.Thread(target=target, daemon=True)
        t.start()

    print_stream("Master A", proc_a)
    print_stream("Master B", proc_b)
    print_stream("Worker", proc_w)

    # Let the simulation run for 25 seconds to see all transitions:
    # 1. Master A saturates -> asks Master B for help
    # 2. Master B accepts -> redirects Worker
    # 3. Worker migrates to Master A -> processes tasks
    # 4. Master A's load drops below release threshold (4) -> releases Worker
    # 5. Worker returns to Master B
    # 6. Master A notifies Master B
    time.sleep(25)

    print("\n=== FINALIZANDO PROCESSOS ===")
    proc_a.terminate()
    proc_b.terminate()
    proc_w.terminate()
    print("Processos encerrados. Teste concluído!")

if __name__ == "__main__":
    run_test()
