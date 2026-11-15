"""
Locust load tests for the ShopMate AI API.

Run:
    uv run locust -f performance/locustfile.py --host http://127.0.0.1:8000

Headless example:
    uv run locust -f performance/locustfile.py --host http://127.0.0.1:8000 \
        --headless -u 50 -r 5 -t 120s \
        --csv performance/reports/run_50u

Requires the perf database seeded by performance/setup_perf_db.py and
the server started by performance/run_server.py.

User mix (weights):
    AnonymousShopper  55  - public catalog/inventory/price reads
    StoreOwner        20  - store management reads
    CustomerShopper   25  - cart + order workflow (JWT customer)

Response policy: HTTP 5xx, 401 and 403 count as failures. Other 4xx
are business rejections (e.g. insufficient stock) and are recorded as
successful requests so the error rate reflects real faults.
"""

import os
import random

from locust import HttpUser, task, between, events

BASE = os.environ.get("LOCUST_BASE", "")

OWNER_USERNAME = os.environ.get("PERF_OWNER_USER", "perf_owner")
OWNER_PASSWORD = os.environ.get("PERF_OWNER_PASS", "PerfOwner123!")

CUSTOMER_COUNT = int(os.environ.get("PERF_CUSTOMER_COUNT", "50"))
CUSTOMER_PASSWORD = os.environ.get(
    "PERF_CUSTOMER_PASS", "PerfCustomer123!"
)

# The perf seed creates the first store with id=1 on a fresh database.
STORE_ID = int(os.environ.get("PERF_STORE_ID", "1"))


def login(client, username, password):
    resp = client.post(
        "/api/auth/token/",
        json={"username": username, "password": password},
        name="auth/token",
    )
    if resp.status_code != 200:
        raise RuntimeError(
            f"login failed for {username}: {resp.status_code}"
        )
    return {"Authorization": f"Bearer {resp.json()['access']}"}


def check_response(response):
    """Return True for expected outcomes, False for real failures."""
    if response.status_code >= 500:
        response.failure(f"server error {response.status_code}")
        return False
    if response.status_code in (401, 403):
        response.failure(f"auth error {response.status_code}")
        return False
    response.success()
    return True


class ShopMateUser(HttpUser):
    abstract = True
    wait_time = between(0.5, 2.0)

    def on_start(self):
        self.product_ids = self._fetch_product_ids()

    def _fetch_product_ids(self):
        resp = self.client.get("/api/products/", name="products/list")
        if resp.status_code != 200:
            return []
        return [p["id"] for p in resp.json()]

    def pick_product(self):
        if not self.product_ids:
            return None
        return random.choice(self.product_ids)


class AnonymousShopper(ShopMateUser):
    weight = 55

    @task(4)
    def browse_products(self):
        params = {}
        r = random.random()
        if r < 0.3 and self.product_ids:
            params["store_id"] = STORE_ID
        elif r < 0.5:
            params["search"] = random.choice(
                ["rice", "milk", "oil", "dal", "soap"]
            )
        self.client.get(
            "/api/products/", params=params, name="products/browse"
        )

    @task(3)
    def browse_inventory(self):
        params = {}
        if random.random() < 0.3:
            params["store_id"] = STORE_ID
        if random.random() < 0.2:
            params["low_stock"] = "true"
        self.client.get(
            "/api/inventory/", params=params, name="inventory/list"
        )

    @task(2)
    def browse_prices(self):
        params = {}
        if random.random() < 0.4:
            params["store_id"] = STORE_ID
        self.client.get("/api/pricing/", params=params, name="pricing/list")

    @task(2)
    def calculate_price(self):
        pid = self.pick_product()
        if pid is None:
            return
        self.client.get(
            "/api/pricing/calculate/",
            params={"product_id": pid, "quantity": "2"},
            name="pricing/calculate",
        )


