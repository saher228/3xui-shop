<div align="center" markdown>

<p align="center">
    <a href="https://github.com/snoups/3xui-shop/blob/main/README.md"><u><b>ENGLISH</b></u></a> •
    <a href="https://github.com/snoups/3xui-shop/blob/main/README.ru_RU.md"><u><b>РУССКИЙ</b></u></a>
</p>

![3xui-shop](https://github.com/user-attachments/assets/282d10db-a355-4c65-a2cf-eb0e8ec8eed1)

**Этот проект представляет собой Telegram-бота для продажи подписок на VPN. Работает с 3X-UI.**

<p align="center">
    <a href="#overview">Обзор</a> •
    <a href="#installation-guide">Руководство по установке</a> •
    <a href="#bugs-and-feature-requests">Ошибки и запросы функций</a> •
    <a href="#support-the-project">Поддержка проекта</a>
</p>

![GitHub License](https://img.shields.io/github/license/snoups/3xui-shop)
![GitHub Downloads (all assets, all releases)](https://img.shields.io/github/downloads/snoups/3xui-shop/total)
![GitHub Release](https://img.shields.io/github/v/release/snoups/3xui-shop)
![GitHub Issues or Pull Requests](https://img.shields.io/github/issues/snoups/3xui-shop)


[![Static Badge](https://img.shields.io/badge/public_channel-white?style=social&logo=Telegram&logoColor=blue&logoSize=auto&labelColor=white&link=https%3A%2F%2Ft.me%2Fsn0ups)](https://t.me/sn0ups)
[![Static Badge](https://img.shields.io/badge/contact_me-white?style=social&logo=Telegram&logoColor=blue&logoSize=auto&labelColor=white&link=https%3A%2F%2Ft.me%2Fsnoups)](https://t.me/snoups)
![GitHub Repo stars](https://img.shields.io/github/stars/snoups/3xui-shop)
</div>

<a id="overview"></a>

## 📝 Обзор

**3X-UI-SHOP** — это комплексное решение, предназначенное для автоматизации продажи подписок на VPN через Telegram. Бот использует API панели **3X-UI** для управления клиентами и поддерживает различные способы оплаты, включая **Cryptomus**, **Heleket**, **YooKassa**, **YooMoney** и **Telegram Stars**.

Основные возможности:

- **Управление серверами**
    - Добавление, удаление, отключение и проверка серверов в пуле
    - Автоматическое распределение новых клиентов по серверам
    - Управление серверами без перезапуска или перенастройки бота
    - Замена одного сервера другим (Смена локации) Доработка by SaHeR
- **Промокоды**
    - Создание, редактирование и удаление промокодов
    - Промокоды для добавления дополнительного времени подписки
    - ~~Промокоды со скидками~~
- **Уведомления**
    - Отправка сообщений конкретному пользователю или всем пользователям
    - Редактирование последнего отправленного уведомления
    - Форматирование текста с использованием HTML
    - Предпросмотр уведомлений перед отправкой
    - Системные уведомления для разработчика и администраторов
- **Двухуровневая реферальная система** (by [@Heimlet](https://github.com/Heimlet))
    - Просмотр статистики рефералов
    - Вознаграждение за привлечение новых пользователей
    - Поддержка двухуровневой реферальной системы
- **Пробный период** (by [@Heimlet](https://github.com/Heimlet))
    - Предоставление бесплатной пробной подписки
    - Увеличенный пробный период для приглашённых пользователей
    - Настройка и отключение пробного периода
- **Гибкая платежная система**
    - Изменение валюты по умолчанию
    - Гибкая архитектура для добавления новых платёжных шлюзов
    - ~~Добавление, редактирование и удаление тарифных планов в любое время~~
    - ~~Изменение порядка отображения вариантов оплаты~~
- **Редактор пользователей** (by [@SaHeR](https://github.com/saher228))
    - Просмотр информации о пользователе
    - Редактирование подписки
    - Смена локации пользователю
    - Удаление пользователя с базы данных бота или с 3x-ui либо удаление везде
    - Блокировка и разблокировка пользователей
    - Создание пользователя в ручную
    - Просмотр список пользователей
    - Поиск пользователей по ключевым фразам либо указать id или @name
    - ~~Быстрый доступ к пользователю через пересланное сообщение~~
    - ~~Персональные скидки для пользователей~~
    - ~~Просмотр статистики рефералов~~
    - ~~Просмотр истории платежей и активированных промокодов~~
    - ~~Просмотр информации о сервере~~

### ⚙️ Админ-панель
Бот включает удобную панель администратора с инструментами для эффективного управления.
Администраторы не имеют доступа к управлению серверами.

- **`Менеджер серверов`**: Добавление, удаление, отключение и проверка серверов в пуле
- **`Статистика`**: Просмотр аналитики использования и различных данных
- **`Редактор пользователей`**: Управление пользователями и подписками
- **`Редактор промокодов`**: Создание, редактирование и удаление промокодов
- **`Отправка уведомлений`**: Отправка уведомлений
- **`Резервное копирование БД`**: Создание резервной копии базы данных
- **`Режим обслуживания`**: Отключение доступа для пользователей


### 🚧 Текущие задачи
- [x] Пробный период
- [x] Реферальная система
- [ ] Статистика
- [x] Редактор пользователей
- [ ] Редактор планов
- [ ] Гибкий пул серверов
- [ ] Кастомные промокоды

<a id="installation-guide"></a>

## 🛠️ Руководство по установке

### Зависимости

Перед началом установки убедитесь, что у вас установлен [**Docker**](https://www.docker.com/)

### Docker Установка 

1. **Установка/Обновление:**
   ```bash
   bash <(curl -Ls https://raw.githubusercontent.com/saher228/3xui-shop/main/scripts/install.sh) -q
   cd 3xui-shop
   ```

2. **Настройка переменных окружения и планов:**
- Скопируйте `plans.example.json` в `plans.json` и `.env.example` в `.env`:
    ```bash
    cp plans.example.json plans.json
    cp .env.example .env
    ```
    > Обновите файл `plans.json` согласно вашим тарифным планам. [(Настройка планов)](#subscription-plans-configuration) 

    > Обновите файл `.env` согласно вашей конфигурации. [(Настройка переменных окружения)](#environment-variables-configuration)

1. **Соберите образ Docker:**
   ```bash
   docker compose build
   ```

2. **Запустите контейнер Docker выбрав docker-compose или docker-compose-traefik:**

   ```bash
   # Используйте docker-compose.yml для обычной установки если используете Nginx
   docker compose -f docker-compose.yml up -d

   # Или docker-compose-traefik.yml для установки с Traefik
   docker compose -f docker-compose-traefik.yml up -d
   ```

3. **Конфиг Nginx если выбрали docker-compose.yml**

   > [(Установка Nginx)](https://nginx.org/en/linux_packages.html)
   >
   > [(Установка Certbot Для получение сертификата домену)](https://certbot.eff.org/instructions?ws=nginx&os=snap) 
   > Certbot вам не нужен если используете сертификат Cloudflaer

    ```bash
    # nano /etc/nginx/sites-enabled/bot.domian.com.conf
    # Конфиг для бота SSL
    server {
        server_name bot.domian.com;
        listen 80;
    
        location /{
            proxy_pass http://127.0.0.1:8443;
            proxy_set_header Host $host;
        }
    
        listen 443 ssl; # managed by Certbot
        ssl_certificate /etc/letsencrypt/live/bot.domian.com/fullchain.pem; 
        ssl_certificate_key /etc/letsencrypt/live/bot.domian.com/privkey.pem; 
    
    }
    
    server {
        if ($host = bot.domian.com) {
            return 301 https://$host$request_uri;
        }
    
    
    
        server_name bot.domian.com;
        listen 80;
        return 404;
    
    
    }
    ```
    
    ```bash
    # nano /etc/nginx/sites-enabled/vpn.domian.com.conf
    # Конфиг для Vpn Панели SSL
    server {
    
        server_name vpn.domian.com;
    
    
    
        location / {
            proxy_pass http://127.0.0.1:2053;
            proxy_http_version 1.1;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_set_header X-Frame-Options SAMEORIGIN;
            proxy_buffers 256 16k;
            proxy_buffer_size 16k;
            proxy_read_timeout 600s;
            proxy_cache_revalidate on;
            proxy_cache_min_uses 2;
            proxy_cache_use_stale timeout;
            proxy_cache_lock on;
            client_max_body_size 50M;
        }
    
        location /user {
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Host $http_host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header Range $http_range;
        proxy_set_header If-Range $http_if_range; 
        proxy_redirect off;
        proxy_pass http://127.0.0.1:2096;
    }
        
            location ~ /\.ht {
    
            deny all;
    
        }
    
        listen 443 ssl;
        ssl_certificate /root/cert-CF/vpn.domian.com/fullchain.pem; # Путь к сертификату если от    Cloudflaer
        ssl_certificate_key /root/cert-CF/vpn.domian.com/privkey.pem;
    }
    
    server {
    
        if ($host = vpn.domian.com) {
        
            return 301 https://$host$request_uri;
    
        }
    
    
    
    
    
        listen 80;
    
        server_name vpn.domian.com;
    
        return 404; 
    
    }
    ```

    ```bash
    # nano /etc/nginx/sites-enabled/bot.domian.com.conf
    # Конфиг для бота NON SSL
    server {
        server_name bot.domian.com;
        listen 80;
    
        location /{
            proxy_pass http://127.0.0.1:8443;
            proxy_set_header Host $host;
        }    
    }
    ```
    
    ```bash
    # nano /etc/nginx/sites-enabled/vpn.domian.com.conf
    # Конфиг для Vpn Панели NON SSL
    server {
    
        server_name vpn.domian.com;
    
    
    
        location / {
            proxy_pass http://127.0.0.1:2053;
            proxy_http_version 1.1;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_set_header X-Frame-Options SAMEORIGIN;
            proxy_buffers 256 16k;
            proxy_buffer_size 16k;
            proxy_read_timeout 600s;
            proxy_cache_revalidate on;
            proxy_cache_min_uses 2;
            proxy_cache_use_stale timeout;
            proxy_cache_lock on;
            client_max_body_size 50M;
        }
    
        location /user {
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Host $http_host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header Range $http_range;
        proxy_set_header If-Range $http_if_range; 
        proxy_redirect off;
        proxy_pass http://127.0.0.1:2096;
    }
        
            location ~ /\.ht {
    
            deny all;
    
        }
    
    }

    ```
  >  Приоритет для сервера "По этому пути /3xui-shop/app/bot/services/server_pool.py Строка 177 указывать название сервера который будет выдаваться первым для пробной подписки"
              
               ``if s.name == "🇳🇱 Нидерланды"``
              
              
 >  По пути /3xui-shop/app/bot/routers/main_menu/keyboard.py Можете сменить Url ссылки на свои в главном меню, перевод кнопок в /locales


  >  Изменить название профилей Заголовок или убрать "По этому пути /3xui-shop/app/bot/services/vpn.py Строка 178"
                    ``remarks = f"INZEWORLD VPN-{user.tg_id}"``





### Настройка переменных окружения

| Переменная | Требуется | По умолчанию | Описание |
|-|-|-|-|
| LETSENCRYPT_EMAIL | 🔴 | - | Email, используемый для создания сертификата |
| | | |
| BOT_TOKEN | 🔴 | - | Токен вашего Telegram-бота |
| BOT_ADMINS | ⭕ | - | Список ID администраторов (например, 123456789,987654321) |
| BOT_DEV_ID | 🔴 | - | ID разработчика бота |
| BOT_SUPPORT_ID | 🔴 | - | ID пользователя, отвечающего за поддержку |
| BOT_DOMAIN | 🔴 | - | Домен вашего бота (например, 3xui-shop.com) |
| BOT_PORT | ⭕ | 8080 | Порт, используемый ботом |
| | | |
| SHOP_EMAIL | ⭕ | support@3xui-shop.com | Email для отправки чеков |
| SHOP_CURRENCY | ⭕ | RUB | Валюта для кнопок (например, RUB, USD, XTR) |
| SHOP_TRIAL_ENABLED | ⭕ | True | Включить пробную подписку для новых пользователей |
| SHOP_TRIAL_PERIOD | ⭕ | 3 | Продолжительность пробной подписки в днях |
| SHOP_REFERRED_TRIAL_ENABLED | ⭕ | False | Включить расширенный пробный период для приглашённых пользователей |
| SHOP_REFERRED_TRIAL_PERIOD | ⭕ | 7 | Продолжительность расширенной пробной подписки для приглашённых пользователей (в днях) |
| SHOP_REFERRER_REWARD_ENABLED | ⭕ | True | Включить двухуровневую систему вознаграждений |
| SHOP_REFERRER_LEVEL_ONE_PERIOD | ⭕ | 10 | Вознаграждение в днях от первого уровня реферала |
| SHOP_REFERRER_LEVEL_TWO_PERIOD | ⭕ | 3 | Вознаграждение в днях от второго уровня реферала |
| SHOP_BONUS_DEVICES_COUNT | ⭕ | 1 | Лимит устройств по умолчанию для промокодов, пробной подписки и рефералов (в зависимости от настроек плана) |
| SHOP_PAYMENT_STARS_ENABLED | ⭕ | True | Включить оплату через Telegram Stars |
| SHOP_PAYMENT_CRYPTOMUS_ENABLED | ⭕ | False | Включить оплату через Cryptomus |
| SHOP_PAYMENT_HELEKET_ENABLED | ⭕ | False | Включить оплату через Heleket |
| SHOP_PAYMENT_YOOKASSA_ENABLED | ⭕ | False | Включить оплату через YooKassa |
| SHOP_PAYMENT_YOOMONEY_ENABLED | ⭕ | False | Включить оплату через YooMoney |
| | | |
| XUI_USERNAME | 🔴 | - | Имя пользователя для аутентификации в панели 3X-UI |
| XUI_PASSWORD | 🔴 | - | Пароль для аутентификации в панели 3X-UI |
| XUI_TOKEN | ⭕ | - | Токен для аутентификации (если установлен) |
| XUI_SUBSCRIPTION_PORT | ⭕ | 2096 | Порт для подписки |
| XUI_SUBSCRIPTION_PATH | ⭕ | /user/ | Путь для подписки |
| | | |
| CRYPTOMUS_API_KEY | ⭕ | - | API-ключ для оплаты через Cryptomus |
| CRYPTOMUS_MERCHANT_ID | ⭕ | - | Merchant ID для оплаты через Cryptomus |
| | | |
| HELEKET_API_KEY | ⭕ | - | API-ключ для оплаты через Heleket |
| HELEKET_MERCHANT_ID | ⭕ | - | Merchant ID для оплаты через Heleket |
| | | |
| YOOKASSA_TOKEN | ⭕ | - | Токен для оплаты через YooKassa |
| YOOKASSA_SHOP_ID | ⭕ | - | Shop ID для оплаты через YooKassa |
| | | |
| YOOMONEY_WALLET_ID | ⭕ | - | Wallet ID для оплаты через YooMoney |
| YOOMONEY_NOTIFICATION_SECRET | ⭕ | - | Секретный ключ уведомлений для оплаты через YooMoney |
| | | |
| LOG_LEVEL | ⭕ | DEBUG | Уровень логирования (например, INFO, DEBUG) |
| LOG_FORMAT | ⭕ | %(asctime)s \| %(name)s \| %(levelname)s \| %(message)s | Формат логов |
| LOG_ARCHIVE_FORMAT | ⭕ | zip | Формат архива логов (например, zip, gz) |


### Настройка тарифных планов

```json
{
    "durations": [30, 60, 180, 365],  // Доступные длительности подписок в днях

    "plans": 
    [
        {
            "devices": 1,  // Количество устройств
            "prices": {
                "RUB": {  // Цены в рублях (RUB)
                    "30": 70,   // Цена за 30 дней
                    "60": 120,  // Цена за 60 дней
                    "180": 300, // Цена за 180 дней
                    "365": 600  // Цена за 365 дней
                },
                "USD": {  // Цены в долларах (USD)
                    "30": 0.7,  // Цена за 30 дней
                    "60": 1.2,  // Цена за 60 дней
                    "180": 3,   // Цена за 180 дней
                    "365": 6    // Цена за 365 дней
                },
                "XTR": {  // Цены в Telegram звездах (XTR)
                    "30": 60,   // Цена за 30 дней
                    "60": 100,  // Цена за 60 дней
                    "180": 250, // Цена за 180 дней
                    "365": 500  // Цена за 365 дней
                }
            }
        },
        {
            // Следующий план
        }
    ]
}
```

### Настройка YooKassa

1. **Настройка Webhook:**
    - Перейдите на страницу [HTTP Уведомления](https://yookassa.ru/my/merchant/integration/http-notifications).
    - Введите домен бота в URL для уведомлений, должен заканчиваться на `/yookassa` (например, `https://3xui-shop.com/yookassa`).
    - Выберите следующие события::
        - `payment.succeeded`
        - `payment.waiting_for_capture`
        - `payment.canceled`

2. **Настройка переменных окружения:**
    - Установите следующие переменные окружения:
        - `YOOKASSA_TOKEN`: Ваш секретный ключ
        - `YOOKASSA_SHOP_ID`: Ваш Shop ID

### Настройка YooMoney

1. **Настройка Webhook:**
    - Перейдите на страницу [HTTP Уведомления](https://yoomoney.ru/transfer/myservices/http-notification).
    - Введите домен бота в URL для уведомлений, должен заканчиваться на `/yoomoney` (например, `https://3xui-shop.com/yoomoney`).
    - Скопируйте секретный ключ уведомлений.
    - Отметьте галочку для `отправка HTTP-уведомлений`.
    - Сохраните изменения.

2. **Настройка переменных окружения:**
    - Установите следующие переменные окружения:
        - `YOOMONEY_WALLET_ID`: Ваш ID кошелька
        - `YOOMONEY_NOTIFICATION_SECRET`: Ваш секретный ключ уведомлений

### Настройка 3X-UI

Для правильной работы бота необходимо настроить панель 3X-UI:

- [Настройка SSL сертификата.](https://github.com/MHSanaei/3x-ui?tab=readme-ov-file#ssl-certificate)
- Настройте Inbound **(использоваться будет только первый в списке)** для добавления клиентов.
- Включите сервис подписки с портом `2096` и путем `/user/`.
    > **Не забудьте указать сертификат для подписки.**
- Рекомендуется отключить шифрование конфигурации.

<a id="bugs-and-feature-requests"></a>

### Настройка вознаграждений за рефералов и пробный период

Бот поддерживает **пробные подписки** and a **двухуровневую систему вознаграждений за рефералов**. Вот как это работает: Вся настройка доступна через `.env` [(см. выше)](#environment-variables-configuration).

| Тип вознаграждения | Как это работает |
| - | - |
| Пробный период | Пробная подписка доступна через кнопку "ПОПРОБОВАТЬ БЕСПЛАТНО" на главном меню для любого пользователя, который не имеет активной подписки. |
| Увеличенный пробный период | Эта опция аналогична предыдущему, но позволяет настроить **увеличенный пробный период** для приглашенного пользователя. |
| Реферальные вознаграждения | Когда приглашенный пользователь оплачивает подписку, пригласитель и пригласитель второго уровня (пользователь, который пригласил следующего) получают фиксированное количество дней для каждого уровня. |

## 🐛 Ошибки и запросы функций

Если вы обнаружили ошибку или хотите предложить новую функцию, откройте запрос (issue) в репозитории.
Также вы можете внести свой вклад в проект, открыв Pull Request.

<a id="support-the-project"></a>

## 💸 Поддержка проекта

Особая благодарность следующим людям за их щедрую поддержку:

- **Boto**
- [**@olshevskii-sergey**](https://github.com/olshevskii-sergey/)
- **Aleksey**
- [**@DmitryKryloff**](https://t.me/DmitryKryloff)

Вы можете поддержать меня следующими способами ([или рублями](https://t.me/shop_3xui/2/1580)):

- **Bitcoin:** `bc1ql53lcaukdv3thxcheh3cmgucwlwkr929gar0cy`
- **Ethereum:** `0xe604a10258d26c085ada79cdea9a84a5b0894b91`
- **USDT (TRC20):** `TUqDQ4mdtVJZC76789kPYBMzaLFQBDdKhE`
- **TON:** `UQDogBlLFgrxkVWvDJn6YniCwrJDro7hbk5AqDMoSzmBQ-KQ`

Любая поддержка поможет мне уделять больше времени разработке и ускорить проект!
