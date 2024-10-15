import requests
from datetime import datetime, timedelta

# Настройка API
API_BASE_URL = 'https://pro-api.solscan.io'
API_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJjcmVhdGVkQXQiOjE3Mjg5ODc3OTA2MDUsImVtYWlsIjoiZi5kLm0uYXNhbnRhQGdtYWlsLmNvbSIsImFjdGlvbiI6InRva2VuLWFwaSIsImFwaVZlcnNpb24iOiJ2MiIsImlhdCI6MTcyODk4Nzc5MH0.LlE62rUU41tsP-_9GjWl1Y0RYUSxXE6pfSISLWoE9W0'  # Вставьте ваш API-ключ

# Минимальная сумма перевода для фильтрации транзакций
THRESHOLD_SOL = 50
# Проверка на время создания кошелька (в днях)
RECENT_DAYS = 3

def get_headers():
    """Функция для получения заголовков с API ключом."""
    return {
        'Accept': 'application/json',
        'token': API_KEY
    }

def get_wallet_transactions(wallet_address, limit=10):
    """Получаем транзакции для указанного кошелька."""
    url = f'{API_BASE_URL}/v2.0/account/transactions'
    params = {
        'address': wallet_address,
        'limit': limit
    }
    response = requests.get(url, headers=get_headers(), params=params)
    if response.status_code == 200:
        return response.json().get('data', [])
    else:
        print(f"Ошибка при получении транзакций: {response.status_code}")
        return []

def get_wallet_transfers(wallet_address):
    """Получаем все переводы средств для указанного кошелька."""
    url = f'{API_BASE_URL}/v2.0/account/transfer'
    params = {
        'address': wallet_address,
        'flow': 'in',  # Интересуют только входящие транзакции
        'page_size': 100
    }
    response = requests.get(url, headers=get_headers(), params=params)
    if response.status_code == 200:
        return response.json().get('data', [])
    else:
        print(f"Ошибка при получении переводов: {response.status_code}")
        return []

def get_token_accounts(wallet_address):
    """Получаем информацию о токенах в кошельке."""
    url = f'{API_BASE_URL}/v2.0/account/token-accounts'
    params = {
        'address': wallet_address,
        'page_size': 10
    }
    response = requests.get(url, headers=get_headers(), params=params)
    if response.status_code == 200:
        return response.json().get('data', [])
    else:
        print(f"Ошибка при получении токенов: {response.status_code}")
        return []

def filter_large_transactions(transactions):
    """Фильтруем транзакции с суммой ≥50 SOL."""
    large_txns = []
    for txn in transactions:
        if 'amount' in txn:
            amount = float(txn['amount']) / (10 ** txn['token_decimals'])
            if amount >= THRESHOLD_SOL:
                large_txns.append(txn)
    return large_txns

def is_wallet_recent(wallet_address):
    """Проверяем, создан ли кошелек недавно (за последние 3 дня)."""
    token_accounts = get_token_accounts(wallet_address)
    if token_accounts:
        creation_time = datetime.fromtimestamp(token_accounts[0]['created_at'])
        return datetime.now() - creation_time <= timedelta(days=RECENT_DAYS)
    return False

def find_mixer_wallets(wallet_address):
    """Ищем прослойки - кошельки, отправляющие одинаковые суммы на разные кошельки."""
    transfers = get_wallet_transfers(wallet_address)
    large_transfers = filter_large_transactions(transfers)
    
    mixer_wallets = []
    for transfer in large_transfers:
        recipient_wallet = transfer['to_address']
        outgoing_txns = get_wallet_transactions(recipient_wallet)
        
        # Группировка транзакций по суммам
        txn_groups = {}
        for txn in outgoing_txns:
            amount = float(txn['amount']) / (10 ** txn['token_decimals'])
            if amount not in txn_groups:
                txn_groups[amount] = []
            txn_groups[amount].append(txn['to_address'])
        
        # Проверка на прослойки
        for amount, recipients in txn_groups.items():
            if len(recipients) > 1:
                recent_recipients = [r for r in recipients if is_wallet_recent(r)]
                if recent_recipients:
                    mixer_wallets.append({
                        "mixer_wallet": recipient_wallet,
                        "trader_wallets": recent_recipients
                    })
    
    return mixer_wallets

def main(initial_wallet):
    """Главная функция для поиска прослоек и трейдерских кошельков."""
    mixer_wallets = find_mixer_wallets(initial_wallet)
    
    if mixer_wallets:
        for entry in mixer_wallets:
            mixer_wallet = entry['mixer_wallet']
            trader_wallets = entry['trader_wallets']
            print(f"Mixer Wallet: {mixer_wallet}")
            for trader_wallet in trader_wallets:
                print(f" - Trader Wallet: {trader_wallet}")
    else:
        print("Прослойки не найдены.")

if __name__ == "__main__":
    initial_wallet = "5o1aVDwR8osoVoNmacvnf2BvvHNpHfAfuCsf4FBCT9JE"
    main(initial_wallet)
