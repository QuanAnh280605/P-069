-- SQLite physical schema aligned with the ecommerce metric ground truth.
-- v3.0.0: adds delivery/cancellation/loyalty order facts, session funnel flags,
-- and the cities/customer_addresses chain used by multi-hop join cases.

CREATE TABLE cities (
    city_id INTEGER PRIMARY KEY,
    city_name VARCHAR(50) NOT NULL,
    region_name VARCHAR(50) NOT NULL
);

CREATE TABLE customer_addresses (
    address_id INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL UNIQUE,
    city_id INTEGER NOT NULL,
    address VARCHAR(200) NOT NULL,
    is_default BOOLEAN NOT NULL DEFAULT TRUE,
    FOREIGN KEY (city_id) REFERENCES cities(city_id)
);

CREATE TABLE customers (
    id INTEGER PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    city VARCHAR(50),
    created_at TIMESTAMP NOT NULL,
    default_address_id INTEGER,
    FOREIGN KEY (default_address_id) REFERENCES customer_addresses(address_id)
);

CREATE TABLE products (
    id INTEGER PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    category VARCHAR(50) NOT NULL,
    price DECIMAL(12, 2) NOT NULL,
    status VARCHAR(20) NOT NULL
);

CREATE TABLE fact_orders (
    order_id INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL,
    store_id INTEGER NOT NULL,
    gross_amount DECIMAL(12, 2) NOT NULL,
    discount_amount DECIMAL(12, 2) NOT NULL DEFAULT 0,
    return_amount DECIMAL(12, 2) NOT NULL DEFAULT 0,
    cogs_amount DECIMAL(12, 2) NOT NULL,
    order_status VARCHAR(20) NOT NULL,
    is_test_order BOOLEAN NOT NULL DEFAULT FALSE,
    channel VARCHAR(30) NOT NULL,
    order_date TIMESTAMP NOT NULL,
    customer_order_seq INTEGER NOT NULL,
    delivered_time TIMESTAMP,
    is_delivered BOOLEAN NOT NULL DEFAULT FALSE,
    delivery_type VARCHAR(20),
    is_canceled BOOLEAN NOT NULL DEFAULT FALSE,
    cancel_reason VARCHAR(50),
    loyalty_card_id INTEGER,
    FOREIGN KEY (customer_id) REFERENCES customers(id)
);

CREATE TABLE fact_order_items (
    line_item_id INTEGER PRIMARY KEY,
    order_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    unit_price DECIMAL(12, 2) NOT NULL,
    is_test_order BOOLEAN NOT NULL DEFAULT FALSE,
    channel VARCHAR(30) NOT NULL,
    store_id INTEGER NOT NULL,
    order_date TIMESTAMP NOT NULL,
    is_canceled BOOLEAN NOT NULL DEFAULT FALSE,
    FOREIGN KEY (order_id) REFERENCES fact_orders(order_id),
    FOREIGN KEY (product_id) REFERENCES products(id)
);

CREATE TABLE fact_sessions (
    session_id INTEGER PRIMARY KEY,
    order_id INTEGER,
    store_id INTEGER NOT NULL,
    channel VARCHAR(30) NOT NULL,
    device_type VARCHAR(20) NOT NULL,
    is_bot_traffic BOOLEAN NOT NULL DEFAULT FALSE,
    session_date TIMESTAMP NOT NULL,
    has_cart_addition BOOLEAN NOT NULL DEFAULT FALSE,
    reached_checkout BOOLEAN NOT NULL DEFAULT FALSE,
    completed_checkout BOOLEAN NOT NULL DEFAULT FALSE,
    session_duration_seconds INTEGER,
    utm_source VARCHAR(50),
    FOREIGN KEY (order_id) REFERENCES fact_orders(order_id)
);

CREATE TABLE fact_carts (
    cart_id INTEGER PRIMARY KEY,
    customer_id INTEGER,
    store_id INTEGER NOT NULL,
    channel VARCHAR(30) NOT NULL,
    device_type VARCHAR(20) NOT NULL,
    checkout_completed BOOLEAN NOT NULL DEFAULT FALSE,
    is_test_order BOOLEAN NOT NULL DEFAULT FALSE,
    cart_date TIMESTAMP NOT NULL
);

CREATE TABLE payments (
    id INTEGER PRIMARY KEY,
    order_id INTEGER NOT NULL,
    payment_method VARCHAR(30) NOT NULL,
    amount DECIMAL(12, 2) NOT NULL,
    payment_date TIMESTAMP NOT NULL,
    FOREIGN KEY (order_id) REFERENCES fact_orders(order_id)
);

CREATE TABLE dim_items (
    item_id INTEGER PRIMARY KEY,
    product_id INTEGER NOT NULL,
    item_name VARCHAR(100) NOT NULL,
    current_stock_quantity INTEGER NOT NULL,
    min_stock_quantity INTEGER NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    in_stock BOOLEAN NOT NULL DEFAULT TRUE,
    category_id INTEGER NOT NULL,
    supplier_id INTEGER NOT NULL,
    store_id INTEGER NOT NULL,
    FOREIGN KEY (product_id) REFERENCES products(id)
);
