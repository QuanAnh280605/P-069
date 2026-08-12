-- SQLite physical schema aligned with the ecommerce metric ground truth.

CREATE TABLE customers (
    id INTEGER PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    city VARCHAR(50),
    created_at TIMESTAMP NOT NULL
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
