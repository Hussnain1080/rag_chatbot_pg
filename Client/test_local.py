import asyncio
import httpx
import time
from datetime import datetime
import random
from requests.auth import HTTPBasicAuth
import requests

BASE_URL = "http://127.0.0.1:8000"
ADMIN_USER = "admin"
ADMIN_PASS = "123"

# Test users (will be created if they don't exist)
test_users = [
    ("user1", "123"),
    ("user2", "123"),
    ("user3", "123"),
]

questions = [
    "What is machine learning?",
    "Explain neural networks",
    "Tell me about AI",
    "What is deep learning?",
    "How does NLP work?",
]

def check_and_create_users():
    """Check if test users exist, create if they don't"""
    print("\n🔍 Checking test users...")
    auth = HTTPBasicAuth(ADMIN_USER, ADMIN_PASS)
    
    try:
        # Get existing users
        response = requests.get(f"{BASE_URL}/admin/users", auth=auth)
        if response.status_code != 200:
            print("❌ Cannot connect to admin API. Is the server running?")
            return False
        
        existing_users = {u['username'] for u in response.json()}
        
        # Create missing users
        for username, password in test_users:
            if username not in existing_users:
                print(f"⚠️  User '{username}' not found. Creating...")
                response = requests.post(
                    f"{BASE_URL}/admin/users",
                    json={"username": username, "password": password},
                    auth=auth
                )
                if response.status_code == 200:
                    print(f"✅ Created user: {username}")
                else:
                    print(f"❌ Failed to create {username}: {response.text}")
                    return False
            else:
                print(f"✅ User '{username}' exists")
        
        # Verify authentication
        print("\n🔐 Verifying authentication...")
        for username, password in test_users:
            response = requests.get(
                f"{BASE_URL}/user/auth/check",
                auth=(username, password)
            )
            if response.status_code == 200:
                print(f"✅ {username}: Auth OK")
            else:
                print(f"❌ {username}: Auth failed")
                return False
        
        print("\n✅ All users ready!\n")
        return True
        
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to server. Please start the server first:")
        print("   uvicorn main:app --reload --host 127.0.0.1 --port 8000")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

async def send_chat_request(user_idx, request_num):
    """Send a single chat request"""
    user, password = test_users[user_idx % len(test_users)]
    question = random.choice(questions)
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            start = time.time()
            response = await client.post(
                f"{BASE_URL}/user/chat",
                json={"user_id": user, "message": question},
                auth=(user, password)
            )
            elapsed = time.time() - start
            
            if response.status_code == 200:
                print(f"✅ Request #{request_num:3d} | User: {user:8s} | Time: {elapsed:.2f}s | Status: {response.status_code}")
                return True, elapsed
            else:
                print(f"❌ Request #{request_num:3d} | User: {user:8s} | Status: {response.status_code}")
                return False, elapsed
        except Exception as e:
            print(f"❌ Request #{request_num:3d} | Error: {str(e)[:50]}")
            return False, 0

async def load_test_scenario_1():
    """Scenario 1: Sequential requests (baseline)"""
    print("\n" + "="*80)
    print("SCENARIO 1: Sequential Requests (Baseline)")
    print("="*80)
    print("Testing: 10 sequential requests, one at a time\n")
    
    start_time = time.time()
    success_count = 0
    response_times = []
    
    for i in range(10):
        success, elapsed = await send_chat_request(i % len(test_users), i+1)
        if success:
            success_count += 1
            response_times.append(elapsed)
        await asyncio.sleep(0.5)
    
    total_time = time.time() - start_time
    avg_response = sum(response_times) / len(response_times) if response_times else 0
    
    print(f"\n📊 Results:")
    print(f"   Total Time: {total_time:.2f}s")
    print(f"   Successful: {success_count}/10")
    print(f"   Avg Response Time: {avg_response:.2f}s")
    print(f"   Throughput: {10/total_time:.2f} req/s")
    
    return success_count >= 8  # Allow 2 failures

