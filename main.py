import requests
from datetime import datetime, timedelta

# Настройка API
API_BASE_URL = 'https://pro-api.solscan.io'
API_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJjcmVhdGVkQXQiOjE3MjQ0OTQ4NDk1MDEsImVtYWlsIjoiNG5tZGNhdEBnbWFpbC5jb20iLCJhY3Rpb24iOiJ0b2tlbi1hcGkiLCJhcGlWZXJzaW9uIjoidjIiLCJpYXQiOjE3MjQ0OTQ4NDl9.Hsg-RdpY3dwP8FiIbgnOuit_wdnPE1HVHQ03y6lYGkQ'  # Вставьте ваш API-ключ

# Минимальная сумма перевода для фильтрации транзакций
THRESHOLD_SOL = 50
# Проверка на время создания кошелька (в днях)
RECENT_DAYS = 3

def get_headers():
    """Функция для получения заголовков с API ключом."""
    return {
        'Accept': 'application/json',
        'token': API_KEY  # Используйте правильный API ключ
    }

def get_all_wallet_transactions(wallet_address, limit=100):
    """Получаем все транзакции для указанного кошелька с использованием пагинации, пропуская ошибки."""
    url = f'{API_BASE_URL}/v2.0/account/transactions'
    transactions = []
    last_signature = None

    while True:
        params = {
            'address': wallet_address,  # Убедитесь, что адрес кошелька правильный
            'limit': limit
        }
        if last_signature:
            params['before'] = last_signature

        try:
            response = requests.get(url, headers=get_headers(), params=params)
            response.raise_for_status()  # Генерирует исключение для статусов ошибок
            data = response.json().get('data', [])
            if not data:
                break  # Если данных больше нет, выходим из цикла
            transactions.extend(data)
            
            # Обновляем last_signature для следующей страницы
            last_signature = data[-1]['tx_hash']  # Используем последнюю транзакцию
        except requests.exceptions.RequestException as e:
            print(f"Пропускаем ошибку при получении транзакций: {e}")
            break
    
    return transactions

def get_wallet_transactions(wallet_address, limit=10):
    """Получаем транзакции для указанного кошелька, пропуская ошибки."""
    url = f'{API_BASE_URL}/v2.0/account/transactions'
    params = {
        'address': wallet_address,
        'limit': limit
    }
    try:
        response = requests.get(url, headers=get_headers(), params=params)
        response.raise_for_status()  # Генерирует исключение для статусов ошибок
        return response.json().get('data', [])
    except requests.exceptions.RequestException as e:
        print(f"Пропускаем ошибку при получении транзакций: {e}")
        return []

def get_token_accounts(wallet_address):
    """Получаем информацию о токенах в кошельке, пропуская ошибки."""
    url = f'{API_BASE_URL}/v2.0/account/token-accounts'
    params = {
        'address': wallet_address,
        'page_size': 10
    }
    try:
        response = requests.get(url, headers=get_headers(), params=params)
        response.raise_for_status()  # Генерирует исключение для статусов ошибок
        return response.json().get('data', [])
    except requests.exceptions.RequestException as e:
        print(f"Пропускаем ошибку при получении токенов: {e}")
        return []

def filter_large_transactions(transactions):
    """Фильтруем транзакции с суммой ≥50 SOL, проверяя наличие ключа 'amount'."""
    large_txns = []
    for txn in transactions:
        # Проверка наличия ключей 'amount' и 'token_decimals'
        amount = txn.get('amount')
        token_decimals = txn.get('token_decimals')

        if amount is not None and token_decimals is not None:
            # Преобразование суммы транзакции в правильный формат
            sol_amount = float(amount) / (10 ** token_decimals)
            if sol_amount >= THRESHOLD_SOL:
                large_txns.append(txn)
        else:
            # Логируем транзакции, у которых нет нужных полей
            print(f"Пропускаем транзакцию {txn.get('tx_hash', 'неизвестная транзакция')} без 'amount' или 'token_decimals'")
    
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
    # Получаем все транзакции с использованием пагинации
    transactions = get_all_wallet_transactions(wallet_address)
    large_transfers = filter_large_transactions(transactions)
    
    mixer_wallets = []
    for transfer in large_transfers:
        recipient_wallet = transfer['to_address']
        outgoing_txns = get_wallet_transactions(recipient_wallet)
        
        # Группировка транзакций по суммам
        txn_groups = {}
        for txn in outgoing_txns:
            # Проверка наличия 'amount' и 'token_decimals' в исходящих транзакциях
            amount = txn.get('amount')
            token_decimals = txn.get('token_decimals')

            if amount is not None and token_decimals is not None:
                sol_amount = float(amount) / (10 ** token_decimals)
                if sol_amount not in txn_groups:
                    txn_groups[sol_amount] = []
                txn_groups[sol_amount].append(txn['to_address'])
            else:
                print(f"Пропускаем транзакцию {txn.get('tx_hash', 'неизвестная транзакция')} без 'amount' или 'token_decimals'")
        
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
    # Замените "ВАШ_КОШЕЛЕК" на адрес вашего начального кошелька
    initial_wallet = "5o1aVDwR8osoVoNmacvnf2BvvHNpHfAfuCsf4FBCT9JE"
    main(initial_wallet)