class StoreOwner(ShopMateUser):
    weight = 20

    def on_start(self):
        super().on_start()
        self.client.headers.update(
            login(self.client, OWNER_USERNAME, OWNER_PASSWORD)
        )
        resp = self.client.get("/api/stores/", name="stores/list")
        stores = resp.json() if resp.status_code == 200 else []
        self.store_id = stores[0]["id"] if stores else STORE_ID

    @task(3)
    def list_products(self):
        self.client.get(
            f"/api/stores/{self.store_id}/products/",
            name="mgmt/products",
        )

    @task(3)
    def list_inventory(self):
        self.client.get(
            f"/api/stores/{self.store_id}/inventory/",
            name="mgmt/inventory",
        )

    @task(3)
    def list_prices(self):
        self.client.get(
            f"/api/stores/{self.store_id}/prices/",
            name="mgmt/prices",
        )

    @task(1)
    def price_history(self):
        pid = self.pick_product()
        if pid is None:
            return
        self.client.get(
            f"/api/stores/{self.store_id}/prices/{pid}/history/",
            name="mgmt/price-history",
        )


class CustomerShopper(ShopMateUser):
    weight = 25

    def on_start(self):
        super().on_start()
        index = random.randint(1, CUSTOMER_COUNT)
        self.username = f"perf_cust_{index:02d}"
        self.client.headers.update(
            login(self.client, self.username, CUSTOMER_PASSWORD)
        )
        # Start each user with a clean cart so quantities stay bounded.
        self.cart_products = set()
        self._clear_cart()

    def _clear_cart(self):
        resp = self.client.get(
            "/api/cart/", params={"store_id": STORE_ID}, name="cart/get"
        )
        if resp.status_code != 200:
            return
        for item in resp.json().get("items", []):
            self.client.delete(
                "/api/cart/items/",
                params={
                    "store_id": STORE_ID,
                    "product_id": item["product_id"],
                },
                name="cart/remove",
            )

    @task(5)
    def view_cart(self):
        with self.client.get(
            "/api/cart/",
            params={"store_id": STORE_ID},
            name="cart/get",
            catch_response=True,
        ) as resp:
            check_response(resp)

    @task(4)
    def add_item(self):
        pid = self.pick_product()
        if pid is None or pid in self.cart_products:
            return
        with self.client.post(
            "/api/cart/items/",
            json={
                "store_id": STORE_ID,
                "product_id": pid,
                "quantity": "1.000",
            },
            name="cart/add",
            catch_response=True,
        ) as resp:
            if check_response(resp) and resp.status_code == 200:
                self.cart_products.add(pid)

    @task(3)
    def update_item(self):
        if not self.cart_products:
            return
        pid = random.choice(tuple(self.cart_products))
        with self.client.patch(
            "/api/cart/items/",
            json={
                "store_id": STORE_ID,
                "product_id": pid,
                "quantity": "1.000",
            },
            name="cart/update",
            catch_response=True,
        ) as resp:
            check_response(resp)

    @task(2)
    def remove_item(self):
        if not self.cart_products:
            return
        pid = random.choice(tuple(self.cart_products))
        with self.client.delete(
            "/api/cart/items/",
            params={"store_id": STORE_ID, "product_id": pid},
            name="cart/remove",
            catch_response=True,
        ) as resp:
            if check_response(resp) and resp.status_code == 200:
                self.cart_products.discard(pid)

    @task(1)
    def order_history(self):
        with self.client.get(
            "/api/orders/", name="orders/history", catch_response=True
        ) as resp:
            check_response(resp)

    @task(1)
    def confirm_and_cancel_order(self):
        """Full order cycle: ensure item -> confirm -> cancel.

        Cancel releases the reservation so inventory returns to its
        baseline and the scenario is repeatable.
        """
        if not self.cart_products:
            pid = self.pick_product()
            if pid is None:
                return
            resp = self.client.post(
                "/api/cart/items/",
                json={
                    "store_id": STORE_ID,
                    "product_id": pid,
                    "quantity": "1.000",
                },
                name="cart/add",
            )
            if resp.status_code != 200:
                return
            self.cart_products.add(pid)

        with self.client.post(
            "/api/orders/confirm/",
            json={"store_id": STORE_ID},
            name="orders/confirm",
            catch_response=True,
        ) as resp:
            if not check_response(resp) or resp.status_code != 201:
                return
            order_id = resp.json()["order_id"]

        # Cart is now CONVERTED; local tracking resets.
        self.cart_products.clear()

        with self.client.post(
            f"/api/orders/{order_id}/cancel/",
            name="orders/cancel",
            catch_response=True,
        ) as resp:
            check_response(resp)


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    print(
        f"[locust] store_id={STORE_ID} "
        f"customers={CUSTOMER_COUNT} mix: "
        "anonymous=55 owner=20 customer=25"
    )