async def load_test_scenario_2():
    """Scenario 2: Concurrent requests (stress test)"""
    print("\n" + "="*80)
    print("SCENARIO 2: Concurrent Requests (Stress Test)")
    print("="*80)
    print("Testing: 30 concurrent requests\n")
    
    start_time = time.time()
    
    tasks = [
        send_chat_request(i % len(test_users), i+1)
        for i in range(30)
    ]
    
    results = await asyncio.gather(*tasks)
    
    total_time = time.time() - start_time
    success_count = sum(1 for success, _ in results if success)
    response_times = [elapsed for success, elapsed in results if success]
    avg_response = sum(response_times) / len(response_times) if response_times else 0
    
    print(f"\n📊 Results:")
    print(f"   Total Time: {total_time:.2f}s")
    print(f"   Successful: {success_count}/30")
    print(f"   Failed: {30 - success_count}/30")
    print(f"   Avg Response Time: {avg_response:.2f}s")
    print(f"   Throughput: {30/total_time:.2f} req/s")
    
    return success_count >= 25  # Allow 5 failures

async def load_test_scenario_3():
    """Scenario 3: User isolation test"""
    print("\n" + "="*80)
    print("SCENARIO 3: User Isolation Test")
    print("="*80)
    print("Testing: Verify each user sees only their own data\n")
    
    unique_messages = {
        "user1": "My favorite color is RED",
        "user2": "My favorite color is BLUE",
        "user3": "My favorite color is GREEN",
    }
    
    for user, password in test_users:
        message = unique_messages[user]
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{BASE_URL}/user/chat",
                json={"user_id": user, "message": message},
                auth=(user, password)
            )
            if response.status_code == 200:
                print(f"✅ {user} said: {message}")
            else:
                print(f"❌ {user} failed to send message")
    
    await asyncio.sleep(2)
    
    print("\n🔍 Verifying user isolation...")
    all_passed = True
    
    for user, password in test_users:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{BASE_URL}/user/chat/history",
                auth=(user, password)
            )
            if response.status_code == 200:
                history = response.json().get("history", [])
                expected_message = unique_messages[user]
                
                if expected_message in str(history):
                    print(f"✅ {user}: Can see their own message")
                    
                    other_messages = [msg for u, msg in unique_messages.items() if u != user]
                    sees_others = any(msg in str(history) for msg in other_messages)
                    
                    if sees_others:
                        print(f"❌ {user}: WARNING - Can see other users' messages!")
                        all_passed = False
                    else:
                        print(f"✅ {user}: Cannot see other users' messages (ISOLATED)")
                else:
                    print(f"❌ {user}: Cannot see their own message")
                    all_passed = False
    
    return all_passed

async def main():
    """Run all test scenarios"""
    print("\n" + "🚀"*40)
    print("RAG CHATBOT - LOCAL LOAD TESTING")
    print("🚀"*40)
    print(f"\n📅 Test Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🎯 Target: {BASE_URL}")
    print(f"👥 Test Users: {len(test_users)}")
    
    # Check/create users first
    if not check_and_create_users():
        print("\n❌ Cannot proceed without users. Exiting.")
        return
    
    # Run scenarios
    results = {}
    
    results['scenario1'] = await load_test_scenario_1()
    await asyncio.sleep(3)
    
    results['scenario2'] = await load_test_scenario_2()
    await asyncio.sleep(3)
    
    results['scenario3'] = await load_test_scenario_3()
    
    # Summary
    print("\n" + "="*80)
    print("📊 FINAL TEST SUMMARY")
    print("="*80)
    print(f"Scenario 1 (Sequential):  {'✅ PASSED' if results['scenario1'] else '❌ FAILED'}")
    print(f"Scenario 2 (Concurrent):  {'✅ PASSED' if results['scenario2'] else '❌ FAILED'}")
    print(f"Scenario 3 (Isolation):   {'✅ PASSED' if results['scenario3'] else '❌ FAILED'}")
    print("="*80)
    
    all_passed = all(results.values())
    if all_passed:
        print("\n🎉 ALL TESTS PASSED! Ready for AWS deployment.")
    else:
        print("\n⚠️  Some tests failed. Review results above.")

if __name__ == "__main__":
    asyncio.run(main())